"""
Multi-Vector Store - różne embeddingi dla tego samego tekstu
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

from app.vector_db.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class MultiVectorStore:
    """
    Multi-vector search z różnymi embeddingami:
    - semantic: embedding semantyczny (główny)
    - keyword: embedding dla słów kluczowych
    - summary: embedding dla podsumowania
    """
    
    def __init__(self, collection_name: str = "rag_docs"):
        self.vector_store = VectorStore()
        self.embedding_service = EmbeddingService()
        self.collection_name = collection_name
    
    async def store_multi_vector(
        self,
        text: str,
        semantic_embedding: Optional[List[float]] = None,
        keyword_embedding: Optional[List[float]] = None,
        summary_embedding: Optional[List[float]] = None,
        payload: Dict[str, Any] = None
    ) -> Dict[str, UUID]:
        """
        Zapisuje tekst z wieloma embeddingami
        
        Args:
            text: Tekst
            semantic_embedding: Embedding semantyczny
            keyword_embedding: Embedding dla słów kluczowych
            summary_embedding: Embedding dla podsumowania
            payload: Metadane
        
        Returns:
            Dict z point_id dla każdego typu embeddingu
        """
        payload = payload or {}
        results = {}
        
        # Semantic embedding (główny)
        if semantic_embedding:
            semantic_id = await self.vector_store.store_vector(
                collection_name=f"{self.collection_name}_semantic",
                vector=semantic_embedding,
                payload={**payload, "text": text, "vector_type": "semantic"}
            )
            results["semantic"] = semantic_id
        
        # Keyword embedding
        if keyword_embedding:
            keyword_id = await self.vector_store.store_vector(
                collection_name=f"{self.collection_name}_keyword",
                vector=keyword_embedding,
                payload={**payload, "text": text, "vector_type": "keyword"}
            )
            results["keyword"] = keyword_id
        
        # Summary embedding
        if summary_embedding:
            summary_id = await self.vector_store.store_vector(
                collection_name=f"{self.collection_name}_summary",
                vector=summary_embedding,
                payload={**payload, "text": text, "vector_type": "summary"}
            )
            results["summary"] = summary_id
        
        return results
    
    async def search_multi_vector(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
        weights: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """
        Wyszukuje używając wielu embeddingów z weighted combination
        
        Args:
            query: Zapytanie
            query_embedding: Embedding zapytania
            top_k: Liczba wyników
            weights: Wagi dla różnych typów (semantic, keyword, summary)
        
        Returns:
            Lista wyników z combined scores
        """
        weights = weights or {"semantic": 0.6, "keyword": 0.3, "summary": 0.1}
        
        if not query_embedding:
            query_embedding = await self.embedding_service.create_embedding(query)
        
        all_results = {}
        
        # Wyszukiwanie w każdej kolekcji
        for vector_type, weight in weights.items():
            collection_name = f"{self.collection_name}_{vector_type}"
            
            try:
                results = await self.vector_store.search_similar(
                    collection_name=collection_name,
                    query_vector=query_embedding,
                    limit=top_k * 2,  # Bierzemy więcej, potem filtrujemy
                    score_threshold=0.3
                )
                
                # Ważymy scores
                for result in results:
                    text = result.get("payload", {}).get("text", "")
                    if not text:
                        continue
                    
                    # Klucz to tekst (dla deduplikacji)
                    if text not in all_results:
                        all_results[text] = {
                            "text": text,
                            "payload": result.get("payload", {}),
                            "scores": {},
                            "combined_score": 0.0
                        }
                    
                    # Zapisujemy score dla tego typu
                    original_score = result.get("score", 0.0)
                    weighted_score = original_score * weight
                    all_results[text]["scores"][vector_type] = original_score
                    all_results[text]["combined_score"] += weighted_score
                    
            except Exception as e:
                logger.warning(f"Error searching in {vector_type} collection: {e}")
                continue
        
        # Sortujemy po combined score
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        return sorted_results[:top_k]

