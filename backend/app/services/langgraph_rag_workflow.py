"""
LangGraph RAG Workflow для анализа больших документов
Поддерживает:
- Анализ PDF документов любого размера
- Формирование резюме с минимальными искажениями
- Ответы на вопросы на основе документов
- Описание содержания документа
"""
import logging
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from uuid import UUID
from enum import Enum
import operator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Попытка импортировать LangGraph
try:
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph не установлен. Установите: pip install langgraph langchain-core")


class QueryType(str, Enum):
    """Типы запросов для RAG"""
    QUESTION = "question"  # Ответ на вопрос
    SUMMARY = "summary"  # Резюме документа/блока
    DESCRIPTION = "description"  # Описание содержания документа
    ANALYSIS = "analysis"  # Глубокий анализ документа


@dataclass
class RAGConfig:
    """Конфигурация RAG workflow"""
    # Рекомендуемые значения для разных моделей
    
    # Для GPT-4 / Claude: макс. контекст ~128k токенов
    # Для GPT-3.5: макс. контекст ~16k токенов
    # Для DeepSeek: макс. контекст ~64k токенов
    
    max_context_tokens: int = 100000  # Максимум токенов контекста
    max_output_tokens: int = 4096  # Максимум токенов ответа
    chunk_size: int = 1500  # Размер чанка (символов)
    chunk_overlap: int = 300  # Перекрытие чанков
    top_k_retrieval: int = 10  # Количество чанков для поиска
    temperature: float = 0.2  # Низкая температура для точности
    
    # Промпты для разных типов запросов
    system_prompts: Dict[QueryType, str] = None
    
    def __post_init__(self):
        if self.system_prompts is None:
            self.system_prompts = {
                QueryType.QUESTION: """Ты эксперт-аналитик. Отвечай на вопросы ТОЛЬКО на основе предоставленного контекста.
                
Правила:
1. Если информации нет в контексте - честно скажи об этом
2. Цитируй конкретные факты из контекста
3. Используй точные цифры, даты, названия из документа
4. Отвечай структурированно и по существу
5. Язык ответа: русский""",
                
                QueryType.SUMMARY: """Ты эксперт по созданию точных резюме документов.

Задача: Создать краткое, но полное резюме документа.

Требования:
1. Длина: 500-1000 символов
2. Включи ВСЕ ключевые темы и факты
3. Сохрани точность: цифры, даты, имена, термины
4. Структура: главная тема → ключевые пункты → выводы
5. Минимальные искажения - не добавляй информацию, которой нет
6. Язык: русский""",
                
                QueryType.DESCRIPTION: """Ты аналитик документов. Твоя задача - описать содержание документа.

Требования:
1. Опиши основные темы и разделы документа
2. Укажи тип документа (отчет, инструкция, договор и т.д.)
3. Перечисли ключевые сущности (компании, люди, даты, суммы)
4. Кратко опиши структуру документа
5. Язык: русский""",
                
                QueryType.ANALYSIS: """Ты глубокий аналитик документов.

Задача: Провести детальный анализ документа.

Требования:
1. Определи тип и назначение документа
2. Выдели ключевые факты и данные
3. Проанализируй структуру и логику документа
4. Выяви важные связи между частями документа
5. Сделай выводы на основе содержимого
6. Язык: русский"""
            }


class RAGState(TypedDict):
    """Состояние RAG workflow"""
    query: str
    query_type: QueryType
    project_id: str
    document_id: Optional[str]
    chunks: List[Dict[str, Any]]
    context: str
    answer: str
    sources: List[str]
    confidence: float
    error: Optional[str]
    metadata: Dict[str, Any]


