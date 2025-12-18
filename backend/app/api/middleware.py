"""
Middleware для API (rate limiting и т.д.)
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict
from typing import Dict


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
        
        # Пропускаем OPTIONS запросы (CORS preflight)
        if request.method == "OPTIONS":
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
            return JSONResponse(
                status_code=429,
                content={"detail": "Превышен лимит запросов. Попробуйте позже."}
            )
        
        # Добавление текущего запроса
        self.requests[client_id].append(current_time)
        
        # Продолжение обработки
        response = await call_next(request)
        return response



