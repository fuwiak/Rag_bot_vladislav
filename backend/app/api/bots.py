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
from app.bot.bot_factory import BotFactory
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
    
    # Получаем BotFactory из app state
    bot_factory = getattr(request.app.state, 'bot_factory', None)
    active_bots = set()
    if bot_factory:
        # active_bots теперь содержит bot_token, нужно проверить project_id в token_to_projects
        active_tokens = set(bot_factory.bots.keys())
        for token in active_tokens:
            if token in bot_factory.token_to_projects:
                for project_id in bot_factory.token_to_projects[token]:
                    active_bots.add(project_id)
    
    bots_info = []
    
    # Получаем количество пользователей для каждого проекта
    users_counts = {}
    for project in projects:
        result = await db.execute(
            select(func.count(User.id)).where(User.project_id == project.id)
        )
        users_counts[project.id] = result.scalar() or 0
    
    for project in projects:
        bot_info = BotInfoResponse(
            project_id=project.id,
            project_name=project.name,
            bot_token=project.bot_token,
            users_count=users_counts.get(project.id, 0),
            is_active=project.bot_token is not None and str(project.id) in active_bots
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
    """Запустить бота для проекта"""
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
    
    # Получаем BotFactory из app state
    bot_factory = getattr(request.app.state, 'bot_factory', None)
    if not bot_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис ботов недоступен"
        )
    
    try:
        await bot_factory.create_bot(str(project_id), project.bot_token)
        return {"message": "Бот успешно запущен"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запуска бота: {str(e)}"
        )


@router.post("/{project_id}/stop")
async def stop_bot(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Остановить бота для проекта"""
    # Получаем BotFactory из app state
    bot_factory = getattr(request.app.state, 'bot_factory', None)
    if not bot_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис ботов недоступен"
        )
    
    try:
        await bot_factory.stop_bot(str(project_id))
        return {"message": "Бот успешно остановлен"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка остановки бота: {str(e)}"
        )

