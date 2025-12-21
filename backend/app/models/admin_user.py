"""
Модель AdminUser - администраторы системы
"""
from sqlalchemy import Column, String, DateTime
import uuid
from datetime import datetime

from app.core.database import Base, GUID


class AdminUser(Base):
    """Администратор системы"""
    __tablename__ = "admin_users"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)











