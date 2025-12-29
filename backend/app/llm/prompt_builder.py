"""
Построение промптов для LLM
"""
from typing import List, Dict
from app.core.prompt_config import get_prompt, get_constant, get_default


class PromptBuilder:
    """Построитель промптов"""
    
    @property
    def DEFAULT_TEMPLATE(self) -> str:
        """Дефолтный шаблон промпта из config.yaml"""
        return get_prompt("prompts.default_template")
    
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
                summaries_prefix = get_constant("constants.context.summaries_prefix", "")
                summaries_suffix = get_constant("constants.context.summaries_suffix", "")
                context = "\n\n".join([f"{chunk}" for chunk in chunks])
                context = f"{summaries_prefix}{context}{summaries_suffix}"
            else:
                # Это обычные чанки
                context = "\n\n".join([f"[Чанк {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)])
        else:
            # Если нет чанков, но есть метаданные - используем их
            if metadata_context:
                metadata_prefix = get_constant("constants.context.metadata_prefix", "")
                metadata_instruction = get_constant("constants.context.metadata_instruction", "")
                context = f"""{metadata_prefix}{metadata_context}

{metadata_instruction}"""
            else:
                context = get_constant("constants.context.no_chunks", "Контекст из документов отсутствует. Отвечай на основе своих знаний, но учитывай настройки проекта.")
        
        # Добавляем метаданные к контексту, если они есть и есть чанки (для дополнительного контекста)
        if metadata_context and chunks:
            additional_metadata = get_constant("constants.context.additional_metadata", "")
            context += additional_metadata.format(metadata_context=metadata_context)
        
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
