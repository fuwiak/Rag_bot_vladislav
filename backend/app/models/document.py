"""
Модели Document и DocumentChunk - документы и их чанки
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from sqlalchemy import DateTime

from app.core.database import Base, GUID


class Document(Base):
    """Загруженный документ"""
    __tablename__ = "documents"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    file_type = Column(String(10), nullable=False)  # txt, docx, pdf
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    project = relationship("Project", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Чанк документа для векторного поиска"""
    __tablename__ = "document_chunks"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID, ForeignKey("documents.id"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    qdrant_point_id = Column(GUID, nullable=True)  # ID точки в Qdrant
    chunk_metadata = Column(JSONB, nullable=True)  # Переименовано из metadata, чтобы избежать конфликта с SQLAlchemy
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    document = relationship("Document", back_populates="chunks")

