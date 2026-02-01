"""
Qdrant Helper - вспомогательные функции для работы с Qdrant
Поддерживает:
- Индексацию Q&A пар в формате "Q: ... A: ..."
- Загрузку документов в RAG
- Поиск по базе знаний
"""
import logging
import hashlib
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import httpx

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct, 
    VectorParams, 
    Distance,
    Filter,
    FieldCondition,
    MatchValue
)

from app.core.config import settings

# Импортируем загрузчик конфигурации
try:
    from config.config_loader import get_qdrant_config_value
except ImportError:
    def get_qdrant_config_value(key: str, default=None, base_path=None):
        return default

logger = logging.getLogger(__name__)

# Конфигурация коллекции (из config/qdrant.yaml или defaults)
COLLECTION_NAME = get_qdrant_config_value("collection_name", default="data")
EMBEDDING_DIMENSION = get_qdrant_config_value("target_dimension", default=1536)
SCORE_THRESHOLD = get_qdrant_config_value("search.score_threshold", default=0.3)

# Глобальный клиент Qdrant
_qdrant_client: Optional[QdrantClient] = None


def get_qdrant_client() -> Optional[QdrantClient]:
    """
    Получить клиент Qdrant с подключением к Railway
    Использует конфигурацию из config/qdrant.yaml
    """
    global _qdrant_client
    
    if _qdrant_client is not None:
        return _qdrant_client
    
    try:
        # URL Qdrant из конфигурации или переменных окружения
        qdrant_url = get_qdrant_config_value("url", default=None)
        
        if not qdrant_url:
            # Fallback на settings
            qdrant_url = settings.QDRANT_URL
        
        if not qdrant_url:
            # Попробуем получить из переменных окружения напрямую
            import os
            qdrant_url = os.getenv("QDRANT_URL", "https://qdrant-production-ad0b.up.railway.app")
        
        qdrant_api_key = get_qdrant_config_value("api_key", default=None) or settings.QDRANT_API_KEY
        
        logger.info(f"🔗 Подключаемся к Qdrant: {qdrant_url}")
        logger.info(f"📦 Коллекция: {COLLECTION_NAME}, Размерность: {EMBEDDING_DIMENSION}")
        
        _qdrant_client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key if qdrant_api_key else None,
            prefer_grpc=False,
            timeout=60.0  # Увеличенный таймаут для стабильности (60 секунд)
        )
        
        # Проверяем подключение (не критично, если не получится - клиент все равно может работать)
        try:
            collections = _qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            logger.info(f"✅ Подключено к Qdrant. Коллекции: {collection_names}")
        except Exception as check_error:
            error_str = str(check_error).lower()
            if "timeout" in error_str or "timed out" in error_str:
                logger.warning(f"⚠️ Qdrant проверка таймаут - сервис может быть медленным, но клиент создан")
            else:
                logger.warning(f"⚠️ Qdrant проверка ошибка: {check_error}, но клиент создан")
            # Не возвращаем None, клиент может быть полезен для других операций
        
        return _qdrant_client
        
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Qdrant: {e}")
        return None


def is_qdrant_available() -> bool:
    """
    Быстрая проверка доступности Qdrant (без долгих операций)
    
    Returns:
        True если Qdrant доступен, False если таймаут или ошибка
    """
    try:
        client = get_qdrant_client()
        if not client:
            return False
        
        # Быстрая проверка - просто пытаемся получить коллекции
        # Используем короткий таймаут на уровне клиента (уже установлен в get_qdrant_client)
        try:
            _ = client.get_collections()
            return True
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                logger.warning(f"⚠️ Qdrant check timeout")
            else:
                logger.warning(f"⚠️ Qdrant check error: {e}")
            return False
            
    except Exception as e:
        logger.warning(f"⚠️ Qdrant availability check failed: {e}")
        return False


