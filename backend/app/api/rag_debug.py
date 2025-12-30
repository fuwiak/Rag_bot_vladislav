"""
RAG Debug API endpoints dla testowania i przeglądania traces
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID

from app.core.database import get_db
from app.api.dependencies import get_current_admin
from app.services.rag_service import RAGService
from app.observability.otel_setup import get_current_trace_id
from app.observability.metrics import rag_metrics

router = APIRouter()


class DebugQueryRequest(BaseModel):
    """Request dla debug query"""
    question: str
    user_id: UUID
    top_k: int = 5


class DebugQueryResponse(BaseModel):
    """Response dla debug query"""
    answer: str
    trace_id: Optional[str] = None
    chunks_retrieved: int
    duration: float
    metrics: Dict[str, Any]


@router.post("/debug/query", response_model=DebugQueryResponse)
async def debug_query(
    request: DebugQueryRequest,
    db = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Testuje zapytanie RAG z pełnym trace
    
    Args:
        request: Zapytanie testowe
        db: Database session
        current_admin: Admin user
    
    Returns:
        Odpowiedź z metrykami i trace ID
    """
    import time
    
    start_time = time.time()
    
    try:
        rag_service = RAGService(db)
        answer = await rag_service.generate_answer(
            user_id=request.user_id,
            question=request.question,
            top_k=request.top_k
        )
        
        duration = time.time() - start_time
        trace_id = get_current_trace_id()
        
        return DebugQueryResponse(
            answer=answer,
            trace_id=trace_id,
            chunks_retrieved=request.top_k,  # Można ulepszyć pobierając rzeczywistą liczbę
            duration=duration,
            metrics={
                "duration": duration,
                "top_k": request.top_k
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/trace/{trace_id}")
async def get_trace(
    trace_id: str,
    current_admin = Depends(get_current_admin)
):
    """
    Pobiera informacje o trace (wymaga integracji z Jaeger/Zipkin)
    
    Args:
        trace_id: ID trace
        current_admin: Admin user
    
    Returns:
        Informacje o trace
    """
    # W produkcji można zintegrować z Jaeger API
    return {
        "trace_id": trace_id,
        "message": "Trace visualization requires Jaeger/Zipkin integration",
        "jaeger_url": f"http://localhost:16686/trace/{trace_id}"  # Przykładowy URL
    }


@router.get("/debug/metrics")
async def get_debug_metrics(
    current_admin = Depends(get_current_admin)
):
    """
    Zwraca metryki w czasie rzeczywistym
    
    Args:
        current_admin: Admin user
    
    Returns:
        Metryki RAG
    """
    from prometheus_client import generate_latest, REGISTRY
    
    try:
        metrics_data = generate_latest(REGISTRY)
        return {
            "metrics": metrics_data.decode('utf-8'),
            "format": "prometheus"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/cache/stats")
async def get_cache_stats(
    current_admin = Depends(get_current_admin)
):
    """
    Zwraca statystyki cache
    
    Args:
        current_admin: Admin user
    
    Returns:
        Statystyki cache
    """
    from app.services.cache_service import cache_service
    
    try:
        stats = await cache_service.get_cache_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DiagnosticsRequest(BaseModel):
    """Request dla diagnostyki RAG"""
    project_id: UUID
    user_id: UUID
    question: str


class DiagnosticsStep(BaseModel):
    """Jeden krok diagnostyki"""
    step: str
    status: str  # pending, running, success, error
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str


class DiagnosticsResponse(BaseModel):
    """Response dla diagnostyki RAG"""
    question: str
    project_id: str
    user_id: str
    steps: List[DiagnosticsStep]
    final_answer: Optional[str] = None
    execution_time: Optional[float] = None


@router.post("/diagnostics", response_model=DiagnosticsResponse)
async def run_rag_diagnostics(
    request: DiagnosticsRequest,
    db = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Запускает полную диагностику RAG с детальным отслеживанием каждого шага
    
    Args:
        request: Запрос на диагностику
        db: Database session
        current_admin: Admin user
    
    Returns:
        Детальная информация о каждом шаге обработки
    """
    import time
    from datetime import datetime
    
    start_time = time.time()
    steps: List[DiagnosticsStep] = []
    
    def add_step(step_name: str, status: str, data: Any = None, error: str = None):
        steps.append(DiagnosticsStep(
            step=step_name,
            status=status,
            data=data if data else None,
            error=error,
            timestamp=datetime.now().isoformat()
        ))
    
    try:
        rag_service = RAGService(db)
        
        # Шаг 1: Проверка пользователя и проекта
        add_step("Проверка пользователя и проекта", "running")
        from app.models.user import User
        from app.models.project import Project
        from sqlalchemy import select
        
        user_result = await db.execute(select(User).where(User.id == request.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            add_step("Проверка пользователя и проекта", "error", error="Пользователь не найден")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        project_result = await db.execute(select(Project).where(Project.id == request.project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            add_step("Проверка пользователя и проекта", "error", error="Проект не найден")
            raise HTTPException(status_code=404, detail="Проект не найден")
        
        add_step("Проверка пользователя и проекта", "success", {
            "user_id": str(user.id),
            "project_id": str(project.id),
            "project_name": project.name
        })
        
        # Шаг 2: Проверка документов
        add_step("Проверка документов в проекте", "running")
        from app.models.document import Document
        from sqlalchemy import func
        
        docs_count_result = await db.execute(
            select(func.count(Document.id)).where(Document.project_id == project.id)
        )
        documents_count = docs_count_result.scalar() or 0
        add_step("Проверка документов в проекте", "success", {
            "documents_count": documents_count
        })
        
        # Шаг 3: Проверка Qdrant коллекции
        add_step("Проверка Qdrant коллекции", "running")
        collection_name = f"project_{project.id}"
        collection_exists = await rag_service.vector_store.collection_exists(collection_name)
        add_step("Проверка Qdrant коллекции", "success" if collection_exists else "error", {
            "collection_name": collection_name,
            "exists": collection_exists
        }, error=None if collection_exists else "Коллекция не существует")
        
        # Шаг 4: Проверка chunks
        add_step("Проверка chunks в базе данных", "running")
        from app.models.document import DocumentChunk
        
        chunks_result = await db.execute(
            select(func.count(DocumentChunk.id))
            .join(Document)
            .where(Document.project_id == project.id)
        )
        total_chunks = chunks_result.scalar() or 0
        
        processed_chunks_result = await db.execute(
            select(func.count(DocumentChunk.id))
            .join(Document)
            .where(Document.project_id == project.id)
            .where(DocumentChunk.qdrant_point_id.isnot(None))
        )
        processed_chunks = processed_chunks_result.scalar() or 0
        
        add_step("Проверка chunks в базе данных", "success", {
            "total_chunks": total_chunks,
            "processed_chunks": processed_chunks
        })
        
        # Шаг 5: Создание embedding для вопроса
        if collection_exists:
            add_step("Создание embedding для вопроса", "running")
            from app.services.embedding_service import EmbeddingService
            
            embedding_service = EmbeddingService(use_local=True)
            question_embedding = await embedding_service.create_embedding(request.question)
            add_step("Создание embedding для вопроса", "success", {
                "embedding_dimension": len(question_embedding),
                "use_local": True
            })
            
            # Шаг 6: Поиск в Qdrant
            add_step("Поиск похожих chunks в Qdrant", "running")
            similar_chunks = await rag_service.vector_store.search_similar(
                collection_name=collection_name,
                query_vector=question_embedding,
                limit=5,
                score_threshold=0.0
            )
            add_step("Поиск похожих chunks в Qdrant", "success", {
                "chunks_found": len(similar_chunks),
                "chunks": [
                    {
                        "score": chunk.get("score", 0.0),
                        "source": chunk.get("payload", {}).get("source", "Unknown"),
                        "chunk_preview": chunk.get("payload", {}).get("chunk_text", "")[:100] + "..."
                    }
                    for chunk in similar_chunks[:3]
                ]
            })
        
        # Шаг 7: Генерация ответа
        add_step("Генерация ответа через RAG", "running")
        answer = await rag_service.generate_answer_simple(
            user_id=request.user_id,
            question=request.question,
            top_k=5,
            use_local_embeddings=True
        )
        add_step("Генерация ответа через RAG", "success", {
            "answer_length": len(answer),
            "answer_preview": answer[:200] + "..." if len(answer) > 200 else answer
        })
        
        execution_time = time.time() - start_time
        
        return DiagnosticsResponse(
            question=request.question,
            project_id=str(request.project_id),
            user_id=str(request.user_id),
            steps=steps,
            final_answer=answer,
            execution_time=execution_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        add_step("Ошибка выполнения", "error", error=str(e))
        execution_time = time.time() - start_time
        return DiagnosticsResponse(
            question=request.question,
            project_id=str(request.project_id),
            user_id=str(request.user_id),
            steps=steps,
            execution_time=execution_time
        )


class CollectionActionRequest(BaseModel):
    """Request для действий с коллекцией"""
    project_id: UUID
    action: str  # "create" или "delete"


@router.post("/collections/{action}")
async def manage_collection(
    action: str,
    request: CollectionActionRequest,
    db = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Создать или удалить коллекцию Qdrant для проекта
    
    Args:
        action: "create" или "delete"
        request: Запрос с project_id
        db: Database session
        current_admin: Admin user
    
    Returns:
        Информация о выполненном действии
    """
    from app.vector_db.collections_manager import CollectionsManager
    from app.vector_db.vector_store import VectorStore
    from app.core.config import settings
    
    collection_name = f"project_{request.project_id}"
    
    try:
        if action == "create":
            # Создаем коллекцию
            vector_store = VectorStore()
            created = await vector_store.ensure_collection(
                collection_name=collection_name,
                vector_size=settings.EMBEDDING_DIMENSION
            )
            
            if created:
                return {
                    "message": "Collection created successfully",
                    "collection_name": collection_name,
                    "vector_size": settings.EMBEDDING_DIMENSION,
                    "action": "create"
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create collection (may already exist)"
                )
        
        elif action == "delete":
            # Удаляем коллекцию
            collections_manager = CollectionsManager()
            await collections_manager.delete_collection(str(request.project_id))
            
            return {
                "message": "Collection deleted successfully",
                "collection_name": collection_name,
                "action": "delete"
            }
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}. Use 'create' or 'delete'"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error managing collection: {str(e)}"
        )


class ReprocessDocumentsRequest(BaseModel):
    """Request для переобработки всех документов проекта"""
    project_id: UUID


@router.post("/reprocess-documents")
async def reprocess_all_documents(
    request: ReprocessDocumentsRequest,
    db = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Переобработать все документы проекта и записать их в Qdrant
    
    Использует существующие chunks из базы данных и записывает их в Qdrant
    
    Args:
        request: Запрос с project_id
        db: Database session
        current_admin: Admin user
    
    Returns:
        Информация о переобработанных документах
    """
    from app.models.document import Document, DocumentChunk
    from app.services.embedding_service import EmbeddingService
    from app.vector_db.vector_store import VectorStore
    from app.core.config import settings
    from sqlalchemy import select
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Получаем все документы проекта
        docs_result = await db.execute(
            select(Document)
            .where(Document.project_id == request.project_id)
        )
        documents = docs_result.scalars().all()
        
        if not documents:
            return {
                "message": "No documents found for this project",
                "project_id": str(request.project_id),
                "processed": 0
            }
        
        # Инициализируем сервисы
        embedding_service = EmbeddingService()
        vector_store = VectorStore()
        collection_name = f"project_{request.project_id}"
        
        # Убеждаемся, что коллекция существует
        await vector_store.ensure_collection(
            collection_name=collection_name,
            vector_size=settings.EMBEDDING_DIMENSION
        )
        
        processed_chunks = 0
        processed_documents = 0
        errors = []
        
        for doc in documents:
            try:
                # Получаем все chunks для документа
                chunks_result = await db.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == doc.id)
                    .order_by(DocumentChunk.chunk_index)
                )
                chunks = chunks_result.scalars().all()
                
                if not chunks:
                    # Если нет chunks, ale jest content, próbujemy utworzyć chunks
                    if doc.content and doc.content not in ["Обработка...", "Обработан", ""]:
                        logger.info(f"Document {doc.id} has content but no chunks, creating chunks...")
                        from app.documents.chunker import DocumentChunker
                        chunker = DocumentChunker()
                        text_chunks = chunker.chunk_text(doc.content)
                        
                        # Tworzymy chunks w bazie
                        for idx, chunk_text in enumerate(text_chunks):
                            chunk = DocumentChunk(
                                document_id=doc.id,
                                chunk_text=chunk_text[:10000],  # Max 10KB
                                chunk_index=idx
                            )
                            db.add(chunk)
                        await db.flush()
                        
                        # Pobieramy chunks ponownie
                        chunks_result = await db.execute(
                            select(DocumentChunk)
                            .where(DocumentChunk.document_id == doc.id)
                            .order_by(DocumentChunk.chunk_index)
                        )
                        chunks = chunks_result.scalars().all()
                    else:
                        errors.append(f"Document {doc.id} ({doc.filename}): no content and no chunks")
                        continue
                
                # Przetwarzamy każdy chunk
                for chunk in chunks:
                    try:
                        # Sprawdzamy czy chunk już ma qdrant_point_id
                        if chunk.qdrant_point_id:
                            # Sprawdzamy czy punkt istnieje w Qdrant
                            try:
                                points = await vector_store.client.retrieve(
                                    collection_name=collection_name,
                                    ids=[str(chunk.qdrant_point_id)]
                                )
                                if points:
                                    # Punkt już istnieje, pomijamy
                                    continue
                            except:
                                # Punkt nie istnieje, tworzymy nowy
                                pass
                        
                        # Tworzymy embedding
                        embedding = await embedding_service.create_embedding(chunk.chunk_text)
                        
                        # Zapisujemy do Qdrant
                        point_id = await vector_store.upsert_point(
                            collection_name=collection_name,
                            point_id=str(chunk.id),
                            vector=embedding,
                            payload={
                                "document_id": str(doc.id),
                                "chunk_id": str(chunk.id),
                                "chunk_index": chunk.chunk_index,
                                "filename": doc.filename,
                                "text": chunk.chunk_text[:1000]  # Max 1KB w payload
                            }
                        )
                        
                        # Aktualizujemy qdrant_point_id w bazie
                        chunk.qdrant_point_id = chunk.id  # Używamy chunk.id jako point_id
                        await db.flush()
                        
                        processed_chunks += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing chunk {chunk.id}: {e}")
                        errors.append(f"Chunk {chunk.id} ({doc.filename}): {str(e)}")
                        continue
                
                processed_documents += 1
                
            except Exception as e:
                logger.error(f"Error processing document {doc.id}: {e}")
                errors.append(f"Document {doc.id} ({doc.filename}): {str(e)}")
                continue
        
        await db.commit()
        
        return {
            "message": f"Processed {processed_documents} documents, {processed_chunks} chunks",
            "project_id": str(request.project_id),
            "processed_documents": processed_documents,
            "processed_chunks": processed_chunks,
            "total_documents": len(documents),
            "errors": errors[:10] if errors else None,  # Max 10 errors
            "total_errors": len(errors)
        }
        
    except Exception as e:
        logger.error(f"Error reprocessing documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error reprocessing documents: {str(e)}"
        )

