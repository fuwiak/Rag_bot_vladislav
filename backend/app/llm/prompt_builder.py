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
        conversation_history: List[Dict[str, str]] = None
    ) -> List[Dict[str, str]]:
        """
        Построить промпт для LLM
        
        Args:
            question: Вопрос пользователя
            chunks: Релевантные чанки документов
            prompt_template: Шаблон промпта из проекта
            max_length: Максимальная длина ответа
            conversation_history: История диалога
        
        Returns:
            Список сообщений для LLM
        """
        # Объединение чанков в контекст (может быть пустым)
        if chunks and len(chunks) > 0:
            context = "\n\n".join([f"[Чанк {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)])
        else:
            context = "Контекст из документов отсутствует. Отвечай на основе своих знаний, но учитывай настройки проекта."
        
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















