"""
Модель для хранения кастомных LLM моделей и глобальных настроек
"""
from sqlalchemy import Column, String, Text, Boolean
import uuid
from datetime import datetime
from sqlalchemy import DateTime

from app.core.database import Base, GUID
from pydantic import ConfigDict


class LLMModel(Base):
    """Кастомная модель LLM"""
    __tablename__ = "llm_models"
    
    model_config = ConfigDict(protected_namespaces=())
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    model_id = Column(String(255), nullable=False, unique=True)  # ID модели из OpenRouter или кастомный
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_custom = Column(Boolean, default=True, nullable=False)  # True для кастомных, False для стандартных
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GlobalModelSettings(Base):
    """Глобальные настройки моделей (primary и fallback)"""
    __tablename__ = "global_model_settings"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    primary_model_id = Column(String(255), nullable=True)  # ID primary модели
    fallback_model_id = Column(String(255), nullable=True)  # ID fallback модели
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)










