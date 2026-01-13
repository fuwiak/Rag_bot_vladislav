"""
LangGraph Conversation Workflow для обработки диалогов с контекстом
Поддерживает:
- История диалогов
- Контекстное понимание
- RAG интеграция
- Маршрутизация запросов
"""
import logging
from typing import List, Dict, Any, Optional, TypedDict, Literal
from uuid import UUID
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

logger = logging.getLogger(__name__)

# Попытка импортировать LangGraph
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph не установлен для conversation workflow")


class ConversationState(TypedDict):
    """Состояние Conversation Workflow"""
    user_id: str
    project_id: str
    message: str
    intent: str  # question, summary, description, general, greeting
    conversation_history: List[Dict[str, str]]
    rag_context: str
    response: str
    use_rag: bool
    sources: List[str]
    metadata: Dict[str, Any]


class ConversationIntent(str, Enum):
    """Интенты пользователя"""
    QUESTION = "question"  # Вопрос о документах
    SUMMARY = "summary"  # Запрос резюме
    DESCRIPTION = "description"  # Запрос описания
    GENERAL = "general"  # Общий вопрос (не о документах)
    GREETING = "greeting"  # Приветствие


class LangGraphConversationWorkflow:
    """LangGraph Workflow для обработки диалогов"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._workflow = None
        
        # Ключевые слова для определения интента
        self.intent_keywords = {
            ConversationIntent.SUMMARY: [
                "резюме", "краткое содержание", "кратко", "summary", 
                "основные моменты", "ключевые пункты", "выжимка"
            ],
            ConversationIntent.DESCRIPTION: [
                "опиши", "описание", "describe", "что содержит", 
                "о чем документ", "структура документа", "содержание"
            ],
            ConversationIntent.GREETING: [
                "привет", "здравствуй", "добрый день", "добрый вечер",
                "hello", "hi", "хай", "доброе утро"
            ],
            ConversationIntent.GENERAL: [
                "кто ты", "что ты умеешь", "помощь", "help",
                "как пользоваться", "инструкция"
            ]
        }
        
        if LANGGRAPH_AVAILABLE:
            self._build_workflow()
    
    def _build_workflow(self):
        """Построение conversation workflow"""
        workflow = StateGraph(ConversationState)
        
        # Добавляем ноды
        workflow.add_node("classify_intent", self._classify_intent_node)
        workflow.add_node("load_history", self._load_history_node)
        workflow.add_node("retrieve_context", self._retrieve_context_node)
        workflow.add_node("generate_response", self._generate_response_node)
        workflow.add_node("save_message", self._save_message_node)
        
        # Определяем граф
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "load_history")
        
        # Условная маршрутизация после load_history
        workflow.add_conditional_edges(
            "load_history",
            self._should_use_rag,
            {
                True: "retrieve_context",
                False: "generate_response"
            }
        )
        
        workflow.add_edge("retrieve_context", "generate_response")
        workflow.add_edge("generate_response", "save_message")
        workflow.add_edge("save_message", END)
        
        self._workflow = workflow.compile()
    
    def _should_use_rag(self, state: ConversationState) -> bool:
        """Определяет, нужен ли RAG для данного запроса"""
        intent = state.get('intent', 'question')
        
        # RAG не нужен для приветствий и общих вопросов о боте
        if intent in [ConversationIntent.GREETING.value, ConversationIntent.GENERAL.value]:
            return False
        
        # Явно указано не использовать RAG
        if not state.get('use_rag', True):
            return False
        
        return True
    
    async def _classify_intent_node(self, state: ConversationState) -> ConversationState:
        """Нода классификации интента пользователя"""
        message = state['message'].lower()
        
        # Проверяем ключевые слова
        for intent, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    state['intent'] = intent.value
                    logger.info(f"[Conversation] Intent classified: {intent.value}")
                    return state
        
        # По умолчанию - вопрос о документах
        state['intent'] = ConversationIntent.QUESTION.value
        return state
    
    async def _load_history_node(self, state: ConversationState) -> ConversationState:
        """Нода загрузки истории диалога"""
        try:
            from app.models.message import Message as MessageModel
            
            user_id = UUID(state['user_id'])
            
            result = await self.db.execute(
                select(MessageModel)
                .where(MessageModel.user_id == user_id)
                .order_by(desc(MessageModel.created_at))
                .limit(10)  # Последние 10 сообщений
            )
            messages = result.scalars().all()
            
            # Преобразуем в формат для LLM
            history = []
            for msg in reversed(messages):  # От старых к новым
                history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            state['conversation_history'] = history
            logger.info(f"[Conversation] Loaded {len(history)} messages from history")
            
        except Exception as e:
            logger.warning(f"[Conversation] Failed to load history: {e}")
            state['conversation_history'] = []
        
        return state
    
    async def _retrieve_context_node(self, state: ConversationState) -> ConversationState:
        """Нода получения RAG контекста"""
        try:
            from app.services.langgraph_rag_workflow import (
                LangGraphRAGWorkflow, 
                QueryType
            )
            
            # Определяем тип запроса для RAG
            intent = state['intent']
            if intent == ConversationIntent.SUMMARY.value:
                query_type = QueryType.SUMMARY
            elif intent == ConversationIntent.DESCRIPTION.value:
                query_type = QueryType.DESCRIPTION
            else:
                query_type = QueryType.QUESTION
            
            # Запускаем RAG workflow
            rag_workflow = LangGraphRAGWorkflow(self.db)
            result = await rag_workflow.run(
                query=state['message'],
                query_type=query_type,
                project_id=state['project_id']
            )
            
            state['rag_context'] = result.get('answer', '')
            state['sources'] = result.get('sources', [])
            state['metadata'] = {
                **state.get('metadata', {}),
                'rag_metadata': result.get('metadata', {})
            }
            
            logger.info(f"[Conversation] RAG context retrieved: {len(state['rag_context'])} chars")
            
        except Exception as e:
            logger.error(f"[Conversation] RAG retrieval error: {e}", exc_info=True)
            state['rag_context'] = ''
            state['sources'] = []
        
        return state
    
    async def _generate_response_node(self, state: ConversationState) -> ConversationState:
        """Нода генерации ответа"""
        intent = state['intent']
        
        # Для приветствий - шаблонный ответ
        if intent == ConversationIntent.GREETING.value:
            state['response'] = (
                "👋 Привет! Я бот-помощник для работы с документами.\n\n"
                "Я могу:\n"
                "📄 Отвечать на вопросы по документам\n"
                "📋 Создавать резюме документов (/summary)\n"
                "📝 Описывать содержание (/describe)\n"
                "💡 Предлагать вопросы (/suggest_questions)\n\n"
                "Просто задайте вопрос, и я найду ответ в документах!"
            )
            return state
        
        # Для общих вопросов о боте
        if intent == ConversationIntent.GENERAL.value:
            state['response'] = (
                "🤖 Я RAG-бот для работы с документами.\n\n"
                "Мои возможности:\n"
                "• Поиск информации в загруженных документах\n"
                "• Ответы на вопросы на основе документов\n"
                "• Создание резюме и описаний\n"
                "• Анализ содержимого PDF, Word, Excel\n\n"
                "Команды:\n"
                "/documents - список документов\n"
                "/summary - резюме документа\n"
                "/describe - описание содержания\n"
                "/suggest_questions - предложить вопросы"
            )
            return state
        
        # Если есть RAG контекст - используем его напрямую
        if state.get('rag_context'):
            state['response'] = state['rag_context']
            return state
        
        # Fallback - генерируем через LLM
        try:
            from app.llm.openrouter_client import OpenRouterClient
            
            llm_client = OpenRouterClient()
            
            # Формируем сообщения с историей
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты полезный ассистент. Отвечай на вопросы пользователя."
                        "Если не знаешь ответа, честно скажи об этом."
                    )
                }
            ]
            
            # Добавляем историю диалога
            for msg in state.get('conversation_history', [])[-5:]:
                messages.append(msg)
            
            # Добавляем текущее сообщение
            messages.append({
                "role": "user",
                "content": state['message']
            })
            
            response = await llm_client.chat_completion(
                messages=messages,
                max_tokens=2048,
                temperature=0.7
            )
            
            state['response'] = response
            
        except Exception as e:
            logger.error(f"[Conversation] Generation error: {e}", exc_info=True)
            state['response'] = "Извините, произошла ошибка. Попробуйте позже."
        
        return state
    
    async def _save_message_node(self, state: ConversationState) -> ConversationState:
        """Нода сохранения сообщений в историю"""
        try:
            from app.models.message import Message as MessageModel
            
            user_id = UUID(state['user_id'])
            
            # Сохраняем вопрос пользователя
            user_msg = MessageModel(
                user_id=user_id,
                content=state['message'],
                role="user",
                created_at=datetime.utcnow()
            )
            self.db.add(user_msg)
            
            # Сохраняем ответ бота
            bot_msg = MessageModel(
                user_id=user_id,
                content=state['response'],
                role="assistant",
                created_at=datetime.utcnow()
            )
            self.db.add(bot_msg)
            
            await self.db.commit()
            logger.info(f"[Conversation] Messages saved for user {user_id}")
            
        except Exception as e:
            logger.warning(f"[Conversation] Failed to save messages: {e}")
            await self.db.rollback()
        
        return state
    
    async def run(
        self,
        user_id: str,
        project_id: str,
        message: str,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Запуск conversation workflow
        
        Args:
            user_id: ID пользователя
            project_id: ID проекта
            message: Сообщение пользователя
            use_rag: Использовать RAG для поиска контекста
        
        Returns:
            Словарь с ответом и метаданными
        """
        initial_state: ConversationState = {
            'user_id': user_id,
            'project_id': project_id,
            'message': message,
            'intent': '',
            'conversation_history': [],
            'rag_context': '',
            'response': '',
            'use_rag': use_rag,
            'sources': [],
            'metadata': {}
        }
        
        try:
            if LANGGRAPH_AVAILABLE and self._workflow:
                final_state = await self._workflow.ainvoke(initial_state)
            else:
                # Fallback без LangGraph
                final_state = await self._fallback_run(initial_state)
            
            return {
                'response': final_state['response'],
                'intent': final_state['intent'],
                'sources': final_state['sources'],
                'metadata': final_state.get('metadata', {})
            }
        
        except Exception as e:
            logger.error(f"[Conversation] Workflow error: {e}", exc_info=True)
            return {
                'response': "Извините, произошла ошибка. Попробуйте позже.",
                'intent': 'error',
                'sources': [],
                'metadata': {'error': str(e)}
            }
    
    async def _fallback_run(self, state: ConversationState) -> ConversationState:
        """Fallback метод без LangGraph"""
        state = await self._classify_intent_node(state)
        state = await self._load_history_node(state)
        
        if self._should_use_rag(state):
            state = await self._retrieve_context_node(state)
        
        state = await self._generate_response_node(state)
        state = await self._save_message_node(state)
        
        return state


