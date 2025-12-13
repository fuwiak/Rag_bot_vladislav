"""
Фабрика для создания и управления множественными Telegram ботами
"""
from typing import Dict, Optional
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.project import Project
from app.bot.handlers import register_handlers


class BotFactory:
    """Фабрика для управления Telegram ботами"""
    
    def __init__(self):
        self.bots: Dict[str, Bot] = {}  # Ключ: bot_token
        self.dispatchers: Dict[str, Dispatcher] = {}  # Ключ: bot_token
        self.token_to_projects: Dict[str, list] = {}  # bot_token -> [project_id, ...]
    
    async def start_all_bots(self):
        """Запустить все боты из проектов с настроенными токенами"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Project).where(Project.bot_token.isnot(None))
            )
            projects = result.scalars().all()
            
            # Группируем проекты по bot_token
            projects_by_token: Dict[str, list] = {}
            for project in projects:
                if project.bot_token:
                    token = project.bot_token
                    if token not in projects_by_token:
                        projects_by_token[token] = []
                    projects_by_token[token].append(str(project.id))
            
            # Создаем бота для каждого уникального токена
            for bot_token, project_ids in projects_by_token.items():
                await self.create_bot_for_token(bot_token, project_ids)
    
    async def create_bot_for_token(self, bot_token: str, project_ids: list):
        """
        Создать бота для токена (может обслуживать несколько проектов)
        
        Args:
            bot_token: Токен бота
            project_ids: Список ID проектов, которые используют этот токен
        """
        if bot_token in self.bots:
            # Бот уже существует, просто обновляем список проектов
            self.token_to_projects[bot_token] = project_ids
            return
        
        # Создание бота
        bot = Bot(
            token=bot_token,
            parse_mode=ParseMode.HTML
        )
        
        # Создание диспетчера
        dp = Dispatcher()
        
        # Регистрация обработчиков для всех проектов с этим токеном
        from app.bot.handlers import register_handlers
        for project_id in project_ids:
            register_handlers(dp, project_id)
        
        # Сохранение бота и диспетчера
        self.bots[bot_token] = bot
        self.dispatchers[bot_token] = dp
        self.token_to_projects[bot_token] = project_ids
        
        # Запуск polling в фоновой задаче (не блокируем)
        import asyncio
        asyncio.create_task(dp.start_polling(bot))
    
    async def create_bot(self, project_id: str, bot_token: str):
        """
        Создать и запустить бота для проекта (совместимость со старым API)
        
        Args:
            project_id: ID проекта
            bot_token: Токен бота
        """
        # Добавляем проект к существующему боту или создаем новый
        if bot_token in self.token_to_projects:
            if project_id not in self.token_to_projects[bot_token]:
                self.token_to_projects[bot_token].append(project_id)
                # Перерегистрируем обработчики
                dp = self.dispatchers[bot_token]
                from app.bot.handlers import register_handlers
                register_handlers(dp, project_id)
        else:
            await self.create_bot_for_token(bot_token, [project_id])
    
    async def stop_bot(self, project_id: str):
        """Остановить бота проекта (совместимость - не останавливает если есть другие проекты с тем же токеном)"""
        # Находим токен для этого проекта
        bot_token = None
        for token, project_ids in self.token_to_projects.items():
            if project_id in project_ids:
                bot_token = token
                # Удаляем проект из списка
                project_ids.remove(project_id)
                # Если это был последний проект, останавливаем бота
                if not project_ids:
                    if token in self.bots:
                        await self.bots[token].session.close()
                        del self.bots[token]
                        del self.dispatchers[token]
                        del self.token_to_projects[token]
                break
    
    async def stop_all_bots(self):
        """Остановить все боты"""
        # Останавливаем все боты по токенам
        for bot_token in list(self.bots.keys()):
            bot = self.bots[bot_token]
            await bot.session.close()
            del self.bots[bot_token]
            if bot_token in self.dispatchers:
                del self.dispatchers[bot_token]
            if bot_token in self.token_to_projects:
                del self.token_to_projects[bot_token]
    
    def get_bot(self, project_id: str) -> Optional[Bot]:
        """Получить бота по ID проекта"""
        # Ищем bot_token для этого проекта
        for token, project_ids in self.token_to_projects.items():
            if project_id in project_ids:
                return self.bots.get(token)
        return None

