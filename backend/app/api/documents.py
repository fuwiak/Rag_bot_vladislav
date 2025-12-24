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


async def process_document_async(document_id: UUID, project_id: UUID, file_content: bytes, filename: str, file_type: str):
    """Асинхронная обработка документа (парсинг, эмбеддинги, сохранение в Qdrant)"""
    import asyncio
    import gc  # Для принудительной очистки памяти
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
            
            # Обновляем content в документе
            document.content = text
            await db.commit()
            await db.refresh(document)
            
            # Разбивка на чанки (быстрая операция строк, не блокирует)
            chunks = chunker.chunk_text(text)
            
            if not chunks:
                logger.warning(f"Документ {document_id} не содержит текста")
                return
            
            # Создание эмбеддингов батчами для ускорения
            from app.services.embedding_service import EmbeddingService
            from app.vector_db.vector_store import VectorStore
            from app.models.document import DocumentChunk
            
            embedding_service = EmbeddingService()
            vector_store = VectorStore()
            
            # Обрабатываем чанки батчами (меньший размер батча для больших файлов)
            # Для больших файлов используем меньший батч, чтобы не перегружать память
            total_chunks = len(chunks)
            if total_chunks > 100:
                batch_size = 5  # Меньший батч для больших документов
            else:
                batch_size = 10
            
            for batch_start in range(0, len(chunks), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks))
                batch_chunks = chunks[batch_start:batch_end]
                
                try:
                    # Создаем эмбеддинги батчем
                    try:
                        embeddings = await embedding_service.create_embeddings_batch(batch_chunks)
                    except Exception as e:
                        logger.warning(f"Ошибка создания эмбеддингов для батча {batch_start}-{batch_end}: {e}")
                        # Fallback: создаем эмбеддинги по одному
                        embeddings = []
                        for chunk in batch_chunks:
                            try:
                                emb = await embedding_service.create_embedding(chunk)
                                embeddings.append(emb)
                            except Exception as e2:
                                logger.error(f"Ошибка создания эмбеддинга для чанка: {e2}")
                                # Пропускаем этот чанк, но продолжаем обработку
                                embeddings.append(None)
                    
                    # Сохраняем каждый чанк
                    for i, (chunk_text, embedding) in enumerate(zip(batch_chunks, embeddings)):
                        if embedding is None:
                            continue
                        
                        chunk_index = batch_start + i
                        
                        try:
                            # Сохранение чанка в БД
                            chunk = DocumentChunk(
                                document_id=document.id,
                                chunk_text=chunk_text,
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
                                        "chunk_text": chunk_text
                                    }
                                )
                                chunk.qdrant_point_id = point_id
                            except Exception as e:
                                logger.error(f"Ошибка сохранения вектора в Qdrant для чанка {chunk_index}: {e}")
                                # Продолжаем обработку, даже если Qdrant недоступен
                        except Exception as e:
                            logger.error(f"Ошибка сохранения чанка {chunk_index} в БД: {e}")
                            # Продолжаем обработку следующих чанков
                            continue
                    
                    await db.commit()
                    logger.info(f"Обработано {batch_end} из {len(chunks)} чанков документа {document_id}")
                    
                except Exception as e:
                    logger.error(f"Критическая ошибка при обработке батча {batch_start}-{batch_end}: {e}")
                    # Пробуем откатить транзакцию и продолжить
                    try:
                        await db.rollback()
                    except:
                        pass
                    # Продолжаем обработку следующих батчей
                    continue
                
                # Освобождаем память после каждого батча
                del batch_chunks
                if 'embeddings' in locals():
                    del embeddings
                gc.collect()
                
                # Пауза между батчами для освобождения памяти и неблокирующей обработки
                await asyncio.sleep(0.1)
            
            logger.info(f"Документ {document_id} ({filename}) успешно обработан: {len(chunks)} чанков")
            
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
        if 'file_content' in locals():
            del file_content
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
    from app.core.config import settings
    
    # Максимальный размер файла: 50MB (можно настроить через переменную окружения)
    MAX_FILE_SIZE = getattr(settings, 'MAX_DOCUMENT_SIZE', 50 * 1024 * 1024)  # 50MB по умолчанию
    
    service = DocumentService(db)
    
    documents = []
    for file in files:
        # Валидация формата файла
        if not file.filename.endswith(('.txt', '.docx', '.pdf')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый формат файла: {file.filename}"
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
        
        # Читаем содержимое файла с ограничением размера
        file_content = await file.read()
        actual_size = len(file_content)
        
        # Проверяем размер после чтения (на случай, если Content-Length не был доступен)
        if actual_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Файл {file.filename} слишком большой ({actual_size / 1024 / 1024:.2f}MB). Максимальный размер: {MAX_FILE_SIZE / 1024 / 1024:.2f}MB"
            )
        
        file_type = file.filename.split('.')[-1].lower()
        
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
        
        # Запускаем обработку через BackgroundTasks (выполнится после отправки ответа)
        background_tasks.add_task(
            process_document_async,
            document.id, 
            project_id, 
            file_content, 
            file.filename,
            file_type
        )
    
    # Возвращаем документы сразу (обработка будет происходить в фоне)
    return documents


@router.get("/{project_id}", response_model=List[DocumentResponse])
async def get_project_documents(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить список документов проекта"""
    service = DocumentService(db)
    documents = await service.get_project_documents(project_id)
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


