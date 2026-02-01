"""
Celery задачи для обработки документов
Поддерживает фоновую загрузку в PostgreSQL и Qdrant
Использует Redis для кэширования промежуточных результатов
"""
import os
import gc
import logging
from uuid import UUID
from celery import Task
from app.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Конфигурация для больших документов
LARGE_DOCUMENT_THRESHOLD = 500_000  # 500KB текста
VERY_LARGE_DOCUMENT_THRESHOLD = 2_000_000  # 2MB текста (примерно 200+ страниц)
MAX_BATCH_SIZE_LARGE = 5  # Меньший батч для больших документов
MAX_BATCH_SIZE_NORMAL = 10  # Обычный размер батча
MAX_BATCH_SIZE_VERY_LARGE = 3  # Еще меньший батч для очень больших документов
PDF_PAGES_PER_BATCH = 50  # Обрабатываем PDF по 50 страниц за раз


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
            logger.info(f"[Celery] 🔄 Начало парсинга документа {document_id} ({filename})")
            logger.info(f"[Celery]   - Тип файла: {file_type}")
            logger.info(f"[Celery]   - Размер файла: {len(file_content) / 1024 / 1024:.2f} MB")
            
            try:
                text = await parser.parse(file_content, file_type)
                logger.info(f"[Celery] ✅ Парсинг завершен успешно: извлечено {len(text)} символов")
                
                if not text or len(text.strip()) < 50:
                    logger.error(f"[Celery] ❌ КРИТИЧЕСКАЯ ОШИБКА: Парсинг вернул пустой или слишком короткий текст!")
                    logger.error(f"[Celery] ❌ Длина текста: {len(text) if text else 0} символов")
                    logger.error(f"[Celery] ❌ Это может означать, что PDF сканированный, поврежден или парсер не смог извлечь текст")
                    raise ValueError(f"Парсинг вернул пустой текст: {len(text) if text else 0} символов")
                
                # Логируем превью извлеченного текста
                preview = text[:500] if len(text) > 500 else text
                logger.info(f"[Celery] 📄 Превью извлеченного текста (первые 500 символов): {preview}...")
                
            except Exception as e:
                logger.error(f"[Celery] ❌ Ошибка парсинга документа {document_id} ({filename}): {e}", exc_info=True)
                logger.error(f"[Celery] ❌ Тип ошибки: {type(e).__name__}")
                logger.error(f"[Celery] ❌ Сообщение: {str(e)}")
                document.content = f"Ошибка обработки: {str(e)[:200]}"
                await db.commit()
                return
            
            # КРИТИЧНО: Сохраняем content НЕМЕДЛЕННО после парсинга, чтобы RAG мог его использовать
            # Максимальный размер контента: 2MB текста (примерно 2,000,000 символов)
            logger.info(f"[Celery] 💾 Сохранение контента документа в БД для немедленного доступа RAG...")
            MAX_CONTENT_SIZE = 2_000_000
            if len(text) > MAX_CONTENT_SIZE:
                logger.warning(f"[Celery] ⚠️ Document {document_id} content слишком большой ({len(text)} символов), обрезаем до {MAX_CONTENT_SIZE}")
                document.content = text[:MAX_CONTENT_SIZE] + f"\n\n[... документ обрезан, всего {len(text)} символов ...]"
            else:
                document.content = text
            
            # КОММИТИМ СРАЗУ, чтобы content był dostępен для RAG
            logger.info(f"[Celery] 💾 Коммит изменений в БД...")
            await db.commit()
            await db.refresh(document)
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: убеждаемся что контент действительно сохранился
            saved_content = document.content
            saved_content_length = len(saved_content) if saved_content else 0
            
            logger.info(f"[Celery] ✅✅✅ ДОКУМЕНТ ГОТОВ ДЛЯ RAG ЗАПРОСОВ ✅✅✅")
            logger.info(f"[Celery] 📄 Document ID: {document_id}")
            logger.info(f"[Celery] 📄 Filename: {filename}")
            logger.info(f"[Celery] 📄 Text length (извлечено): {len(text)} символов")
            logger.info(f"[Celery] 📄 Content saved (в БД): {saved_content_length} символов")
            logger.info(f"[Celery] 📄 Content status: {'READY' if saved_content_length > 100 else 'EMPTY/ERROR'}")
            logger.info(f"[Celery] 📄 Content is 'Обработка...': {saved_content == 'Обработка...'}")
            logger.info(f"[Celery] 📄 Document is now READY for RAG queries - можно сразу задавать вопросы!")
            
            if saved_content_length < 100:
                logger.error(f"[Celery] ❌ КРИТИЧЕСКАЯ ОШИБКА: Контент не сохранился в БД!")
                logger.error(f"[Celery] ❌ Ожидалось: {len(text)} символов")
                logger.error(f"[Celery] ❌ Сохранено: {saved_content_length} символов")
                logger.error(f"[Celery] ❌ Значение content: '{saved_content[:200] if saved_content else 'EMPTY'}...'")
            
            # Логируем превью контента для отладки
            if document.content and saved_content_length > 100:
                preview = document.content[:500] if len(document.content) > 500 else document.content
                logger.info(f"[Celery] 📄 Content preview (первые 500 символов): {preview}...")
            else:
                logger.warning(f"[Celery] ⚠️ Content preview недоступен (слишком короткий или пустой)")
            
            # Разбивка на чанки - используем правильные параметры из рабочего скрипта (1000/200)
            logger.info(f"[Celery] 🔪 Начинаем разбивку документа на чанки: {filename}, размер текста: {len(text)} символов")
            from app.documents.advanced_chunker import AdvancedChunker
            advanced_chunker = AdvancedChunker(
                default_chunk_size=1000,  # Правильный размер из рабочего скрипта
                default_overlap=200,  # Правильное перекрытие из рабочего скрипта
                min_chunk_size=100,
                max_chunk_size=2000
            )
            
            chunking_start_memory = process.memory_info().rss / 1024 / 1024
            logger.info(f"[Celery] 🔪 Память перед chunking: {chunking_start_memory:.2f}MB")
            
            # Пробуем продвинутый chunking
            chunks = await advanced_chunker.chunk_document(
                text=text,
                file_type=file_type,
                file_content=file_content if file_type == "pdf" else None,
                filename=filename
            )
            
            # Fallback на простой chunker если продвинутый не сработал
            if not chunks or len(chunks) == 0:
                logger.warning(f"[Celery] ⚠️ Advanced chunking failed, using simple chunker with correct params (1000/200)")
                # Используем правильные параметры chunking
                chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
                chunks = chunker.chunk_text(text)
            if not chunks:
                logger.warning(f"[Celery] ❌ Документ {document_id} не содержит текста после chunking")
                return
            
            chunking_end_memory = process.memory_info().rss / 1024 / 1024
            total_chunks = len(chunks)
            avg_chunk_size = sum(len(c) for c in chunks) / total_chunks if chunks else 0
            logger.info(f"[Celery] ✅ Document split into {total_chunks} chunks:")
            logger.info(f"[Celery]   - Средний размер чанка: {avg_chunk_size:.0f} символов")
            logger.info(f"[Celery]   - Минимальный размер: {min(len(c) for c in chunks) if chunks else 0} символов")
            logger.info(f"[Celery]   - Максимальный размер: {max(len(c) for c in chunks) if chunks else 0} символов")
            logger.info(f"[Celery]   - Память после chunking: {chunking_end_memory:.2f}MB (delta: {chunking_end_memory - chunking_start_memory:.2f}MB)")
            
            # Создание эмбеддингов батчами для эффективности (как в рабочем скрипте)
            from app.services.embedding_service import EmbeddingService
            from app.vector_db.vector_store import VectorStore
            from app.models.document import DocumentChunk
            
            embedding_service = EmbeddingService()
            vector_store = VectorStore()
            
            # Batch processing для эффективной обработки (как в рабочем скрипте)
            EMBEDDING_BATCH_SIZE = 100  # Размер батча для эмбеддингов (как в рабочем скрипте)
            QDRANT_BATCH_SIZE = 100  # Размер батча для Qdrant (как в рабочем скрипте)
            batch_points = []
            batch_chunks = []
            
            # Обрабатываем чанки батчами для эффективности
            logger.info(f"[Celery] 🚀 Начинаем обработку {len(chunks)} чанков: создание эмбеддингов батчами и сохранение в Qdrant")
            embedding_start_memory = process.memory_info().rss / 1024 / 1024
            logger.info(f"[Celery] 📊 Память перед созданием эмбеддингов: {embedding_start_memory:.2f}MB")
            
            successful_chunks = 0
            failed_chunks = 0
            
            # Обрабатываем чанки батчами
            for batch_start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
                batch_chunk_texts = chunks[batch_start:batch_start + EMBEDDING_BATCH_SIZE]
                batch_indices = list(range(batch_start, min(batch_start + EMBEDDING_BATCH_SIZE, len(chunks))))
                
                try:
                    logger.info(f"[Celery] 🔄 Обработка батча {batch_start // EMBEDDING_BATCH_SIZE + 1}: чанки {batch_start + 1}-{batch_start + len(batch_chunk_texts)} из {len(chunks)}")
                    
                    # Создаем эмбеддинги для батча (как в рабочем скрипте)
                    try:
                        embeddings = await embedding_service.create_embeddings_batch(batch_chunk_texts)
                        logger.info(f"[Celery] ✅ Эмбеддинги созданы для батча: {len(embeddings)} эмбеддингов")
                    except Exception as e:
                        logger.error(f"[Celery] ❌ Ошибка создания эмбеддингов для батча: {e}, пробуем по одному")
                        # Fallback: создаем по одному
                        embeddings = []
                        for chunk_text in batch_chunk_texts:
                            try:
                                emb = await embedding_service.create_embedding(chunk_text)
                                embeddings.append(emb)
                            except Exception as single_error:
                                logger.error(f"[Celery] ❌ Ошибка создания эмбеддинга для чанка: {single_error}")
                                embeddings.append(None)
                                failed_chunks += 1
                    
                    # Обрабатываем результаты батча
                    for chunk_index, (chunk_text, embedding) in enumerate(zip(batch_chunk_texts, embeddings)):
                        actual_index = batch_indices[chunk_index]
                        
                        if embedding is None:
                            logger.warning(f"[Celery] ⚠️ Пропуск чанка {actual_index + 1}: эмбеддинг не создан")
                            failed_chunks += 1
                            continue
                        
                        try:
                    
                            # Сохраняем чанк в БД (сохраняем полный текст чанка)
                            # Максимальный размер чанка: 10KB текста (примерно 10,000 символов)
                            MAX_CHUNK_SIZE = 10_000
                            chunk_text_to_save = chunk_text[:MAX_CHUNK_SIZE] if len(chunk_text) > MAX_CHUNK_SIZE else chunk_text
                            if len(chunk_text) > MAX_CHUNK_SIZE:
                                logger.warning(f"[Celery] ⚠️ Chunk {actual_index + 1} слишком большой ({len(chunk_text)} символов), обрезаем до {MAX_CHUNK_SIZE}")
                            
                            chunk = DocumentChunk(
                                document_id=document_id,
                                chunk_text=chunk_text_to_save,
                                chunk_index=actual_index
                            )
                            db.add(chunk)
                            await db.flush()  # Получаем ID чанка
                            
                            # Добавляем в батч для Qdrant (как в рабочем скрипте)
                            from qdrant_client.models import PointStruct
                            import hashlib
                            
                            # Генерируем уникальный ID (как в рабочем скрипте)
                            chunk_hash = hashlib.md5(chunk_text.encode()).hexdigest()
                            point_id = abs(hash(f"{document_id}_{actual_index}_{chunk_hash}")) % (10 ** 10)
                            
                            batch_points.append(PointStruct(
                                id=point_id,
                                vector=embedding,
                                payload={
                                    "document_id": str(document_id),
                                    "chunk_id": str(chunk.id),
                                    "chunk_index": actual_index,
                                    "filename": filename,
                                    "chunk_text": chunk_text[:500],  # Ограничиваем для Qdrant
                                    "text": chunk_text[:500]  # Дублируем для совместимости
                                }
                            ))
                            batch_chunks.append((chunk, point_id))
                            successful_chunks += 1
                            
                        except Exception as chunk_error:
                            logger.error(f"[Celery] ❌ Ошибка обработки чанка {actual_index + 1}: {chunk_error}")
                            failed_chunks += 1
                            continue
                    
                    # Сохраняем батч в Qdrant когда накопилось достаточно или это последний батч
                    if len(batch_points) >= QDRANT_BATCH_SIZE or batch_start + EMBEDDING_BATCH_SIZE >= len(chunks):
                            try:
                                # Batch upsert в Qdrant (как в рабочем скрипте)
                                collection_name = f"project_{project_id}"
                                logger.info(f"[Celery] 💾 Сохранение батча из {len(batch_points)} чанков в Qdrant (коллекция: {collection_name})")
                                await vector_store.ensure_collection(collection_name, len(embedding))
                                vector_store.client.upsert(
                                    collection_name=collection_name,
                                    points=batch_points
                                )
                                
                                # Обновляем qdrant_point_id для всех чанков в батче
                                for batch_chunk, batch_point_id in batch_chunks:
                                    batch_chunk.qdrant_point_id = batch_point_id
                                await db.flush()
                                
                                progress_pct = ((batch_start + len(batch_chunk_texts)) / len(chunks)) * 100
                                logger.info(f"[Celery] ✅ Батч из {len(batch_points)} чанков сохранен в Qdrant (прогресс: {batch_start + len(batch_chunk_texts)}/{len(chunks)} = {progress_pct:.1f}%)")
                            except Exception as e:
                                logger.error(f"[Celery] ❌ Ошибка batch upsert в Qdrant: {e}", exc_info=True)
                                # Пробуем сохранить по одному как fallback
                                for batch_chunk, batch_point_id in batch_chunks:
                                    try:
                                        point_data = next((p for p in batch_points if str(p.id) == str(batch_point_id)), None)
                                        if point_data:
                                            await vector_store.store_vector(
                                                collection_name=f"project_{project_id}",
                                                vector=point_data.vector,
                                                payload=point_data.payload
                                            )
                                            batch_chunk.qdrant_point_id = batch_point_id
                                            successful_chunks += 1
                                            failed_chunks -= 1
                                    except Exception as fallback_error:
                                        logger.error(f"[Celery] ❌ Fallback сохранение чанка {batch_chunk.chunk_index} тоже не удалось: {fallback_error}")
                            
                            # Очищаем батч
                            batch_points = []
                            batch_chunks = []
                            
                except Exception as batch_error:
                    logger.error(f"[Celery] ❌ Ошибка обработки батча {batch_start // EMBEDDING_BATCH_SIZE + 1}: {batch_error}", exc_info=True)
                    failed_chunks += len(batch_chunk_texts)
                    continue
                
                # Логируем прогресс и освобождаем память
                chunk_memory_after = process.memory_info().rss / 1024 / 1024
                progress_pct = ((batch_start + len(batch_chunk_texts)) / len(chunks)) * 100
                logger.info(f"[Celery] 📊 Прогресс: {batch_start + len(batch_chunk_texts)}/{len(chunks)} чанков ({progress_pct:.1f}%), память: {chunk_memory_after:.2f}MB, успешно: {successful_chunks}, ошибок: {failed_chunks}")
                
                # Освобождаем память после каждого батча
                gc.collect()
            
            embedding_end_memory = process.memory_info().rss / 1024 / 1024
            logger.info(f"[Celery] ✅ Обработка чанков завершена:")
            logger.info(f"[Celery]   - Всего чанков: {len(chunks)}")
            logger.info(f"[Celery]   - Успешно обработано: {successful_chunks}")
            logger.info(f"[Celery]   - Ошибок: {failed_chunks}")
            logger.info(f"[Celery]   - Память после обработки: {embedding_end_memory:.2f}MB (delta: {embedding_end_memory - embedding_start_memory:.2f}MB)")
            
            # Коммитим все чанки
            await db.commit()
            
            # Проверяем финальное состояние документа
            logger.info(f"[Celery] 🔍 Финальная проверка состояния документа {document_id}...")
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if document:
                content_length = len(document.content) if document.content else 0
                content_value = document.content if document.content else "EMPTY"
                is_processing = content_value in ["Обработка...", "Обработан", ""] or content_length < 100
                
                logger.info(f"[Celery] ✅ Document {document_id} processed successfully:")
                logger.info(f"  - Filename: {filename}")
                logger.info(f"  - Chunks created: {len(chunks)}")
                logger.info(f"  - Content length: {content_length} chars")
                logger.info(f"  - Content status: {'READY' if not is_processing else 'NOT_READY'}")
                logger.info(f"  - Content is 'Обработка...': {content_value == 'Обработка...'}")
                logger.info(f"  - Content is empty: {not content_value or content_value == ''}")
                logger.info(f"  - Content preview (первые 200 символов): {content_value[:200] if content_value and len(content_value) > 200 else content_value}...")
                
                if is_processing:
                    logger.error(f"[Celery] ❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Документ все еще в статусе обработки после завершения задачи!")
                    logger.error(f"[Celery] ❌ Это означает, что контент не был сохранен или был перезаписан")
                    logger.error(f"[Celery] ❌ Значение content: '{content_value}'")
                    logger.error(f"[Celery] ❌ Длина: {content_length} символов")
                else:
                    logger.info(f"[Celery] ✅ Документ готов для RAG - контент сохранен и доступен")
                    
                if document.content and content_length > 0 and not is_processing:
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


