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
    is_active: bool = False  # Вычисляется из bot_token и bot_is_active
    bot_is_active: Optional[str] = "false"  # Статус из БД
    users_count: int = 0
    llm_model: Optional[str] = None
    description: Optional[str] = None
    documents_count: int = 0


@router.get("/info", response_model=List[BotInfoResponse])
async def get_all_bots_info(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить информацию о всех ботах (оптимизировано - без Telegram API запросов)"""
    import gc
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info("[GET BOTS INFO] Starting to fetch all bots info")
    
    try:
        service = ProjectService(db)
        projects = await service.get_all_projects()
        logger.info(f"[GET BOTS INFO] Found {len(projects)} projects")
        
        # Боты управляются отдельным сервисом telegram-bots
        # Считаем бота активным, если у проекта есть bot_token
        # (бот-сервис автоматически запустит его)
        
        bots_info = []
        
        # Оптимизация: получаем количество пользователей одним запросом
        # Вместо N запросов делаем один с GROUP BY
        if projects:
            project_ids = [p.id for p in projects]
            result = await db.execute(
                select(User.project_id, func.count(User.id))
                .where(User.project_id.in_(project_ids))
                .group_by(User.project_id)
            )
            users_counts = {row[0]: row[1] for row in result.all()}
        else:
            users_counts = {}
        
        # Освобождаем память после запроса
        del result
        gc.collect()
        
        # Получаем количество документов для всех проектов одним запросом
        from app.models.document import Document
        if projects:
            project_ids = [p.id for p in projects]
            docs_result = await db.execute(
                select(Document.project_id, func.count(Document.id))
                .where(Document.project_id.in_(project_ids))
                .group_by(Document.project_id)
            )
            documents_counts = {row[0]: row[1] for row in docs_result.all()}
        else:
            documents_counts = {}
        
        for project in projects:
            # Бот считается активным, если есть токен И bot_is_active == "true"
            bot_is_active_str = getattr(project, 'bot_is_active', 'false') or 'false'
            is_active = project.bot_token is not None and bot_is_active_str == "true"
            
            logger.info(f"[GET BOTS INFO] Project {project.id} ({project.name}): bot_token={'SET' if project.bot_token else 'NULL'}, bot_is_active={bot_is_active_str}, llm_model={project.llm_model}")
            
            bot_info = BotInfoResponse(
                project_id=project.id,
                project_name=project.name,
                bot_token=project.bot_token,
                users_count=users_counts.get(project.id, 0),
                is_active=is_active,
                bot_is_active=bot_is_active_str,
                llm_model=project.llm_model,
                description=project.description,
                documents_count=documents_counts.get(project.id, 0)
            )
            
            logger.info(f"[GET BOTS INFO] BotInfo created for {project.id}: bot_token={'SET' if bot_info.bot_token else 'NULL'}")
            
            # КРИТИЧНО: НЕ делаем запросы к Telegram API в списке
            # Это может вызвать out of memory при большом количестве ботов
            # Telegram API запросы делаются только при необходимости (verify endpoint)
            # bot_info.bot_username = None
            # bot_info.bot_first_name = None
            # bot_info.bot_url = None
            
            bots_info.append(bot_info)
        
        # Освобождаем память
        del projects
        del users_counts
        gc.collect()
        
        logger.info(f"Returning {len(bots_info)} bots info (without Telegram API calls)")
        return bots_info
    except Exception as e:
        logger.error(f"Error getting bots info: {e}", exc_info=True)
        gc.collect()
        return []


@router.post("/{project_id}/verify", response_model=BotInfoResponse)
async def verify_bot_token(
    project_id: UUID,
    token_data: dict,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Проверить токен бота и получить информацию"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[VERIFY TOKEN] Starting verification for project {project_id}")
    logger.info(f"[VERIFY TOKEN] Token data keys: {list(token_data.keys())}")
    
    bot_token = token_data.get('bot_token')
    
    if not bot_token:
        logger.error(f"[VERIFY TOKEN] Token not provided in request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Токен бота не предоставлен"
        )
    
    logger.info(f"[VERIFY TOKEN] Token received (first 10 chars): {bot_token[:10]}...")
    
    # Проверяем токен через Telegram API
    try:
        logger.info(f"[VERIFY TOKEN] Checking token with Telegram API...")
        bot = Bot(token=bot_token)
        bot_user = await bot.get_me()
        await bot.session.close()
        logger.info(f"[VERIFY TOKEN] Token verified successfully. Bot username: {bot_user.username}, first_name: {bot_user.first_name}")
    except Exception as e:
        logger.error(f"[VERIFY TOKEN] Token verification failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверный токен бота: {str(e)}"
        )
    
    # Обновляем проект с новым токеном
    logger.info(f"[VERIFY TOKEN] Updating project with new token...")
    service = ProjectService(db)
    from app.schemas.project import ProjectUpdate
    project_update = ProjectUpdate(bot_token=bot_token)
    project = await service.update_project(project_id, project_update)
    
    if not project:
        logger.error(f"[VERIFY TOKEN] Project {project_id} not found after update")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    logger.info(f"[VERIFY TOKEN] Project updated. Current bot_token: {project.bot_token[:10] if project.bot_token else 'None'}...")
    
    # Получаем количество пользователей для проекта
    result = await db.execute(
        select(func.count(User.id)).where(User.project_id == project.id)
    )
    users_count = result.scalar() or 0
    logger.info(f"[VERIFY TOKEN] Users count: {users_count}")
    
    # Получаем количество документов для проекта
    from app.models.document import Document
    docs_result = await db.execute(
        select(func.count(Document.id)).where(Document.project_id == project.id)
    )
    documents_count = docs_result.scalar() or 0
    logger.info(f"[VERIFY TOKEN] Documents count: {documents_count}")
    
    # Получаем информацию о боте
    bot_info = BotInfoResponse(
        project_id=project.id,
        project_name=project.name,
        bot_token=project.bot_token,
        bot_username=bot_user.username,
        bot_first_name=bot_user.first_name,
        users_count=users_count,
        is_active=False,
        llm_model=project.llm_model,
        description=project.description,
        documents_count=documents_count
    )
    
    if bot_user.username:
        bot_info.bot_url = f"https://t.me/{bot_user.username}"
    
    logger.info(f"[VERIFY TOKEN] Returning bot info: project_id={bot_info.project_id}, bot_token={'SET' if bot_info.bot_token else 'NULL'}, bot_username={bot_info.bot_username}, bot_url={bot_info.bot_url}")
    
    return bot_info


@router.post("/{project_id}/start")
async def start_bot(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Запустить бота для проекта
    
    Устанавливает bot_is_active="true" в БД. Бот-сервис автоматически подхватит изменения
    и запустит бота при следующей проверке БД (обычно в течение 20 секунд).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[START BOT] Starting bot for project {project_id}")
    
    service = ProjectService(db)
    project = await service.get_project_by_id(project_id)
    
    if not project:
        logger.error(f"[START BOT] Project {project_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    if not project.bot_token:
        logger.error(f"[START BOT] Project {project_id} has no bot_token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Токен бота не настроен для этого проекта"
        )
    
    # Устанавливаем bot_is_active="true"
    from app.schemas.project import ProjectUpdate
    project_update = ProjectUpdate(bot_is_active="true")
    updated_project = await service.update_project(project_id, project_update)
    
    if not updated_project:
        logger.error(f"[START BOT] Failed to update project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось обновить статус бота"
        )
    
    logger.info(f"[START BOT] Bot activated for project {project_id}. bot_is_active={updated_project.bot_is_active}")
    
    return {
        "message": "Бот активирован. Бот-сервис автоматически запустит бота в течение 20 секунд.",
        "bot_is_active": updated_project.bot_is_active
    }


@router.post("/{project_id}/stop")
async def stop_bot(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Остановить бота для проекта
    
    Устанавливает bot_is_active="false" в БД. Бот-сервис автоматически подхватит изменения
    и остановит бота при следующей проверке БД (обычно в течение 20 секунд).
    Токен бота остается в БД, но бот не будет работать.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[STOP BOT] Stopping bot for project {project_id}")
    
    service = ProjectService(db)
    project = await service.get_project_by_id(project_id)
    
    if not project:
        logger.error(f"[STOP BOT] Project {project_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Устанавливаем bot_is_active="false" (токен остается в БД)
    from app.schemas.project import ProjectUpdate
    project_update = ProjectUpdate(bot_is_active="false")
    updated_project = await service.update_project(project_id, project_update)
    
    if not updated_project:
        logger.error(f"[STOP BOT] Failed to update project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось обновить статус бота"
        )
    
    logger.info(f"[STOP BOT] Bot deactivated for project {project_id}. bot_is_active={updated_project.bot_is_active}")
    
    return {
        "message": "Бот деактивирован. Бот-сервис автоматически остановит бота в течение 20 секунд.",
        "bot_is_active": updated_project.bot_is_active
    }

