"""
Построение промптов для LLM
"""
from typing import List, Dict


class PromptBuilder:
    """Построитель промптов"""
    
    DEFAULT_TEMPLATE = """Ты помощник, который отвечает на вопросы пользователя.

Контекст из документов (если доступен):
{chunks}

Вопрос пользователя: {question}

Правила:
1. Если есть контекст из документов, отвечай в первую очередь на его основе
2. Если контекста нет или информации недостаточно, можешь использовать свои знания, но укажи это
3. Будь кратким и структурированным
4. Максимальная длина ответа: {max_length} символов
5. Если используешь информацию из документов, укажи это

Ответ:"""
    
    def build_prompt(
        self,
        question: str,
        chunks: List[str],
        prompt_template: str,
        max_length: int,
        conversation_history: List[Dict[str, str]] = None,
        metadata_context: str = ""
    ) -> List[Dict[str, str]]:
        """
        Построить промпт для LLM
        
        Args:
            question: Вопрос пользователя
            chunks: Релевантные чанки документов
            prompt_template: Шаблон промпта из проекта
            max_length: Максимальная длина ответа
            conversation_history: История диалога
            metadata_context: Контекст из метаданных документов (названия файлов, ключевые слова)
        
        Returns:
            Список сообщений для LLM
        """
        # Объединение чанков/summaries в контекст (может быть пустым)
        if chunks and len(chunks) > 0:
            # Проверяем, являются ли это summaries (содержат "Документ 'filename':")
            is_summaries = any("Документ '" in chunk for chunk in chunks)
            if is_summaries:
                # Это summaries - форматируем как summaries документов
                context = "\n\n".join([f"{chunk}" for chunk in chunks])
                context = f"Краткие содержания документов:\n\n{context}\n\nИспользуй эту информацию для ответа на вопрос."
            else:
                # Это обычные чанки
                context = "\n\n".join([f"[Чанк {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)])
        else:
            # Если нет чанков, но есть метаданные - используем их
            if metadata_context:
                context = f"""Метаданные загруженных документов (документы могут еще обрабатываться):

{metadata_context}

ВАЖНО: Используй эту информацию для ответа на вопрос пользователя. 
- Если вопрос касается конкретных файлов (например, "что в файле X.pdf"), используй названия файлов из метаданных
- Если вопрос о ключевых словах или темах, используй ключевые слова из метаданных
- Если вопрос о содержании документов, можешь ответить на основе названий файлов и ключевых слов
- Если информации недостаточно, укажи, что документы еще обрабатываются, но можешь дать ответ на основе доступных метаданных"""
            else:
                context = "Контекст из документов отсутствует. Отвечай на основе своих знаний, но учитывай настройки проекта."
        
        # Добавляем метаданные к контексту, если они есть и есть чанки (для дополнительного контекста)
        if metadata_context and chunks:
            context += f"\n\nДополнительная информация о документах проекта:\n{metadata_context}\n\nИспользуй эту информацию для более полного ответа."
        
        # Замена плейсхолдеров в шаблоне
        system_prompt = prompt_template.format(
            chunks=context,
            question=question,
            max_length=max_length
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Добавление истории диалога если есть
        if conversation_history:
            # Берем последние N сообщений для контекста
            recent_history = conversation_history[-6:]  # Последние 3 пары вопрос-ответ
            messages.extend(recent_history)
        else:
            messages.append({"role": "user", "content": question})
        
        return messages















