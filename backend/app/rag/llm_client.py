"""
Универсальный LLM-клиент с поддержкой OpenRouter.
"""

import os
import httpx
import time
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Ответ от LLM API"""
    content: str
    provider: str
    model: str
    confidence: float = 1.0
    tokens_used: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error: Optional[str] = None


class LLMClient:
    """Универсальный клиент для работы с OpenRouter API"""
    
    def __init__(
        self,
        primary_model: str = None,
        fallback_chain: Optional[List[Dict[str, str]]] = None,
        confidence_threshold: float = 0.7,
        timeout: int = 30
    ):
        from app.core.config import settings
        
        self.primary_model = primary_model or settings.OPENROUTER_MODEL_PRIMARY
        self.confidence_threshold = confidence_threshold
        self.timeout = timeout
        
        # Цепочка fallback моделей
        if fallback_chain is None:
            # Дефолтная цепочка fallback
            self.fallback_chain = [
                {"model": settings.OPENROUTER_MODEL_FALLBACK}
            ]
        else:
            self.fallback_chain = fallback_chain
        
        # Загружаем конфигурацию из ENV
        openrouter_key = os.getenv("OPENROUTER_API_KEY") or settings.OPENROUTER_API_KEY
        self.openrouter_api_key = openrouter_key.strip() if openrouter_key else None
        
        openrouter_url = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
        self.openrouter_api_url = openrouter_url.strip()
        
        app_url = os.getenv("APP_URL", settings.APP_URL).strip()
        self.app_url = app_url
        
        # HTTP клиент создается лениво для thread-safety
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Получает или создает HTTP клиент (thread-safe)"""
        if self._client_lock is None:
            import threading
            self._client_lock = threading.Lock()
        
        # Проверяем, нужно ли пересоздать клиент
        if self._client is None:
            with self._client_lock:
                # Двойная проверка после получения блокировки
                if self._client is None:
                    # Создаем новый клиент
                    self._client = httpx.AsyncClient(timeout=self.timeout)
                    logger.debug("Создан новый HTTP клиент")
        elif self._client.is_closed:
            # Клиент закрыт - пересоздаем
            with self._client_lock:
                # Двойная проверка
                if self._client.is_closed:
                    self._client = httpx.AsyncClient(timeout=self.timeout)
                    logger.debug("HTTP клиент пересоздан (был закрыт)")
        
        return self._client
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Обеспечивает наличие рабочего HTTP клиента (async-safe)"""
        client = self._get_client()
        
        # Проверяем, не закрыт ли клиент
        if client.is_closed:
            logger.warning("HTTP клиент закрыт, пересоздаю...")
            if self._client_lock is not None:
                with self._client_lock:
                    if self._client is not None and self._client.is_closed:
                        try:
                            await self._client.aclose()
                        except:
                            pass
                        self._client = None
            client = self._get_client()
        
        return client
    
    async def _call_api(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> LLMResponse:
        """Выполняет запрос к OpenRouter API"""
        
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment")
        
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "HTTP-Referer": self.app_url,
            "X-Title": "RAG Bot",
            "Content-Type": "application/json"
        }
        
        # Валидация URL
        if '\n' in self.openrouter_api_url or '\r' in self.openrouter_api_url:
            logger.error(f"Invalid URL contains newline characters: {repr(self.openrouter_api_url)}")
            api_url = self.openrouter_api_url.replace('\n', '').replace('\r', '').strip()
            logger.warning(f"Cleaned URL: {api_url}")
        else:
            api_url = self.openrouter_api_url
        
        # Очищаем messages от возможных проблем с форматированием
        cleaned_messages = []
        for msg in messages:
            cleaned_msg = {
                "role": msg.get("role", "user").strip(),
                "content": msg.get("content", "").strip()
            }
            # Удаляем пустые сообщения
            if cleaned_msg["content"]:
                cleaned_messages.append(cleaned_msg)
        
        if not cleaned_messages:
            raise ValueError("No valid messages to send")
        
        payload = {
            "model": model.strip() if isinstance(model, str) else model,
            "messages": cleaned_messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens)
        }
        
        try:
            logger.info(f"Calling OpenRouter API with model {model}")
            start_time = time.time()
            
            # Обеспечиваем наличие рабочего клиента
            client = await self._ensure_client()
            
            try:
                response = await client.post(
                    api_url,
                    headers=headers,
                    json=payload
                )
            except (RuntimeError, httpx.TransportError, httpx.RequestError) as e:
                # Если клиент закрыт или произошла ошибка транспорта - пересоздаем
                error_str = str(e).lower()
                if "closed" in error_str or "client has been closed" in error_str:
                    logger.warning(f"HTTP клиент закрыт ({str(e)}), пересоздаю и повторяю запрос...")
                    # Закрываем старый клиент
                    if self._client_lock is not None:
                        with self._client_lock:
                            if self._client is not None:
                                try:
                                    await self._client.aclose()
                                except:
                                    pass
                            self._client = None
                    # Создаем новый клиент и повторяем запрос
                    client = await self._ensure_client()
                    response = await client.post(
                        api_url,
                        headers=headers,
                        json=payload
                    )
                else:
                    raise
            
            elapsed_time = time.time() - start_time
            logger.info(f"OpenRouter API response in {elapsed_time:.2f}s")
            
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens")
            input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
            output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
            
            # Простая оценка уверенности
            confidence = 1.0 if len(content) > 50 else 0.5
            
            return LLMResponse(
                content=content,
                provider="openrouter",
                model=model,
                confidence=confidence,
                tokens_used=tokens_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
        except httpx.TimeoutException:
            logger.error(f"OpenRouter API timeout")
            return LLMResponse(
                content="",
                provider="openrouter",
                model=model,
                confidence=0.0,
                error="Timeout"
            )
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = f": {error_data}"
            except:
                try:
                    error_detail = f": {e.response.text[:200]}"
                except:
                    pass
            
            logger.error(f"OpenRouter API error: {e.response.status_code}{error_detail}")
            return LLMResponse(
                content="",
                provider="openrouter",
                model=model,
                confidence=0.0,
                error=f"HTTP {e.response.status_code}{error_detail}"
            )
        except Exception as e:
            logger.error(f"OpenRouter API exception: {str(e)}")
            return LLMResponse(
                content="",
                provider="openrouter",
                model=model,
                confidence=0.0,
                error=str(e)
            )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        use_fallback: bool = True
    ) -> LLMResponse:
        """
        Генерирует ответ используя основную модель, при необходимости fallback.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (опционально)
            model: Модель (если не указано, используется дефолтная)
            temperature: Температура генерации
            max_tokens: Максимальное количество токенов
            use_fallback: Использовать fallback при ошибке/низкой уверенности
        
        Returns:
            LLMResponse с ответом или ошибкой
        """
        # Очищаем промпты
        cleaned_prompt = prompt.strip() if prompt else ""
        cleaned_system_prompt = system_prompt.strip() if system_prompt else None
        
        if not cleaned_prompt:
            raise ValueError("Prompt cannot be empty")
        
        messages = []
        if cleaned_system_prompt:
            messages.append({"role": "system", "content": cleaned_system_prompt})
        messages.append({"role": "user", "content": cleaned_prompt})
        
        # Определяем модель для основного провайдера
        primary_model = model or self.primary_model
        
        # Пытаемся вызвать основную модель
        logger.info(f"Trying primary model: {primary_model}")
        response = await self._call_api(
            model=primary_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Если успешно и уверенность достаточна - возвращаем
        if response.error is None and response.confidence >= self.confidence_threshold:
            logger.info(f"Primary model {primary_model} succeeded")
            return response
        
        # Если нужен fallback - пробуем цепочку fallback моделей
        if use_fallback and self.fallback_chain:
            logger.warning(
                f"Primary model {primary_model} failed (error: {response.error}, "
                f"confidence: {response.confidence:.2f}). Trying fallback chain..."
            )
            
            # Пробуем каждую модель в цепочке fallback
            for idx, fallback_config in enumerate(self.fallback_chain, 1):
                fallback_model = fallback_config.get("model")
                
                if not fallback_model:
                    logger.warning(f"Fallback {idx} skipped: model not specified")
                    continue
                
                logger.info(f"Trying fallback {idx}: {fallback_model}")
                
                fallback_response = await self._call_api(
                    model=fallback_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Если успешно - возвращаем ответ
                if fallback_response.error is None:
                    logger.info(f"Fallback {idx} ({fallback_model}) succeeded")
                    return fallback_response
                else:
                    logger.warning(
                        f"Fallback {idx} ({fallback_model}) failed: "
                        f"{fallback_response.error}"
                    )
            
            logger.error("All models in fallback chain failed")
        
        # Если все модели не сработали, возвращаем последний ответ
        logger.error("All providers and fallback models failed")
        return response
    
    async def record_token_usage(
        self,
        response: LLMResponse,
        db_session = None,
        project_id = None
    ):
        """
        Сохраняет использование токенов в БД
        
        Args:
            response: LLMResponse с информацией о токенах
            db_session: AsyncSession для работы с БД (опционально)
            project_id: UUID проекта (опционально)
        """
        if not db_session or not response.input_tokens or not response.output_tokens:
            return
        
        try:
            from app.services.token_usage_service import TokenUsageService
            from uuid import UUID
            
            token_service = TokenUsageService(db_session)
            project_uuid = UUID(project_id) if project_id else None
            
            await token_service.record_token_usage(
                model_id=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                project_id=project_uuid
            )
            
            logger.info(
                f"Token usage recorded: model={response.model}, "
                f"input={response.input_tokens}, output={response.output_tokens}, "
                f"project={project_id}"
            )
        except Exception as e:
            logger.error(f"Failed to record token usage: {e}")
    
    async def close(self):
        """Закрывает HTTP клиент"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

