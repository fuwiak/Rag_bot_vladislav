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
    Авторизация администратора - БЕЗ ПРОВЕРКИ ПАРОЛЯ
    """
    auth_service = AuthService(db)
    # Создаем токен для любого username - БЕЗ ПРОВЕРКИ
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


@router.post("/create-admin")
async def create_admin_endpoint(
    db: AsyncSession = Depends(get_db)
):
    """
    Создать первого администратора (только если администраторов нет)
    ВАЖНО: Удалите этот endpoint после создания администратора!
    """
    from app.models.admin_user import AdminUser
    from sqlalchemy import select
    
    # Проверяем, есть ли уже администраторы
    result = await db.execute(select(AdminUser))
    existing = result.scalars().first()
    
    if existing:
        return {
            "message": "Администратор уже существует",
            "username": existing.username
        }
    
    # Создаем администратора
    auth_service = AuthService(db)
    admin = AdminUser(
        username="admin",
        password_hash=auth_service.get_password_hash("admin")
    )
    db.add(admin)
    await db.commit()
    
    return {
        "message": "Администратор создан успешно",
        "username": "admin",
        "password": "admin"
    }











