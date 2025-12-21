"""
Модель Message - история сообщений для контекста диалога
"""
from sqlalchemy import Column, Text, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.core.database import Base, GUID


class Message(Base):
    """Сообщение в истории диалога"""
    __tablename__ = "messages"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    user = relationship("User", back_populates="messages")











