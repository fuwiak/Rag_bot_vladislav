"""
Роутер для авторизации администраторов
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Авторизация администратора (PASSWORD DISABLED - always succeeds)
    """
    auth_service = AuthService(db)
    # PASSWORD DISABLED - always create token for any username
    token = auth_service.create_access_token(login_data.username)
    
    return LoginResponse(access_token=token, token_type="bearer")


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Выход из системы (опционально, можно реализовать blacklist токенов)
    """
    return {"message": "Выход выполнен успешно"}











