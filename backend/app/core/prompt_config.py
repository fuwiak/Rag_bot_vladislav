"""
Загрузка и управление промптами из config.yaml
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Кэш для загруженной конфигурации
_config_cache: Optional[Dict[str, Any]] = None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Загрузить конфигурацию из config.yaml
    
    Args:
        config_path: Путь к config.yaml (если None, ищется в backend/config.yaml)
    
    Returns:
        Словарь с конфигурацией
    """
    global _config_cache
    
    # Если конфигурация уже загружена, возвращаем кэш
    if _config_cache is not None:
        return _config_cache
    
    # Определяем путь к config.yaml
    if config_path is None:
        # Ищем config.yaml в backend/
        backend_dir = Path(__file__).parent.parent
        config_path = backend_dir / "config.yaml"
    else:
        config_path = Path(config_path)
    
    # Загружаем конфигурацию
    try:
        if not config_path.exists():
            logger.warning(f"Config file not found at {config_path}, using defaults")
            _config_cache = _get_default_config()
            return _config_cache
        
        with open(config_path, 'r', encoding='utf-8') as f:
            _config_cache = yaml.safe_load(f)
        
        logger.info(f"Loaded prompt configuration from {config_path}")
        return _config_cache
    
    except Exception as e:
        logger.error(f"Error loading config.yaml: {e}, using defaults")
        _config_cache = _get_default_config()
        return _config_cache


def get_prompt(key: str, **kwargs) -> str:
    """
    Получить промпт по ключу с подстановкой переменных
    
    Args:
        key: Ключ промпта (например, "prompts.system.basic_assistant")
        **kwargs: Переменные для подстановки в промпт
    
    Returns:
        Промпт с подставленными переменными
    """
    config = load_config()
    
    # Разбиваем ключ на части (например, "prompts.system.basic_assistant")
    keys = key.split('.')
    value = config
    
    try:
        for k in keys:
            value = value[k]
        
        # Если это строка, подставляем переменные
        if isinstance(value, str):
            return value.format(**kwargs)
        return str(value)
    
    except (KeyError, TypeError) as e:
        logger.warning(f"Prompt key '{key}' not found, returning key as fallback")
        return key


def get_constant(key: str, default: Any = None) -> Any:
    """
    Получить константу по ключу
    
    Args:
        key: Ключ константы (например, "constants.errors.processing_error")
        default: Значение по умолчанию, если ключ не найден
    
    Returns:
        Значение константы
    """
    config = load_config()
    
    keys = key.split('.')
    value = config
    
    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        if default is not None:
            return default
        logger.warning(f"Constant key '{key}' not found, returning None")
        return None


def get_default(key: str, default: Any = None) -> Any:
    """
    Получить значение по умолчанию
    
    Args:
        key: Ключ (например, "defaults.top_k")
        default: Значение по умолчанию, если ключ не найден
    
    Returns:
        Значение
    """
    config = load_config()
    
    keys = key.split('.')
    value = config
    
    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        if default is not None:
            return default
        logger.warning(f"Default key '{key}' not found, returning provided default")
        return default


def reload_config():
    """Перезагрузить конфигурацию (очистить кэш)"""
    global _config_cache
    _config_cache = None
    load_config()


def _get_default_config() -> Dict[str, Any]:
    """Возвращает конфигурацию по умолчанию, если config.yaml не найден"""
    return {
        "prompts": {
            "default_template": "Ты помощник, который отвечает на вопросы пользователя.\n\nКонтекст из документов (если доступен):\n{chunks}\n\nВопрос пользователя: {question}\n\nПравила:\n1. Если есть контекст из документов, отвечай в первую очередь на его основе\n2. Если контекста нет или информации недостаточно, можешь использовать свои знания, но укажи это\n3. Будь кратким и структурированным\n4. Максимальная длина ответа: {max_length} символов\n5. Если используешь информацию из документов, укажи это\n\nОтвет:",
            "system": {
                "basic_assistant": "Ты - полезный ассистент, который отвечает на вопросы пользователей. Отвечай на русском языке, будь дружелюбным и информативным."
            }
        },
        "constants": {
            "errors": {
                "processing_error": "Извините, произошла ошибка при обработке вашего вопроса. Пожалуйста, попробуйте переформулировать вопрос или обратитесь к администратору."
            }
        },
        "defaults": {
            "top_k": 5
        }
    }

