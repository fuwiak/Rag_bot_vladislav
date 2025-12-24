"""
RAG Quality Evaluator - Golden Standard Implementation
Evaluates RAG system using Ground-Truth QA pairs with metrics:
- Precision@K (≥0.85 for regulated, ≥0.75 for general)
- Halucination Rate (fact-checking against sources)
- MRR (Mean Reciprocal Rank, target ≥0.9)
- Groundedness (target ≥0.9)
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
from rag_chain import RAGChain
from qdrant_loader import QdrantLoader

logger = logging.getLogger(__name__)


@dataclass
class GroundTruthQA:
    """Ground-Truth QA пара"""
    question: str
    expected_answer: str
    category: str  # "regulated" или "general"
    expected_sources: List[str]  # Ожидаемые источники
    key_facts: List[str]  # Ключевые факты для проверки


@dataclass
class EvaluationResult:
    """Результат оценки одного QA"""
    question: str
    expected_answer: str
    actual_answer: str
    category: str
    precision_at_k: float
    mrr: float
    groundedness: float
    halucination_rate: float
    retrieved_sources: List[str]
    expected_sources: List[str]
    matched_sources: List[str]
    error: Optional[str] = None


@dataclass
class EvaluationSummary:
    """Сводка оценки"""
    total_questions: int
    precision_at_k_regulated: float
    precision_at_k_general: float
    precision_at_k_overall: float
    mrr_overall: float
    groundedness_overall: float
    halucination_rate_overall: float
    timestamp: str
    results: List[EvaluationResult]


class HalucinationDetector:
    """Детектор галлюцинаций - проверка фактов против источников"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".HalucinationDetector")
    
    def check_facts(
        self,
        answer: str,
        context_docs: List[Dict[str, Any]],
        key_facts: Optional[List[str]] = None
    ) -> Tuple[float, List[str]]:
        """
        Проверяет факты в ответе против источников.
        
        Args:
            answer: Ответ модели
            context_docs: Контекстные документы из RAG
            key_facts: Ключевые факты для проверки (опционально)
        
        Returns:
            Tuple[groundedness_score, halucinated_facts]
            - groundedness_score: 0.0-1.0 (1.0 = все факты подтверждены)
            - halucinated_facts: список не подтвержденных фактов
        """
        if not context_docs:
            # Если нет контекста, но есть key_facts - проверяем их в ответе
            # Это значит LLM мог генерировать из собственных знаний
            # Это частично валидная ситуация - не полная галлюцинация
            if key_facts and answer:
                answer_lower = answer.lower()
                matched_facts = sum(1 for fact in key_facts if fact.lower() in answer_lower)
                if matched_facts > 0:
                    # Если хотя бы некоторые факты есть в ответе - частично правильно
                    # Но все равно снижаем оценку из-за отсутствия контекста
                    groundedness = min(0.4, matched_facts / len(key_facts) * 0.6)  # Максимум 0.4 даже при всех совпадениях
                    return groundedness, []
            
            # Если нет контекста и нет совпадений - все галлюцинация
            # Но не возвращаем весь ответ как галлюцинацию - это слишком строго
            if answer:
                return 0.0, ["Нет контекста для проверки фактов"]
            return 0.0, []
        
        # Собираем весь контекст в один текст
        context_text = " ".join([doc.get("text", "") for doc in context_docs])
        context_text_lower = context_text.lower()
        answer_lower = answer.lower()
        
        # Разбиваем ответ на предложения (простые факты)
        sentences = self._extract_facts(answer)
        
        if not sentences:
            return 1.0, []  # Нет фактов для проверки
        
        grounded_count = 0
        halucinated = []
        
        for fact in sentences:
            if self._fact_grounded(fact, context_text_lower, key_facts):
                grounded_count += 1
            else:
                halucinated.append(fact[:100])
        
        groundedness = grounded_count / len(sentences) if sentences else 1.0
        halucination_rate = 1.0 - groundedness
        
        return groundedness, halucinated[:5]  # Максимум 5 примеров
    
    def _extract_facts(self, text: str) -> List[str]:
        """Извлекает факты из текста (простые предложения)"""
        if not text or len(text.strip()) < 10:
            return []
        
        import re
        # Разбиваем на предложения
        sentences = re.split(r'[.!?]\s+', text)
        # Фильтруем слишком короткие и служебные фразы
        facts = [
            s.strip() for s in sentences
            if len(s.strip()) > 12 and not s.strip().startswith(('Источники:', '📚', 'Если', 'Пожалуйста', 'К сожалению', 'Однако', 'Вопрос', 'Ответ'))
        ]
        
        # Если фактов мало, пробуем по запятым
        if len(facts) < 2 and ',' in text:
            comma_split = text.split(',')
            facts.extend([
                s.strip() for s in comma_split
                if len(s.strip()) > 15 and not s.strip().startswith(('Источники:', '📚'))
            ])
        
        # Убираем дубликаты и короткие факты
        facts = list(dict.fromkeys(facts))  # Убираем дубликаты сохраняя порядок
        facts = [f for f in facts if len(f) > 12]  # Фильтруем короткие
        
        return facts[:10]  # Максимум 10 фактов
    
    def _fact_grounded(
        self,
        fact: str,
        context: str,
        key_facts: Optional[List[str]] = None
    ) -> bool:
        """Проверяет, подтвержден ли факт контекстом"""
        fact_lower = fact.lower()
        
        # Если указаны ключевые факты, проверяем их в первую очередь
        if key_facts:
            for key_fact in key_facts:
                if key_fact.lower() in fact_lower and key_fact.lower() in context:
                    return True
        
        # Извлекаем ключевые слова из факта
        import re
        words = re.findall(r'\b\w{4,}\b', fact_lower)  # Слова длиной >= 4 символов
        
        if not words:
            return False
        
        # Проверяем, есть ли ключевые слова в контексте
        # Нужно чтобы хотя бы 50% ключевых слов было в контексте
        matched_words = sum(1 for word in words if word in context)
        match_ratio = matched_words / len(words) if words else 0
        
        # Если >50% слов совпадает - считаем факт подтвержденным
        return match_ratio >= 0.5