class LangGraphRAGWorkflow:
    """LangGraph RAG Workflow для обработки документов"""
    
    def __init__(
        self,
        db: AsyncSession,
        config: Optional[RAGConfig] = None
    ):
        self.db = db
        self.config = config or RAGConfig()
        self._workflow = None
        
        if LANGGRAPH_AVAILABLE:
            self._build_workflow()
    
    def _build_workflow(self):
        """Построение LangGraph workflow"""
        workflow = StateGraph(RAGState)
        
        # Добавляем ноды
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("build_context", self._build_context_node)
        workflow.add_node("generate", self._generate_node)
        workflow.add_node("format_output", self._format_output_node)
        
        # Определяем граф
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "build_context")
        workflow.add_edge("build_context", "generate")
        workflow.add_edge("generate", "format_output")
        workflow.add_edge("format_output", END)
        
        self._workflow = workflow.compile()
    
    async def _retrieve_node(self, state: RAGState) -> RAGState:
        """Нода поиска релевантных чанков"""
        logger.info(f"[LangGraph RAG] Retrieving chunks for query: {state['query'][:50]}...")
        
        try:
            from app.services.embedding_service import EmbeddingService
            from app.vector_db.vector_store import VectorStore
            
            embedding_service = EmbeddingService()
            vector_store = VectorStore()
            
            # Создаем embedding для запроса
            query_embedding = await embedding_service.create_embedding(state['query'])
            
            # Определяем коллекцию
            collection_name = f"project_{state['project_id']}"
            
            # Поиск похожих чанков
            results = await vector_store.search_similar(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=self.config.top_k_retrieval * 2,  # Берем больше для фильтрации
                score_threshold=0.3  # Низкий порог для полноты
            )
            
            # Фильтруем по document_id если указан
            if state.get('document_id'):
                results = [
                    r for r in results 
                    if r.get('payload', {}).get('document_id') == state['document_id']
                ]
            
            # Преобразуем в чанки
            chunks = []
            for r in results[:self.config.top_k_retrieval]:
                payload = r.get('payload', {})
                chunk = {
                    'text': payload.get('chunk_text', ''),
                    'document_id': payload.get('document_id', ''),
                    'filename': payload.get('filename', ''),
                    'chunk_index': payload.get('chunk_index', 0),
                    'score': r.get('score', 0.0)
                }
                if chunk['text']:
                    chunks.append(chunk)
            
            logger.info(f"[LangGraph RAG] Retrieved {len(chunks)} chunks")
            
            # Если мало чанков, пробуем получить из БД напрямую
            if len(chunks) < 3 and state.get('document_id'):
                chunks = await self._get_chunks_from_db(state['document_id'])
            
            state['chunks'] = chunks
            state['metadata'] = {
                **state.get('metadata', {}),
                'chunks_retrieved': len(chunks)
            }
            
        except Exception as e:
            logger.error(f"[LangGraph RAG] Retrieval error: {e}", exc_info=True)
            state['chunks'] = []
            state['error'] = f"Ошибка поиска: {str(e)}"
        
        return state
    
    async def _get_chunks_from_db(self, document_id: str) -> List[Dict[str, Any]]:
        """Получение чанков напрямую из БД"""
        from app.models.document import Document, DocumentChunk
        
        try:
            # Сначала пробуем получить чанки из таблицы chunks
            result = await self.db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == UUID(document_id))
                .order_by(DocumentChunk.chunk_index)
                .limit(50)
            )
            db_chunks = result.scalars().all()
            
            if db_chunks:
                return [
                    {
                        'text': chunk.chunk_text,
                        'document_id': str(document_id),
                        'chunk_index': chunk.chunk_index,
                        'score': 1.0
                    }
                    for chunk in db_chunks
                ]
            
            # Если нет чанков, используем content документа
            result = await self.db.execute(
                select(Document).where(Document.id == UUID(document_id))
            )
            document = result.scalar_one_or_none()
            
            if document and document.content:
                # Разбиваем контент на чанки
                from app.documents.chunker import DocumentChunker
                chunker = DocumentChunker(
                    chunk_size=self.config.chunk_size,
                    chunk_overlap=self.config.chunk_overlap
                )
                text_chunks = chunker.chunk_text(document.content)
                
                return [
                    {
                        'text': text,
                        'document_id': str(document_id),
                        'filename': document.filename,
                        'chunk_index': i,
                        'score': 1.0
                    }
                    for i, text in enumerate(text_chunks[:50])
                ]
        
        except Exception as e:
            logger.error(f"[LangGraph RAG] DB chunks error: {e}")
        
        return []
    
    async def _build_context_node(self, state: RAGState) -> RAGState:
        """Нода построения контекста из чанков"""
        logger.info(f"[LangGraph RAG] Building context from {len(state['chunks'])} chunks")
        
        chunks = state['chunks']
        if not chunks:
            state['context'] = ""
            state['sources'] = []
            return state
        
        # Сортируем по score и chunk_index
        chunks_sorted = sorted(
            chunks, 
            key=lambda x: (-x.get('score', 0), x.get('chunk_index', 0))
        )
        
        # Формируем контекст с учетом лимита токенов
        # Примерная оценка: 1 токен ≈ 4 символа для русского текста
        max_context_chars = self.config.max_context_tokens * 3
        
        context_parts = []
        current_length = 0
        sources = set()
        
        for chunk in chunks_sorted:
            text = chunk.get('text', '')
            filename = chunk.get('filename', 'Документ')
            chunk_index = chunk.get('chunk_index', 0)
            
            if not text:
                continue
            
            # Форматируем чанк
            formatted = f"[{filename}, часть {chunk_index + 1}]\n{text}\n"
            
            if current_length + len(formatted) > max_context_chars:
                break
            
            context_parts.append(formatted)
            current_length += len(formatted)
            sources.add(filename)
        
        context = "\n---\n".join(context_parts)
        
        state['context'] = context
        state['sources'] = list(sources)
        state['metadata'] = {
            **state.get('metadata', {}),
            'context_length': len(context),
            'chunks_used': len(context_parts)
        }
        
        logger.info(f"[LangGraph RAG] Context built: {len(context)} chars from {len(context_parts)} chunks")
        
        return state
    
    async def _generate_node(self, state: RAGState) -> RAGState:
        """Нода генерации ответа через LLM"""
        logger.info(f"[LangGraph RAG] Generating response for query type: {state['query_type']}")
        
        try:
            from app.llm.openrouter_client import OpenRouterClient
            
            # Получаем системный промпт для типа запроса
            query_type = state['query_type']
            system_prompt = self.config.system_prompts.get(
                query_type, 
                self.config.system_prompts[QueryType.QUESTION]
            )
            
            # Формируем промпт в зависимости от типа запроса
            context = state['context']
            query = state['query']
            
            if query_type == QueryType.SUMMARY:
                user_prompt = f"""Создай точное резюме следующего документа:

СОДЕРЖИМОЕ ДОКУМЕНТА:
{context}

РЕЗЮМЕ:"""
            
            elif query_type == QueryType.DESCRIPTION:
                user_prompt = f"""Опиши содержание следующего документа:

СОДЕРЖИМОЕ ДОКУМЕНТА:
{context}

ОПИСАНИЕ:"""
            
            elif query_type == QueryType.ANALYSIS:
                user_prompt = f"""Проведи детальный анализ следующего документа:

СОДЕРЖИМОЕ ДОКУМЕНТА:
{context}

АНАЛИЗ:"""
            
            else:  # QueryType.QUESTION
                if context:
                    user_prompt = f"""На основе следующего контекста ответь на вопрос пользователя.

КОНТЕКСТ ИЗ ДОКУМЕНТОВ:
{context}

ВОПРОС: {query}

ОТВЕТ:"""
                else:
                    user_prompt = f"""Вопрос: {query}

К сожалению, в документах не найдено релевантной информации для ответа на этот вопрос.
Сообщи пользователю об этом и предложи уточнить вопрос."""
            
            # Вызываем LLM
            llm_client = OpenRouterClient()
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await llm_client.chat_completion_with_usage(
                messages=messages,
                max_tokens=self.config.max_output_tokens,
                temperature=self.config.temperature
            )
            
            state['answer'] = response['content']
            state['confidence'] = 1.0 if context else 0.5
            state['metadata'] = {
                **state.get('metadata', {}),
                'model': response.get('model', 'unknown'),
                'input_tokens': response.get('input_tokens', 0),
                'output_tokens': response.get('output_tokens', 0)
            }
            
            logger.info(f"[LangGraph RAG] Generated answer: {len(state['answer'])} chars")
            
        except Exception as e:
            logger.error(f"[LangGraph RAG] Generation error: {e}", exc_info=True)
            state['answer'] = f"Ошибка генерации ответа: {str(e)}"
            state['error'] = str(e)
            state['confidence'] = 0.0
        
        return state
    
    async def _format_output_node(self, state: RAGState) -> RAGState:
        """Нода форматирования финального ответа"""
        answer = state['answer']
        sources = state['sources']
        
        # Очищаем ответ от лишних пробелов
        answer = answer.strip()
        
        # Добавляем источники если есть
        if sources and state['query_type'] in [QueryType.QUESTION]:
            sources_text = ", ".join(sources[:3])
            answer += f"\n\n📄 Источники: {sources_text}"
        
        state['answer'] = answer
        
        return state
    
    async def run(
        self,
        query: str,
        query_type: QueryType = QueryType.QUESTION,
        project_id: str = None,
        document_id: str = None
    ) -> Dict[str, Any]:
        """
        Запуск RAG workflow
        
        Args:
            query: Текст запроса
            query_type: Тип запроса (вопрос, резюме, описание, анализ)
            project_id: ID проекта
            document_id: ID конкретного документа (опционально)
        
        Returns:
            Словарь с ответом, источниками и метаданными
        """
        if not LANGGRAPH_AVAILABLE:
            return await self._fallback_run(query, query_type, project_id, document_id)
        
        initial_state: RAGState = {
            'query': query,
            'query_type': query_type,
            'project_id': project_id or '',
            'document_id': document_id,
            'chunks': [],
            'context': '',
            'answer': '',
            'sources': [],
            'confidence': 0.0,
            'error': None,
            'metadata': {}
        }
        
        try:
            # Запускаем workflow
            final_state = await self._workflow.ainvoke(initial_state)
            
            return {
                'answer': final_state['answer'],
                'sources': final_state['sources'],
                'confidence': final_state['confidence'],
                'error': final_state.get('error'),
                'metadata': final_state.get('metadata', {})
            }
        
        except Exception as e:
            logger.error(f"[LangGraph RAG] Workflow error: {e}", exc_info=True)
            return await self._fallback_run(query, query_type, project_id, document_id)
    
    async def _fallback_run(
        self,
        query: str,
        query_type: QueryType,
        project_id: str,
        document_id: str
    ) -> Dict[str, Any]:
        """Fallback метод без LangGraph"""
        logger.info("[LangGraph RAG] Using fallback method (without LangGraph)")
        
        state: RAGState = {
            'query': query,
            'query_type': query_type,
            'project_id': project_id or '',
            'document_id': document_id,
            'chunks': [],
            'context': '',
            'answer': '',
            'sources': [],
            'confidence': 0.0,
            'error': None,
            'metadata': {}
        }
        
        # Последовательно вызываем ноды
        state = await self._retrieve_node(state)
        state = await self._build_context_node(state)
        state = await self._generate_node(state)
        state = await self._format_output_node(state)
        
        return {
            'answer': state['answer'],
            'sources': state['sources'],
            'confidence': state['confidence'],
            'error': state.get('error'),
            'metadata': state.get('metadata', {})
        }
    
    # === Удобные методы для типовых запросов ===
    
    async def answer_question(
        self,
        question: str,
        project_id: str,
        document_id: str = None
    ) -> str:
        """Ответ на вопрос пользователя"""
        result = await self.run(
            query=question,
            query_type=QueryType.QUESTION,
            project_id=project_id,
            document_id=document_id
        )
        return result['answer']
    
    async def generate_summary(
        self,
        project_id: str,
        document_id: str = None
    ) -> str:
        """Создание резюме документа"""
        result = await self.run(
            query="Создай резюме документа",
            query_type=QueryType.SUMMARY,
            project_id=project_id,
            document_id=document_id
        )
        return result['answer']
    
    async def describe_content(
        self,
        project_id: str,
        document_id: str = None
    ) -> str:
        """Описание содержания документа"""
        result = await self.run(
            query="Опиши содержание документа",
            query_type=QueryType.DESCRIPTION,
            project_id=project_id,
            document_id=document_id
        )
        return result['answer']
    
    async def analyze_document(
        self,
        project_id: str,
        document_id: str = None
    ) -> str:
        """Глубокий анализ документа"""
        result = await self.run(
            query="Проанализируй документ",
            query_type=QueryType.ANALYSIS,
            project_id=project_id,
            document_id=document_id
        )
        return result['answer']


