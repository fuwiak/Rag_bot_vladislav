"""
Сервис для управления пользователями ботов
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.schemas.user import UserStatusUpdate, UserUpdate


class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_project_users(self, project_id: UUID) -> List[User]:
        """Получить всех пользователей проекта (оптимизировано - без загрузки relationships)"""
        from sqlalchemy.orm import noload
        import gc
        
        # Загружаем пользователей без relationships для экономии памяти
        # Используем noload чтобы явно не загружать project и messages
        # Добавляем лимит на количество пользователей (500) для предотвращения out of memory
        result = await self.db.execute(
            select(User)
            .where(User.project_id == project_id)
            .options(noload(User.project), noload(User.messages))
            .limit(500)
            .order_by(User.created_at.desc())
        )
        users = list(result.scalars().all())
        
        # Явно освобождаем память
        gc.collect()
        
        return users
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Получить пользователя по ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_phone(self, project_id: UUID, phone: str) -> Optional[User]:
        """Получить пользователя по номеру телефона и проекту"""
        result = await self.db.execute(
            select(User).where(
                User.project_id == project_id,
                User.phone == phone
            )
        )
        return result.scalar_one_or_none()
    
    async def create_user(self, project_id: UUID, phone: str, username: Optional[str] = None) -> User:
        """Создать нового пользователя"""
        user = User(
            project_id=project_id,
            phone=phone,
            username=username,
            status="active"
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def update_user(self, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        """Обновить пользователя"""
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return None
        
        # Обновляем поля, если они указаны
        if user_data.phone is not None:
            user.phone = user_data.phone
        if user_data.username is not None:
            user.username = user_data.username
        if user_data.project_id is not None:
            user.project_id = user_data.project_id
        if user_data.status is not None:
            user.status = user_data.status
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def update_user_status(self, user_id: UUID, status: str) -> Optional[User]:
        """Обновить статус пользователя"""
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return None
        
        user.status = status
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def delete_user(self, user_id: UUID) -> bool:
        """Удалить пользователя"""
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return False
        
        await self.db.delete(user)
        await self.db.commit()
        
        return True



