"""
Универсальный загрузчик конфигурации из YAML файлов
Поддерживает переменные окружения в формате ${VAR_NAME} и ${VAR_NAME:-default}
"""
import yaml
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Кэш для загруженных конфигураций
_config_cache: Dict[str, Dict[str, Any]] = {}


def resolve_env_vars(value: Any) -> Any:
    """
    Рекурсивно разрешает переменные окружения в значениях конфигурации
    
    Поддерживает форматы:
    - ${VAR_NAME} - обязательная переменная
    - ${VAR_NAME:-default} - переменная с значением по умолчанию
    """
    if isinstance(value, str):
        # Заменяем ${VAR_NAME:-default}
        def replace_with_default(match):
            var_name = match.group(1)
            default = match.group(2) if match.group(2) else ""
            return os.getenv(var_name, default)
        
        # Заменяем ${VAR_NAME}
        def replace_var(match):
            var_name = match.group(1)
            value = os.getenv(var_name)
            if value is None:
                logger.warning(f"Environment variable {var_name} is not set")
                return match.group(0)  # Возвращаем исходную строку, если переменная не найдена
            return value
        
        # Сначала заменяем формат с default
        value = re.sub(r'\$\{(\w+):-([^}]*)\}', replace_with_default, value)
        # Затем заменяем обычный формат
        value = re.sub(r'\$\{(\w+)\}', replace_var, value)
        return value
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    else:
        return value


def load_config_file(config_path: Path, config_name: str = None) -> Dict[str, Any]:
    """
    Загрузить конфигурацию из YAML файла
    
    Args:
        config_path: Путь к YAML файлу
        config_name: Имя конфигурации для кэширования (если None, используется имя файла)
    
    Returns:
        Словарь с конфигурацией
    """
    if config_name is None:
        config_name = config_path.stem
    
    # Проверяем кэш
    if config_name in _config_cache:
        return _config_cache[config_name]
    
    try:
        if not config_path.exists():
            logger.warning(f"Config file not found at {config_path}, returning empty dict")
            _config_cache[config_name] = {}
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if config is None:
            config = {}
        
        # Разрешаем переменные окружения
        config = resolve_env_vars(config)
        
        # Кэшируем результат
        _config_cache[config_name] = config
        
        logger.info(f"Loaded configuration from {config_path}")
        return config
    
    except Exception as e:
        logger.error(f"Error loading config file {config_path}: {e}")
        _config_cache[config_name] = {}
        return {}


def get_config_dir(base_path: Optional[Path] = None) -> Path:
    """
    Получить путь к директории config
    
    Args:
        base_path: Базовый путь (если None, определяется автоматически)
    
    Returns:
        Path к директории config
    """
    if base_path is None:
        # Определяем путь относительно текущего файла
        # config_loader.py находится в backend/config/
        # Поэтому config_dir = Path(__file__).parent
        config_dir = Path(__file__).parent
    else:
        config_dir = Path(base_path) / "config"
    
    return config_dir


def load_qdrant_config(base_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Загрузить конфигурацию Qdrant из config/qdrant.yaml
    
    Args:
        base_path: Базовый путь к директории проекта (если None, определяется автоматически)
    
    Returns:
        Словарь с конфигурацией Qdrant
    """
    config_dir = get_config_dir(base_path)
    config_path = config_dir / "qdrant.yaml"
    return load_config_file(config_path, "qdrant")


def load_llm_config(base_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Загрузить конфигурацию LLM из config/llm.yaml
    
    Args:
        base_path: Базовый путь к директории проекта (если None, определяется автоматически)
    
    Returns:
        Словарь с конфигурацией LLM
    """
    config_dir = get_config_dir(base_path)
    config_path = config_dir / "llm.yaml"
    return load_config_file(config_path, "llm")


def load_prompts_config(base_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Загрузить конфигурацию промптов из config.yaml или config/prompts.yaml
    
    Args:
        base_path: Базовый путь к директории проекта (если None, определяется автоматически)
    
    Returns:
        Словарь с конфигурацией промптов
    """
    if base_path is None:
        # Определяем путь относительно backend/
        # config_loader.py находится в backend/config/
        # Поэтому backend_dir = Path(__file__).parent.parent
        backend_dir = Path(__file__).parent.parent
    else:
        backend_dir = Path(base_path)
    
    # Сначала пробуем config/prompts.yaml
    prompts_path = backend_dir / "config" / "prompts.yaml"
    if prompts_path.exists():
        return load_config_file(prompts_path, "prompts")
    
    # Если не найден, пробуем config.yaml в корне backend/
    config_path = backend_dir / "config.yaml"
    if config_path.exists():
        return load_config_file(config_path, "prompts")
    
    logger.warning("Prompts config file not found, returning empty dict")
    return {}


def reload_config(config_name: Optional[str] = None):
    """
    Перезагрузить конфигурацию (очистить кэш)
    
    Args:
        config_name: Имя конфигурации для перезагрузки (если None, очищается весь кэш)
    """
    global _config_cache
    if config_name:
        _config_cache.pop(config_name, None)
        logger.info(f"Cleared cache for config: {config_name}")
    else:
        _config_cache.clear()
        logger.info("Cleared all config cache")


def get_qdrant_config_value(key: str, default: Any = None, base_path: Optional[Path] = None) -> Any:
    """
    Получить значение из конфигурации Qdrant
    
    Args:
        key: Ключ в формате "qdrant.host" или "host" (qdrant. будет добавлен автоматически)
        default: Значение по умолчанию, если ключ не найден
        base_path: Базовый путь к директории проекта
    
    Returns:
        Значение из конфигурации или default
    """
    config = load_qdrant_config(base_path)
    
    # Если ключ не начинается с "qdrant.", добавляем префикс
    if not key.startswith("qdrant."):
        key = f"qdrant.{key}"
    
    keys = key.split('.')
    value = config
    
    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        if default is not None:
            return default
        logger.warning(f"Qdrant config key '{key}' not found, returning None")
        return None


def get_llm_config_value(key: str, default: Any = None, base_path: Optional[Path] = None) -> Any:
    """
    Получить значение из конфигурации LLM
    
    Args:
        key: Ключ в формате "llm.embeddings.api_key" или "embeddings.api_key" (llm. будет добавлен автоматически)
        default: Значение по умолчанию, если ключ не найден
        base_path: Базовый путь к директории проекта
    
    Returns:
        Значение из конфигурации или default
    """
    config = load_llm_config(base_path)
    
    # Если ключ не начинается с "llm.", добавляем префикс
    if not key.startswith("llm."):
        key = f"llm.{key}"
    
    keys = key.split('.')
    value = config
    
    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        if default is not None:
            return default
        logger.warning(f"LLM config key '{key}' not found, returning None")
        return None
