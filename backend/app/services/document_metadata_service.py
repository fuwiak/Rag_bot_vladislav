"""
Сервис для извлечения метаданных из документов
Использует легкий NLP для извлечения информации из названий файлов и метаданных
"""
import logging
import re
from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)

# Пробуем импортировать spaCy, но не критично если его нет
try:
    import spacy
    SPACY_AVAILABLE = True
    nlp = None
    try:
        # Пробуем загрузить русскую модель
        nlp = spacy.load("ru_core_news_sm")
        logger.debug("spaCy Russian model loaded successfully")
    except OSError:
        # Если русской модели нет, используем английскую
        try:
            nlp = spacy.load("en_core_web_sm")
            logger.debug("spaCy English model loaded successfully (Russian model not available)")
        except OSError:
            # Модели недоступны, но это не критично - используем простую экстракцию
            nlp = None
            SPACY_AVAILABLE = False
            logger.debug("spaCy models not available, using simple keyword extraction (this is normal)")
except ImportError:
    SPACY_AVAILABLE = False
    nlp = None
    logger.debug("spaCy not installed, using simple keyword extraction (this is normal)")


class DocumentMetadataService:
    """Сервис для извлечения метаданных из документов"""
    
    def __init__(self):
        self.nlp = nlp if SPACY_AVAILABLE and nlp else None
    
    def extract_keywords_from_filename(self, filename: str) -> List[str]:
        """
        Извлекает ключевые слова из названия файла
        
        Args:
            filename: Название файла
            
        Returns:
            Список ключевых слов
        """
        # Убираем расширение
        name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # Разделяем по подчеркиваниям, дефисам, пробелам
        parts = re.split(r'[_\-\s]+', name_without_ext)
        
        keywords = []
        for part in parts:
            part = part.strip()
            if part and len(part) > 2:  # Игнорируем очень короткие части
                # Убираем спецсимволы
                part_clean = re.sub(r'[^\w\s]', '', part)
                if part_clean:
                    keywords.append(part_clean.lower())
        
        # Если есть spaCy, используем его для извлечения сущностей
        if self.nlp and name_without_ext:
            try:
                doc = self.nlp(name_without_ext[:200])  # Ограничиваем длину
                # Извлекаем именованные сущности
                entities = [ent.text for ent in doc.ents if len(ent.text) > 2]
                keywords.extend([e.lower() for e in entities])
            except Exception as e:
                logger.debug(f"spaCy extraction failed: {e}")
        
        # Убираем дубликаты и возвращаем
        return list(set(keywords))[:10]  # Максимум 10 ключевых слов
    
    def extract_metadata_from_filename(self, filename: str) -> Dict[str, Any]:
        """
        Извлекает метаданные из названия файла
        
        Args:
            filename: Название файла
            
        Returns:
            Словарь с метаданными
        """
        metadata = {
            "filename": filename,
            "file_type": filename.rsplit('.', 1)[-1].lower() if '.' in filename else "unknown",
            "keywords": self.extract_keywords_from_filename(filename),
            "suggested_topics": []
        }
        
        # Извлекаем темы из названия файла
        name_lower = filename.lower()
        
        # Определяем возможные темы по ключевым словам
        topic_keywords = {
            "курс": ["курс", "course", "обучение", "training"],
            "ml": ["ml", "machine learning", "машинное обучение", "нейросеть"],
            "документ": ["документ", "document", "договор", "contract"],
            "письмо": ["письмо", "letter", "email", "письма"],
            "технический": ["технический", "technical", "support", "поддержка"],
            "соглашение": ["соглашение", "agreement", "договор"]
        }
        
        for topic, keywords_list in topic_keywords.items():
            if any(keyword in name_lower for keyword in keywords_list):
                metadata["suggested_topics"].append(topic)
        
        return metadata
    
    def create_metadata_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        Создает контекст из метаданных документов для использования в промпте
        
        Args:
            documents: Список документов с метаданными
            
        Returns:
            Текст контекста для промпта
        """
        if not documents:
            return ""
        
        context_parts = []
        context_parts.append("Доступные документы в проекте:")
        
        for i, doc in enumerate(documents, 1):
            filename = doc.get("filename", "Неизвестный файл")
            file_type = doc.get("file_type", "unknown")
            keywords = doc.get("keywords", [])
            created_at = doc.get("created_at")
            
            doc_info = f"{i}. Файл: {filename} (тип: {file_type.upper()})"
            
            if keywords:
                doc_info += f"\n   Ключевые слова: {', '.join(keywords[:5])}"
            
            if created_at:
                if isinstance(created_at, datetime):
                    date_str = created_at.strftime("%Y-%m-%d")
                else:
                    date_str = str(created_at)[:10]
                doc_info += f"\n   Загружен: {date_str}"
            
            context_parts.append(doc_info)
        
        return "\n".join(context_parts)
    
    async def get_documents_metadata(self, project_id: UUID, db) -> List[Dict[str, Any]]:
        """
        Получает метаданные всех документов проекта
        
        Args:
            project_id: ID проекта
            db: Сессия базы данных
            
        Returns:
            Список словарей с метаданными документов
        """
        try:
            from app.models.document import Document
            from sqlalchemy import select, text
            
            # Пробуем получить документы безопасно
            try:
                result = await db.execute(
                    select(Document.id, Document.filename, Document.file_type, Document.created_at)
                    .where(Document.project_id == project_id)
                    .limit(20)
                )
                rows = result.all()
            except Exception:
                # Fallback на raw SQL
                result = await db.execute(
                    text("""
                        SELECT id, filename, file_type, created_at 
                        FROM documents 
                        WHERE project_id = :project_id 
                        LIMIT 20
                    """),
                    {"project_id": str(project_id)}
                )
                rows = result.all()
            
            metadata_list = []
            for row in rows:
                doc_id = row[0]
                filename = row[1] or "Неизвестный файл"
                file_type = row[2] or "unknown"
                created_at = row[3]
                
                # Извлекаем метаданные из названия файла
                metadata = self.extract_metadata_from_filename(filename)
                metadata["id"] = doc_id
                metadata["file_type"] = file_type
                metadata["created_at"] = created_at
                
                metadata_list.append(metadata)
            
            return metadata_list
            
        except Exception as e:
            logger.error(f"Error getting documents metadata: {e}", exc_info=True)
            return []

