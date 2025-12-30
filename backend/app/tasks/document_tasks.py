"""
Celery задачи для обработки документов
"""
import os
import gc
import logging
from uuid import UUID
from celery import Task
from app.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Базовый класс для задач с доступом к БД"""
    _db = None

    @property
    def db(self):
        if self._db is None:
            # Для Celery задач используем синхронный доступ к БД
            # или создаем новую сессию для каждой задачи
            pass
        return self._db


@celery_app.task(bind=True, name='app.tasks.document_tasks.process_document_task')
def process_document_task(self, document_id: str, project_id: str, file_path: str, filename: str, file_type: str):
    """
    Celery задача для обработки документа из файла
    Выполняется в отдельном воркере для предотвращения out of memory
    """
    import asyncio
    import psutil
    
    process = psutil.Process(os.getpid())
    start_memory = process.memory_info().rss / 1024 / 1024
    logger.info(f"[Celery] Starting processing document {document_id} ({filename}), memory: {start_memory:.2f}MB")
    
    file_content = None
    try:
        # Проверяем размер файла
        if not os.path.exists(file_path):
            logger.error(f"[Celery] File not found: {file_path}")
            return {"status": "error", "message": f"File not found: {file_path}"}
        
        file_size = os.path.getsize(file_path) / 1024 / 1024
        logger.info(f"[Celery] Reading file {file_path}, size: {file_size:.2f}MB")
        
        # Читаем файл
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        read_memory = process.memory_info().rss / 1024 / 1024
        logger.info(f"[Celery] File read into memory, memory: {read_memory:.2f}MB (delta: {read_memory - start_memory:.2f}MB)")
        
        # Удаляем временный файл сразу после чтения
        try:
            os.unlink(file_path)
            logger.info(f"[Celery] Temp file deleted: {file_path}")
        except Exception as e:
            logger.warning(f"[Celery] Не удалось удалить временный файл {file_path}: {e}")
        
        # Вызываем основную функцию обработки асинхронно
        # Celery задачи выполняются синхронно, но мы используем asyncio.run для async функций
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                process_document_async(
                    UUID(document_id),
                    UUID(project_id),
                    file_content,
                    filename,
                    file_type
                )
            )
            logger.info(f"[Celery] Document {document_id} processed successfully")
            return {"status": "success", "document_id": document_id}
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"[Celery] Error processing document {document_id}: {e}", exc_info=True)
        # Удаляем временный файл в случае ошибки
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except:
                pass
        return {"status": "error", "message": str(e)}
    finally:
        # Освобождаем память
        if file_content is not None:
            del file_content
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        logger.info(f"[Celery] Processing complete for document {document_id}, final memory: {final_memory:.2f}MB")


async def process_document_async(document_id: UUID, project_id: UUID, file_content: bytes, filename: str, file_type: str):
    """Асинхронная обработка документа (парсинг, эмбеддинги, сохранение в Qdrant)"""
    import gc
    import psutil
    
    process = psutil.Process(os.getpid())
    try:
        async with AsyncSessionLocal() as db:
            # Парсинг и разбивка на чанки
            from app.documents.parser import DocumentParser
            from app.documents.chunker import DocumentChunker
            from app.models.document import Document
            from sqlalchemy import select
            
            parser = DocumentParser()
            chunker = DocumentChunker()
            
            # Получаем документ ПЕРЕД парсингом, aby móc szybko zaktualizować content
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if not document:
                logger.error(f"[Celery] Document {document_id} not found")
                return
            
            # Парсинг документа
            try:
                text = await parser.parse(file_content, file_type)
            except Exception as e:
                logger.error(f"[Celery] Ошибка парсинга документа {document_id} ({filename}): {e}")
                document.content = f"Ошибка обработки: {str(e)[:200]}"
                await db.commit()
                return
            
            # КРИТИЧНО: Сохраняем content НЕМЕДЛЕННО после парсинга, чтобы RAG мог его использовать
            # Максимальный размер контента: 2MB текста (примерно 2,000,000 символов)
            MAX_CONTENT_SIZE = 2_000_000
            if len(text) > MAX_CONTENT_SIZE:
                logger.warning(f"[Celery] Document {document_id} content too large ({len(text)} chars), truncating to {MAX_CONTENT_SIZE}")
                document.content = text[:MAX_CONTENT_SIZE] + f"\n\n[... документ обрезан, всего {len(text)} символов ...]"
            else:
                document.content = text
            
            # КОММИТИМ СРАЗУ, чтобы content był dostępен для RAG
            await db.commit()
            await db.refresh(document)
            
            logger.info(f"[Celery] ✅ Document content saved IMMEDIATELY - ID: {document_id}, Filename: {filename}, "
                       f"Text length: {len(text)} chars, Content saved: {len(document.content)} chars")
            logger.info(f"[Celery] Document is now READY for RAG queries")
            
            # Логируем превью контента для отладки
            if document.content:
                preview = document.content[:500] if len(document.content) > 500 else document.content
                logger.info(f"[Celery] Document content preview (first 500 chars): {preview}...")
            
            # Разбивка на чанки
            chunks = chunker.chunk_text(text)
            if not chunks:
                logger.warning(f"[Celery] Документ {document_id} не содержит текста")
                return
            
            logger.info(f"[Celery] Document split into {len(chunks)} chunks")
            
            # Создание эмбеддингов по одному для минимального использования памяти
            from app.services.embedding_service import EmbeddingService
            from app.vector_db.vector_store import VectorStore
            from app.models.document import DocumentChunk
            
            embedding_service = EmbeddingService()
            vector_store = VectorStore()
            
            # Batch processing для szybszego zapisu do Qdrant
            BATCH_SIZE = 10  # Zapisujemy po 10 chunks naraz
            batch_points = []
            batch_chunks = []
            
            # Обрабатываем чанки по одному для минимального использования памяти
            for chunk_index, chunk_text in enumerate(chunks):
                try:
                    chunk_memory_before = process.memory_info().rss / 1024 / 1024
                    
                    # Создаем эмбеддинг для одного чанка
                    try:
                        embedding = await embedding_service.create_embedding(chunk_text)
                    except Exception as e:
                        logger.error(f"[Celery] Ошибка создания эмбеддинга для чанка {chunk_index}: {e}")
                        continue
                    
                    # Сохраняем чанк в БД (сохраняем полный текст чанка)
                    # Максимальный размер чанка: 10KB текста (примерно 10,000 символов)
                    MAX_CHUNK_SIZE = 10_000
                    chunk_text_to_save = chunk_text[:MAX_CHUNK_SIZE] if len(chunk_text) > MAX_CHUNK_SIZE else chunk_text
                    if len(chunk_text) > MAX_CHUNK_SIZE:
                        logger.warning(f"[Celery] Chunk {chunk_index} too large ({len(chunk_text)} chars), truncating to {MAX_CHUNK_SIZE}")
                    
                    chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_text=chunk_text_to_save,
                        chunk_index=chunk_index
                    )
                    db.add(chunk)
                    await db.flush()  # Получаем ID чанка
                    
                    # Dodajemy do batcha dla szybszego zapisu do Qdrant
                    from qdrant_client.models import PointStruct
                    point_id = chunk.id  # Używamy chunk.id jako point_id
                    batch_points.append(PointStruct(
                        id=str(point_id),
                        vector=embedding,
                        payload={
                            "document_id": str(document_id),
                            "chunk_id": str(chunk.id),
                            "chunk_index": chunk_index,
                            "filename": filename,
                            "chunk_text": chunk_text[:500]  # Ограничиваем для Qdrant
                        }
                    ))
                    batch_chunks.append((chunk, point_id))
                    
                    # Zapisujemy batch co BATCH_SIZE chunks
                    if len(batch_points) >= BATCH_SIZE or chunk_index == len(chunks) - 1:
                        try:
                            # Batch upsert do Qdrant
                            collection_name = f"project_{project_id}"
                            await vector_store.ensure_collection(collection_name, len(embedding))
                            vector_store.client.upsert(
                                collection_name=collection_name,
                                points=batch_points
                            )
                            
                            # Aktualizujemy qdrant_point_id dla wszystkich chunks w batchu
                            for batch_chunk, batch_point_id in batch_chunks:
                                batch_chunk.qdrant_point_id = batch_point_id
                            await db.flush()
                            
                            logger.info(f"[Celery] ✅ Batch upserted {len(batch_points)} chunks to Qdrant (up to chunk {chunk_index})")
                        except Exception as e:
                            logger.error(f"[Celery] Ошибка batch upsert в Qdrant: {e}")
                            # Próbujemy zapisać pojedynczo jako fallback
                            for batch_chunk, batch_point_id in batch_chunks:
                                try:
                                    await vector_store.store_vector(
                                        collection_name=f"project_{project_id}",
                                        vector=embedding,  # Używamy ostatniego embedding
                                        payload={
                                            "document_id": str(document_id),
                                            "chunk_id": str(batch_chunk.id),
                                            "chunk_index": batch_chunk.chunk_index,
                                            "filename": filename,
                                            "chunk_text": batch_chunk.chunk_text[:500]
                                        }
                                    )
                                    batch_chunk.qdrant_point_id = batch_point_id
                                except:
                                    pass
                        
                        # Czyszczenie batcha
                        batch_points = []
                        batch_chunks = []
                    
                    chunk_memory_after = process.memory_info().rss / 1024 / 1024
                    if chunk_index % 10 == 0:
                        logger.info(f"[Celery] Processed chunk {chunk_index}/{len(chunks)}, memory: {chunk_memory_after:.2f}MB")
                    
                    # Освобождаем память каждые 10 чанков
                    if chunk_index % 10 == 0:
                        gc.collect()
                    
                except Exception as e:
                    logger.error(f"[Celery] Ошибка обработки чанка {chunk_index}: {e}", exc_info=True)
                    continue
            
            # Коммитим все чанки
            await db.commit()
            
            # Проверяем финальное состояние документа
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if document:
                content_length = len(document.content) if document.content else 0
                logger.info(f"[Celery] ✅ Document {document_id} processed successfully:")
                logger.info(f"  - Filename: {filename}")
                logger.info(f"  - Chunks created: {len(chunks)}")
                logger.info(f"  - Content length: {content_length} chars")
                logger.info(f"  - Content status: {'READY' if content_length > 100 else 'EMPTY'}")
                if document.content and content_length > 0:
                    preview = document.content[:300] if content_length > 300 else document.content
                    logger.info(f"  - Content preview: {preview}...")
            else:
                logger.error(f"[Celery] ❌ Document {document_id} not found after processing!")
            
            # Генерируем summary для документа через LLM (в фоне)
            try:
                from app.services.document_summary_service import DocumentSummaryService
                summary_service = DocumentSummaryService(db)
                summary = await summary_service.generate_summary(document_id)
                if summary:
                    logger.info(f"[Celery] Summary generated for document {document_id}")
            except Exception as summary_error:
                logger.warning(f"[Celery] Error generating summary for document {document_id}: {summary_error}")
            
    except Exception as e:
        logger.error(f"[Celery] Error processing document {document_id}: {e}", exc_info=True)
    finally:
        gc.collect()


@celery_app.task(bind=True, name='app.tasks.document_tasks.generate_document_summary_task')
def generate_document_summary_task(self, document_id: str):
    """
    Celery задача для генерации summary документа через LLM
    """
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def generate_summary_async():
                async with AsyncSessionLocal() as db:
                    from app.services.document_summary_service import DocumentSummaryService
                    summary_service = DocumentSummaryService(db)
                    summary = await summary_service.generate_summary(UUID(document_id))
                    return summary
            
            result = loop.run_until_complete(generate_summary_async())
            logger.info(f"[Celery] Summary generated for document {document_id}")
            return {"status": "success", "document_id": document_id}
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"[Celery] Error generating summary for document {document_id}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

