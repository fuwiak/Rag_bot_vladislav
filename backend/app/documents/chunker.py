"""
Разбивка текста на чанки для векторного поиска
Использует параметры из рабочего скрипта: chunk_size=1000, chunk_overlap=200
"""
from typing import List

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    RECURSIVE_SPLITTER_AVAILABLE = True
except ImportError:
    RECURSIVE_SPLITTER_AVAILABLE = False


class DocumentChunker:
    """Разбивка документов на чанки"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Инициализация chunker
        
        Args:
            chunk_size: Размер чанка в символах (по умолчанию 1000, как в рабочем скрипте)
            chunk_overlap: Перекрытие между чанками (по умолчанию 200, как в рабочем скрипте)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Используем RecursiveCharacterTextSplitter если доступен (как в рабочем скрипте)
        if RECURSIVE_SPLITTER_AVAILABLE:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
        else:
            self.text_splitter = None
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Разбить текст на чанки
        
        Args:
            text: Текст для разбивки
        
        Returns:
            Список чанков
        """
        if not text or len(text.strip()) == 0:
            return []
        
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []
        
        # Используем RecursiveCharacterTextSplitter если доступен (как в рабочем скрипте)
        if self.text_splitter:
            try:
                chunks = self.text_splitter.split_text(text)
                # Фильтруем пустые чанки
                chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
                return chunks
            except Exception as e:
                # Fallback на простой метод при ошибке
                pass
        
        # Fallback: простой метод разбивки (если RecursiveCharacterTextSplitter недоступен)
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Попытка разбить по предложению
            if end < len(text):
                # Ищем ближайшую точку, восклицательный или вопросительный знак
                for delimiter in ['. ', '.\n', '! ', '!\n', '? ', '?\n', '\n\n', '\n']:
                    last_delimiter = text.rfind(delimiter, start, end)
                    if last_delimiter != -1:
                        end = last_delimiter + len(delimiter)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Переход к следующему чанку с учетом overlap
            start = end - self.chunk_overlap
            if start >= len(text):
                break
        
        return chunks
























