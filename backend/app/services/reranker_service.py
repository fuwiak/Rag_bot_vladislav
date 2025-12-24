"""
Легкий reranker для улучшения релевантности найденных чанков
Использует cross-encoder модель или простую scoring функцию
"""
import logging
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)

# Попытка загрузить cross-encoder (опционально)
CROSS_ENCODER_AVAILABLE = False
cross_encoder_model = None

try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
    try:
        # Используем легкую мультиязычную модель
        cross_encoder_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        logger.info("[RERANKER] Loaded cross-encoder model: ms-marco-MiniLM-L-6-v2")
    except Exception as e:
        logger.warning(f"[RERANKER] Failed to load cross-encoder model: {e}")
        CROSS_ENCODER_AVAILABLE = False
except ImportError:
    logger.debug("[RERANKER] sentence-transformers not available, using simple reranking")


class RerankerService:
    """Сервис для переранжирования результатов поиска"""
    
    def __init__(self):
        self.use_cross_encoder = CROSS_ENCODER_AVAILABLE and cross_encoder_model is not None
    
    def rerank(
        self,
        question: str,
        chunks: List[Dict],
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Переранжирует чанки по релевантности к вопросу
        
        Args:
            question: Вопрос пользователя
            chunks: Список чанков с полями 'text', 'score', 'source'
            top_k: Количество лучших результатов (если None, возвращает все)
            
        Returns:
            Переранжированный список чанков
        """
        if not chunks:
            return []
        
        if self.use_cross_encoder:
            return self._rerank_with_cross_encoder(question, chunks, top_k)
        else:
            return self._rerank_with_simple_scoring(question, chunks, top_k)
    
    def _rerank_with_cross_encoder(
        self,
        question: str,
        chunks: List[Dict],
        top_k: Optional[int]
    ) -> List[Dict]:
        """Переранжирование с использованием cross-encoder модели"""
        try:
            # Подготавливаем пары (question, chunk_text)
            pairs = []
            for chunk in chunks:
                text = chunk.get("text", "")
                if text:
                    pairs.append([question, text])
            
            if not pairs:
                return chunks
            
            # Получаем scores от cross-encoder
            scores = cross_encoder_model.predict(pairs)
            
            # Обновляем scores в чанках
            for i, chunk in enumerate(chunks):
                if i < len(scores):
                    # Комбинируем оригинальный score с cross-encoder score
                    original_score = chunk.get("score", 0.5)
                    cross_score = float(scores[i])
                    # Нормализуем cross_score к диапазону 0-1 (если нужно)
                    if cross_score < 0:
                        cross_score = (cross_score + 1) / 2
                    # Взвешенная комбинация: 30% оригинальный, 70% cross-encoder
                    chunk["rerank_score"] = 0.3 * original_score + 0.7 * cross_score
                    chunk["score"] = chunk["rerank_score"]
            
            # Сортируем по новому score
            reranked = sorted(chunks, key=lambda x: x.get("rerank_score", x.get("score", 0)), reverse=True)
            
            logger.info(f"[RERANKER] Reranked {len(chunks)} chunks using cross-encoder")
            return reranked[:top_k] if top_k else reranked
            
        except Exception as e:
            logger.warning(f"[RERANKER] Cross-encoder reranking failed: {e}, falling back to simple scoring")
            return self._rerank_with_simple_scoring(question, chunks, top_k)
    
    def _rerank_with_simple_scoring(
        self,
        question: str,
        chunks: List[Dict],
        top_k: Optional[int]
    ) -> List[Dict]:
        """Простое переранжирование на основе ключевых слов и длины"""
        try:
            # Извлекаем ключевые слова из вопроса
            question_lower = question.lower()
            words = re.findall(r'\b\w+\b', question_lower)
            keywords = {w for w in words if len(w) > 3}  # Слова длиннее 3 символов
            
            # Стоп-слова для исключения
            stop_words = {
                "что", "как", "где", "когда", "почему", "кто", "какой", "какая", "какое",
                "the", "a", "an", "is", "are", "was", "were", "this", "that", "these", "those"
            }
            keywords = {kw for kw in keywords if kw not in stop_words}
            
            # Пересчитываем scores для каждого чанка
            for chunk in chunks:
                text = chunk.get("text", "")
                if not text:
                    continue
                
                text_lower = text.lower()
                original_score = chunk.get("score", 0.5)
                
                # Подсчитываем совпадения ключевых слов
                keyword_matches = sum(1 for kw in keywords if kw in text_lower)
                keyword_score = min(1.0, keyword_matches / max(len(keywords), 1))
                
                # Бонус за точное совпадение фраз из вопроса
                question_phrases = [phrase.strip() for phrase in question.split() if len(phrase.strip()) > 3]
                phrase_matches = sum(1 for phrase in question_phrases if phrase.lower() in text_lower)
                phrase_score = min(0.5, phrase_matches * 0.1)
                
                # Штраф за слишком длинные или короткие чанки (оптимальная длина ~200-500 символов)
                text_length = len(text)
                if 200 <= text_length <= 500:
                    length_bonus = 0.1
                elif text_length < 50:
                    length_bonus = -0.2
                elif text_length > 2000:
                    length_bonus = -0.1
                else:
                    length_bonus = 0.0
                
                # Комбинируем scores
                # 40% оригинальный score, 40% keyword matches, 20% phrase matches + length bonus
                rerank_score = (
                    0.4 * original_score +
                    0.4 * keyword_score +
                    0.2 * phrase_score +
                    length_bonus
                )
                
                # Ограничиваем диапазон 0-1
                rerank_score = max(0.0, min(1.0, rerank_score))
                chunk["rerank_score"] = rerank_score
                chunk["score"] = rerank_score
            
            # Сортируем по новому score
            reranked = sorted(chunks, key=lambda x: x.get("rerank_score", x.get("score", 0)), reverse=True)
            
            logger.info(f"[RERANKER] Reranked {len(chunks)} chunks using simple scoring")
            return reranked[:top_k] if top_k else reranked
            
        except Exception as e:
            logger.error(f"[RERANKER] Simple reranking error: {e}", exc_info=True)
            # В случае ошибки возвращаем оригинальный список
            return chunks[:top_k] if top_k else chunks

