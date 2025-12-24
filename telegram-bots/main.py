"""
Entry point для Telegram Bots Service
Отдельный сервис для управления Telegram ботами
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Добавляем путь к backend для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.bot.bot_factory import BotFactory
from app.models.project import Project
from sqlalchemy import select

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BotService:
    """Сервис для управления Telegram ботами"""
    
    def __init__(self):
        self.bot_factory = BotFactory()
        self.running = False
        self.check_interval = 20  # Проверка изменений каждые 20 секунд
        self.last_projects_hash = None
    
    async def start(self):
        """Запуск сервиса"""
        logger.info("Starting Telegram Bots Service...")
        
        # Инициализация БД
        try:
            if not settings.SKIP_DB_INIT:
                await init_db()
                logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            logger.warning("Service will continue, but bots may not work properly")
        
        # Запуск всех активных ботов при старте
        try:
            await self.bot_factory.start_all_bots()
            logger.info("All active bots started")
        except Exception as e:
            logger.error(f"Failed to start bots: {e}")
        
        self.running = True
        
        # Запуск периодической проверки изменений
        asyncio.create_task(self._monitor_changes())
        
        logger.info("Telegram Bots Service started successfully")
    
    async def stop(self):
        """Остановка сервиса"""
        logger.info("Stopping Telegram Bots Service...")
        self.running = False
        
        try:
            await self.bot_factory.stop_all_bots()
            logger.info("All bots stopped")
        except Exception as e:
            logger.error(f"Error stopping bots: {e}")
        
        logger.info("Telegram Bots Service stopped")
    
    async def _monitor_changes(self):
        """Периодическая проверка БД на изменения"""
        while self.running:
            try:
                await asyncio.sleep(self.check_interval)
                
                if not self.running:
                    break
                
                # Получаем текущее состояние проектов
                async with AsyncSessionLocal() as db:
                    try:
                        # Пытаемся загрузить с bot_is_active
                        result = await db.execute(
                            select(Project).where(Project.bot_token.isnot(None))
                        )
                        projects = result.scalars().all()
                    except Exception as e:
                        # Если поле bot_is_active не существует, используем raw SQL
                        logger.warning(f"Field bot_is_active not found in monitor, using raw query: {e}")
                        # Откатываем транзакцию
                        await db.rollback()
                        # Используем raw SQL без bot_is_active
                        from sqlalchemy import text
                        result = await db.execute(
                            text("SELECT id, name, description, bot_token, llm_model, created_at, updated_at FROM projects WHERE bot_token IS NOT NULL")
                        )
                        # Создаем объекты Project вручную
                        projects = []
                        for row in result:
                            project = Project()
                            project.id = row.id
                            project.name = row.name
                            project.description = row.description
                            project.bot_token = row.bot_token
                            project.llm_model = row.llm_model
                            project.created_at = row.created_at
                            project.updated_at = row.updated_at
                            # bot_is_active не существует, используем значение по умолчанию
                            setattr(project, 'bot_is_active', 'false')
                            projects.append(project)
                
                # Создаем хеш текущего состояния для сравнения
                current_hash = self._get_projects_hash(projects)
                
                # Если состояние изменилось, обновляем боты
                if current_hash != self.last_projects_hash:
                    logger.info("Projects changed, updating bots...")
                    await self._update_bots(projects)
                    self.last_projects_hash = current_hash
                    
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)  # Короткая пауза при ошибке
    
    def _get_projects_hash(self, projects):
        """Создать хеш состояния проектов для сравнения"""
        # Создаем строку из ID проектов, их токенов и bot_is_active
        project_data = [
            (str(p.id), p.bot_token or "", getattr(p, 'bot_is_active', 'false') or 'false')
            for p in projects
        ]
        return hash(tuple(sorted(project_data)))
    
    async def _update_bots(self, projects):
        """Обновить боты на основе текущего состояния проектов"""
        # Группируем проекты по bot_token, учитывая bot_is_active
        projects_by_token = {}
        for project in projects:
            if project.bot_token:
                # Проверяем bot_is_active (может быть строкой "true"/"false" или None)
                # Если поле не существует в БД, считаем бота активным (для обратной совместимости)
                bot_is_active = getattr(project, 'bot_is_active', None)
                
                # Если поле не установлено или не существует, считаем бота активным
                # Это нужно для обратной совместимости, пока миграция не применится
                if bot_is_active is None or not hasattr(project, 'bot_is_active'):
                    # Поле не существует - считаем бота активным (обратная совместимость)
                    token = project.bot_token
                    if token not in projects_by_token:
                        projects_by_token[token] = []
                    projects_by_token[token].append(str(project.id))
                    logger.debug(f"Project {project.id} has bot_token, bot_is_active field missing - treating as active")
                elif bot_is_active == 'true':
                    # Поле существует и значение "true" - бот активен
                    token = project.bot_token
                    if token not in projects_by_token:
                        projects_by_token[token] = []
                    projects_by_token[token].append(str(project.id))
                else:
                    # Поле существует, но значение "false" - бот неактивен
                    logger.debug(f"Project {project.id} has bot_token but bot_is_active='false', skipping")
        
        # Получаем текущие активные токены
        active_tokens = set(self.bot_factory.bots.keys())
        new_tokens = set(projects_by_token.keys())
        
        # Останавливаем боты, которых больше нет в активных
        tokens_to_remove = active_tokens - new_tokens
        for token in tokens_to_remove:
            logger.info(f"Stopping bot with token {token[:10]}... (no longer active)")
            if token in self.bot_factory.bots:
                try:
                    await self.bot_factory.bots[token].session.close()
                    del self.bot_factory.bots[token]
                    if token in self.bot_factory.dispatchers:
                        del self.bot_factory.dispatchers[token]
                    if token in self.bot_factory.token_to_projects:
                        del self.bot_factory.token_to_projects[token]
                except Exception as e:
                    logger.error(f"Error stopping bot {token[:10]}: {e}")
        
        # Запускаем новые боты или обновляем существующие
        for bot_token, project_ids in projects_by_token.items():
            try:
                await self.bot_factory.create_bot_for_token(bot_token, project_ids)
                logger.info(f"Bot {bot_token[:10]}... is active for projects: {project_ids}")
            except Exception as e:
                logger.error(f"Error creating/updating bot {bot_token[:10]}: {e}")


# Глобальный экземпляр сервиса
bot_service = BotService()


def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"Received signal {signum}, shutting down...")
    asyncio.create_task(bot_service.stop())
    sys.exit(0)


async def main():
    """Главная функция"""
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot_service.start()
        
        # Бесконечный цикл для поддержания работы сервиса
        while bot_service.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await bot_service.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service crashed: {e}", exc_info=True)
        sys.exit(1)