# === Рекомендации по использованию ===
"""
РЕКОМЕНДАЦИИ ПО МОДЕЛЯМ И ПАРАМЕТРАМ:

1. Для анализа больших документов (>100 страниц):
   - Модель: Claude 3.5 Sonnet или GPT-4 Turbo (большой контекст)
   - chunk_size: 2000 символов
   - chunk_overlap: 400 символов
   - top_k_retrieval: 15-20
   - max_context_tokens: 100000

2. Для быстрых ответов на вопросы:
   - Модель: GPT-3.5 Turbo или DeepSeek Chat
   - chunk_size: 1000 символов
   - chunk_overlap: 200 символов
   - top_k_retrieval: 5-10
   - max_context_tokens: 15000

3. Для создания резюме с минимальными искажениями:
   - Модель: Claude 3.5 Sonnet (лучшая точность)
   - temperature: 0.1-0.2 (низкая для точности)
   - chunk_size: 1500 символов
   - Использовать QueryType.SUMMARY

4. Формат промптов:
   - Для вопросов: "На основе контекста ответь на вопрос..."
   - Для резюме: "Создай точное резюме, сохраняя факты..."
   - Для описания: "Опиши структуру и содержание документа..."

5. Объём текста:
   - Оптимальный размер чанка: 1000-2000 символов
   - Максимум чанков в контексте: 10-20
   - Общий контекст: 30-50K символов для точности
"""
