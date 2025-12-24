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
        """Получить все проекты"""
        result = await self.db.execute(select(Project))
        return list(result.scalars().all())
    
    async def get_project_by_id(self, project_id: UUID) -> Optional[Project]:
        """Получить проект по ID"""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()
    
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
        project = await self.get_project_by_id(project_id)
        
        if not project:
            return None
        
        update_data = project_data.model_dump(exclude_unset=True)
        # Преобразуем пустую строку bot_token в None для избежания конфликтов unique constraint
        if 'bot_token' in update_data and update_data['bot_token'] == '':
            update_data['bot_token'] = None
        
        for field, value in update_data.items():
            setattr(project, field, value)
        
        await self.db.commit()
        await self.db.refresh(project)
        
        return project
    
    async def delete_project(self, project_id: UUID) -> bool:
        """Удалить проект"""
        project = await self.get_project_by_id(project_id)
        
        if not project:
            return False
        
        # Удаление коллекции из Qdrant (опционально, не блокируем удаление проекта при ошибке)
        try:
            await self.collections_manager.delete_collection(str(project_id))
        except Exception as e:
            # Логируем ошибку, но не прерываем удаление проекта
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось удалить коллекцию Qdrant для проекта {project_id}: {e}")
            # Продолжаем удаление проекта даже если коллекция не найдена
        
        await self.db.delete(project)
        await self.db.commit()
        
        return True

