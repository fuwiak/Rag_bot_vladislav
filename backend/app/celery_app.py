"""
Celery приложение для фоновой обработки задач
"""
from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Создаем Celery приложение
celery_app = Celery(
    "rag_bot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks.document_tasks']
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут максимум на задачу
    task_soft_time_limit=25 * 60,  # 25 минут мягкий лимит
    worker_prefetch_multiplier=1,  # Обрабатываем по одной задаче за раз
    worker_max_tasks_per_child=50,  # Перезапускаем воркер после 50 задач для освобождения памяти
    task_acks_late=True,  # Подтверждаем задачу только после выполнения
    worker_disable_rate_limits=False,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)

# Логируем настройки подключения к Redis
logger.info(f"[CELERY] Инициализация Celery приложения...")

# Безопасное логирование URL (скрываем пароль)
def mask_redis_url(url: str) -> str:
    """Скрывает пароль в Redis URL для логирования"""
    if not url:
        return "НЕ УСТАНОВЛЕН!"
    if '@' in url:
        # Формат: redis://:password@host:port/db
        parts = url.split('@')
        if len(parts) == 2:
            return f"{parts[0].split(':')[0]}://:***@{parts[1]}"
    return url

broker_url_masked = mask_redis_url(settings.CELERY_BROKER_URL)
backend_url_masked = mask_redis_url(settings.CELERY_RESULT_BACKEND)

logger.info(f"[CELERY] Broker URL: {broker_url_masked}")
logger.info(f"[CELERY] Result Backend: {backend_url_masked}")

# Проверяем наличие пароля в URL
if settings.CELERY_BROKER_URL and '@' not in settings.CELERY_BROKER_URL:
    logger.warning(f"[CELERY] ⚠️ ВНИМАНИЕ: Broker URL не содержит пароль (@ отсутствует)")
    logger.warning(f"[CELERY] ⚠️ Если Redis требует пароль, добавьте REDIS_PASSWORD в переменные окружения")

if not settings.CELERY_BROKER_URL or not settings.CELERY_RESULT_BACKEND:
    logger.error("[CELERY] ❌ КРИТИЧЕСКАЯ ОШИБКА: Redis не настроен!")
    logger.error("[CELERY] ❌ CELERY_BROKER_URL или CELERY_RESULT_BACKEND не установлены")
    logger.error("[CELERY] ❌ Установите переменные окружения:")
    logger.error("[CELERY] ❌   - REDIS_URL (Railway создает автоматически)")
    logger.error("[CELERY] ❌   ИЛИ")
    logger.error("[CELERY] ❌   - REDIS_HOST=redis.railway.internal")
    logger.error("[CELERY] ❌   - REDIS_PORT=6379")
    logger.error("[CELERY] ❌   - REDIS_PASSWORD=<пароль из Railway>")
    logger.error("[CELERY] ❌   - REDIS_DB=0")
else:
    logger.info(f"[CELERY] ✅ Celery app initialized successfully")

