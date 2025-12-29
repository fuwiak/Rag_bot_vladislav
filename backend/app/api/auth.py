"""
Роутер для авторизации администраторов
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse, ResetPasswordRequest, ResetPasswordResponse
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
    import logging
    logger = logging.getLogger(__name__)
    
    auth_service = AuthService(db)
    
    # Проверяем учетные данные
    token = await auth_service.authenticate(login_data.username, login_data.password)
    
    if not token:
        logger.warning(f"Failed login attempt for username: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль"
        )
    
    logger.info(f"Successful login for username: {login_data.username}")
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


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    reset_data: ResetPasswordRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Сброс пароля администратора
    Требует текущий пароль для подтверждения
    """
    import logging
    from jose import JWTError, jwt
    from app.core.config import settings
    from app.models.admin_user import AdminUser
    from sqlalchemy import select
    
    logger = logging.getLogger(__name__)
    
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
    
    # Получаем администратора
    auth_service = AuthService(db)
    admin = await auth_service.get_admin_by_username(username)
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Администратор не найден"
        )
    
    # Проверяем текущий пароль
    if not auth_service.verify_password(reset_data.current_password, admin.password_hash):
        logger.warning(f"Failed password reset attempt for username: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный текущий пароль"
        )
    
    # Обновляем пароль
    admin.password_hash = auth_service.get_password_hash(reset_data.new_password)
    await db.commit()
    
    logger.info(f"Password reset successful for username: {username}")
    return ResetPasswordResponse(
        message="Пароль успешно изменен",
        username=username
    )











