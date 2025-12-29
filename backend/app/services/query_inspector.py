"""
Query Inspector - zapis i wizualizacja wszystkich kroków RAG pipeline
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class QueryInspector:
    """
    Inspector do zapisywania i analizowania kroków RAG pipeline
    """
    
    def __init__(self):
        self.inspections: Dict[str, Dict[str, Any]] = {}
    
    def start_inspection(self, query_id: str, question: str, user_id: UUID, project_id: UUID):
        """
        Rozpoczyna inspekcję zapytania
        
        Args:
            query_id: ID zapytania
            question: Pytanie
            user_id: ID użytkownika
            project_id: ID projektu
        """
        self.inspections[query_id] = {
            "query_id": query_id,
            "question": question,
            "user_id": str(user_id),
            "project_id": str(project_id),
            "start_time": datetime.utcnow().isoformat(),
            "steps": [],
            "chunks_retrieved": [],
            "strategies_tried": [],
            "final_answer": None,
            "duration": None,
            "metrics": {}
        }
    
    def add_step(
        self,
        query_id: str,
        step_name: str,
        step_data: Dict[str, Any],
        duration: Optional[float] = None
    ):
        """
        Dodaje krok do inspekcji
        
        Args:
            query_id: ID zapytania
            step_name: Nazwa kroku
            step_data: Dane kroku
            duration: Czas trwania kroku
        """
        if query_id not in self.inspections:
            logger.warning(f"Inspection {query_id} not started")
            return
        
        step = {
            "name": step_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": step_data,
            "duration": duration
        }
        
        self.inspections[query_id]["steps"].append(step)
    
    def add_chunks(
        self,
        query_id: str,
        chunks: List[Dict[str, Any]],
        method: str = "unknown"
    ):
        """
        Dodaje pobrane chunki do inspekcji
        
        Args:
            query_id: ID zapytania
            chunks: Lista chunków
            method: Metoda pobrania
        """
        if query_id not in self.inspections:
            return
        
        for chunk in chunks:
            chunk_info = {
                "text": chunk.get("text", "")[:200],  # Ograniczamy długość
                "score": chunk.get("score", 0.0),
                "source": chunk.get("source", "unknown"),
                "method": method
            }
            self.inspections[query_id]["chunks_retrieved"].append(chunk_info)
    
    def add_strategy(
        self,
        query_id: str,
        strategy_name: str,
        strategy_result: Dict[str, Any]
    ):
        """
        Dodaje próbę strategii
        
        Args:
            query_id: ID zapytania
            strategy_name: Nazwa strategii
            strategy_result: Wynik strategii
        """
        if query_id not in self.inspections:
            return
        
        strategy_info = {
            "name": strategy_name,
            "timestamp": datetime.utcnow().isoformat(),
            "result": strategy_result
        }
        
        self.inspections[query_id]["strategies_tried"].append(strategy_info)
    
    def finish_inspection(
        self,
        query_id: str,
        answer: str,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """
        Kończy inspekcję
        
        Args:
            query_id: ID zapytania
            answer: Finalna odpowiedź
            metrics: Metryki
        """
        if query_id not in self.inspections:
            return
        
        inspection = self.inspections[query_id]
        inspection["final_answer"] = answer
        inspection["end_time"] = datetime.utcnow().isoformat()
        
        # Obliczamy czas trwania
        start = datetime.fromisoformat(inspection["start_time"])
        end = datetime.fromisoformat(inspection["end_time"])
        inspection["duration"] = (end - start).total_seconds()
        
        if metrics:
            inspection["metrics"] = metrics
    
    def get_inspection(self, query_id: str) -> Optional[Dict[str, Any]]:
        """
        Pobiera inspekcję
        
        Args:
            query_id: ID zapytania
        
        Returns:
            Dane inspekcji lub None
        """
        return self.inspections.get(query_id)
    
    def get_inspection_summary(self, query_id: str) -> Optional[Dict[str, Any]]:
        """
        Pobiera podsumowanie inspekcji
        
        Args:
            query_id: ID zapytania
        
        Returns:
            Podsumowanie inspekcji
        """
        inspection = self.get_inspection(query_id)
        if not inspection:
            return None
        
        return {
            "query_id": inspection["query_id"],
            "question": inspection["question"],
            "duration": inspection.get("duration"),
            "steps_count": len(inspection["steps"]),
            "chunks_count": len(inspection["chunks_retrieved"]),
            "strategies_count": len(inspection["strategies_tried"]),
            "answer_length": len(inspection.get("final_answer", "")),
            "metrics": inspection.get("metrics", {})
        }
    
    def compare_strategies(self, query_id: str) -> Dict[str, Any]:
        """
        Porównuje różne strategie użyte w zapytaniu
        
        Args:
            query_id: ID zapytania
        
        Returns:
            Porównanie strategii
        """
        inspection = self.get_inspection(query_id)
        if not inspection:
            return {}
        
        strategies = inspection.get("strategies_tried", [])
        
        comparison = {
            "strategies": [],
            "best_strategy": None,
            "best_score": 0.0
        }
        
        for strategy in strategies:
            result = strategy.get("result", {})
            score = result.get("score", 0.0)
            
            strategy_info = {
                "name": strategy["name"],
                "score": score,
                "chunks_found": result.get("chunks_found", 0),
                "duration": result.get("duration", 0.0)
            }
            
            comparison["strategies"].append(strategy_info)
            
            if score > comparison["best_score"]:
                comparison["best_score"] = score
                comparison["best_strategy"] = strategy["name"]
        
        return comparison


# Globalna instancja
query_inspector = QueryInspector()