def ensure_collection() -> bool:
    """
    Убедиться, что коллекция существует
    """
    logger.info(f"[COLLECTION] Проверка коллекции '{COLLECTION_NAME}'")
    logger.info(f"[COLLECTION] Ожидаемая размерность: {EMBEDDING_DIMENSION}")
    
    try:
        client = get_qdrant_client()
        if not client:
            logger.error(f"[COLLECTION] ❌ Qdrant клиент недоступен")
            return False
        
        logger.info(f"[COLLECTION] ✅ Qdrant клиент получен")
        
        # Проверяем существование коллекции
        logger.info(f"[COLLECTION] Получаю список коллекций...")
        try:
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]
            logger.info(f"[COLLECTION] Найдено коллекций: {len(collection_names)}")
            logger.info(f"[COLLECTION] Список коллекций: {collection_names}")
        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__
            
            # Специальная обработка таймаутов
            if "timeout" in error_str or "timed out" in error_str or "ConnectTimeout" in error_type or "ResponseHandlingException" in error_type:
                logger.error(f"[COLLECTION] ❌ Таймаут подключения к Qdrant")
                logger.error(f"[COLLECTION] Qdrant сервис недоступен или слишком медленный")
                logger.error(f"[COLLECTION] Проверьте:")
                logger.error(f"[COLLECTION]   - Доступность Qdrant URL")
                logger.error(f"[COLLECTION]   - Сетевое подключение")
                logger.error(f"[COLLECTION]   - Статус Qdrant сервиса")
                return False
            else:
                logger.error(f"[COLLECTION] ❌ Ошибка при получении списка коллекций: {e}")
                logger.error(f"[COLLECTION] Тип ошибки: {error_type}")
                import traceback
                logger.error(f"[COLLECTION] Traceback: {traceback.format_exc()}")
                return False
        
        if COLLECTION_NAME in collection_names:
            logger.info(f"[COLLECTION] ✅ Коллекция '{COLLECTION_NAME}' существует")
            return True
        
        # Создаем коллекцию если не существует
        logger.info(f"[COLLECTION] 📦 Коллекция '{COLLECTION_NAME}' не найдена, создаю...")
        logger.info(f"[COLLECTION] Параметры: размерность={EMBEDDING_DIMENSION}, расстояние=COSINE")
        
        try:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIMENSION,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"[COLLECTION] ✅ Коллекция '{COLLECTION_NAME}' успешно создана")
            return True
        except Exception as create_error:
            error_str = str(create_error).lower()
            error_type = type(create_error).__name__
            
            # Специальная обработка таймаутов
            if "timeout" in error_str or "timed out" in error_str or "ConnectTimeout" in error_type or "ResponseHandlingException" in error_type:
                logger.error(f"[COLLECTION] ❌ Таймаут при создании коллекции")
                logger.error(f"[COLLECTION] Qdrant сервис недоступен или слишком медленный")
                return False
            else:
                logger.error(f"[COLLECTION] ❌ Ошибка при создании коллекции: {create_error}")
                logger.error(f"[COLLECTION] Тип ошибки: {error_type}")
                import traceback
                logger.error(f"[COLLECTION] Traceback: {traceback.format_exc()}")
                return False
        
    except Exception as e:
        logger.error(f"[COLLECTION] ❌ Ошибка при проверке/создании коллекции: {e}")
        logger.error(f"[COLLECTION] Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"[COLLECTION] Traceback: {traceback.format_exc()}")
        return False


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Генерация эмбеддинга синхронно через OpenRouter API
    """
    try:
        import httpx
        
        api_key = settings.OPENROUTER_API_KEY
        model = settings.EMBEDDING_MODEL
        
        response = httpx.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "input": text
            },
            timeout=30.0
        )
        
        response.raise_for_status()
        data = response.json()
        embedding = data["data"][0]["embedding"]
        
        # Проверяем размерность
        if len(embedding) != EMBEDDING_DIMENSION:
            # Дополняем или обрезаем до нужной размерности
            if len(embedding) < EMBEDDING_DIMENSION:
                embedding.extend([0.0] * (EMBEDDING_DIMENSION - len(embedding)))
            else:
                embedding = embedding[:EMBEDDING_DIMENSION]
        
        return embedding
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации эмбеддинга: {e}")
        return None


async def generate_embedding_async(text: str) -> Optional[List[float]]:
    """
    Генерация эмбеддинга асинхронно через OpenRouter API
    """
    logger.info(f"[EMBEDDING] Начало генерации эмбеддинга")
    logger.info(f"[EMBEDDING] Текст: {text[:100]}...")
    logger.info(f"[EMBEDDING] Длина текста: {len(text)} символов")
    
    try:
        api_key = settings.OPENROUTER_API_KEY
        model = settings.EMBEDDING_MODEL
        
        if not api_key:
            logger.error(f"[EMBEDDING] ❌ OPENROUTER_API_KEY не установлен")
            return None
        
        if not model:
            logger.error(f"[EMBEDDING] ❌ EMBEDDING_MODEL не установлен")
            return None
        
        logger.info(f"[EMBEDDING] Модель: {model}")
        logger.info(f"[EMBEDDING] API Key: {'установлен' if api_key else 'НЕ УСТАНОВЛЕН'}")
        logger.info(f"[EMBEDDING] Ожидаемая размерность: {EMBEDDING_DIMENSION}")
        logger.info(f"[EMBEDDING] Отправляю запрос к OpenRouter API...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "input": text
                }
            )
            
            logger.info(f"[EMBEDDING] Получен ответ от API: статус {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"[EMBEDDING] ❌ Ошибка API: статус {response.status_code}")
                logger.error(f"[EMBEDDING] Ответ: {response.text[:500]}")
                response.raise_for_status()
            
            data = response.json()
            embedding = data["data"][0]["embedding"]
            
            logger.info(f"[EMBEDDING] ✅ Эмбеддинг получен, размерность: {len(embedding)}")
            
            # Проверяем размерность
            if len(embedding) != EMBEDDING_DIMENSION:
                logger.warning(f"[EMBEDDING] ⚠️ Размерность не совпадает: {len(embedding)} != {EMBEDDING_DIMENSION}")
                if len(embedding) < EMBEDDING_DIMENSION:
                    logger.info(f"[EMBEDDING] Дополняю эмбеддинг нулями до {EMBEDDING_DIMENSION}")
                    embedding.extend([0.0] * (EMBEDDING_DIMENSION - len(embedding)))
                else:
                    logger.info(f"[EMBEDDING] Обрезаю эмбеддинг до {EMBEDDING_DIMENSION}")
                    embedding = embedding[:EMBEDDING_DIMENSION]
            
            logger.info(f"[EMBEDDING] ✅ Финальная размерность: {len(embedding)}")
            return embedding
        
    except httpx.HTTPError as e:
        logger.error(f"[EMBEDDING] ❌ HTTP ошибка при генерации эмбеддинга: {e}")
        logger.error(f"[EMBEDDING] Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"[EMBEDDING] Traceback: {traceback.format_exc()}")
        return None
    except Exception as e:
        logger.error(f"[EMBEDDING] ❌ Ошибка генерации эмбеддинга async: {e}")
        logger.error(f"[EMBEDDING] Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"[EMBEDDING] Traceback: {traceback.format_exc()}")
        return None


def index_qa_to_qdrant(
    question: str, 
    answer: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Индексировать пару вопрос-ответ в Qdrant для RAG базы знаний
    
    Формат добавления: Q: <вопрос> A: <ответ>
    
    Args:
        question: Вопрос
        answer: Ответ
        metadata: Дополнительные метаданные (user_id, category, etc.)
    
    Returns:
        True если успешно, False при ошибке
    """
    if not question or not answer or not question.strip() or not answer.strip():
        logger.warning("⚠️ Вопрос и ответ не могут быть пустыми")
        return False
    
    try:
        # Генерируем эмбеддинг для вопроса (для поиска)
        embedding = generate_embedding(question)
        if not embedding:
            logger.warning("⚠️ Не удалось сгенерировать эмбеддинг для вопроса")
            return False
        
        # Получаем клиент Qdrant
        client = get_qdrant_client()
        if not client:
            logger.warning("⚠️ Qdrant клиент недоступен")
            return False
        
        # Убеждаемся что коллекция существует
        if not ensure_collection():
            logger.error("❌ Не удалось создать/проверить коллекцию")
            return False
        
        # Подготавливаем метаданные
        payload = {
            "source": "manual_qa",
            "type": "qa_pair",
            "question": question,
            "answer": answer,
            "text": f"Вопрос: {question}\nОтвет: {answer}",  # Полный текст для поиска
            "content": answer,  # Ответ для отображения
            "timestamp": datetime.now().isoformat()
        }
        if metadata:
            payload.update(metadata)
        
        # Генерируем ID для точки (детерминированный на основе Q&A)
        text_hash = hashlib.md5(f"qa_{question}_{answer}".encode()).hexdigest()
        point_id = int(text_hash[:8], 16)
        
        # Добавляем точку в Qdrant
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
            ]
        )
        
        logger.info(f"✅ Q&A пара индексирована в Qdrant (point_id={point_id})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка индексации Q&A пары в Qdrant: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False


async def index_qa_to_qdrant_async(
    question: str, 
    answer: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Асинхронная версия индексации Q&A пары
    """
    logger.info(f"[Q&A INDEX] Начало индексации Q&A пары")
    logger.info(f"[Q&A INDEX] Вопрос: {question[:100]}...")
    logger.info(f"[Q&A INDEX] Ответ: {answer[:100]}...")
    logger.info(f"[Q&A INDEX] Метаданные: {metadata}")
    
    if not question or not answer or not question.strip() or not answer.strip():
        logger.warning("⚠️ Вопрос и ответ не могут быть пустыми")
        logger.warning(f"   Вопрос пустой: {not question or not question.strip()}")
        logger.warning(f"   Ответ пустой: {not answer or not answer.strip()}")
        return False
    
    try:
        # Генерируем эмбеддинг асинхронно
        logger.info(f"[Q&A INDEX] 🔍 Генерирую эмбеддинг для вопроса...")
        logger.info(f"[Q&A INDEX]    Модель: {getattr(settings, 'EMBEDDING_MODEL', 'не установлена')}")
        logger.info(f"[Q&A INDEX]    API Key установлен: {bool(getattr(settings, 'OPENROUTER_API_KEY', None))}")
        
        embedding = await generate_embedding_async(question)
        if not embedding:
            logger.error("⚠️ Не удалось сгенерировать эмбеддинг для вопроса")
            logger.error(f"   Проверьте OPENROUTER_API_KEY и EMBEDDING_MODEL в настройках")
            logger.error(f"   OPENROUTER_API_KEY: {'установлен' if getattr(settings, 'OPENROUTER_API_KEY', None) else 'НЕ УСТАНОВЛЕН'}")
            logger.error(f"   EMBEDDING_MODEL: {getattr(settings, 'EMBEDDING_MODEL', 'НЕ УСТАНОВЛЕН')}")
            return False
        
        logger.info(f"[Q&A INDEX] ✅ Эмбеддинг сгенерирован, размерность: {len(embedding)}")
        
        # Получаем клиент Qdrant
        logger.info(f"[Q&A INDEX] 🔗 Подключаюсь к Qdrant...")
        logger.info(f"[Q&A INDEX]    QDRANT_URL: {get_qdrant_config_value('url', default='не установлен')}")
        logger.info(f"[Q&A INDEX]    QDRANT_API_KEY: {'установлен' if get_qdrant_config_value('api_key', default=None) or getattr(settings, 'QDRANT_API_KEY', None) else 'не установлен'}")
        
        client = get_qdrant_client()
        if not client:
            logger.error("⚠️ Qdrant клиент недоступен")
            logger.error(f"   Проверьте QDRANT_URL и QDRANT_API_KEY в настройках")
            logger.error(f"   QDRANT_URL: {get_qdrant_config_value('url', default='не установлен')}")
            logger.error(f"   QDRANT_API_KEY: {'установлен' if get_qdrant_config_value('api_key', default=None) or getattr(settings, 'QDRANT_API_KEY', None) else 'НЕ УСТАНОВЛЕН'}")
            return False
        
        logger.info(f"[Q&A INDEX] ✅ Qdrant клиент подключен")
        
        # Убеждаемся что коллекция существует
        logger.info(f"[Q&A INDEX] 📦 Проверяю коллекцию '{COLLECTION_NAME}'...")
        logger.info(f"[Q&A INDEX]    Размерность эмбеддингов: {EMBEDDING_DIMENSION}")
        
        if not ensure_collection():
            logger.error(f"❌ Не удалось создать/проверить коллекцию '{COLLECTION_NAME}'")
            logger.error(f"   Проверьте подключение к Qdrant и права доступа")
            return False
        
        logger.info(f"[Q&A INDEX] ✅ Коллекция '{COLLECTION_NAME}' проверена/создана")
        
        # Подготавливаем метаданные
        payload = {
            "source": "manual_qa",
            "type": "qa_pair",
            "question": question,
            "answer": answer,
            "text": f"Вопрос: {question}\nОтвет: {answer}",
            "content": answer,
            "timestamp": datetime.now().isoformat()
        }
        if metadata:
            payload.update(metadata)
        
        # Генерируем ID для точки
        text_hash = hashlib.md5(f"qa_{question}_{answer}".encode()).hexdigest()
        point_id = int(text_hash[:8], 16)
        logger.info(f"[Q&A INDEX] 📍 Сгенерирован point_id: {point_id}")
        logger.info(f"[Q&A INDEX]    Hash: {text_hash[:16]}...")
        
        # Добавляем точку в Qdrant (синхронный вызов в executor)
        logger.info(f"[Q&A INDEX] 💾 Добавляю точку в Qdrant...")
        logger.info(f"[Q&A INDEX]    Коллекция: {COLLECTION_NAME}")
        logger.info(f"[Q&A INDEX]    Размер payload: {len(str(payload))} символов")
        
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=[
                        PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload=payload
                        )
                    ]
                )
            )
            logger.info(f"[Q&A INDEX] ✅ Точка успешно добавлена в Qdrant")
        except Exception as upsert_error:
            error_str = str(upsert_error).lower()
            error_type = type(upsert_error).__name__
            
            # Специальная обработка таймаутов
            if "timeout" in error_str or "timed out" in error_str or "ConnectTimeout" in error_type or "ResponseHandlingException" in error_type:
                logger.error(f"[Q&A INDEX] ❌ Таймаут при добавлении точки в Qdrant")
                logger.error(f"[Q&A INDEX] Qdrant сервис недоступен или слишком медленный")
                logger.error(f"[Q&A INDEX] Проверьте доступность Qdrant сервиса")
                raise
            else:
                logger.error(f"[Q&A INDEX] ❌ Ошибка при добавлении точки в Qdrant: {upsert_error}")
                logger.error(f"[Q&A INDEX]    Тип ошибки: {error_type}")
                import traceback
                logger.error(f"[Q&A INDEX]    Traceback: {traceback.format_exc()}")
                raise
        
        logger.info(f"✅ Q&A пара индексирована в Qdrant async (point_id={point_id})")
        logger.info(f"[Q&A INDEX] ✅ Индексация завершена успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка индексации Q&A пары async: {e}")
        logger.error(f"   Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False


async def index_document_chunks_to_qdrant(
    chunks: List[str],
    file_name: str,
    doc_id: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Индексация чанков документа в Qdrant (коллекция 'data')
    
    Args:
        chunks: Список текстовых чанков
        file_name: Имя файла
        doc_id: ID документа
        user_id: ID пользователя (опционально)
        username: Username пользователя (опционально)
        project_id: ID проекта (опционально)
    
    Returns:
        Словарь с результатом: {"success": bool, "chunks_count": int, "error": str}
    """
    try:
        client = get_qdrant_client()
        if not client:
            return {"success": False, "error": "Qdrant клиент недоступен"}
        
        if not ensure_collection():
            return {"success": False, "error": "Не удалось создать коллекцию"}
        
        points = []
        batch_size = 10
        total_indexed = 0
        
        for batch_start in range(0, len(chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(chunks))
            batch_chunks = chunks[batch_start:batch_end]
            
            logger.info(f"📊 Обрабатываю чанки {batch_start + 1}-{batch_end} из {len(chunks)}")
            
            # Генерируем эмбеддинги для батча параллельно
            embedding_tasks = [generate_embedding_async(chunk) for chunk in batch_chunks]
            embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)
            
            # Создаем точки для батча
            batch_points = []
            for i, (chunk, embedding) in enumerate(zip(batch_chunks, embeddings)):
                if isinstance(embedding, Exception) or embedding is None:
                    logger.warning(f"⚠️ Пропуск чанка {batch_start + i}: ошибка эмбеддинга")
                    continue
                
                chunk_index = batch_start + i
                chunk_id = f"{doc_id}_chunk_{chunk_index}"
                
                # Генерируем числовой ID
                point_id = abs(hash(chunk_id)) % (10 ** 10)
                
                payload = {
                    "source": "document_upload",
                    "type": "document_chunk",
                    "text": chunk,
                    "content": chunk,
                    "file_name": file_name,
                    "title": file_name,
                    "doc_id": doc_id,
                    "chunk_index": chunk_index,
                    "total_chunks": len(chunks),
                    "chunk_id": chunk_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                if user_id:
                    payload["user_id"] = user_id
                if username:
                    payload["uploaded_by"] = username
                if project_id:
                    payload["project_id"] = project_id
                
                batch_points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload
                    )
                )
            
            # Загружаем батч в Qdrant
            if batch_points:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: client.upsert(
                        collection_name=COLLECTION_NAME,
                        points=batch_points
                    )
                )
                total_indexed += len(batch_points)
                logger.info(f"✅ Загружено {len(batch_points)} чанков в Qdrant")
        
        logger.info(f"✅ Всего индексировано {total_indexed} чанков из документа {file_name}")
        
        return {
            "success": True,
            "chunks_count": total_indexed,
            "doc_id": doc_id
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка индексации документа в Qdrant: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return {"success": False, "error": str(e)}


async def search_qdrant(
    query: str,
    limit: int = 5,
    score_threshold: float = None,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    # Используем порог из конфигурации если не указан
    if score_threshold is None:
        score_threshold = SCORE_THRESHOLD
    """
    Поиск в Qdrant по запросу
    
    Args:
        query: Поисковый запрос
        limit: Количество результатов
        score_threshold: Минимальный порог релевантности
        user_id: Фильтр по пользователю (опционально)
        project_id: Фильтр по проекту (опционально)
    
    Returns:
        Список найденных документов
    """
    try:
        client = get_qdrant_client()
        if not client:
            logger.warning("⚠️ Qdrant клиент недоступен")
            return []
        
        # Генерируем эмбеддинг для запроса
        query_embedding = await generate_embedding_async(query)
        if not query_embedding:
            logger.warning("⚠️ Не удалось создать эмбеддинг для запроса")
            return []
        
        # Выполняем поиск
        search_results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=limit
        )
        
        # Обрабатываем результаты
        results = []
        for point in search_results.points:
            payload = point.payload if hasattr(point, 'payload') else {}
            score = point.score if hasattr(point, 'score') else 0.0
            
            if score < score_threshold:
                continue
            
            # Фильтр по user_id если указан
            if user_id and payload.get('user_id') and payload.get('user_id') != user_id:
                continue
            
            # Фильтр по project_id если указан
            if project_id and payload.get('project_id') and payload.get('project_id') != project_id:
                continue
            
            results.append({
                "text": payload.get("text") or payload.get("content", ""),
                "file_name": payload.get("file_name") or payload.get("title") or payload.get("source", "Документ"),
                "score": score,
                "type": payload.get("type", "unknown"),
                "question": payload.get("question"),
                "answer": payload.get("answer"),
                "payload": payload
            })
        
        logger.info(f"✅ Найдено {len(results)} результатов для запроса: '{query[:50]}'")
        return results
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска в Qdrant: {e}")
        return []


def parse_qa_message(text: str) -> Optional[Dict[str, str]]:
    """
    Парсинг сообщения в формате Q&A
    
    Поддерживаемые форматы:
    - Q: вопрос A: ответ
    - Q: вопрос\nA: ответ
    - В: вопрос О: ответ (русский)
    - Вопрос: ... Ответ: ...
    
    Returns:
        {"question": str, "answer": str} или None если не Q&A формат
    """
    if not text:
        return None
    
    # Паттерны для распознавания Q&A
    patterns = [
        # Q: ... A: ...
        re.compile(r'Q:\s*(.+?)\s*A:\s*(.+?)$', re.DOTALL | re.IGNORECASE),
        # В: ... О: ... (русский)
        re.compile(r'В:\s*(.+?)\s*О:\s*(.+?)$', re.DOTALL | re.IGNORECASE),
        # Вопрос: ... Ответ: ...
        re.compile(r'Вопрос:\s*(.+?)\s*Ответ:\s*(.+?)$', re.DOTALL | re.IGNORECASE),
        # Question: ... Answer: ...
        re.compile(r'Question:\s*(.+?)\s*Answer:\s*(.+?)$', re.DOTALL | re.IGNORECASE),
    ]
    
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            question = match.group(1).strip()
            answer = match.group(2).strip()
            
            if question and answer:
                return {
                    "question": question,
                    "answer": answer
                }
    
    return None


# Экспортируем функции
__all__ = [
    'get_qdrant_client',
    'ensure_collection',
    'generate_embedding',
    'generate_embedding_async',
    'index_qa_to_qdrant',
    'index_qa_to_qdrant_async',
    'index_document_chunks_to_qdrant',
    'search_qdrant',
    'parse_qa_message',
    'COLLECTION_NAME',
    'EMBEDDING_DIMENSION'
]
