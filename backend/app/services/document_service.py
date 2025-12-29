"""
Сервис для управления документами
"""
from typing import List, Optional
from uuid import UUID
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document
from app.documents.parser import DocumentParser
from app.documents.chunker import DocumentChunker
from app.vector_db.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService


class DocumentService:
    """Сервис для работы с документами"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.parser = DocumentParser()
        self.chunker = DocumentChunker()
        self.vector_store = VectorStore()
        self.embedding_service = EmbeddingService()
    
    async def upload_document(self, project_id: UUID, file: UploadFile) -> Document:
        """
        Загрузить и обработать документ
        
        1. Парсинг файла
        2. Разбивка на чанки
        3. Создание эмбеддингов
        4. Сохранение в PostgreSQL и Qdrant
        """
        # Чтение файла
        content = await file.read()
        
        # Определение типа файла
        file_type = file.filename.split('.')[-1].lower()
        
        # Парсинг документа
        text = await self.parser.parse(content, file_type)
        
        # Создание записи документа в БД
        document = Document(
            project_id=project_id,
            filename=file.filename,
            content=text,
            file_type=file_type
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        # Разбивка на чанки
        chunks = self.chunker.chunk_text(text)
        
        # Создание эмбеддингов и сохранение в Qdrant
        for index, chunk_text in enumerate(chunks):
            # Создание эмбеддинга
            embedding = await self.embedding_service.create_embedding(chunk_text)
            
            # Сохранение чанка в БД
            from app.models.document import DocumentChunk
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_text=chunk_text,
                chunk_index=index
            )
            self.db.add(chunk)
            await self.db.flush()  # Получаем ID чанка
            
            # Сохранение вектора в Qdrant
            point_id = await self.vector_store.store_vector(
                collection_name=f"project_{project_id}",
                vector=embedding,
                payload={
                    "document_id": str(document.id),
                    "chunk_id": str(chunk.id),
                    "chunk_index": index,
                    "chunk_text": chunk_text
                }
            )
            
            # Обновление point_id в БД
            chunk.qdrant_point_id = point_id
        
        await self.db.commit()
        
        return document
    
    async def get_project_documents(self, project_id: UUID) -> List[Document]:
        """Получить все документы проекта"""
        result = await self.db.execute(
            select(Document).where(Document.project_id == project_id)
        )
        return list(result.scalars().all())
    
    async def delete_document(self, document_id: UUID) -> bool:
        """Удалить документ и его векторы из Qdrant"""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            return False
        
        # Удаление векторов из Qdrant
        from app.models.document import DocumentChunk
        chunks_result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        chunks = chunks_result.scalars().all()
        
        for chunk in chunks:
            if chunk.qdrant_point_id:
                await self.vector_store.delete_vector(
                    collection_name=f"project_{document.project_id}",
                    point_id=chunk.qdrant_point_id
                )
        
        # Удаление документа из БД (каскадное удаление чанков)
        await self.db.delete(document)
        await self.db.commit()
        
        return True






















