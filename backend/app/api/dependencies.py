"""
Зависимости для API (авторизация и т.д.)
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.config import settings
from app.services.auth_service import AuthService

security = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить текущего администратора (PASSWORD DISABLED - always returns mock admin)
    """
    # PASSWORD DISABLED - always return mock admin
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










