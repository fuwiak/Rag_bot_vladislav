"""
Зависимости для API (авторизация и т.д.)
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.config import settings
from app.services.auth_service import AuthService

# Делаем токен опциональным - не требуем обязательного наличия Authorization заголовка
security = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить текущего администратора (AUTHENTICATION DISABLED - always returns mock admin)
    Токен не требуется - функция всегда возвращает mock admin
    """
    # AUTHENTICATION DISABLED - always return mock admin without checking token
    from app.models.admin_user import AdminUser
    from uuid import uuid4
    
    # Create mock admin object
    mock_admin = AdminUser(
        id=uuid4(),
        username="admin",
        password_hash="",
        created_at=None
    )
    
    return mock_admin














