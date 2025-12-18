"""
Клиент для работы с OpenRouter API
"""
from typing import Optional, List, Dict, Any
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Клиент для OpenRouter API с fallback логикой"""
    
    def __init__(self, model_primary: str = None, model_fallback: str = None):
        self.api_key = settings.OPENROUTER_API_KEY
        # Если модель указана при инициализации, используем её, иначе глобальные настройки
        self.model_primary = model_primary or settings.OPENROUTER_MODEL_PRIMARY
        self.model_fallback = model_fallback or settings.OPENROUTER_MODEL_FALLBACK
        self.timeout_primary = settings.OPENROUTER_TIMEOUT_PRIMARY
        self.timeout_fallback = settings.OPENROUTER_TIMEOUT_FALLBACK
        self.app_url = settings.APP_URL
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Генерация ответа через LLM с fallback
        
        Args:
            messages: Список сообщений в формате [{"role": "user", "content": "..."}]
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
        
        Returns:
            Сгенерированный текст
        
        Raises:
            Exception: Если обе модели не сработали
        """
        # Попытка с основной моделью
        try:
            response = await self._make_request(
                model=self.model_primary,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.timeout_primary
            )
            return response
        except Exception as e:
            logger.warning(f"Ошибка при использовании основной модели {self.model_primary}: {e}")
            logger.info(f"Переключение на fallback модель {self.model_fallback}")
            
            # Fallback на резервную модель
            try:
                response = await self._make_request(
                    model=self.model_fallback,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=self.timeout_fallback
                )
                logger.info("Успешно использована fallback модель")
                return response
            except Exception as e2:
                logger.error(f"Ошибка при использовании fallback модели {self.model_fallback}: {e2}")
                raise Exception(f"Обе модели не сработали. Основная: {e}, Fallback: {e2}")
    
    async def _make_request(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int],
        temperature: float,
        timeout: int
    ) -> str:
        """Выполнить запрос к OpenRouter"""
        async with httpx.AsyncClient(timeout=timeout) as client:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": self.app_url,
                    "X-Title": "Telegram RAG Bot",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            response.raise_for_status()
            data = response.json()
            
            if "choices" not in data or len(data["choices"]) == 0:
                raise Exception("Пустой ответ от API")
            
            return data["choices"][0]["message"]["content"]