@celery_app.task(bind=True, name='app.tasks.document_tasks.process_large_document_with_langgraph')
def process_large_document_with_langgraph(
    self, 
    document_id: str, 
    project_id: str, 
    file_path: str, 
    filename: str, 
    file_type: str
):
    """
    Celery задача для обработки большого документа с использованием LangGraph
    Оптимизировано для PDF >100 страниц
    """
    import asyncio
    import psutil
    
    process = psutil.Process(os.getpid())
    start_memory = process.memory_info().rss / 1024 / 1024
    logger.info(f"[Celery LangGraph] Starting processing document {document_id} ({filename}), memory: {start_memory:.2f}MB")
    
    file_content = None
    try:
        # Проверяем размер файла
        if not os.path.exists(file_path):
            logger.error(f"[Celery LangGraph] File not found: {file_path}")
            return {"status": "error", "message": f"File not found: {file_path}"}
        
        file_size = os.path.getsize(file_path) / 1024 / 1024
        logger.info(f"[Celery LangGraph] Reading file {file_path}, size: {file_size:.2f}MB")
        
        # Читаем файл
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Удаляем временный файл
        try:
            os.unlink(file_path)
            logger.info(f"[Celery LangGraph] Temp file deleted: {file_path}")
        except Exception as e:
            logger.warning(f"[Celery LangGraph] Не удалось удалить временный файл {file_path}: {e}")
        
        # Запускаем обработку
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                process_large_document_async_langgraph(
                    UUID(document_id),
                    UUID(project_id),
                    file_content,
                    filename,
                    file_type
                )
            )
            logger.info(f"[Celery LangGraph] Document {document_id} processed successfully")
            return {"status": "success", "document_id": document_id}
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"[Celery LangGraph] Error processing document {document_id}: {e}", exc_info=True)
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except:
                pass
        return {"status": "error", "message": str(e)}
    finally:
        if file_content is not None:
            del file_content
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        logger.info(f"[Celery LangGraph] Processing complete, final memory: {final_memory:.2f}MB")


