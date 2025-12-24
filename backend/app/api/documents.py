"""
Роутер для управления документами
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
import logging

from app.core.database import get_db, AsyncSessionLocal
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from app.api.dependencies import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter()


async def process_document_async_from_file(document_id: UUID, project_id: UUID, file_path: str, filename: str, file_type: str):
    """
    Асинхронная обработка документа из файла (парсинг, эмбеддинги, сохранение в Qdrant)
    Использует путь к файлу вместо содержимого в памяти для экономии памяти
    """
    import os
    import gc
    import psutil
    
    process = psutil.Process(os.getpid())
    start_memory = process.memory_info().rss / 1024 / 1024
    logger.info(f"[Process] Starting processing document {document_id} ({filename}), memory: {start_memory:.2f}MB")
    
    file_content = None
    try:
        # Проверяем размер файла
        file_size = os.path.getsize(file_path) / 1024 / 1024
        logger.info(f"[Process] Reading file {file_path}, size: {file_size:.2f}MB")
        
        # Читаем файл асинхронно в отдельном потоке, чтобы не блокировать event loop
        def read_file_sync(path):
            with open(path, 'rb') as f:
                return f.read()
        
        import asyncio
        loop = asyncio.get_event_loop()
        file_content = await loop.run_in_executor(None, read_file_sync, file_path)
        
        read_memory = process.memory_info().rss / 1024 / 1024
        logger.info(f"[Process] File read into memory, memory: {read_memory:.2f}MB (delta: {read_memory - start_memory:.2f}MB)")
        
        # Удаляем временный файл сразу после чтения (освобождаем диск)
        try:
            os.unlink(file_path)
            logger.info(f"[Process] Temp file deleted: {file_path}")
        except Exception as e:
            logger.warning(f"[Process] Не удалось удалить временный файл {file_path}: {e}")
        
        # Вызываем основную функцию обработки
        # Добавляем небольшую задержку, чтобы дать время основному запросу завершиться
        await asyncio.sleep(0.1)
        await process_document_async(document_id, project_id, file_content, filename, file_type)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке файла {file_path}: {e}", exc_info=True)
        # Удаляем временный файл в случае ошибки
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except:
                pass
    finally:
        # Освобождаем память
        if file_content is not None:
            del file_content
        gc.collect()


async def process_document_async(document_id: UUID, project_id: UUID, file_content: bytes, filename: str, file_type: str):
    """Асинхронная обработка документа (парсинг, эмбеддинги, сохранение в Qdrant)"""
    import asyncio
    import gc  # Для принудительной очистки памяти
    import os
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
            
            # Парсинг документа (неблокирующий, выполняется в thread pool для PDF/DOCX)
            # Обрабатываем ошибки парсинга, чтобы приложение не падало
            try:
                text = await parser.parse(file_content, file_type)
            except Exception as e:
                logger.error(f"Ошибка парсинга документа {document_id} ({filename}): {e}")
                # Обновляем статус документа на ошибку
                result = await db.execute(select(Document).where(Document.id == document_id))
                document = result.scalar_one_or_none()
                if document:
                    document.content = f"Ошибка обработки: {str(e)[:200]}"
                    await db.commit()
                return  # Прерываем обработку, но не падаем
            
            # Получаем документ и обновляем его content
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            
            if not document:
                logger.error(f"Документ {document_id} не найден для обработки")
                return
            
            # Обновляем content в документе - сохраняем только первые 500 символов для экономии памяти
            # Это критично для предотвращения out of memory
            document.content = text[:500] + "..." if len(text) > 500 else text
            await db.commit()
            await db.refresh(document)
            
            # Освобождаем file_content сразу после парсинга
            if 'file_content' in locals():
                del file_content
            gc.collect()
            
            parse_memory = process.memory_info().rss / 1024 / 1024
            logger.info(f"[Process] After parse, memory: {parse_memory:.2f}MB, text_length: {len(text)} chars")
            
            # Разбивка на чанки (быстрая операция строк, не блокирует)
            chunks = chunker.chunk_text(text)
            
            # Освобождаем text сразу после разбивки на чанки
            del text
            gc.collect()
            
            if not chunks:
                logger.warning(f"Документ {document_id} не содержит текста")
                return
            
            logger.info(f"[Process] Document split into {len(chunks)} chunks")
            
            # Создание эмбеддингов по одному для минимального использования памяти
            from app.services.embedding_service import EmbeddingService
            from app.vector_db.vector_store import VectorStore
            from app.models.document import DocumentChunk
            
            embedding_service = EmbeddingService()
            vector_store = VectorStore()
            
            # Обрабатываем чанки по одному для минимального использования памяти
            # Это медленнее, но предотвращает out of memory
            
            # Обрабатываем чанки по одному для минимального использования памяти
            for chunk_index, chunk_text in enumerate(chunks):
                try:
                    chunk_memory_before = process.memory_info().rss / 1024 / 1024
                    
                    # Создаем эмбеддинг для одного чанка
                    try:
                        embedding = await embedding_service.create_embedding(chunk_text)
                    except Exception as e:
                        logger.error(f"Ошибка создания эмбеддинга для чанка {chunk_index}: {e}")
                        # Пропускаем этот чанк, но продолжаем обработку
                        continue
                    
                    # Сохранение чанка в БД - сохраняем только первые 1000 символов для экономии памяти
                    chunk = DocumentChunk(
                        document_id=document.id,
                        chunk_text=chunk_text[:1000] if len(chunk_text) > 1000 else chunk_text,
                        chunk_index=chunk_index
                    )
                    db.add(chunk)
                    await db.flush()
                    
                    # Сохранение вектора в Qdrant
                    try:
                        point_id = await vector_store.store_vector(
                            collection_name=f"project_{project_id}",
                            vector=embedding,
                            payload={
                                "document_id": str(document.id),
                                "chunk_id": str(chunk.id),
                                "chunk_index": chunk_index,
                                "chunk_text": chunk_text[:500]  # Сохраняем только первые 500 символов в payload
                            }
                        )
                        chunk.qdrant_point_id = point_id
                    except Exception as e:
                        logger.error(f"Ошибка сохранения вектора в Qdrant для чанка {chunk_index}: {e}")
                        # Продолжаем обработку, даже если Qdrant недоступен
                    
                    await db.commit()
                    
                    # Освобождаем память после каждого чанка
                    del embedding
                    del chunk_text
                    gc.collect()
                    
                    chunk_memory_after = process.memory_info().rss / 1024 / 1024
                    
                    # Логируем каждые 10 чанков
                    if (chunk_index + 1) % 10 == 0:
                        logger.info(f"[Process] Processed {chunk_index + 1}/{len(chunks)} chunks, memory: {chunk_memory_after:.2f}MB")
                    
                    # Пауза каждые 5 чанков для освобождения памяти
                    if (chunk_index + 1) % 5 == 0:
                        await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"[Process] Ошибка при обработке чанка {chunk_index}: {e}")
                    # Пробуем откатить транзакцию и продолжить
                    try:
                        await db.rollback()
                    except:
                        pass
                    # Продолжаем обработку следующих чанков
                    continue
            
            final_memory = process.memory_info().rss / 1024 / 1024
            logger.info(f"[Process] Документ {document_id} ({filename}) успешно обработан: {len(chunks)} чанков, final memory: {final_memory:.2f}MB")
            
            # Обновляем статус документа на успешную обработку
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if document and document.content == "Обработка...":
                # Обновляем только если еще placeholder
                document.content = text[:1000] + "..." if len(text) > 1000 else text
                await db.commit()
                
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке документа {document_id}: {e}", exc_info=True)
        # Пробуем обновить статус документа на ошибку
        try:
            from sqlalchemy import select
            from app.models.document import Document
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Document).where(Document.id == document_id))
                document = result.scalar_one_or_none()
                if document:
                    document.content = f"Ошибка обработки: {str(e)[:200]}"
                    await db.commit()
        except Exception as e2:
            logger.error(f"Не удалось обновить статус документа после ошибки: {e2}")
    finally:
        # Освобождаем память после обработки
        # file_content уже удален после парсинга
        if 'text' in locals():
            del text
        if 'chunks' in locals():
            del chunks
        gc.collect()


@router.post("/{project_id}/upload", response_model=List[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def upload_documents(
    project_id: UUID,
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Загрузить документы в проект"""
    import psutil
    import os
    from app.core.config import settings
    
    # Максимальный размер файла: 50MB (можно настроить через переменную окружения)
    MAX_FILE_SIZE = getattr(settings, 'MAX_DOCUMENT_SIZE', 50 * 1024 * 1024)  # 50MB по умолчанию
    
    # Логируем начальное состояние памяти
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    logger.info(f"[Upload] Starting upload for project {project_id}, files: {len(files)}, initial memory: {initial_memory:.2f}MB")
    
    service = DocumentService(db)
    
    documents = []
    for file_index, file in enumerate(files):
        logger.info(f"[Upload] Processing file {file_index + 1}/{len(files)}: {file.filename}")
        # Валидация формата файла (PDF, Excel, Word, TXT)
        if not file.filename.endswith(('.txt', '.docx', '.pdf', '.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый формат файла: {file.filename}. Поддерживаются: PDF, Excel (.xlsx, .xls), Word (.docx), TXT"
            )
        
        # Проверяем размер файла перед чтением
        # Получаем размер из заголовка Content-Length, если доступен
        file_size = 0
        if hasattr(file, 'size') and file.size:
            file_size = file.size
        elif hasattr(file, 'headers') and 'content-length' in file.headers:
            try:
                file_size = int(file.headers['content-length'])
            except (ValueError, TypeError):
                pass
        
        file_type = file.filename.split('.')[-1].lower()
        
        # Логируем размер файла
        file_size_mb = 0
        if hasattr(file, 'size') and file.size:
            file_size_mb = file.size / 1024 / 1024
        logger.info(f"[Upload] File {file.filename}: type={file_type}, size={file_size_mb:.2f}MB")
        
        # Читаем файл по частям для проверки размера (streaming)
        import tempfile
        import shutil
        
        # Создаем временный файл для хранения содержимого
        # Это позволяет не держать весь файл в памяти
        temp_file = None
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_type}') as temp_file:
                temp_path = temp_file.name
                total_size = 0
                chunk_count = 0
                
                logger.info(f"[Upload] Writing file to temp: {temp_path}")
                
                # Читаем файл по частям и записываем во временный файл
                while True:
                    chunk = await file.read(8192)  # Читаем по 8KB
                    if not chunk:
                        break
                    total_size += len(chunk)
                    chunk_count += 1
                    
                    # Проверяем размер во время чтения
                    if total_size > MAX_FILE_SIZE:
                        os.unlink(temp_path)
                        logger.error(f"[Upload] File {file.filename} too large: {total_size / 1024 / 1024:.2f}MB")
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Файл {file.filename} слишком большой ({total_size / 1024 / 1024:.2f}MB). Максимальный размер: {MAX_FILE_SIZE / 1024 / 1024:.2f}MB"
                        )
                    
                    temp_file.write(chunk)
                
                temp_file.flush()
                temp_file.close()
                
                logger.info(f"[Upload] File written to temp: {total_size / 1024 / 1024:.2f}MB, {chunk_count} chunks")
                
                # Проверяем память после записи
                current_memory = process.memory_info().rss / 1024 / 1024
                logger.info(f"[Upload] Memory after writing file: {current_memory:.2f}MB (delta: {current_memory - initial_memory:.2f}MB)")
            
            # Создаем документ в БД сразу (временно с placeholder content)
            from app.models.document import Document
            document = Document(
                project_id=project_id,
                filename=file.filename,
                content="Обработка...",  # Временный placeholder
                file_type=file_type
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)
            
            documents.append(document)
            
            # Запускаем обработку через Celery в отдельном воркере
            # Это предотвращает out of memory, так как обработка происходит в отдельном процессе
            from app.tasks.document_tasks import process_document_task
            logger.info(f"[Upload] Scheduling Celery task for document {document.id}, temp_file: {temp_path}")
            
            # Отправляем задачу в Celery очередь
            # Задача будет выполнена в отдельном воркере, не блокируя основной процесс
            task_result = process_document_task.delay(
                str(document.id),
                str(project_id),
                temp_path,
                file.filename,
                file_type
            )
            logger.info(f"[Upload] Celery task created: {task_result.id} for document {document.id}")
        except HTTPException:
            # Если ошибка размера, удаляем временный файл если был создан
            if temp_file and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            raise
        except Exception as e:
            # Если другая ошибка, удаляем временный файл
            if temp_file and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при загрузке файла: {str(e)}"
            )
    
    # Логируем финальное состояние памяти
    final_memory = process.memory_info().rss / 1024 / 1024
    logger.info(f"[Upload] Upload complete: {len(documents)} documents created, final memory: {final_memory:.2f}MB (delta: {final_memory - initial_memory:.2f}MB)")
    
    # Возвращаем документы сразу (обработка будет происходить в фоне)
    return documents


@router.get("/{project_id}", response_model=List[DocumentResponse])
async def get_project_documents(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить список документов проекта (оптимизировано - без загрузки chunks)"""
    from sqlalchemy.orm import noload
    from app.models.document import Document
    from sqlalchemy import select
    
    # Загружаем документы без chunks для экономии памяти
    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .options(noload(Document.chunks))
        .order_by(Document.created_at.desc())
    )
    documents = list(result.scalars().all())
    
    return documents


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Удалить документ"""
    service = DocumentService(db)
    success = await service.delete_document(document_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Документ не найден"
        )


