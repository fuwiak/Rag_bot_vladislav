"""
Adaptive Retrieval - dynamiczne dostosowanie top_k i reranking thresholds
"""
import logging
from typing import List, Dict, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class AdaptiveRetrieval:
    """
    Adaptacyjne dostosowanie parametrów retrieval na podstawie jakości wyników
    """
    
    def __init__(self):
        self.min_top_k = 3
        self.max_top_k = 20
        self.default_top_k = 5
        self.min_score_threshold = 0.3
        self.max_score_threshold = 0.8
        self.default_score_threshold = 0.5
    
    def detect_query_complexity(self, question: str) -> str:
        """
        Wykrywa złożoność zapytania
        
        Args:
            question: Pytanie użytkownika
        
        Returns:
            "simple", "medium", "complex"
        """
        question_lower = question.lower()
        question_length = len(question.split())
        
        # Proste pytania - krótkie, pojedyncze pytania
        if question_length <= 5 and any(word in question_lower for word in ["что", "как", "где", "когда", "кто"]):
            return "simple"
        
        # Złożone pytania - długie, wieloczęściowe
        if question_length > 15 or any(word in question_lower for word in ["объясни", "расскажи", "опиши", "сравни", "проанализируй"]):
            return "complex"
        
        return "medium"
    
    def adjust_top_k(
        self,
        base_top_k: int,
        query_complexity: str,
        previous_results_quality: Optional[float] = None
    ) -> int:
        """
        Dostosowuje top_k na podstawie złożoności i jakości poprzednich wyników
        
        Args:
            base_top_k: Bazowy top_k
            query_complexity: Złożoność zapytania
            previous_results_quality: Jakość poprzednich wyników (0-1)
        
        Returns:
            Dostosowany top_k
        """
        adjusted_k = base_top_k
        
        # Dostosowanie na podstawie złożoności
        if query_complexity == "simple":
            adjusted_k = max(self.min_top_k, base_top_k - 2)
        elif query_complexity == "complex":
            adjusted_k = min(self.max_top_k, base_top_k + 5)
        
        # Dostosowanie na podstawie jakości poprzednich wyników
        if previous_results_quality is not None:
            if previous_results_quality < 0.5:
                # Niska jakość - zwiększamy top_k
                adjusted_k = min(self.max_top_k, adjusted_k + 3)
            elif previous_results_quality > 0.8:
                # Wysoka jakość - zmniejszamy top_k
                adjusted_k = max(self.min_top_k, adjusted_k - 2)
        
        return adjusted_k
    
    def adjust_score_threshold(
        self,
        base_threshold: float,
        query_complexity: str,
        chunks_found: int,
        target_chunks: int = 5
    ) -> float:
        """
        Dostosowuje próg score na podstawie liczby znalezionych chunków
        
        Args:
            base_threshold: Bazowy próg
            query_complexity: Złożoność zapytania
            chunks_found: Liczba znalezionych chunków
            target_chunks: Docelowa liczba chunków
        
        Returns:
            Dostosowany próg
        """
        adjusted_threshold = base_threshold
        
        # Jeśli znaleziono za mało chunków - obniżamy próg
        if chunks_found < target_chunks:
            adjusted_threshold = max(
                self.min_score_threshold,
                adjusted_threshold - 0.1
            )
        # Jeśli znaleziono za dużo chunków - podnosimy próg
        elif chunks_found > target_chunks * 2:
            adjusted_threshold = min(
                self.max_score_threshold,
                adjusted_threshold + 0.1
            )
        
        # Dostosowanie na podstawie złożoności
        if query_complexity == "complex":
            # Dla złożonych zapytań obniżamy próg
            adjusted_threshold = max(
                self.min_score_threshold,
                adjusted_threshold - 0.05
            )
        
        return adjusted_threshold
    
    def calculate_results_quality(
        self,
        chunks: List[Dict],
        min_score: float = 0.5
    ) -> float:
        """
        Oblicza jakość wyników na podstawie scores
        
        Args:
            chunks: Lista chunków z scores
            min_score: Minimalny akceptowalny score
        
        Returns:
            Jakość wyników (0-1)
        """
        if not chunks:
            return 0.0
        
        scores = [chunk.get("score", 0.0) for chunk in chunks]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Jakość = średni score znormalizowany do 0-1
        quality = min(1.0, max(0.0, avg_score))
        
        # Bonus za liczbę chunków powyżej progu
        high_quality_chunks = sum(1 for score in scores if score >= min_score)
        quality_bonus = min(0.2, high_quality_chunks / len(chunks) * 0.2)
        
        return min(1.0, quality + quality_bonus)
    
    def get_retrieval_params(
        self,
        question: str,
        base_top_k: int = 5,
        base_score_threshold: float = 0.5,
        previous_quality: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Zwraca dostosowane parametry retrieval
        
        Args:
            question: Pytanie
            base_top_k: Bazowy top_k
            base_score_threshold: Bazowy próg score
            previous_quality: Jakość poprzednich wyników
        
        Returns:
            Dict z dostosowanymi parametrami
        """
        complexity = self.detect_query_complexity(question)
        
        adjusted_top_k = self.adjust_top_k(
            base_top_k,
            complexity,
            previous_quality
        )
        
        adjusted_threshold = self.adjust_score_threshold(
            base_score_threshold,
            complexity,
            adjusted_top_k
        )
        
        return {
            "top_k": adjusted_top_k,
            "score_threshold": adjusted_threshold,
            "query_complexity": complexity,
            "base_top_k": base_top_k,
            "base_score_threshold": base_score_threshold
        }

