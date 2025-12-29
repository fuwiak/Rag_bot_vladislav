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

