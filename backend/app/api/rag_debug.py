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

