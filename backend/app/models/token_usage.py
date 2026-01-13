"""
Модель для отслеживания использования токенов LLM
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.core.database import Base, GUID


class TokenUsage(Base):
    """Статистика использования токенов LLM"""
    __tablename__ = "token_usage"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    model_id = Column(String(255), nullable=False, index=True)  # ID модели из OpenRouter
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    input_tokens = Column(Integer, nullable=False, default=0)  # Количество входных токенов
    output_tokens = Column(Integer, nullable=False, default=0)  # Количество выходных токенов
    total_tokens = Column(Integer, nullable=False, default=0)  # Общее количество токенов
    cost = Column(String(50), nullable=True)  # Стоимость в виде строки (для точности)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Связь с проектом (опционально)
    project = relationship("Project", backref="token_usages")
