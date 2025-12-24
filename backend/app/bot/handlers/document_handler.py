"""
Обработчики загрузки документов в Telegram бот
"""
from aiogram import Dispatcher, F
from aiogram.types import Message, Document as TelegramDocument
from aiogram.fsm.context import FSMContext
from uuid import UUID
import logging
import os
import tempfile
from pathlib import Path

from app.core.database import AsyncSessionLocal
from app.bot.handlers.auth_handler import AuthStates
from app.models.document import Document
from app.tasks.document_tasks import process_document_task

logger = logging.getLogger(__name__)


async def handle_document(message: Message, state: FSMContext):
    """Обработка загрузки документа (PDF, Excel)"""
    # Проверка авторизации
    current_state = await state.get_state()
    if current_state != AuthStates.authorized:
        await message.answer("❌ Сначала авторизуйтесь через /start")
        return
    
    # Получаем project_id из состояния
    data = await state.get_data()
    project_id_str = data.get("project_id")
    
    if not project_id_str:
        await message.answer("❌ Ошибка: проект не найден. Используйте /start")
        return
    
    try:
        project_id = UUID(project_id_str)
    except ValueError:
        await message.answer("❌ Ошибка: неверный ID проекта")
        return
    
    # Проверяем, что это документ
    if not message.document:
        await message.answer("❌ Пожалуйста, отправьте файл (PDF или Excel)")
        return
    
    doc = message.document
    file_name = doc.file_name or "document"
    file_size = doc.file_size or 0
    
    # Проверяем размер файла (максимум 50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    if file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB")
        return
    
    # Определяем тип файла
    file_ext = Path(file_name).suffix.lower()
    if file_ext not in ['.pdf', '.xlsx', '.xls', '.docx', '.txt']:
        await message.answer("❌ Поддерживаются только файлы: PDF, Excel (.xlsx, .xls), Word (.docx), TXT")
        return
    
    file_type = file_ext.lstrip('.')
    
    # Отправляем сообщение о начале обработки
    processing_msg = await message.answer(f"📥 Загружаю файл: {file_name}...")
    
    try:
        # Скачиваем файл
        bot = message.bot
        file_info = await bot.get_file(doc.file_id)
        
        # Создаем временный файл
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / f"telegram_upload_{doc.file_id}_{file_name}"
        
        # Скачиваем файл
        await bot.download_file(file_info.file_path, destination=temp_file)
        
        logger.info(f"[TELEGRAM UPLOAD] File downloaded: {temp_file}, size: {file_size} bytes")
        
        # Читаем файл в память для обработки
        with open(temp_file, 'rb') as f:
            file_content = f.read()
        
        # Удаляем временный файл
        try:
            os.unlink(temp_file)
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")
        
        async with AsyncSessionLocal() as db:
            # Создаем документ в БД
            document = Document(
                project_id=project_id,
                filename=file_name,
                content="Обработка...",  # Временный placeholder
                file_type=file_type
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)
            
            logger.info(f"[TELEGRAM UPLOAD] Document created in DB: {document.id}")
            
            # Сохраняем файл во временное место для Celery задачи
            temp_path = temp_dir / f"celery_doc_{document.id}_{file_name}"
            with open(temp_path, 'wb') as f:
                f.write(file_content)
            
            # Запускаем обработку через Celery
            task_result = process_document_task.delay(
                str(document.id),
                str(project_id),
                str(temp_path),
                file_name,
                file_type
            )
            
            logger.info(f"[TELEGRAM UPLOAD] Celery task created: {task_result.id} for document {document.id}")
            
            await processing_msg.edit_text(
                f"✅ Файл загружен!\n\n"
                f"📄 Название: {file_name}\n"
                f"📊 Тип: {file_type.upper()}\n"
                f"📏 Размер: {file_size / 1024:.1f} KB\n\n"
                f"⏳ Обработка документа начата. Это может занять некоторое время.\n"
                f"Используйте /documents для просмотра списка документов."
            )
    
    except Exception as e:
        logger.error(f"[TELEGRAM UPLOAD] Error uploading document: {e}", exc_info=True)
        await processing_msg.edit_text(
            f"❌ Ошибка при загрузке файла: {str(e)}\n"
            f"Попробуйте позже или обратитесь к администратору."
        )


def register_document_handlers(dp: Dispatcher, project_id: str):
    """Регистрация обработчиков документов"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Регистрируем обработчик для документов (только для авторизованных пользователей)
    dp.message.register(handle_document, AuthStates.authorized, F.document)
    logger.info(f"[REGISTER HANDLERS] Document handlers registered for project {project_id}")

