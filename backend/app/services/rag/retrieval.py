"""
Retrieval methods for RAG service - advanced chunk search techniques
"""
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.vector_db.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService
from app.rag.qdrant_loader import QdrantLoader
from app.services.reranker_service import RerankerService
from app.observability.structured_logging import get_logger

logger = get_logger(__name__)


class RAGRetrieval:
    """Advanced retrieval methods for RAG service"""
    
    def __init__(self, db: AsyncSession, vector_store: VectorStore, embedding_service: EmbeddingService, reranker: RerankerService):
        self.db = db
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.reranker = reranker
    
    async def advanced_chunk_search(
        self,
        question: str,
        collection_name: str,
        project_id: UUID,
        top_k: int = 5,
        strategy: Optional[Dict] = None
    ) -> tuple:
        """
        Расширенный поиск чанков с использованием множественных техник:
        1. Hybrid Search (Semantic + Keyword/BM25)
        2. Query Expansion и Multiple Retrievals
        3. Iteracyjne wyszukiwanie z reformulacją query
        4. Keyword search как fallback
        
        Args:
            question: Вопрос пользователя
            collection_name: Имя коллекции в векторной БД
            project_id: ID проекта
            top_k: Количество результатов
            strategy: Стратегия от AI агента
            
        Returns:
            Tuple (chunk_texts, similar_chunks) - найденные чанки
        """
        chunk_texts = []
        similar_chunks = []
        all_found_chunks = {}  # Для дедупликации по тексту
        
        try:
            # ТЕХНИКА 1: Hybrid Search (Semantic + BM25)
            logger.info(f"[RAG RETRIEVAL] Technique 1: Hybrid Search (Semantic + BM25)")
            try:
                qdrant_loader = QdrantLoader(collection_name=collection_name)
                hybrid_results = await qdrant_loader.search(
                    query=question,
                    top_k=top_k * 2,
                    score_threshold=0.4,  # Более низкий порог для большего охвата
                    search_strategy="hybrid",
                    dense_weight=0.5,
                    bm25_weight=0.5,
                    project_id=str(project_id)
                )
                
                for result in hybrid_results:
                    text = result.get("text", "")
                    if text and len(text) > 20:  # Минимальная длина чанка
                        text_key = text[:100]  # Ключ для дедупликации
                        if text_key not in all_found_chunks:
                            score = result.get("score", 0.5)
                            all_found_chunks[text_key] = {
                                "text": text,
                                "source": result.get("source_url", result.get("filename", "Документ")),
                                "score": score,
                                "method": "hybrid"
                            }
                            similar_chunks.append({
                                "payload": {"chunk_text": text},
                                "score": score
                            })
                
                if all_found_chunks:
                    logger.info(f"[RAG RETRIEVAL] Hybrid search found {len(all_found_chunks)} unique chunks")
            except Exception as e:
                logger.warning(f"[RAG RETRIEVAL] Hybrid search failed: {e}")
            
            # ТЕХНИКА 2: Query Expansion и Multiple Retrievals
            if len(all_found_chunks) < top_k:
                logger.info(f"[RAG RETRIEVAL] Technique 2: Query Expansion and Multiple Retrievals")
                try:
                    # Создаем варианты запроса
                    query_variants = self.expand_query(question)
                    
                    for variant in query_variants:
                        if len(all_found_chunks) >= top_k * 2:
                            break
                        
                        try:
                            variant_embedding = await self.embedding_service.create_embedding(variant)
                            variant_chunks = await self.vector_store.search_similar(
                                collection_name=collection_name,
                                query_vector=variant_embedding,
                                limit=top_k,
                                score_threshold=0.3  # Еще более низкий порог для вариантов
                            )
                            
                            for chunk in variant_chunks:
                                payload = chunk.get("payload", {})
                                text = payload.get("chunk_text", "")
                                if text and len(text) > 20:
                                    text_key = text[:100]
                                    if text_key not in all_found_chunks:
                                        score = chunk.get("score", 0.4) * 0.9  # Немного снижаем score для вариантов
                                        all_found_chunks[text_key] = {
                                            "text": text,
                                            "source": payload.get("filename", payload.get("source_url", "Документ")),
                                            "score": score,
                                            "method": "query_expansion"
                                        }
                                        similar_chunks.append({
                                            "payload": payload,
                                            "score": score
                                        })
                        except Exception as e:
                            logger.debug(f"[RAG RETRIEVAL] Query variant '{variant}' failed: {e}")
                            continue
                    
                    if all_found_chunks:
                        logger.info(f"[RAG RETRIEVAL] Query expansion found {len(all_found_chunks)} total unique chunks")
                except Exception as e:
                    logger.warning(f"[RAG RETRIEVAL] Query expansion failed: {e}")
            
            # ТЕХНИКА 3: Iteracyjne wyszukiwanie z reformulacją query через LLM + follow-up вопросы
            if len(all_found_chunks) < top_k:
                logger.info(f"[RAG RETRIEVAL] Technique 3: Iterative search with query reformulation and follow-up questions")
                try:
                    # Первая итерация: переформулируем запрос через LLM
                    reformulated_queries = await self.reformulate_query(question, project_id)
                    
                    for reformulated in reformulated_queries:
                        if len(all_found_chunks) >= top_k * 3:
                            break
                        
                        try:
                            reform_embedding = await self.embedding_service.create_embedding(reformulated)
                            reform_chunks = await self.vector_store.search_similar(
                                collection_name=collection_name,
                                query_vector=reform_embedding,
                                limit=top_k,
                                score_threshold=0.35
                            )
                            
                            for chunk in reform_chunks:
                                payload = chunk.get("payload", {})
                                text = payload.get("chunk_text", "")
                                if text and len(text) > 20:
                                    text_key = text[:100]
                                    if text_key not in all_found_chunks:
                                        score = chunk.get("score", 0.4) * 0.85
                                        all_found_chunks[text_key] = {
                                            "text": text,
                                            "source": payload.get("filename", payload.get("source_url", "Документ")),
                                            "score": score,
                                            "method": "iterative_reformulation"
                                        }
                                        similar_chunks.append({
                                            "payload": payload,
                                            "score": score
                                        })
                        except Exception as e:
                            logger.debug(f"[RAG RETRIEVAL] Reformulated query '{reformulated}' failed: {e}")
                            continue
                    
                    # Вторая итерация: генерируем follow-up вопросы на основе найденных фрагментов
                    if len(all_found_chunks) > 0 and len(all_found_chunks) < top_k:
                        logger.info(f"[RAG RETRIEVAL] Generating follow-up questions based on found chunks")
                        try:
                            # Берем первые несколько найденных чанков для анализа
                            sample_chunks = list(all_found_chunks.values())[:3]
                            follow_up_queries = await self.generate_followup_questions(question, sample_chunks, project_id)
                            
                            for follow_up in follow_up_queries:
                                if len(all_found_chunks) >= top_k * 2:
                                    break
                                
                                try:
                                    follow_embedding = await self.embedding_service.create_embedding(follow_up)
                                    follow_chunks = await self.vector_store.search_similar(
                                        collection_name=collection_name,
                                        query_vector=follow_embedding,
                                        limit=top_k // 2,
                                        score_threshold=0.3
                                    )
                                    
                                    for chunk in follow_chunks:
                                        payload = chunk.get("payload", {})
                                        text = payload.get("chunk_text", "")
                                        if text and len(text) > 20:
                                            text_key = text[:100]
                                            if text_key not in all_found_chunks:
                                                score = chunk.get("score", 0.3) * 0.8
                                                all_found_chunks[text_key] = {
                                                    "text": text,
                                                    "source": payload.get("filename", payload.get("source_url", "Документ")),
                                                    "score": score,
                                                    "method": "iterative_followup"
                                                }
                                                similar_chunks.append({
                                                    "payload": payload,
                                                    "score": score
                                                })
                                except Exception as e:
                                    logger.debug(f"[RAG RETRIEVAL] Follow-up query '{follow_up}' failed: {e}")
                                    continue
                        except Exception as e:
                            logger.warning(f"[RAG RETRIEVAL] Follow-up questions generation failed: {e}")
                    
                    if all_found_chunks:
                        logger.info(f"[RAG RETRIEVAL] Iterative search found {len(all_found_chunks)} total unique chunks")
                except Exception as e:
                    logger.warning(f"[RAG RETRIEVAL] Iterative search failed: {e}")
            
            # ТЕХНИКА 4: Keyword Search как дополнительный fallback
            if len(all_found_chunks) < top_k:
                logger.info(f"[RAG RETRIEVAL] Technique 4: Keyword search fallback")
                try:
                    keyword_chunks = await self.keyword_search_chunks(
                        question=question,
                        collection_name=collection_name,
                        project_id=project_id,
                        top_k=top_k
                    )
                    
                    for chunk_data in keyword_chunks:
                        text = chunk_data.get("text", "")
                        if text and len(text) > 20:
                            text_key = text[:100]
                            if text_key not in all_found_chunks:
                                all_found_chunks[text_key] = chunk_data
                                similar_chunks.append({
                                    "payload": {"chunk_text": text},
                                    "score": chunk_data.get("score", 0.3)
                                })
                    
                    if keyword_chunks:
                        logger.info(f"[RAG RETRIEVAL] Keyword search found {len(keyword_chunks)} additional chunks")
                except Exception as e:
                    logger.warning(f"[RAG RETRIEVAL] Keyword search failed: {e}")
            
            # Сортируем и берем лучшие результаты для reranking
            chunk_texts_list = sorted(
                all_found_chunks.values(),
                key=lambda x: x.get("score", 0),
                reverse=True
            )[:top_k * 3]  # Берем больше для reranking
            
            # RERANKING: Переранжируем результаты для улучшения релевантности
            if chunk_texts_list:
                logger.info(f"[RAG RETRIEVAL] Reranking {len(chunk_texts_list)} chunks for better relevance")
                chunk_texts = self.reranker.rerank(
                    question=question,
                    chunks=chunk_texts_list,
                    top_k=top_k * 2  # После reranking берем лучшие
                )
                logger.info(f"[RAG RETRIEVAL] Reranking completed: {len(chunk_texts)} top chunks selected")
            else:
                chunk_texts = []
            
            logger.info(f"[RAG RETRIEVAL] Advanced search completed: {len(chunk_texts)} final chunks")
            
        except Exception as e:
            logger.error(f"[RAG RETRIEVAL] Advanced chunk search error: {e}", exc_info=True)
        
        return chunk_texts, similar_chunks[:top_k * 2]

    
    def expand_query(self, question: str) -> List[str]:
        """
        Расширяет запрос на несколько вариантов для лучшего поиска
        
        Args:
            question: Оригинальный вопрос
            
        Returns:
            Список вариантов запроса
        """
        variants = [question]  # Всегда включаем оригинал
        
        # Извлекаем ключевые слова
        import re
        words = re.findall(r'\b\w+\b', question.lower())
        keywords = [w for w in words if len(w) > 3][:5]
        
        if keywords:
            # Вариант 1: Только ключевые слова
            variants.append(" ".join(keywords))
            
            # Вариант 2: Вопрос без стоп-слов
            stop_words = {"что", "как", "где", "когда", "почему", "кто", "какой", "какая", "какое", "the", "a", "an", "is", "are", "was", "were"}
            filtered_words = [w for w in words if w not in stop_words and len(w) > 2]
            if filtered_words:
                variants.append(" ".join(filtered_words))
        
        # Вариант 3: Упрощенная версия (первые слова)
        if len(words) > 3:
            variants.append(" ".join(words[:5]))
        
        return list(set(variants))[:5]  # Максимум 5 вариантов

    
    async def reformulate_query(self, question: str, project_id: UUID) -> List[str]:
        """
        Переформулирует запрос через LLM для лучшего поиска
        
        Args:
            question: Оригинальный вопрос
            project_id: ID проекта
            
        Returns:
            Список переформулированных запросов
        """
        try:
            from app.llm.openrouter_client import OpenRouterClient
            from app.models.llm_model import GlobalModelSettings
            from sqlalchemy import select
            
            # Получаем модель для переформулировки
            settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
            global_settings = settings_result.scalar_one_or_none()
            
            primary_model = global_settings.primary_model_id if global_settings else None
            fallback_model = global_settings.fallback_model_id if global_settings else None
            
            if not primary_model:
                from app.core.config import settings as app_settings
                primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
                fallback_model = fallback_model or app_settings.OPENROUTER_MODEL_FALLBACK
            
            llm_client = OpenRouterClient(
                model_primary=primary_model,
                model_fallback=fallback_model
            )
            
            reformulate_prompt = f"""Переформулируй следующий вопрос в 2-3 разных варианта для поиска информации в документах.
Каждый вариант должен быть оптимизирован для поиска релевантных фрагментов текста.

Оригинальный вопрос: {question}

Верни только варианты вопросов, каждый с новой строки, без нумерации и дополнительных комментариев."""
            
            messages = [
                {"role": "system", "content": "Ты помощник, который переформулирует вопросы для лучшего поиска информации."},
                {"role": "user", "content": reformulate_prompt}
            ]
            
            response = await llm_client.chat_completion(
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )
            
            # Парсим ответ - каждая строка это вариант
            reformulated = [line.strip() for line in response.strip().split("\n") if line.strip() and len(line.strip()) > 10]
            return reformulated[:3]  # Максимум 3 варианта
            
        except Exception as e:
            logger.warning(f"[RAG RETRIEVAL] Query reformulation failed: {e}")
            return []

    
    async def keyword_search_chunks(
        self,
        question: str,
        collection_name: str,
        project_id: UUID,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Keyword search по чанкам в БД
        
        Args:
            question: Вопрос пользователя
            collection_name: Имя коллекции
            project_id: ID проекта
            top_k: Количество результатов
            
        Returns:
            Список найденных чанков
        """
        try:
            from app.models.document import Document, DocumentChunk
            from sqlalchemy import select, text
            import re
            
            # Извлекаем ключевые слова
            keywords = set(re.findall(r'\b\w+\b', question.lower()))
            keywords = {w for w in keywords if len(w) > 3}  # Слова длиннее 3 символов
            
            if not keywords:
                return []
            
            # Ищем чанки содержащие ключевые слова
            try:
                result = await self.db.execute(
                    select(DocumentChunk)
                    .join(Document)
                    .where(Document.project_id == project_id)
                    .where(DocumentChunk.chunk_text.isnot(None))
                    .where(DocumentChunk.chunk_text != "")
                    .limit(top_k * 3)
                )
                db_chunks = result.scalars().all()
            except Exception:
                # Fallback на raw SQL
                result = await self.db.execute(
                    text("""
                        SELECT dc.id, dc.chunk_text, d.filename
                        FROM document_chunks dc
                        JOIN documents d ON dc.document_id = d.id
                        WHERE d.project_id = :project_id
                        AND dc.chunk_text IS NOT NULL
                        AND dc.chunk_text != ''
                        LIMIT :limit
                    """),
                    {"project_id": str(project_id), "limit": top_k * 3}
                )
                rows = result.all()
                db_chunks = []
                for row in rows:
                    chunk = DocumentChunk()
                    chunk.id = row[0]
                    chunk.chunk_text = row[1]
                    doc = Document()
                    doc.filename = row[2]
                    chunk.document = doc
                    db_chunks.append(chunk)
            
            # Ранжируем по количеству совпадающих ключевых слов
            scored_chunks = []
            for chunk in db_chunks:
                chunk_text_lower = chunk.chunk_text.lower()
                matches = sum(1 for kw in keywords if kw in chunk_text_lower)
                if matches > 0:
                    score = min(0.9, 0.3 + (matches / len(keywords)) * 0.6)
                    scored_chunks.append({
                        "text": chunk.chunk_text,
                        "source": chunk.document.filename if chunk.document else "Документ",
                        "score": score,
                        "method": "keyword_search"
                    })
            
            # Сортируем по score
            scored_chunks.sort(key=lambda x: x["score"], reverse=True)
            return scored_chunks[:top_k]
            
        except Exception as e:
            logger.warning(f"[RAG RETRIEVAL] Keyword search error: {e}")
            return []

    
    async def generate_followup_questions(
        self,
        question: str,
        sample_chunks: List[Dict],
        project_id: UUID
    ) -> List[str]:
        """
        Генерирует follow-up вопросы на основе найденных фрагментов для итеративного поиска
        
        Args:
            question: Оригинальный вопрос
            sample_chunks: Примеры найденных чанков
            project_id: ID проекта
            
        Returns:
            Список follow-up вопросов
        """
        try:
            from app.llm.openrouter_client import OpenRouterClient
            from app.models.llm_model import GlobalModelSettings
            from sqlalchemy import select
            
            # Получаем модель для генерации вопросов
            settings_result = await self.db.execute(select(GlobalModelSettings).limit(1))
            global_settings = settings_result.scalar_one_or_none()
            
            primary_model = global_settings.primary_model_id if global_settings else None
            fallback_model = global_settings.fallback_model_id if global_settings else None
            
            if not primary_model:
                from app.core.config import settings as app_settings
                primary_model = app_settings.OPENROUTER_MODEL_PRIMARY
                fallback_model = fallback_model or app_settings.OPENROUTER_MODEL_FALLBACK
            
            llm_client = OpenRouterClient(
                model_primary=primary_model,
                model_fallback=fallback_model
            )
            
            # Формируем контекст из найденных чанков
            chunks_text = "\n\n".join([chunk.get("text", "")[:300] for chunk in sample_chunks[:3]])
            
            followup_prompt = f"""На основе следующего вопроса и найденных фрагментов документов, сгенерируй 2-3 дополнительных вопроса для более глубокого поиска информации.

Оригинальный вопрос: {question}

Найденные фрагменты:
{chunks_text}

Сгенерируй вопросы, которые помогут найти более релевантную информацию. Каждый вопрос с новой строки, без нумерации."""
            
            messages = [
                {"role": "system", "content": "Ты помощник, который генерирует дополнительные вопросы для улучшения поиска информации."},
                {"role": "user", "content": followup_prompt}
            ]
            
            response = await llm_client.chat_completion(
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )
            
            # Парсим вопросы
            followup_questions = [line.strip() for line in response.strip().split("\n") if line.strip() and len(line.strip()) > 10]
            return followup_questions[:3]  # Максимум 3 вопроса
            
        except Exception as e:
            logger.warning(f"[RAG RETRIEVAL] Follow-up questions generation failed: {e}")
            return []
