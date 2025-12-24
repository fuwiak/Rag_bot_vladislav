"""
Схемы для проектов
"""
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class ProjectBase(BaseModel):
    """Базовая схема проекта"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    bot_token: Optional[str] = None
    bot_is_active: Optional[str] = Field(default="false")  # "true" или "false"
    access_password: str = Field(..., min_length=4)
    prompt_template: str = Field(..., min_length=10)
    max_response_length: int = Field(default=1000, ge=100, le=10000)
    llm_model: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Схема для создания проекта"""
    pass


class ProjectUpdate(BaseModel):
    """Схема для обновления проекта"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    bot_token: Optional[str] = None
    bot_is_active: Optional[str] = Field(None)  # "true" или "false"
    access_password: Optional[str] = Field(None, min_length=4)
    prompt_template: Optional[str] = Field(None, min_length=10)
    max_response_length: Optional[int] = Field(None, ge=100, le=10000)
    llm_model: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Схема ответа с проектом"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ProjectListResponse(BaseModel):
    """Упрощенная схема для списка проектов (без больших полей)"""
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


