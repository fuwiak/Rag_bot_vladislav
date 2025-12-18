"""
Роутер для управления пользователями ботов
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.schemas.user import UserResponse, UserStatusUpdate, UserCreate, UserUpdate
from app.services.user_service import UserService
from app.api.dependencies import get_current_admin

router = APIRouter()


@router.get("/project/{project_id}", response_model=List[UserResponse])
async def get_project_users(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить список пользователей проекта"""
    service = UserService(db)
    users = await service.get_project_users(project_id)
    return users


@router.post("/project/{project_id}", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    project_id: UUID,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Создать нового пользователя в проекте"""
    service = UserService(db)
    
    # Проверка на существование пользователя с таким телефоном в проекте
    existing = await service.get_user_by_phone(project_id, user_data.phone)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким номером телефона уже существует в этом проекте"
        )
    
    user = await service.create_user(project_id, user_data.phone, user_data.username)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить пользователя по ID"""
    service = UserService(db)
    user = await service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return user


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: UUID,
    status_data: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Обновить статус пользователя (активен/заблокирован)"""
    service = UserService(db)
    user = await service.update_user_status(user_id, status_data.status)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Обновить пользователя"""
    service = UserService(db)
    
    # Проверка существования пользователя
    existing_user = await service.get_user_by_id(user_id)
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Если изменяется телефон, проверяем на дубликат в проекте
    if user_data.phone and user_data.phone != existing_user.phone:
        project_id = user_data.project_id or existing_user.project_id
        duplicate = await service.get_user_by_phone(project_id, user_data.phone)
        if duplicate and duplicate.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким номером телефона уже существует в этом проекте"
            )
    
    user = await service.update_user(user_id, user_data)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Удалить пользователя"""
    service = UserService(db)
    success = await service.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

