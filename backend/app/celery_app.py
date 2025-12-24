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

logger.info(f"Celery app initialized with broker: {settings.CELERY_BROKER_URL}")

