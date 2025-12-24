"""
Клиент для работы с OpenRouter API
"""
from typing import Optional, List, Dict, Any
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Клиент для OpenRouter API с fallback логикой и цепочкой моделей для русского языка"""
    
    # Дополнительные fallback модели для русского языка (в порядке приоритета)
    RUSSIAN_FALLBACK_MODELS = [
        "deepseek/deepseek-chat",  # DeepSeek - отличная поддержка русского
        "qwen/qwen-2.5-72b-instruct",  # Qwen - хорошая поддержка русского
        "nex-ai/nex-agi-deepseek-v3.1-nex-n1",  # DeepSeek V3.1 Nex N1 (free)
        "minimax/minimax-m2.1",  # MiniMax M2.1
        "mistralai/mistral-7b-instruct",  # Mistral 7B Instruct (free)
    ]
    
    def __init__(self, model_primary: str = None, model_fallback: str = None):
        self.api_key = settings.OPENROUTER_API_KEY
        # Если модель указана при инициализации, используем её, иначе глобальные настройки
        self.model_primary = model_primary or settings.OPENROUTER_MODEL_PRIMARY
        self.model_fallback = model_fallback or settings.OPENROUTER_MODEL_FALLBACK
        self.timeout_primary = settings.OPENROUTER_TIMEOUT_PRIMARY
        self.timeout_fallback = settings.OPENROUTER_TIMEOUT_FALLBACK
        self.app_url = settings.APP_URL
        
        # Формируем полную цепочку моделей: primary -> fallback -> русские модели
        self.model_chain = []
        if self.model_primary:
            self.model_chain.append(self.model_primary)
        if self.model_fallback and self.model_fallback != self.model_primary:
            self.model_chain.append(self.model_fallback)
        # Добавляем русские модели, исключая уже добавленные
        for model in self.RUSSIAN_FALLBACK_MODELS:
            if model not in self.model_chain:
                self.model_chain.append(model)
        
        logger.info(f"[OpenRouterClient] Model chain: {self.model_chain}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Генерация ответа через LLM с цепочкой fallback моделей
        
        Args:
            messages: Список сообщений в формате [{"role": "user", "content": "..."}]
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
        
        Returns:
            Сгенерированный текст
        
        Raises:
            Exception: Если все модели в цепочке не сработали
        """
        last_error = None
        
        # Пробуем каждую модель в цепочке
        for idx, model in enumerate(self.model_chain):
            try:
                timeout = self.timeout_primary if idx == 0 else self.timeout_fallback
                logger.info(f"[OpenRouterClient] Trying model {idx + 1}/{len(self.model_chain)}: {model}")
                
                response = await self._make_request(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout
                )
                
                if idx > 0:
                    logger.info(f"[OpenRouterClient] Successfully used fallback model {idx}: {model}")
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"[OpenRouterClient] Model {model} failed: {e}")
                if idx < len(self.model_chain) - 1:
                    logger.info(f"[OpenRouterClient] Trying next model in chain...")
                continue
        
        # Если все модели не сработали
        error_msg = f"Все модели в цепочке не сработали. Последняя ошибка: {last_error}"
        logger.error(f"[OpenRouterClient] {error_msg}")
        raise Exception(error_msg)
    
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


