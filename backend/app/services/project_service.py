"""
Сервис для управления проектами
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.vector_db.collections_manager import CollectionsManager


class ProjectService:
    """Сервис для работы с проектами"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.collections_manager = CollectionsManager()
    
    async def get_all_projects(self) -> List[Project]:
        """Получить все проекты (оптимизировано - загружаем только нужные поля)"""
        from sqlalchemy.orm import noload
        from sqlalchemy import select
        import gc
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            # КРИТИЧНО: Загружаем только нужные поля, не всю модель
            # Это предотвращает загрузку больших полей (prompt_template, access_password) в память
            result = await self.db.execute(
                select(
                    Project.id,
                    Project.name,
                    Project.description,
                    Project.created_at,
                    Project.updated_at
                )
                .limit(50)
                .order_by(Project.created_at.desc())
            )
            
            # Преобразуем результат в объекты Project с минимальными данными
            projects = []
            for row in result.all():
                # Создаем минимальный объект Project только с нужными полями
                project = Project()
                project.id = row.id
                project.name = row.name
                # Ограничиваем description до 200 символов сразу при загрузке
                project.description = (row.description[:200] + "...") if row.description and len(row.description) > 200 else row.description
                project.created_at = row.created_at
                project.updated_at = row.updated_at
                # НЕ загружаем prompt_template, access_password и другие большие поля
                projects.append(project)
            
            # Явно освобождаем память
            del result
            gc.collect()
            
            logger.info(f"Loaded {len(projects)} projects (minimal fields only)")
            return projects
        except Exception as e:
            logger.error(f"Error loading projects: {e}", exc_info=True)
            gc.collect()
            return []
    
    async def get_project_by_id(self, project_id: UUID) -> Optional[Project]:
        """Получить проект по ID (оптимизировано - без загрузки relationships)"""
        from sqlalchemy.orm import noload
        import logging
        logger = logging.getLogger(__name__)
        
        # Загружаем проект без relationships для экономии памяти
        result = await self.db.execute(
            select(Project)
            .where(Project.id == project_id)
            .options(noload(Project.users), noload(Project.documents))
        )
        project = result.scalar_one_or_none()
        
        if project:
            logger.info(f"[GET PROJECT BY ID] Project {project_id} found: bot_token={'SET' if project.bot_token else 'NULL'}")
        else:
            logger.warning(f"[GET PROJECT BY ID] Project {project_id} not found")
        
        return project
    
    async def create_project(self, project_data: ProjectCreate) -> Project:
        """Создать новый проект"""
        # Преобразуем пустую строку bot_token в None для избежания конфликтов unique constraint
        project_dict = project_data.model_dump()
        if project_dict.get('bot_token') == '':
            project_dict['bot_token'] = None
        
        project = Project(**project_dict)
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        
        # Создание коллекции в Qdrant для проекта (не блокируем создание проекта при ошибке)
        try:
            await self.collections_manager.create_collection(str(project.id))
        except Exception as e:
            # Логируем ошибку, но не прерываем создание проекта
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create Qdrant collection for project {project.id}: {e}")
            # Проект уже создан в БД, продолжаем
        
        return project
    
    async def update_project(self, project_id: UUID, project_data: ProjectUpdate) -> Optional[Project]:
        """Обновить проект"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[UPDATE PROJECT] Starting update for project {project_id}")
        project = await self.get_project_by_id(project_id)
        
        if not project:
            logger.error(f"[UPDATE PROJECT] Project {project_id} not found")
            return None
        
        update_data = project_data.model_dump(exclude_unset=True)
        logger.info(f"[UPDATE PROJECT] Update data keys: {list(update_data.keys())}")
        
        # Преобразуем пустую строку bot_token в None для избежания конфликтов unique constraint
        if 'bot_token' in update_data:
            if update_data['bot_token'] == '':
                logger.info(f"[UPDATE PROJECT] Empty bot_token, setting to None")
                update_data['bot_token'] = None
            else:
                logger.info(f"[UPDATE PROJECT] Setting bot_token (first 10 chars): {update_data['bot_token'][:10]}...")
        
        for field, value in update_data.items():
            old_value = getattr(project, field, None)
            logger.info(f"[UPDATE PROJECT] Setting {field}: {old_value} -> {value if field != 'bot_token' else (value[:10] + '...' if value else None)}")
            setattr(project, field, value)
        
        logger.info(f"[UPDATE PROJECT] Committing changes...")
        await self.db.commit()
        logger.info(f"[UPDATE PROJECT] Changes committed")
        
        await self.db.refresh(project)
        logger.info(f"[UPDATE PROJECT] Project refreshed. bot_token after refresh: {project.bot_token[:10] if project.bot_token else 'None'}...")
        
        return project
    
    async def delete_project(self, project_id: UUID) -> bool:
        """Удалить проект и все связанные данные"""
        project = await self.get_project_by_id(project_id)
        
        if not project:
            return False
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Удаляем все документы проекта (и их векторы из Qdrant)
        from app.models.document import Document, DocumentChunk
        from app.vector_db.vector_store import VectorStore
        
        documents_result = await self.db.execute(
            select(Document).where(Document.project_id == project_id)
        )
        documents = documents_result.scalars().all()
        
        vector_store = VectorStore()
        for document in documents:
            # Удаляем векторы из Qdrant
            chunks_result = await self.db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == document.id)
            )
            chunks = chunks_result.scalars().all()
            
            for chunk in chunks:
                if chunk.qdrant_point_id:
                    try:
                        await vector_store.delete_vector(
                            collection_name=f"project_{project_id}",
                            point_id=chunk.qdrant_point_id
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось удалить вектор {chunk.qdrant_point_id} из Qdrant: {e}")
            
            # Удаляем документ (чанки удалятся каскадно)
            await self.db.delete(document)
        
        # Удаляем всех пользователей проекта (сообщения удалятся каскадно)
        from app.models.user import User
        users_result = await self.db.execute(
            select(User).where(User.project_id == project_id)
        )
        users = users_result.scalars().all()
        for user in users:
            await self.db.delete(user)
        
        # Удаление коллекции из Qdrant (опционально, не блокируем удаление проекта при ошибке)
        try:
            await self.collections_manager.delete_collection(str(project_id))
        except Exception as e:
            logger.warning(f"Не удалось удалить коллекцию Qdrant для проекта {project_id}: {e}")
            # Продолжаем удаление проекта даже если коллекция не найдена
        
        # Удаляем сам проект
        await self.db.delete(project)
        await self.db.commit()
        
        logger.info(f"Проект {project_id} и все связанные данные успешно удалены")
        return True

