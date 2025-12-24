"""
Скрипт для загрузки PDF файлов в векторную БД Qdrant.
Извлекает текст из PDF и загружает его для использования в RAG.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from qdrant_loader import QdrantLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_pdf(pdf_path: str, source_url: str = None, qdrant_loader: QdrantLoader = None) -> int:
    """
    Загружает PDF файл в векторную БД.
    
    Args:
        pdf_path: Путь к PDF файлу
        source_url: URL источника (если есть)
        qdrant_loader: Существующий экземпляр QdrantLoader (опционально)
    
    Returns:
        Количество загруженных чанков
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF файл не найден: {pdf_path}")
    
    if pdf_path.suffix.lower() != '.pdf':
        raise ValueError(f"Файл не является PDF: {pdf_path}")
    
    # Если source_url не указан, используем путь относительно media/
    if source_url is None:
        # Извлекаем относительный путь начиная с media/
        pdf_path_str = str(pdf_path)
        media_index = pdf_path_str.find("media/")
        if media_index != -1:
            # Используем путь начиная с media/
            source_url = f"file://{pdf_path_str[media_index:]}"
        else:
            # Если media/ не найден, используем просто имя файла с префиксом media/
            source_url = f"file://media/{pdf_path.name}"
    
    logger.info(f"Загрузка PDF файла: {pdf_path}")
    logger.info(f"Источник: {source_url}")
    
    try:
        # Используем переданный loader или создаем новый
        loader = qdrant_loader or QdrantLoader()
        chunks_count = loader.load_from_file(
            file_path=str(pdf_path),
            source_url=source_url,
            metadata={
                "document_type": "pdf",
                "source": "local_file"
            }
        )
        
        logger.info(f"✅ Успешно загружено {chunks_count} чанков из PDF")
        return chunks_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке PDF: {str(e)}")
        raise


def main():
    """Главная функция для запуска скрипта"""
    load_dotenv()
    
    logger.info("="*50)
    logger.info("Загрузка PDF файла в векторную БД Qdrant")
    logger.info("="*50)
    logger.warning("⚠️  ВАЖНО: Убедитесь, что бот НЕ запущен!")
    logger.warning("Локальный Qdrant не поддерживает одновременный доступ.")
    logger.info("")
    
    # Путь к PDF файлу
    pdf_path = os.getenv(
        "PDF_PATH",
        "media/Сравнение продуктов для бизнеса _ Лаборатория Касперского.pdf"
    )
    
    # Полный путь, если указан относительный
    if not Path(pdf_path).is_absolute():
        pdf_path = Path(__file__).parent / pdf_path
    
    pdf_path = str(pdf_path)
    
    if not Path(pdf_path).exists():
        logger.error(f"PDF файл не найден: {pdf_path}")
        logger.info("Укажите правильный путь в переменной окружения PDF_PATH")
        logger.info("Или поместите PDF файл в папку media/")
        return
    
    # URL источника (можно указать через переменную окружения)
    source_url = os.getenv("PDF_SOURCE_URL")
    if source_url is None:
        # Извлекаем относительный путь начиная с media/
        pdf_path_str = str(pdf_path)
        media_index = pdf_path_str.find("media/")
        if media_index != -1:
            # Используем путь начиная с media/
            source_url = f"file://{pdf_path_str[media_index:]}"
        else:
            # Если media/ не найден, используем просто имя файла с префиксом media/
            source_url = f"file://media/{Path(pdf_path).name}"
    
    try:
        chunks_count = load_pdf(pdf_path, source_url)
        
        logger.info("="*50)
        logger.info(f"✅ Успешно загружено {chunks_count} чанков в векторную БД")
        logger.info("Теперь данные из PDF доступны для RAG поиска")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке PDF: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