async def process_large_document_async_langgraph(
    document_id: UUID, 
    project_id: UUID, 
    file_content: bytes, 
    filename: str, 
    file_type: str
):
    """
    Асинхронная обработка большого документа с LangGraph
    Использует иерархическое разбиение для больших PDF
    """
    import gc
    import psutil
    
    process = psutil.Process(os.getpid())
    
    async with AsyncSessionLocal() as db:
        from app.documents.parser import DocumentParser
        from app.documents.advanced_chunker import AdvancedChunker
        from app.models.document import Document, DocumentChunk
        from sqlalchemy import select
        
        # Получаем документ
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            logger.error(f"[Celery LangGraph] Document {document_id} not found")
            return
        
        # Парсинг документа
        parser = DocumentParser()
        try:
            text = await parser.parse(file_content, file_type)
        except Exception as e:
            logger.error(f"[Celery LangGraph] Ошибка парсинга: {e}")
            document.content = f"Ошибка обработки: {str(e)[:200]}"
            await db.commit()
            return
        
        # Определяем размер документа
        is_large_document = len(text) > LARGE_DOCUMENT_THRESHOLD
        is_very_large_document = len(text) > VERY_LARGE_DOCUMENT_THRESHOLD
        logger.info(f"[Celery LangGraph] Document size: {len(text)} chars, is_large: {is_large_document}, is_very_large: {is_very_large_document}")
        
        # Сохраняем контент
        MAX_CONTENT_SIZE = 2_000_000
        if len(text) > MAX_CONTENT_SIZE:
            document.content = text[:MAX_CONTENT_SIZE] + f"\n\n[... документ обрезан, всего {len(text)} символов ...]"
        else:
            document.content = text
        
        await db.commit()
        await db.refresh(document)
        logger.info(f"[Celery LangGraph] ✅ Document content saved: {len(document.content)} chars")
        
        # Используем advanced chunker с правильными параметрами (1000/200 для обычных, больше для больших)
        advanced_chunker = AdvancedChunker(
            default_chunk_size=1500 if is_large_document else 1000,  # Правильный размер из рабочего скрипта
            default_overlap=300 if is_large_document else 200,  # Правильное перекрытие из рабочего скрипта
            min_chunk_size=100,
            max_chunk_size=3000 if is_large_document else 2000
        )
        
        if is_large_document:
            # Для больших документов используем иерархическое разбиение
            chunk_result = await advanced_chunker.chunk_large_document(
                text=text,
                file_type=file_type,
                file_content=file_content if file_type == "pdf" else None,
                filename=filename,
                use_hierarchical=True
            )
            chunks = [c['text'] for c in chunk_result.get('chunks', [])]
            sections = chunk_result.get('sections', [])
            logger.info(f"[Celery LangGraph] Hierarchical chunking: {len(chunks)} chunks, {len(sections)} sections")
        else:
            # Для обычных документов используем стандартный chunking
            chunks = await advanced_chunker.chunk_document(
                text=text,
                file_type=file_type,
                file_content=file_content if file_type == "pdf" else None,
                filename=filename
            )
        
        if not chunks:
            logger.warning(f"[Celery LangGraph] No chunks generated for document {document_id}")
            return
        
        logger.info(f"[Celery LangGraph] Document split into {len(chunks)} chunks")
        
        # Создание эмбеддингов и сохранение в Qdrant
        from app.services.embedding_service import EmbeddingService
        from app.vector_db.vector_store import VectorStore
        from qdrant_client.models import PointStruct
        
        embedding_service = EmbeddingService()
        vector_store = VectorStore()
        
        # Определяем размер батча в зависимости от размера документа
        if is_very_large_document:
            batch_size = MAX_BATCH_SIZE_VERY_LARGE
            logger.info(f"[Celery LangGraph] Используем очень маленький батч ({batch_size}) для быстрой индексации")
        elif is_large_document:
            batch_size = MAX_BATCH_SIZE_LARGE
        else:
            batch_size = MAX_BATCH_SIZE_NORMAL
        
        batch_points = []
        batch_chunks = []
        
        for chunk_index, chunk_text in enumerate(chunks):
            try:
                chunk_memory_before = process.memory_info().rss / 1024 / 1024
                
                # Создаем эмбеддинг
                try:
                    embedding = await embedding_service.create_embedding(chunk_text)
                except Exception as e:
                    logger.error(f"[Celery LangGraph] Ошибка создания эмбеддинга для чанка {chunk_index}: {e}")
                    continue
                
                # Сохраняем чанк в БД
                MAX_CHUNK_SIZE = 10_000
                chunk_text_to_save = chunk_text[:MAX_CHUNK_SIZE] if len(chunk_text) > MAX_CHUNK_SIZE else chunk_text
                
                chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_text=chunk_text_to_save,
                    chunk_index=chunk_index
                )
                db.add(chunk)
                await db.flush()
                
                # Добавляем в батч для Qdrant
                point_id = chunk.id
                batch_points.append(PointStruct(
                    id=str(point_id),
                    vector=embedding,
                    payload={
                        "document_id": str(document_id),
                        "chunk_id": str(chunk.id),
                        "chunk_index": chunk_index,
                        "filename": filename,
                        "chunk_text": chunk_text[:500]
                    }
                ))
                batch_chunks.append((chunk, point_id))
                
                # Сохраняем батч
                if len(batch_points) >= batch_size or chunk_index == len(chunks) - 1:
                    try:
                        collection_name = f"project_{project_id}"
                        await vector_store.ensure_collection(collection_name, len(embedding))
                        vector_store.client.upsert(
                            collection_name=collection_name,
                            points=batch_points
                        )
                        
                        for batch_chunk, batch_point_id in batch_chunks:
                            batch_chunk.qdrant_point_id = batch_point_id
                        await db.flush()
                        
                        logger.info(f"[Celery LangGraph] ✅ Batch upserted {len(batch_points)} chunks (up to {chunk_index})")
                    except Exception as e:
                        logger.error(f"[Celery LangGraph] Ошибка batch upsert в Qdrant: {e}")
                    
                    batch_points = []
                    batch_chunks = []
                
                # Логируем прогресс (чаще для очень больших документов)
                log_interval = 10 if is_very_large_document else 20
                if chunk_index % log_interval == 0:
                    chunk_memory_after = process.memory_info().rss / 1024 / 1024
                    progress_pct = (chunk_index + 1) / len(chunks) * 100
                    logger.info(f"[Celery LangGraph] Processed {chunk_index + 1}/{len(chunks)} ({progress_pct:.1f}%), memory: {chunk_memory_after:.2f}MB")
                    gc.collect()
                
            except Exception as e:
                logger.error(f"[Celery LangGraph] Ошибка обработки чанка {chunk_index}: {e}", exc_info=True)
                continue
        
        # Коммитим все чанки
        await db.commit()
        
        # Генерируем summary с использованием LangGraph
        try:
            from app.services.document_summary_service import DocumentSummaryService
            summary_service = DocumentSummaryService(db)
            
            if is_large_document:
                # Для больших документов используем Map-Reduce
                summary = await summary_service.generate_map_reduce_summary(document_id)
            else:
                # Для обычных документов используем LangGraph
                summary = await summary_service.generate_summary_with_langgraph(document_id)
            
            if summary:
                logger.info(f"[Celery LangGraph] Summary generated for document {document_id}")
        except Exception as summary_error:
            logger.warning(f"[Celery LangGraph] Error generating summary: {summary_error}")
        
        logger.info(f"[Celery LangGraph] ✅ Document {document_id} processing complete: {len(chunks)} chunks")


