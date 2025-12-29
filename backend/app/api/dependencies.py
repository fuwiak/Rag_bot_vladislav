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
    Получить текущего администратора по JWT токену
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация"
        )
    
    try:
        # Декодируем токен
        payload = jwt.decode(credentials.credentials, settings.ADMIN_SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен"
        )
    
    # Получаем администратора из БД
    auth_service = AuthService(db)
    admin = await auth_service.get_admin_by_username(username)
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Администратор не найден"
        )
    
    return admin














