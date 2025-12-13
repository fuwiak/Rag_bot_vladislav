"""
Middleware для API (rate limiting и т.д.)
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from collections import defaultdict
from typing import Dict, Tuple


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware для ограничения количества запросов"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        # Пропускаем health checks
        if request.url.path in ["/health", "/ready"]:
            return await call_next(request)
        
        # Получаем идентификатор клиента
        client_id = request.client.host if request.client else "unknown"
        
        # Проверка rate limit
        current_time = time.time()
        
        # Удаление старых запросов (старше минуты)
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if current_time - req_time < 60
        ]
        
        # Проверка лимита
        if len(self.requests[client_id]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Превышен лимит запросов. Попробуйте позже."
            )
        
        # Добавление текущего запроса
        self.requests[client_id].append(current_time)
        
        # Продолжение обработки
        response = await call_next(request)
        return response

