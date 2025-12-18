"""
Middleware для бота (проверка авторизации и т.д.)
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class ProjectIDMiddleware(BaseMiddleware):
    """Middleware для передачи project_id в обработчики"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Добавляем project_id в data для обработчиков
        data["project_id"] = self.project_id
        return await handler(event, data)










