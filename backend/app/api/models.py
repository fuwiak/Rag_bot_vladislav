"""
Роутер для управления моделями LLM
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
import httpx
import logging

from app.core.database import get_db
from app.core.config import settings
from app.api.dependencies import get_current_admin
from app.models.project import Project
from app.models.llm_model import LLMModel, GlobalModelSettings
from app.schemas.project import ProjectUpdate
from app.schemas.llm_model import (
    LLMModelCreate, LLMModelResponse, 
    GlobalModelSettingsUpdate, GlobalModelSettingsResponse,
    ModelTestRequest, ModelTestResponse
)
from app.schemas.token_usage import (
    TokenUsageStatisticsResponse, TokenUsageResponse, ModelPriceUpdate
)
from app.services.token_usage_service import TokenUsageService
from datetime import datetime, timedelta
from app.services.project_service import ProjectService
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/available")
async def get_available_models(
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin),
    search: Optional[str] = Query(None, description="Поиск моделей по названию или ID")
):
    """Получить список доступных моделей из OpenRouter + кастомные модели"""
    try:
        # Получаем кастомные модели из БД
        result = await db.execute(select(LLMModel))
        custom_models = result.scalars().all()
        
        # Получаем модели из OpenRouter
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "HTTP-Referer": settings.APP_URL,
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                # Форматируем все модели
                models = []
                for model_data in data.get("data", []):
                    model_id = model_data.get("id", "")
                    model_name = model_data.get("name", model_id)
                    # Используем красивое название, если есть, иначе ID
                    display_name = model_name if model_name and model_name != model_id else model_id
                    
                    models.append({
                        "id": model_id,
                        "name": display_name,
                        "description": model_data.get("description", ""),
                        "context_length": model_data.get("context_length", 0),
                        "pricing": model_data.get("pricing", {}),
                        "is_custom": False,
                    })
                
                # Добавляем кастомные модели
                for custom_model in custom_models:
                    models.append({
                        "id": custom_model.model_id,
                        "name": custom_model.name,
                        "description": custom_model.description or "",
                        "context_length": 0,
                        "pricing": {},
                        "is_custom": True,
                    })
                
                # Фильтрация по поиску
                if search:
                    search_lower = search.lower()
                    models = [
                        m for m in models 
                        if search_lower in m["name"].lower() or search_lower in m["id"].lower()
                    ]
                
                return {"models": models}
        except Exception as e:
            logger.error(f"Ошибка получения моделей из OpenRouter: {e}")
            # В случае ошибки возвращаем только кастомные модели
            custom_only = [
                {
                    "id": custom_model.model_id,
                    "name": custom_model.name,
                    "description": custom_model.description or "",
                    "context_length": 0,
                    "pricing": {},
                    "is_custom": True,
                }
                for custom_model in custom_models
            ]
            return {"models": custom_only}
    except Exception as e:
        logger.error(f"Ошибка получения моделей: {e}")
        return {"models": []}


@router.patch("/project/{project_id}")
async def assign_model_to_project(
    project_id: UUID,
    model_id: str = Query(None, description="ID модели LLM (если пусто, используется глобальная)"),
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Присвоить модель LLM проекту"""
    service = ProjectService(db)
    project = await service.get_project_by_id(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    # Обновляем модель проекта
    update_data = ProjectUpdate(llm_model=model_id if model_id else None)
    updated_project = await service.update_project(project_id, update_data)
    
    if not updated_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    return {
        "project_id": str(project_id),
        "llm_model": updated_project.llm_model,
        "message": "Модель успешно присвоена проекту"
    }


@router.post("/custom", response_model=LLMModelResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_model(
    model_data: LLMModelCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Создать кастомную модель"""
    # Проверяем, не существует ли уже модель с таким ID
    result = await db.execute(select(LLMModel).where(LLMModel.model_id == model_data.model_id))
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Модель с таким ID уже существует"
        )
    
    model = LLMModel(
        model_id=model_data.model_id,
        name=model_data.name,
        description=model_data.description,
        is_custom=True
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    
    return model


@router.get("/custom", response_model=List[LLMModelResponse])
async def get_custom_models(
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить список кастомных моделей"""
    result = await db.execute(select(LLMModel).where(LLMModel.is_custom == True))
    models = result.scalars().all()
    return list(models)


@router.delete("/custom/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Удалить кастомную модель"""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Модель не найдена"
        )
    
    await db.delete(model)
    await db.commit()


@router.get("/global-settings", response_model=GlobalModelSettingsResponse)
async def get_global_settings(
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить глобальные настройки моделей"""
    result = await db.execute(select(GlobalModelSettings).limit(1))
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Создаем настройки по умолчанию из .env
        from app.core.config import settings as app_settings
        settings = GlobalModelSettings(
            primary_model_id=app_settings.OPENROUTER_MODEL_PRIMARY,
            fallback_model_id=app_settings.OPENROUTER_MODEL_FALLBACK
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    else:
        # Если настройки есть, но модели не установлены, используем значения по умолчанию
        from app.core.config import settings as app_settings
        if not settings.primary_model_id:
            settings.primary_model_id = app_settings.OPENROUTER_MODEL_PRIMARY
        if not settings.fallback_model_id:
            settings.fallback_model_id = app_settings.OPENROUTER_MODEL_FALLBACK
        await db.commit()
        await db.refresh(settings)
    
    return settings


@router.patch("/global-settings", response_model=GlobalModelSettingsResponse)
async def update_global_settings(
    settings_data: GlobalModelSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Обновить глобальные настройки моделей"""
    result = await db.execute(select(GlobalModelSettings).limit(1))
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Создаем настройки
        settings = GlobalModelSettings()
        db.add(settings)
    
    if settings_data.primary_model_id is not None:
        settings.primary_model_id = settings_data.primary_model_id if settings_data.primary_model_id else None
    if settings_data.fallback_model_id is not None:
        settings.fallback_model_id = settings_data.fallback_model_id if settings_data.fallback_model_id else None
    
    await db.commit()
    await db.refresh(settings)
    
    return settings


@router.post("/test", response_model=ModelTestResponse)
async def test_model(
    test_request: ModelTestRequest,
    current_admin = Depends(get_current_admin)
):
    """Протестировать модель с заданными сообщениями"""
    try:
        # Отправляем запрос напрямую к OpenRouter для тестирования конкретной модели
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": test_request.model_id,
                "messages": test_request.messages,
                "temperature": test_request.temperature
            }
            
            if test_request.max_tokens:
                payload["max_tokens"] = test_request.max_tokens
            
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "HTTP-Referer": settings.APP_URL,
                    "X-Title": "Telegram RAG Bot - Model Testing",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            response.raise_for_status()
            data = response.json()
            
            if "choices" not in data or len(data["choices"]) == 0:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Пустой ответ от API"
                )
            
            return ModelTestResponse(
                response=data["choices"][0]["message"]["content"],
                model_id=test_request.model_id
            )
    except httpx.HTTPStatusError as e:
        error_detail = f"Ошибка API OpenRouter: {e.response.status_code}"
        try:
            error_data = e.response.json()
            logger.error(f"OpenRouter API error: {error_data}")
            if "error" in error_data:
                error_detail = error_data["error"].get("message", error_detail)
                # Добавляем дополнительную информацию, если есть
                if "type" in error_data["error"]:
                    error_detail += f" (тип: {error_data['error']['type']})"
        except Exception as parse_error:
            logger.error(f"Failed to parse error response: {parse_error}")
            # Пробуем получить текст ответа
            try:
                error_text = e.response.text
                if error_text:
                    error_detail = f"Ошибка API: {error_text[:200]}"
            except:
                pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail
        )
    except Exception as e:
        logger.error(f"Ошибка тестирования модели: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестирования модели: {str(e)}"
        )


@router.get("/token-statistics", response_model=TokenUsageStatisticsResponse)
async def get_token_statistics(
    model_id: Optional[str] = Query(None, description="Фильтр по модели"),
    project_id: Optional[UUID] = Query(None, description="Фильтр по проекту"),
    days: Optional[int] = Query(30, ge=1, le=365, description="Количество дней для статистики"),
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить статистику использования токенов"""
    try:
        token_service = TokenUsageService(db)
        
        # Вычисляем даты
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        if model_id:
            # Статистика для конкретной модели
            stats = await token_service.get_token_statistics(
                model_id=model_id,
                project_id=project_id,
                start_date=start_date,
                end_date=end_date
            )
            statistics = [TokenUsageResponse(
                model_id=model_id,
                total_input_tokens=stats["total_input_tokens"],
                total_output_tokens=stats["total_output_tokens"],
                total_tokens=stats["total_tokens"],
                usage_count=stats["usage_count"]
            )]
        else:
            # Статистика по всем моделям
            statistics_data = await token_service.get_token_statistics_by_model(
                start_date=start_date,
                end_date=end_date
            )
            statistics = [
                TokenUsageResponse(**stat) for stat in statistics_data
            ]
        
        # Вычисляем общие суммы
        total_input_tokens = sum(s.total_input_tokens for s in statistics)
        total_output_tokens = sum(s.total_output_tokens for s in statistics)
        total_tokens = sum(s.total_tokens for s in statistics)
        total_usage_count = sum(s.usage_count for s in statistics)
        
        return TokenUsageStatisticsResponse(
            statistics=statistics,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tokens=total_tokens,
            total_usage_count=total_usage_count
        )
    except Exception as e:
        logger.error(f"Ошибка получения статистики токенов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )


@router.patch("/custom/{model_id}/prices", response_model=LLMModelResponse)
async def update_model_prices(
    model_id: UUID,
    prices: ModelPriceUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Обновить цены модели"""
    try:
        result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Модель не найдена"
            )
        
        if prices.input_price is not None:
            model.input_price = prices.input_price
        if prices.output_price is not None:
            model.output_price = prices.output_price
        
        await db.commit()
        await db.refresh(model)
        
        logger.info(f"Updated prices for model {model.model_id}: input={prices.input_price}, output={prices.output_price}")
        
        return model
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления цен модели: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления цен: {str(e)}"
        )
