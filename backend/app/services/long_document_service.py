"""
Сервис для обработки длинных документов (400+ страниц) с оптимизацией памяти
Использует текущие модели: OpenRouter embeddings и LLM
"""
import logging
from typing import List, Optional, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding_service import EmbeddingService
from app.vector_db.vector_store import VectorStore
from app.documents.chunker import DocumentChunker
from app.llm.openrouter_client import OpenRouterClient
from app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)


class LongDocumentService:
    """
    Сервис для обработки длинных документов (сотни страниц)
    Оптимизирован для работы с большими объемами текста
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()
        # Используем больший chunk_size для длинных документов
        self.chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
    
    async def process_long_document(
        self,
        document_id: UUID,
        project_id: UUID,
        text: str,
        batch_size: int = 50
    ) -> int:
        """
        Обрабатывает длинный документ батчами для оптимизации памяти
        
        Args:
            document_id: ID документа
            project_id: ID проекта
            text: Текст документа
            batch_size: Размер батча для обработки чанков
        
        Returns:
            Количество обработанных чанков
        """
        logger.info(f"[LongDocument] Starting processing document {document_id}, text length: {len(text)} chars")
        
        # Разбивка на чанки
        chunks = self.chunker.chunk_text(text)
        logger.info(f"[LongDocument] Document split into {len(chunks)} chunks")
        
        if not chunks:
            logger.warning(f"[LongDocument] Document {document_id} has no chunks")
            return 0
        
        # Получаем документ
        from sqlalchemy import select
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        
        if not document:
            logger.error(f"[LongDocument] Document {document_id} not found")
            return 0
        
        # Обработка батчами
        total_processed = 0
        collection_name = f"project_{project_id}"
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_texts = batch
            
            try:
                # Создаем embeddings для батча (эффективнее чем по одному)
                embeddings = await self.embedding_service.create_embeddings_batch(batch_texts)
                
                # Сохраняем каждый чанк из батча
                for chunk_index, (chunk_text, embedding) in enumerate(zip(batch_texts, embeddings)):
                    global_chunk_index = i + chunk_index
                    
                    try:
                        # Сохранение чанка в БД
                        chunk = DocumentChunk(
                            document_id=document.id,
                            chunk_text=chunk_text[:10000],  # Максимум 10KB
                            chunk_index=global_chunk_index
                        )
                        self.db.add(chunk)
                        await self.db.flush()  # Получаем ID чанка
                        
                        # Сохранение вектора в Qdrant
                        point_id = await self.vector_store.store_vector(
                            collection_name=collection_name,
                            vector=embedding,
                            payload={
                                "document_id": str(document.id),
                                "chunk_id": str(chunk.id),
                                "chunk_index": global_chunk_index,
                                "chunk_text": chunk_text[:500]  # Первые 500 символов в payload
                            }
                        )
                        
                        chunk.qdrant_point_id = point_id
                        await self.db.commit()
                        
                        total_processed += 1
                        
                    except Exception as e:
                        logger.error(f"[LongDocument] Error processing chunk {global_chunk_index}: {e}")
                        await self.db.rollback()
                        continue
                
                # Логируем прогресс каждые 50 чанков
                if (i + batch_size) % 50 == 0 or (i + batch_size) >= len(chunks):
                    logger.info(f"[LongDocument] Processed {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")
                
            except Exception as e:
                logger.error(f"[LongDocument] Error processing batch {i}-{i+batch_size}: {e}")
                continue
        
        logger.info(f"[LongDocument] Successfully processed {total_processed}/{len(chunks)} chunks for document {document_id}")
        return total_processed
    
    async def search_long_document(
        self,
        project_id: UUID,
        query: str,
        document_id: Optional[UUID] = None,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Поиск по длинному документу
        
        Args:
            project_id: ID проекта
            query: Поисковый запрос
            document_id: Фильтр по документу (опционально)
            n_results: Количество результатов
        
        Returns:
            Список найденных чанков с метаданными
        """
        # Создаем embedding для запроса
        query_embedding = await self.embedding_service.create_embedding(query)
        
        # Поиск в Qdrant
        collection_name = f"project_{project_id}"
        
        # Поиск похожих векторов
        search_results = await self.vector_store.search_similar(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=n_results * 2,  # Берем больше для фильтрации
            score_threshold=0.0
        )
        
        # Фильтруем по document_id если указан
        if document_id:
            search_results = [
                r for r in search_results
                if r.get("payload", {}).get("document_id") == str(document_id)
            ]
        
        # Форматируем результаты
        results = []
        for result in search_results[:n_results]:
            payload = result.get("payload", {})
            results.append({
                "chunk_id": payload.get("chunk_id"),
                "document_id": payload.get("document_id"),
                "chunk_index": payload.get("chunk_index"),
                "chunk_text": payload.get("chunk_text", ""),
                "score": result.get("score", 0.0)
            })
        
        return results
    
    async def get_context_for_query(
        self,
        project_id: UUID,
        query: str,
        document_id: Optional[UUID] = None,
        n_results: int = 5,
        context_window: int = 3000
    ) -> str:
        """
        Получает контекст для запроса, объединяя найденные фрагменты
        
        Args:
            project_id: ID проекта
            query: Поисковый запрос
            document_id: Фильтр по документу
            n_results: Количество результатов
            context_window: Максимальная длина контекста
        
        Returns:
            Объединенный контекст
        """
        results = await self.search_long_document(
            project_id=project_id,
            query=query,
            document_id=document_id,
            n_results=n_results * 2  # Берем больше для фильтрации
        )
        
        context_parts = []
        current_length = 0
        
        for result in results:
            chunk_text = result.get('chunk_text', '')
            if not chunk_text:
                # Если нет в payload, получаем из БД
                chunk_id = result.get('chunk_id')
                if chunk_id:
                    try:
                        from sqlalchemy import select
                        chunk_result = await self.db.execute(
                            select(DocumentChunk).where(DocumentChunk.id == UUID(chunk_id))
                        )
                        chunk = chunk_result.scalar_one_or_none()
                        if chunk:
                            chunk_text = chunk.chunk_text
                    except Exception as e:
                        logger.warning(f"[LongDocument] Error fetching chunk {chunk_id}: {e}")
                        continue
            
            if chunk_text and current_length + len(chunk_text) <= context_window:
                context_parts.append(chunk_text)
                current_length += len(chunk_text)
            elif current_length >= context_window:
                break
        
        return "\n\n---\n\n".join(context_parts)
    
    async def rag_query_long_document(
        self,
        project_id: UUID,
        query: str,
        document_id: Optional[UUID] = None,
        n_results: int = 5,
        system_prompt: Optional[str] = None,
        model_primary: Optional[str] = None,
        model_fallback: Optional[str] = None
    ) -> str:
        """
        RAG-запрос для длинного документа: поиск контекста + генерация ответа
        
        Args:
            project_id: ID проекта
            query: Пользовательский запрос
            document_id: Фильтр по документу
            n_results: Количество результатов для поиска
            system_prompt: Дополнительный системный промпт
            model_primary: Основная модель LLM
            model_fallback: Fallback модель LLM
        
        Returns:
            Ответ AI с использованием найденного контекста
        """
        logger.info(f"[LongDocument] RAG query for document {document_id}: {query[:50]}...")
        
        # Поиск релевантного контекста
        context = await self.get_context_for_query(
            project_id=project_id,
            query=query,
            document_id=document_id,
            n_results=n_results
        )
        
        if not context:
            return "Не найдено релевантной информации в документе."
        
        # Формирование промпта
        system = system_prompt or (
            "Ты опытный эксперт. Используй предоставленный контекст из документа "
            "для ответа на вопрос. Если в контексте нет достаточной информации, укажи это."
        )
        
        prompt = f"""{system}

КОНТЕКСТ ИЗ ДОКУМЕНТА:
{context}

ВОПРОС: {query}

ОТВЕТ:"""
        
        # Вызов LLM через OpenRouterClient
        llm_client = OpenRouterClient(
            model_primary=model_primary,
            model_fallback=model_fallback
        )
        
        logger.info("[LongDocument] Generating answer with RAG through OpenRouter...")
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        response = await llm_client.chat_completion(
            messages=messages,
            max_tokens=4096,
            temperature=0.2
        )
        
        return response

