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
    Авторизация администратора
    """
    from app.core.config import settings
    
    auth_service = AuthService(db)
    
    # Если проверка пароля отключена - создаем токен для любого username
    if settings.DISABLE_PASSWORD_CHECK:
        token = auth_service.create_access_token(login_data.username)
        return LoginResponse(access_token=token, token_type="bearer")
    
    # Обычная проверка пароля
    admin_user = await auth_service.get_admin_by_username(login_data.username)

    if not admin_user or not auth_service.verify_password(login_data.password, admin_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_service.create_access_token(admin_user.username)
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











