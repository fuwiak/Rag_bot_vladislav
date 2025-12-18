"""
Схемы для моделей LLM
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime


class LLMModelBase(BaseModel):
    """Базовая схема модели"""
    model_id: str = Field(..., min_length=1, max_length=255, alias="model_id")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    
    model_config = {"protected_namespaces": ()}


class LLMModelCreate(LLMModelBase):
    """Схема для создания модели"""
    pass


class LLMModelResponse(LLMModelBase):
    """Схема ответа с моделью"""
    id: UUID
    is_custom: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
        protected_namespaces = ()


class GlobalModelSettingsUpdate(BaseModel):
    """Схема для обновления глобальных настроек"""
    primary_model_id: Optional[str] = None
    fallback_model_id: Optional[str] = None


class GlobalModelSettingsResponse(BaseModel):
    """Схема ответа с глобальными настройками"""
    primary_model_id: Optional[str] = None
    fallback_model_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class ModelTestRequest(BaseModel):
    """Схема для запроса тестирования модели"""
    model_id: str = Field(..., min_length=1, description="ID модели для тестирования")
    messages: List[Dict[str, str]] = Field(..., description="Список сообщений в формате [{\"role\": \"user\", \"content\": \"...\"}]")
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="Температура генерации")
    max_tokens: Optional[int] = Field(None, gt=0, description="Максимальное количество токенов")


class ModelTestResponse(BaseModel):
    """Схема ответа тестирования модели"""
    response: str = Field(..., description="Ответ от модели")
    model_id: str = Field(..., description="ID использованной модели")

