"""
Модель для хранения кастомных LLM моделей и глобальных настроек
"""
from sqlalchemy import Column, String, Text, Boolean, Numeric
import uuid
from datetime import datetime
from sqlalchemy import DateTime
from decimal import Decimal

from app.core.database import Base, GUID
from pydantic import ConfigDict


class LLMModel(Base):
    """Кастомная модель LLM"""
    __tablename__ = "llm_models"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    model_id = Column(String(255), nullable=False, unique=True)  # ID модели из OpenRouter или кастомный
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_custom = Column(Boolean, default=True, nullable=False)  # True для кастомных, False для стандартных
    input_price = Column(Numeric(20, 10), nullable=True)  # Цена за 1M входных токенов
    output_price = Column(Numeric(20, 10), nullable=True)  # Цена за 1M выходных токенов
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GlobalModelSettings(Base):
    """Глобальные настройки моделей (primary и fallback)"""
    __tablename__ = "global_model_settings"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    primary_model_id = Column(String(255), nullable=True)  # ID primary модели
    fallback_model_id = Column(String(255), nullable=True)  # ID fallback модели
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)