class ConversationHistoryIndexer:
    """Индексатор истории диалогов для поиска"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def index_conversation(
        self,
        user_id: str,
        messages: List[Dict[str, str]]
    ) -> bool:
        """
        Индексирует историю диалога для последующего поиска
        
        Args:
            user_id: ID пользователя
            messages: Список сообщений для индексации
        
        Returns:
            True если индексация успешна
        """
        try:
            from app.services.embedding_service import EmbeddingService
            from app.vector_db.vector_store import VectorStore
            
            embedding_service = EmbeddingService()
            vector_store = VectorStore()
            
            collection_name = f"conversations_{user_id}"
            
            for i, msg in enumerate(messages):
                content = msg.get('content', '')
                role = msg.get('role', 'user')
                
                if not content or len(content) < 10:
                    continue
                
                # Создаем embedding
                embedding = await embedding_service.create_embedding(content)
                
                # Сохраняем в Qdrant
                await vector_store.store_vector(
                    collection_name=collection_name,
                    vector=embedding,
                    payload={
                        'user_id': user_id,
                        'role': role,
                        'content': content,
                        'message_index': i,
                        'indexed_at': datetime.utcnow().isoformat()
                    }
                )
            
            logger.info(f"[ConversationIndexer] Indexed {len(messages)} messages for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[ConversationIndexer] Indexing error: {e}", exc_info=True)
            return False
    
    async def search_history(
        self,
        user_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Поиск по истории диалогов
        
        Args:
            user_id: ID пользователя
            query: Поисковый запрос
            limit: Количество результатов
        
        Returns:
            Список найденных сообщений
        """
        try:
            from app.services.embedding_service import EmbeddingService
            from app.vector_db.vector_store import VectorStore
            
            embedding_service = EmbeddingService()
            vector_store = VectorStore()
            
            # Создаем embedding для запроса
            query_embedding = await embedding_service.create_embedding(query)
            
            collection_name = f"conversations_{user_id}"
            
            # Поиск
            results = await vector_store.search_similar(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=0.5
            )
            
            return [
                {
                    'content': r.get('payload', {}).get('content', ''),
                    'role': r.get('payload', {}).get('role', ''),
                    'score': r.get('score', 0.0)
                }
                for r in results
            ]
            
        except Exception as e:
            logger.warning(f"[ConversationIndexer] Search error: {e}")
            return []
