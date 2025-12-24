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
            
            # Парсинг документа
            try:
                text = await parser.parse(file_content, file_type)
            except Exception as e:
                logger.error(f"[Celery] Ошибка парсинга документа {document_id} ({filename}): {e}")
                result = await db.execute(select(Document).where(Document.id == document_id))
                document = result.scalar_one_or_none()
                if document:
                    document.content = f"Ошибка обработки: {str(e)[:200]}"
                    await db.commit()
                return
            
            # Получаем документ и обновляем его content
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if not document:
                logger.error(f"[Celery] Document {document_id} not found")
                return
            
            # Ограничиваем размер content для экономии памяти
            document.content = text[:500] + "..." if len(text) > 500 else text
            await db.commit()
            
            logger.info(f"[Celery] Document parsed, text length: {len(text)}")
            
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
                    
                    # Сохраняем чанк в БД
                    chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_text=chunk_text[:1000],  # Ограничиваем для экономии памяти
                        chunk_index=chunk_index
                    )
                    db.add(chunk)
                    await db.flush()  # Получаем ID чанка
                    
                    # Сохраняем в Qdrant (ограничиваем payload для экономии памяти)
                    try:
                        point_id = await vector_store.store_vector(
                            collection_name=f"project_{project_id}",
                            vector=embedding,
                            payload={
                                "document_id": str(document_id),
                                "chunk_id": str(chunk.id),
                                "chunk_index": chunk_index,
                                "chunk_text": chunk_text[:500]  # Ограничиваем для Qdrant
                            }
                        )
                        chunk.qdrant_point_id = point_id
                        await db.flush()  # Обновляем qdrant_point_id
                    except Exception as e:
                        logger.error(f"[Celery] Ошибка сохранения вектора в Qdrant для чанка {chunk_index}: {e}")
                        # Продолжаем обработку, даже если Qdrant недоступен
                    
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
            
            logger.info(f"[Celery] Document {document_id} processed successfully, {len(chunks)} chunks created")
            
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

