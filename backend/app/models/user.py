"""
Модель User - пользователи Telegram ботов
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.core.database import Base


class User(Base):
    """Пользователь Telegram бота"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    phone = Column(String(20), nullable=False)
    username = Column(String(255), nullable=True)
    status = Column(String(20), default="active", nullable=False)  # active, blocked
    first_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    project = relationship("Project", back_populates="users")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")

