"""
Адаптер Agent Service для обработки файлов из папки /documents
Оптимизирован для быстрой индексации больших PDF (200+ страниц)
"""
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.document import Document
from app.models.project import Project
from app.documents.parser import DocumentParser
from app.tasks.document_tasks import process_document_task, process_large_document_with_langgraph
from sqlalchemy import select

logger = logging.getLogger(__name__)


class DocumentAgentAdapter:
    """
    Адаптер для обработки файлов из папки /documents через Agent Service
    Оптимизирован для быстрой индексации больших PDF
    """
    
    def __init__(self, documents_path: Optional[Path] = None):
        """
        Args:
            documents_path: Путь к папке с документами (по умолчанию media/documents)
        """
        if documents_path is None:
            # По умолчанию используем media/documents
            self.documents_path = Path("media") / "documents"
        else:
            self.documents_path = Path(documents_path)
        
        self.parser = DocumentParser()
        self.supported_extensions = {'.pdf', '.docx', '.txt', '.xlsx', '.xls', '.md'}
    
    async def scan_documents_folder(
        self,
        project_id: Optional[UUID] = None,
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Сканирует папку с документами и возвращает список файлов
        
        Args:
            project_id: ID проекта (если указан, ищет в подпапке проекта)
            recursive: Рекурсивный поиск
        
        Returns:
            Список словарей с информацией о файлах
        """
        if not self.documents_path.exists():
            logger.warning(f"Папка документов не найдена: {self.documents_path}")
            return []
        
        # Если указан project_id, ищем в подпапке проекта
        if project_id:
            search_path = self.documents_path / str(project_id)
        else:
            search_path = self.documents_path
        
        if not search_path.exists():
            logger.info(f"Папка проекта не найдена: {search_path}")
            return []
        
        files = []
        pattern = "**/*" if recursive else "*"
        
        for file_path in search_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                file_info = {
                    "path": str(file_path),
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "extension": file_path.suffix.lower().lstrip('.'),
                    "relative_path": str(file_path.relative_to(search_path))
                }
                files.append(file_info)
        
        logger.info(f"Найдено {len(files)} файлов в {search_path}")
        return files
    
    async def process_file_from_folder(
        self,
        file_path: str,
        project_id: UUID,
        use_fast_indexing: bool = True
    ) -> Dict[str, Any]:
        """
        Обрабатывает один файл из папки
        
        Args:
            file_path: Путь к файлу
            project_id: ID проекта
            use_fast_indexing: Использовать быструю индексацию для больших PDF
        
        Returns:
            Результат обработки
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            return {
                "success": False,
                "error": f"Файл не найден: {file_path}"
            }
        
        file_type = file_path_obj.suffix.lower().lstrip('.')
        filename = file_path_obj.name
        file_size = file_path_obj.stat().st_size
        
        logger.info(f"[Agent Adapter] Обработка файла: {filename} ({file_size / 1024 / 1024:.2f} MB)")
        
        async with AsyncSessionLocal() as db:
            # Проверяем, существует ли уже документ с таким именем
            result = await db.execute(
                select(Document)
                .where(
                    Document.project_id == project_id,
                    Document.filename == filename
                )
            )
            existing_doc = result.scalar_one_or_none()
            
            if existing_doc:
                logger.info(f"[Agent Adapter] Документ {filename} уже существует, пропускаем")
                return {
                    "success": True,
                    "skipped": True,
                    "document_id": str(existing_doc.id),
                    "message": "Документ уже обработан"
                }
            
            # Читаем файл
            with open(file_path_obj, 'rb') as f:
                file_content = f.read()
            
            # Определяем, большой ли это PDF (для оптимизации)
            is_large_pdf = (
                file_type == "pdf" and 
                file_size > 5 * 1024 * 1024  # Больше 5MB
            )
            
            # Быстрая проверка размера текста для PDF
            if is_large_pdf:
                try:
                    # Быстрый парсинг первой страницы для оценки размера
                    preview_text = await self._quick_pdf_preview(file_content)
                    estimated_pages = len(preview_text) // 3000  # Примерно 3000 символов на страницу
                    
                    if estimated_pages > 100:
                        is_large_pdf = True
                        logger.info(f"[Agent Adapter] Большой PDF обнаружен: ~{estimated_pages} страниц")
                except Exception as e:
                    logger.warning(f"[Agent Adapter] Не удалось оценить размер PDF: {e}")
            
            # Создаем документ в БД
            document = Document(
                project_id=project_id,
                filename=filename,
                content="Обработка...",
                file_type=file_type
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)
            
            logger.info(f"[Agent Adapter] Документ создан в БД: {document.id}")
            
            # Выбираем стратегию обработки
            if is_large_pdf and use_fast_indexing:
                # Используем оптимизированную обработку для больших PDF
                logger.info(f"[Agent Adapter] Используем быструю индексацию для большого PDF")
                task_result = process_large_document_with_langgraph.delay(
                    str(document.id),
                    str(project_id),
                    str(file_path_obj),
                    filename,
                    file_type
                )
            else:
                # Обычная обработка
                task_result = process_document_task.delay(
                    str(document.id),
                    str(project_id),
                    str(file_path_obj),
                    filename,
                    file_type
                )
            
            return {
                "success": True,
                "document_id": str(document.id),
                "task_id": task_result.id,
                "filename": filename,
                "file_size": file_size,
                "is_large_pdf": is_large_pdf,
                "use_fast_indexing": is_large_pdf and use_fast_indexing
            }
    
    async def _quick_pdf_preview(self, content: bytes, max_pages: int = 5) -> str:
        """
        Быстрый предпросмотр PDF для оценки размера
        
        Args:
            content: Содержимое PDF файла
            max_pages: Максимальное количество страниц для парсинга
        
        Returns:
            Текст первых страниц
        """
        try:
            import PyPDF2
            import io
            
            pdf_file = io.BytesIO(content)
            reader = PyPDF2.PdfReader(pdf_file)
            
            total_pages = len(reader.pages)
            pages_to_read = min(max_pages, total_pages)
            
            text_parts = []
            for i in range(pages_to_read):
                try:
                    text = reader.pages[i].extract_text()
                    if text:
                        text_parts.append(text)
                except Exception:
                    continue
            
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.warning(f"Ошибка быстрого предпросмотра PDF: {e}")
            return ""
    
    async def process_all_files_from_folder(
        self,
        project_id: UUID,
        use_fast_indexing: bool = True,
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """
        Обрабатывает все файлы из папки проекта
        
        Args:
            project_id: ID проекта
            use_fast_indexing: Использовать быструю индексацию
            max_concurrent: Максимальное количество одновременных задач
        
        Returns:
            Результат обработки всех файлов
        """
        files = await self.scan_documents_folder(project_id=project_id)
        
        if not files:
            return {
                "success": True,
                "processed": 0,
                "skipped": 0,
                "errors": 0,
                "message": "Файлы не найдены"
            }
        
        logger.info(f"[Agent Adapter] Найдено {len(files)} файлов для обработки")
        
        # Обрабатываем файлы с ограничением параллелизма
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        
        async def process_with_semaphore(file_info):
            async with semaphore:
                return await self.process_file_from_folder(
                    file_info["path"],
                    project_id,
                    use_fast_indexing
                )
        
        # Запускаем обработку всех файлов
        tasks = [process_with_semaphore(file_info) for file_info in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Подсчитываем результаты
        processed = 0
        skipped = 0
        errors = 0
        
        for result in results:
            if isinstance(result, Exception):
                errors += 1
                logger.error(f"[Agent Adapter] Ошибка обработки: {result}")
            elif result.get("success"):
                if result.get("skipped"):
                    skipped += 1
                else:
                    processed += 1
            else:
                errors += 1
        
        return {
            "success": True,
            "processed": processed,
            "skipped": skipped,
            "errors": errors,
            "total": len(files),
            "results": results
        }
    
    async def get_processing_status(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """
        Получает статус обработки документов проекта
        
        Args:
            project_id: ID проекта
        
        Returns:
            Статус обработки
        """
        async with AsyncSessionLocal() as db:
            # Получаем все документы проекта
            result = await db.execute(
                select(Document)
                .where(Document.project_id == project_id)
            )
            documents = result.scalars().all()
            
            # Подсчитываем статусы
            total = len(documents)
            processing = sum(1 for doc in documents if doc.content == "Обработка...")
            ready = sum(1 for doc in documents if doc.content and doc.content != "Обработка...")
            errors = sum(1 for doc in documents if doc.content and doc.content.startswith("Ошибка"))
            
            return {
                "total": total,
                "processing": processing,
                "ready": ready,
                "errors": errors,
                "documents": [
                    {
                        "id": str(doc.id),
                        "filename": doc.filename,
                        "status": (
                            "processing" if doc.content == "Обработка..." else
                            "error" if doc.content and doc.content.startswith("Ошибка") else
                            "ready"
                        ),
                        "file_type": doc.file_type,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None
                    }
                    for doc in documents
                ]
            }
