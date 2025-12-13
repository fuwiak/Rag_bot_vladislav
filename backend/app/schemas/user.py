"""
Схемы для пользователей
"""
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class UserCreate(BaseModel):
    """Схема для создания пользователя"""
    phone: str = Field(..., min_length=1, max_length=20)
    username: Optional[str] = Field(None, max_length=255)


class UserResponse(BaseModel):
    """Схема ответа с пользователем"""
    id: UUID
    project_id: UUID
    phone: str
    username: Optional[str] = None
    status: str
    first_login_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserStatusUpdate(BaseModel):
    """Схема для обновления статуса пользователя"""
    status: str = Field(..., pattern="^(active|blocked)$")