@celery_app.task(bind=True, name='app.tasks.document_tasks.reindex_document_to_qdrant')
def reindex_document_to_qdrant(self, document_id: str, project_id: str):
    """
    Celery задача для переиндексации документа в Qdrant
    Полезно для миграции существующих документов из PostgreSQL в Qdrant
    """
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                reindex_document_async(UUID(document_id), UUID(project_id))
            )
            logger.info(f"[Celery Reindex] Document {document_id} reindexed successfully")
            return {"status": "success", "document_id": document_id}
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"[Celery Reindex] Error reindexing document {document_id}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def reindex_document_async(document_id: UUID, project_id: UUID):
    """Переиндексация документа из PostgreSQL в Qdrant"""
    async with AsyncSessionLocal() as db:
        from app.models.document import Document, DocumentChunk
        from app.services.embedding_service import EmbeddingService
        from app.vector_db.vector_store import VectorStore
        from sqlalchemy import select
        from qdrant_client.models import PointStruct
        
        # Получаем чанки из PostgreSQL
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = result.scalars().all()
        
        if not chunks:
            # Если нет чанков, пробуем создать из контента документа
            doc_result = await db.execute(select(Document).where(Document.id == document_id))
            document = doc_result.scalar_one_or_none()
            
            if document and document.content:
                from app.documents.chunker import DocumentChunker
                # Используем правильные параметры chunking (1000/200)
                chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
                text_chunks = chunker.chunk_text(document.content)
                
                chunks = []
                for i, text in enumerate(text_chunks):
                    chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_text=text,
                        chunk_index=i
                    )
                    db.add(chunk)
                    await db.flush()
                    chunks.append(chunk)
                
                await db.commit()
                logger.info(f"[Reindex] Created {len(chunks)} chunks from document content")
        
        if not chunks:
            logger.warning(f"[Reindex] No chunks found for document {document_id}")
            return
        
        embedding_service = EmbeddingService()
        vector_store = VectorStore()
        collection_name = f"project_{project_id}"
        
        batch_points = []
        
        for chunk in chunks:
            try:
                embedding = await embedding_service.create_embedding(chunk.chunk_text)
                
                batch_points.append(PointStruct(
                    id=str(chunk.id),
                    vector=embedding,
                    payload={
                        "document_id": str(document_id),
                        "chunk_id": str(chunk.id),
                        "chunk_index": chunk.chunk_index,
                        "chunk_text": chunk.chunk_text[:500]
                    }
                ))
                
                # Сохраняем батчами
                if len(batch_points) >= 20:
                    await vector_store.ensure_collection(collection_name, len(embedding))
                    vector_store.client.upsert(
                        collection_name=collection_name,
                        points=batch_points
                    )
                    logger.info(f"[Reindex] Upserted batch of {len(batch_points)} points")
                    batch_points = []
                    
            except Exception as e:
                logger.error(f"[Reindex] Error processing chunk {chunk.id}: {e}")
                continue
        
        # Сохраняем оставшиеся точки
        if batch_points:
            await vector_store.ensure_collection(collection_name, len(embedding))
            vector_store.client.upsert(
                collection_name=collection_name,
                points=batch_points
            )
            logger.info(f"[Reindex] Upserted final batch of {len(batch_points)} points")
        
        logger.info(f"[Reindex] Document {document_id} reindexed: {len(chunks)} chunks")

