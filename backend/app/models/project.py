"""
Модель Project - проекты/отделы
"""
from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from sqlalchemy import DateTime

from app.core.database import Base, GUID


class Project(Base):
    """Проект/отдел с набором документов"""
    __tablename__ = "projects"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    bot_token = Column(String(255), nullable=True)  # Не unique - один бот может использоваться в нескольких проектах
    bot_is_active = Column(String(10), default="false", nullable=False)  # "true" или "false" - активен ли бот
    access_password = Column(String(255), nullable=False)
    prompt_template = Column(Text, nullable=False)
    max_response_length = Column(Integer, default=1000, nullable=False)
    llm_model = Column(String(255), nullable=True)  # Модель LLM для проекта (если None, используется глобальная)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Связи
    users = relationship("User", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")

