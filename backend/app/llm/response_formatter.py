"""
Форматирование ответов от LLM
"""
from typing import List, Dict


class ResponseFormatter:
    """Форматировщик ответов"""
    
    def format_response(
        self,
        response: str,
        max_length: int,
        chunks: List[Dict[str, any]] = None
    ) -> str:
        """
        Форматировать ответ с учетом ограничений
        
        Args:
            response: Ответ от LLM
            max_length: Максимальная длина ответа
            chunks: Релевантные чанки для добавления цитат
        
        Returns:
            Отформатированный ответ
        """
        # Обрезка по длине если необходимо
        if len(response) > max_length:
            response = response[:max_length].rsplit('.', 1)[0] + "..."
        
        # Добавление цитат если есть релевантные чанки
        if chunks and len(chunks) > 0:
            # Можно добавить ссылки на источники
            # response += "\n\nИсточники: [1, 2, 3]"
            pass
        
        return response.strip()