class RAGEvaluator:
    """Оценщик качества RAG системы"""
    
    def __init__(self, rag_chain: Optional[RAGChain] = None):
        self.rag_chain = rag_chain or RAGChain()
        self.halucination_detector = HalucinationDetector()
        self.logger = logging.getLogger(__name__ + ".RAGEvaluator")
    
    async def evaluate(
        self,
        ground_truth_qa: List[GroundTruthQA],
        k: int = 5
    ) -> EvaluationSummary:
        """
        Оценивает RAG систему на Ground-Truth QA наборе.
        
        Args:
            ground_truth_qa: Список Ground-Truth QA пар
            k: K для Precision@K
        
        Returns:
            EvaluationSummary с метриками
        """
        self.logger.info(f"Начинаю оценку на {len(ground_truth_qa)} QA парах...")
        
        results = []
        
        for i, qa in enumerate(ground_truth_qa, 1):
            self.logger.info(f"Оценка {i}/{len(ground_truth_qa)}: {qa.question[:60]}...")
            
            try:
                result = await self._evaluate_single(qa, k)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Ошибка при оценке QA {i}: {str(e)}")
                results.append(EvaluationResult(
                    question=qa.question,
                    expected_answer=qa.expected_answer,
                    actual_answer="",
                    category=qa.category,
                    precision_at_k=0.0,
                    mrr=0.0,
                    groundedness=0.0,
                    halucination_rate=1.0,
                    retrieved_sources=[],
                    expected_sources=qa.expected_sources,
                    matched_sources=[],
                    error=str(e)
                ))
        
        # Вычисляем сводные метрики
        summary = self._calculate_summary(results)
        
        return summary
    
    async def _evaluate_single(
        self,
        qa: GroundTruthQA,
        k: int
    ) -> EvaluationResult:
        """Оценивает один QA"""
        # Выполняем RAG запрос
        rag_result = await self.rag_chain.query(
            user_query=qa.question,
            use_rag=True,
            top_k=k
        )
        
        actual_answer = rag_result.get("answer", "")
        context_count = rag_result.get("context_count", 0)
        retrieved_sources = rag_result.get("sources", [])
        
        # Получаем контекстные документы для проверки фактов
        # Используем те же результаты что и в RAG запросе
        context_docs = await self._get_context_docs(qa.question, k)
        
        # Если нет контекста - логируем предупреждение
        if not context_docs:
            self.logger.warning(
                f"⚠️ Нет контекста для проверки фактов в вопросе: {qa.question[:60]}..."
            )
            self.logger.warning(
                f"   Возможные причины: Qdrant пуст, пороги слишком высокие, "
                f"или данные не загружены"
            )
        
        # Precision@K - проверка источников
        precision_at_k = self._calculate_precision_at_k(
            retrieved_sources,
            qa.expected_sources,
            k
        )
        
        # MRR (Mean Reciprocal Rank)
        mrr = self._calculate_mrr(
            retrieved_sources,
            qa.expected_sources
        )
        
        # Groundedness и Halucination Rate
        groundedness, halucinated = self.halucination_detector.check_facts(
            actual_answer,
            context_docs,
            qa.key_facts
        )
        halucination_rate = 1.0 - groundedness
        
        # Матчинг источников
        matched_sources = [
            src for src in retrieved_sources
            if any(exp in src or src in exp for exp in qa.expected_sources)
        ]
        
        return EvaluationResult(
            question=qa.question,
            expected_answer=qa.expected_answer,
            actual_answer=actual_answer,
            category=qa.category,
            precision_at_k=precision_at_k,
            mrr=mrr,
            groundedness=groundedness,
            halucination_rate=halucination_rate,
            retrieved_sources=retrieved_sources,
            expected_sources=qa.expected_sources,
            matched_sources=matched_sources
        )
    
    async def _get_context_docs(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Получает контекстные документы для проверки фактов"""
        try:
            # Пробуем с фильтром whitelist
            docs = self.rag_chain.qdrant_loader.search(
                query=query,
                top_k=k * 2,  # Больше документов для проверки
                score_threshold=0.2,  # Низкий порог
                filter_by_whitelist=True
            )
            
            # Если нет результатов, пробуем без фильтра
            if not docs:
                self.logger.debug(f"Нет результатов с фильтром, пробуем без фильтра...")
                docs = self.rag_chain.qdrant_loader.search(
                    query=query,
                    top_k=k * 2,
                    score_threshold=0.2,
                    filter_by_whitelist=False
                )
            
            return docs[:k]  # Возвращаем только нужное количество
        except Exception as e:
            self.logger.warning(f"Ошибка получения контекста: {str(e)}")
            return []
    
    def _calculate_precision_at_k(
        self,
        retrieved: List[str],
        expected: List[str],
        k: int
    ) -> float:
        """
        Вычисляет Precision@K.
        Precision@K = (количество релевантных в топ-K) / K
        """
        if not retrieved:
            return 0.0
        
        # Нормализуем источники для сравнения
        retrieved_normalized = [self._normalize_url(url) for url in retrieved[:k]]
        expected_normalized = [self._normalize_url(url) for url in expected]
        
        # Считаем релевантные
        relevant_count = sum(
            1 for url in retrieved_normalized
            if any(exp in url or url in exp for exp in expected_normalized)
        )
        
        precision = relevant_count / min(k, len(retrieved)) if retrieved else 0.0
        return precision
    
    def _calculate_mrr(
        self,
        retrieved: List[str],
        expected: List[str]
    ) -> float:
        """
        Вычисляет MRR (Mean Reciprocal Rank).
        MRR = 1 / rank первого релевантного документа
        """
        if not retrieved or not expected:
            return 0.0
        
        retrieved_normalized = [self._normalize_url(url) for url in retrieved]
        expected_normalized = [self._normalize_url(url) for url in expected]
        
        # Находим позицию первого релевантного
        for rank, url in enumerate(retrieved_normalized, 1):
            if any(exp in url or url in exp for exp in expected_normalized):
                return 1.0 / rank
        
        return 0.0
    
    def _normalize_url(self, url: str) -> str:
        """Нормализует URL для сравнения"""
        url = url.lower().strip()
        # Убираем протокол и www
        url = url.replace("https://", "").replace("http://", "").replace("www.", "")
        # Убираем trailing slash
        url = url.rstrip("/")
        return url
    
    def _calculate_summary(self, results: List[EvaluationResult]) -> EvaluationSummary:
        """Вычисляет сводные метрики"""
        if not results:
            return EvaluationSummary(
                total_questions=0,
                precision_at_k_regulated=0.0,
                precision_at_k_general=0.0,
                precision_at_k_overall=0.0,
                mrr_overall=0.0,
                groundedness_overall=0.0,
                halucination_rate_overall=1.0,
                timestamp=datetime.now().isoformat(),
                results=[]
            )
        
        # Разделяем по категориям
        regulated = [r for r in results if r.category == "regulated"]
        general = [r for r in results if r.category == "general"]
        
        # Precision@K
        precision_regulated = (
            sum(r.precision_at_k for r in regulated) / len(regulated)
            if regulated else 0.0
        )
        precision_general = (
            sum(r.precision_at_k for r in general) / len(general)
            if general else 0.0
        )
        precision_overall = sum(r.precision_at_k for r in results) / len(results)
        
        # MRR
        mrr_overall = sum(r.mrr for r in results) / len(results)
        
        # Groundedness
        groundedness_overall = sum(r.groundedness for r in results) / len(results)
        
        # Halucination Rate
        halucination_overall = sum(r.halucination_rate for r in results) / len(results)
        
        return EvaluationSummary(
            total_questions=len(results),
            precision_at_k_regulated=precision_regulated,
            precision_at_k_general=precision_general,
            precision_at_k_overall=precision_overall,
            mrr_overall=mrr_overall,
            groundedness_overall=groundedness_overall,
            halucination_rate_overall=halucination_overall,
            timestamp=datetime.now().isoformat(),
            results=results
        )
    
    def save_results(
        self,
        summary: EvaluationSummary,
        output_path: str = "evaluation_results.json"
    ):
        """Сохраняет результаты оценки в JSON"""
        output = {
            "summary": {
                "total_questions": summary.total_questions,
                "precision_at_k_regulated": summary.precision_at_k_regulated,
                "precision_at_k_general": summary.precision_at_k_general,
                "precision_at_k_overall": summary.precision_at_k_overall,
                "mrr_overall": summary.mrr_overall,
                "groundedness_overall": summary.groundedness_overall,
                "halucination_rate_overall": summary.halucination_rate_overall,
                "timestamp": summary.timestamp
            },
            "results": [asdict(r) for r in summary.results]
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Результаты сохранены в {output_path}")
    
    async def close(self):
        """Закрывает ресурсы"""
        await self.rag_chain.close()

