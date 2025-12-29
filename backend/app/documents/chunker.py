"""
Разбивка текста на чанки для векторного поиска
"""
from typing import List


class DocumentChunker:
    """Разбивка документов на чанки"""
    
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 200):
        """
        Инициализация chunker
        
        Args:
            chunk_size: Размер чанка в символах
            chunk_overlap: Перекрытие между чанками
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Разбить текст на чанки
        
        Args:
            text: Текст для разбивки
        
        Returns:
            Список чанков
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Попытка разбить по предложению
            if end < len(text):
                # Ищем ближайшую точку, восклицательный или вопросительный знак
                for delimiter in ['. ', '.\n', '! ', '!\n', '? ', '?\n']:
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





















