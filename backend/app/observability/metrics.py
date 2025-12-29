"""
Prometheus metrics dla RAG systemu
"""
import time
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

from app.observability.otel_setup import get_meter
from app.core.config import settings

# Prometheus metrics (legacy, dla kompatybilności)
rag_query_duration = Histogram(
    'rag_query_duration_seconds',
    'Czas trwania zapytania RAG w sekundach',
    ['project_id', 'status']
)

rag_chunks_retrieved = Histogram(
    'rag_chunks_retrieved',
    'Liczba pobranych chunków dla zapytania',
    ['project_id']
)

rag_llm_tokens_used = Counter(
    'rag_llm_tokens_total',
    'Całkowita liczba tokenów użytych przez LLM',
    ['project_id', 'model', 'type']  # type: input/output
)

rag_answer_relevance_score = Histogram(
    'rag_answer_relevance_score',
    'Ocena relewantności odpowiedzi (0-1)',
    ['project_id']
)

rag_hallucination_detected = Counter(
    'rag_hallucination_detected_total',
    'Liczba wykrytych halucynacji',
    ['project_id']
)

vector_db_query_duration = Histogram(
    'vector_db_query_duration_seconds',
    'Czas trwania zapytania do bazy wektorowej',
    ['collection_name', 'operation']
)

embedding_generation_duration = Histogram(
    'embedding_generation_duration_seconds',
    'Czas generowania embeddingu',
    ['model']
)

rag_queries_per_project = Counter(
    'rag_queries_total',
    'Całkowita liczba zapytań RAG',
    ['project_id', 'status']
)

rag_cache_hit_rate = Counter(
    'rag_cache_hits_total',
    'Liczba trafień w cache',
    ['cache_type', 'project_id']
)

rag_cache_miss_rate = Counter(
    'rag_cache_misses_total',
    'Liczba chybień w cache',
    ['cache_type', 'project_id']
)

# Gauges dla aktualnego stanu
rag_active_queries = Gauge(
    'rag_active_queries',
    'Liczba aktywnych zapytań RAG',
    ['project_id']
)

rag_vector_db_size = Gauge(
    'rag_vector_db_size',
    'Rozmiar bazy wektorowej (liczba punktów)',
    ['collection_name']
)


class RAGMetrics:
    """Klasa pomocnicza do zarządzania metrykami RAG"""
    
    def __init__(self):
        self.meter = get_meter("rag_metrics")
        
        # OpenTelemetry metrics (nowoczesne podejście)
        self.otel_query_duration = self.meter.create_histogram(
            "rag.query.duration",
            description="Czas trwania zapytania RAG",
            unit="s"
        )
        
        self.otel_chunks_retrieved = self.meter.create_histogram(
            "rag.chunks.retrieved",
            description="Liczba pobranych chunków"
        )
        
        self.otel_tokens_used = self.meter.create_counter(
            "rag.llm.tokens",
            description="Liczba tokenów użytych przez LLM"
        )
        
        self.otel_relevance_score = self.meter.create_histogram(
            "rag.answer.relevance",
            description="Ocena relewantności odpowiedzi",
            unit="1"
        )
    
    def record_query_duration(
        self,
        duration: float,
        project_id: Optional[str] = None,
        status: str = "success"
    ):
        """Zapisuje czas trwania zapytania"""
        labels = {}
        if project_id:
            labels["project_id"] = project_id
        labels["status"] = status
        
        # Prometheus
        rag_query_duration.labels(
            project_id=project_id or "unknown",
            status=status
        ).observe(duration)
        
        # OpenTelemetry
        self.otel_query_duration.record(duration, attributes=labels)
    
    def record_chunks_retrieved(
        self,
        count: int,
        project_id: Optional[str] = None
    ):
        """Zapisuje liczbę pobranych chunków"""
        labels = {}
        if project_id:
            labels["project_id"] = project_id
        
        # Prometheus
        rag_chunks_retrieved.labels(
            project_id=project_id or "unknown"
        ).observe(count)
        
        # OpenTelemetry
        self.otel_chunks_retrieved.record(count, attributes=labels)
    
    def record_tokens_used(
        self,
        tokens: int,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        token_type: str = "total"
    ):
        """Zapisuje liczbę użytych tokenów"""
        labels = {}
        if project_id:
            labels["project_id"] = project_id
        if model:
            labels["model"] = model
        labels["type"] = token_type
        
        # Prometheus
        rag_llm_tokens_used.labels(
            project_id=project_id or "unknown",
            model=model or "unknown",
            type=token_type
        ).inc(tokens)
        
        # OpenTelemetry
        self.otel_tokens_used.add(tokens, attributes=labels)
    
    def record_relevance_score(
        self,
        score: float,
        project_id: Optional[str] = None
    ):
        """Zapisuje ocenę relewantności"""
        labels = {}
        if project_id:
            labels["project_id"] = project_id
        
        # Prometheus
        rag_answer_relevance_score.labels(
            project_id=project_id or "unknown"
        ).observe(score)
        
        # OpenTelemetry
        self.otel_relevance_score.record(score, attributes=labels)
    
    def record_cache_hit(self, cache_type: str, project_id: Optional[str] = None):
        """Zapisuje trafienie w cache"""
        rag_cache_hit_rate.labels(
            cache_type=cache_type,
            project_id=project_id or "unknown"
        ).inc()
    
    def record_cache_miss(self, cache_type: str, project_id: Optional[str] = None):
        """Zapisuje chybienie w cache"""
        rag_cache_miss_rate.labels(
            cache_type=cache_type,
            project_id=project_id or "unknown"
        ).inc()
    
    def record_vector_db_query(
        self,
        duration: float,
        collection_name: str,
        operation: str = "search"
    ):
        """Zapisuje czas zapytania do bazy wektorowej"""
        vector_db_query_duration.labels(
            collection_name=collection_name,
            operation=operation
        ).observe(duration)
    
    def record_embedding_generation(
        self,
        duration: float,
        model: Optional[str] = None
    ):
        """Zapisuje czas generowania embeddingu"""
        embedding_generation_duration.labels(
            model=model or "unknown"
        ).observe(duration)
    
    def increment_query(self, project_id: Optional[str] = None, status: str = "success"):
        """Zwiększa licznik zapytań"""
        rag_queries_per_project.labels(
            project_id=project_id or "unknown",
            status=status
        ).inc()
    
    def set_active_queries(self, count: int, project_id: Optional[str] = None):
        """Ustawia liczbę aktywnych zapytań"""
        rag_active_queries.labels(
            project_id=project_id or "unknown"
        ).set(count)


# Globalna instancja metryk
rag_metrics = RAGMetrics()


def get_metrics_exporter():
    """Zwraca Prometheus metrics exporter dla FastAPI endpoint"""
    return generate_latest(REGISTRY)

