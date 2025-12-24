"""
Форматирование ответов от LLM
"""
import re
from typing import List, Dict, Optional


class ResponseFormatter:
    """Форматировщик ответов"""
    
    def format_response(
        self,
        response: str,
        max_length: int,
        chunks: List[Dict[str, any]] = None
    ) -> str:
        """
        Форматировать ответ с учетом ограничений и добавлением цитат
        
        Args:
            response: Ответ от LLM
            max_length: Максимальная длина ответа
            chunks: Релевантные чанки для добавления цитат
        
        Returns:
            Отформатированный ответ
        """
        # Очищаем markdown форматирование для Telegram
        response = self._clean_markdown(response)
        
        # Обрезка по длине если необходимо (оставляем место для цитат)
        max_response_length = max_length - 200  # Резерв для цитат
        if len(response) > max_response_length:
            response = response[:max_response_length].rsplit('.', 1)[0] + "..."
        
        # Добавление цитат если есть релевантные чанки
        if chunks and len(chunks) > 0:
            sources = self._extract_sources(chunks)
            if sources:
                response += "\n\n📚 Источники:\n" + sources
        
        # Финальная проверка длины
        if len(response) > max_length:
            response = response[:max_length].rsplit('.', 1)[0] + "..."
        
        return response.strip()
    
    def _clean_markdown(self, text: str) -> str:
        """
        Очищает markdown форматирование для Telegram
        Удаляет markdown синтаксис, оставляя только чистый текст
        
        Args:
            text: Текст с markdown форматированием
        
        Returns:
            Очищенный текст без markdown
        """
        if not text:
            return text
        
        # Удаляем заголовки markdown (###, ##, #)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Удаляем жирный текст markdown (**text** или __text__) - убираем звездочки и подчеркивания
        # Сначала обрабатываем двойные звездочки
        text = re.sub(r'\*\*([^*]+?)\*\*', r'\1', text)
        # Затем одиночные звездочки для жирного (если есть)
        text = re.sub(r'\*([^*\n]+?)\*', r'\1', text)
        # Двойные подчеркивания
        text = re.sub(r'__([^_]+?)__', r'\1', text)
        
        # Удаляем курсив markdown (_text_ или *text*, но аккуратно)
        # Одиночные подчеркивания (курсив)
        text = re.sub(r'(?<![_*])_([^_\n]+?)_(?![_*])', r'\1', text)
        
        # Удаляем зачеркнутый текст (~~text~~)
        text = re.sub(r'~~([^~]+?)~~', r'\1', text)
        
        # Удаляем inline code блоки (`code`) - оставляем только текст
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # Удаляем code blocks (```code```)
        text = re.sub(r'```[\s\S]*?```', '', text)
        
        # Удаляем ссылки markdown [text](url) - оставляем только текст
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Удаляем списки markdown (-, *, +) - заменяем на простые списки
        text = re.sub(r'^[\s]*[-*+]\s+', '• ', text, flags=re.MULTILINE)
        
        # Удаляем нумерованные списки (1., 2., etc) - оставляем только текст
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
        
        # Удаляем горизонтальные линии (---, ***)
        text = re.sub(r'^[-*]{3,}$', '', text, flags=re.MULTILINE)
        
        # Удаляем оставшиеся одиночные звездочки (которые могли остаться)
        text = re.sub(r'\*+', '', text)
        
        # Удаляем оставшиеся одиночные подчеркивания (которые могли остаться)
        text = re.sub(r'_+', '', text)
        
        # Удаляем лишние пустые строки (более 2 подряд)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Убираем пробелы в начале и конце строк
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def _extract_sources(self, chunks: List[Dict[str, any]]) -> str:
        """
        Извлечь источники из чанков
        
        Args:
            chunks: Список релевантных чанков
        
        Returns:
            Форматированная строка с источниками
        """
        sources = []
        seen_docs = set()
        
        for i, chunk in enumerate(chunks[:3], 1):  # Берем максимум 3 источника
            payload = chunk.get("payload", {})
            document_id = payload.get("document_id")
            chunk_index = payload.get("chunk_index", 0)
            chunk_text = payload.get("chunk_text", "")
            
            # Получаем название документа если есть
            doc_name = f"Документ {document_id[:8]}" if document_id else f"Чанк {i}"
            
            # Создаем короткую цитату (первые 100 символов)
            quote = chunk_text[:100].strip()
            if len(chunk_text) > 100:
                quote += "..."
            
            # Избегаем дубликатов
            source_key = f"{document_id}_{chunk_index}"
            if source_key not in seen_docs:
                seen_docs.add(source_key)
                sources.append(f"{i}. {doc_name}, чанк {chunk_index + 1}: \"{quote}\"")
        
        return "\n".join(sources) if sources else ""











