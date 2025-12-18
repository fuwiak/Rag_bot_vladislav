"""
Сервис для авторизации администраторов
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.admin_user import AdminUser
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Сервис для работы с авторизацией"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Проверка пароля"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Хеширование пароля"""
        return pwd_context.hash(password)
    
    def create_access_token(self, username: str) -> str:
        """Создание JWT токена"""
        expire = datetime.utcnow() + timedelta(days=7)
        to_encode = {"sub": username, "exp": expire}
        encoded_jwt = jwt.encode(to_encode, settings.ADMIN_SECRET_KEY, algorithm="HS256")
        return encoded_jwt
    
    async def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Аутентификация пользователя
        
        Returns:
            JWT токен или None если аутентификация не удалась
        """
        admin = await self.get_admin_by_username(username)
        
        if not admin:
            return None
        
        if not self.verify_password(password, admin.password_hash):
            return None
        
        return self.create_access_token(username)
    
    async def get_admin_by_username(self, username: str) -> Optional[AdminUser]:
        """Получить администратора по username"""
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        return result.scalar_one_or_none()






