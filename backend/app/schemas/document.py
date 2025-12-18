"""
Схемы для документов
"""
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class DocumentResponse(BaseModel):
    """Схема ответа с документом"""
    id: UUID
    project_id: UUID
    filename: str
    file_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True








