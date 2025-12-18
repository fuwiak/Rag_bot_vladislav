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
    Получить текущего администратора из JWT токена
    """
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, settings.ADMIN_SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )
        
        # Проверка существования пользователя в БД
        auth_service = AuthService(db)
        admin = await auth_service.get_admin_by_username(username)
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден"
            )
        
        return admin
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен"
        )








