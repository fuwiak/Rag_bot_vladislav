"""
Роутер для управления Telegram ботами
"""
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.schemas.project import ProjectResponse
from app.services.project_service import ProjectService
from app.api.dependencies import get_current_admin
from app.models.user import User
from aiogram import Bot

router = APIRouter()


class BotInfoResponse(BaseModel):
    """Информация о боте"""
    project_id: UUID
    project_name: str
    bot_token: Optional[str] = None
    bot_username: Optional[str] = None
    bot_url: Optional[str] = None
    bot_first_name: Optional[str] = None
    is_active: bool = False
    users_count: int = 0


@router.get("/info", response_model=List[BotInfoResponse])
async def get_all_bots_info(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить информацию о всех ботах"""
    service = ProjectService(db)
    projects = await service.get_all_projects()
    
    # Боты управляются отдельным сервисом telegram-bots
    # Считаем бота активным, если у проекта есть bot_token
    # (бот-сервис автоматически запустит его)
    
    bots_info = []
    
    # Получаем количество пользователей для каждого проекта
    users_counts = {}
    for project in projects:
        result = await db.execute(
            select(func.count(User.id)).where(User.project_id == project.id)
        )
        users_counts[project.id] = result.scalar() or 0
    
    for project in projects:
        # Бот считается активным, если есть токен
        # Бот-сервис автоматически подхватит изменения
        is_active = project.bot_token is not None
        
        bot_info = BotInfoResponse(
            project_id=project.id,
            project_name=project.name,
            bot_token=project.bot_token,
            users_count=users_counts.get(project.id, 0),
            is_active=is_active
        )
        
        # Получаем информацию о боте через Telegram API
        if project.bot_token:
            try:
                bot = Bot(token=project.bot_token)
                bot_user = await bot.get_me()
                bot_info.bot_username = bot_user.username
                bot_info.bot_first_name = bot_user.first_name
                if bot_user.username:
                    bot_info.bot_url = f"https://t.me/{bot_user.username}"
                await bot.session.close()
            except Exception as e:
                # Бот невалиден или недоступен
                pass
        
        bots_info.append(bot_info)
    
    return bots_info


@router.post("/{project_id}/verify", response_model=BotInfoResponse)
async def verify_bot_token(
    project_id: UUID,
    token_data: dict,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Проверить токен бота и получить информацию"""
    bot_token = token_data.get('bot_token')
    
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Токен бота не предоставлен"
        )
    
    # Проверяем токен через Telegram API
    try:
        bot = Bot(token=bot_token)
        bot_user = await bot.get_me()
        await bot.session.close()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверный токен бота: {str(e)}"
        )
    
    # Обновляем проект с новым токеном
    service = ProjectService(db)
    from app.schemas.project import ProjectUpdate
    project_update = ProjectUpdate(bot_token=bot_token)
    project = await service.update_project(project_id, project_update)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Получаем количество пользователей для проекта
    result = await db.execute(
        select(func.count(User.id)).where(User.project_id == project.id)
    )
    users_count = result.scalar() or 0
    
    # Получаем информацию о боте
    bot_info = BotInfoResponse(
        project_id=project.id,
        project_name=project.name,
        bot_token=project.bot_token,
        bot_username=bot_user.username,
        bot_first_name=bot_user.first_name,
        users_count=users_count,
        is_active=False
    )
    
    if bot_user.username:
        bot_info.bot_url = f"https://t.me/{bot_user.username}"
    
    return bot_info


@router.post("/{project_id}/start")
async def start_bot(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Запустить бота для проекта
    
    Бот-сервис автоматически подхватит изменения в БД и запустит бота.
    Этот endpoint просто проверяет, что у проекта есть токен.
    """
    service = ProjectService(db)
    project = await service.get_project_by_id(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    if not project.bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Токен бота не настроен для этого проекта"
        )
    
    # Бот-сервис автоматически подхватит изменения при следующей проверке БД
    # Просто возвращаем успех - бот будет запущен бот-сервисом
    return {
        "message": "Бот будет запущен бот-сервисом автоматически. Обычно это происходит в течение 20 секунд."
    }


@router.post("/{project_id}/stop")
async def stop_bot(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Остановить бота для проекта
    
    Удаляет токен бота из проекта. Бот-сервис автоматически подхватит изменения
    и остановит бота при следующей проверке БД.
    """
    service = ProjectService(db)
    project = await service.get_project_by_id(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Удаляем токен бота - бот-сервис остановит бота при следующей проверке
    from app.schemas.project import ProjectUpdate
    project_update = ProjectUpdate(bot_token=None)
    await service.update_project(project_id, project_update)
    
    return {
        "message": "Токен бота удален. Бот будет остановлен бот-сервисом автоматически. Обычно это происходит в течение 20 секунд."
    }

