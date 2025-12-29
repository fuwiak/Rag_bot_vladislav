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

# Fix bcrypt compatibility with passlib - patch before creating CryptContext
try:
    import bcrypt as _bcrypt
    import passlib.handlers.bcrypt as bcrypt_handler
    
    # Patch _load_backend_mixin to handle newer bcrypt versions
    if hasattr(bcrypt_handler, 'BcryptHandler') and not hasattr(_bcrypt, '__about__'):
        original_load = getattr(bcrypt_handler.BcryptHandler, '_load_backend_mixin', None)
        if original_load:
            def patched_load_backend_mixin(self):
                try:
                    # Try to get version from new bcrypt API
                    version = getattr(_bcrypt, '__version__', None)
                    if version is None:
                        # Fallback: try to import version
                        try:
                            from importlib.metadata import version
                            version = version('bcrypt')
                        except Exception:
                            version = '<unknown>'
                    
                    # Set version for passlib
                    if hasattr(self, '_backend'):
                        self._backend._bcrypt_version = version
                    
                    # Call original if it exists
                    if callable(original_load):
                        return original_load(self)
                except Exception:
                    # If patching fails, try original
                    if callable(original_load):
                        return original_load(self)
            
            bcrypt_handler.BcryptHandler._load_backend_mixin = patched_load_backend_mixin
except Exception:
    pass  # If patching fails, passlib will handle it with warnings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Сервис для работы с авторизацией"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Проверка пароля"""
        try:
            # Bcrypt ma limit 72 bajty - sprawdź czy hasło nie jest za długie
            if len(plain_password.encode('utf-8')) > 72:
                return False
            return pwd_context.verify(plain_password, hashed_password)
        except (ValueError, Exception) as e:
            # Jeśli hash jest niepoprawny lub hasło za długie, zwróć False
            return False
    
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
            JWT токен если авторизация успешна, None если неверные данные
        """
        # Получаем администратора по username
        admin = await self.get_admin_by_username(username)
        if not admin:
            return None
        
        # Проверяем пароль
        if not self.verify_password(password, admin.password_hash):
            return None
        
        # Создаем токен
        return self.create_access_token(username)
    
    async def get_admin_by_username(self, username: str) -> Optional[AdminUser]:
        """Получить администратора по username"""
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        return result.scalar_one_or_none()






















