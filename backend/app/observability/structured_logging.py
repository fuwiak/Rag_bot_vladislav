"""
Structured logging z JSON format i correlation IDs
"""
import logging
import json
import sys
from typing import Any, Dict, Optional
from contextvars import ContextVar
import structlog

from app.observability.otel_setup import get_current_trace_id, get_current_span_id

# Context variable dla correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
project_id_var: ContextVar[Optional[str]] = ContextVar('project_id', default=None)


def set_correlation_id(correlation_id: str):
    """Ustawia correlation ID dla obecnego kontekstu"""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Pobiera correlation ID z obecnego kontekstu"""
    return correlation_id_var.get()


def set_user_id(user_id: str):
    """Ustawia user ID dla obecnego kontekstu"""
    user_id_var.set(user_id)


def get_user_id() -> Optional[str]:
    """Pobiera user ID z obecnego kontekstu"""
    return user_id_var.get()


def set_project_id(project_id: str):
    """Ustawia project ID dla obecnego kontekstu"""
    project_id_var.set(project_id)


def get_project_id() -> Optional[str]:
    """Pobiera project ID z obecnego kontekstu"""
    return project_id_var.get()


def add_context_to_log(logger, method_name, event_dict):
    """Dodaje kontekst do logów (correlation ID, trace ID, user ID, project ID)"""
    # Correlation ID
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    
    # Trace ID z OpenTelemetry
    trace_id = get_current_trace_id()
    if trace_id:
        event_dict["trace_id"] = trace_id
    
    # Span ID z OpenTelemetry
    span_id = get_current_span_id()
    if span_id:
        event_dict["span_id"] = span_id
    
    # User ID
    user_id = get_user_id()
    if user_id:
        event_dict["user_id"] = user_id
    
    # Project ID
    project_id = get_project_id()
    if project_id:
        event_dict["project_id"] = project_id
    
    return event_dict


def setup_structured_logging(
    json_output: bool = True,
    log_level: str = "INFO"
):
    """
    Konfiguruje structured logging z JSON format
    
    Args:
        json_output: Jeśli True, używa JSON format, w przeciwnym razie używa human-readable
        log_level: Poziom logowania (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Konfigurujemy structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        add_context_to_log,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend([
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer()
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Konfigurujemy standardowe Python logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    
    # Ustawiamy poziom dla różnych modułów
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pydantic").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Pobiera structured logger dla danego modułu"""
    return structlog.get_logger(name)


class ContextLogger:
    """Logger z automatycznym dodawaniem kontekstu"""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def _add_context(self, **kwargs) -> Dict[str, Any]:
        """Dodaje kontekst do logów"""
        context = {}
        
        correlation_id = get_correlation_id()
        if correlation_id:
            context["correlation_id"] = correlation_id
        
        trace_id = get_current_trace_id()
        if trace_id:
            context["trace_id"] = trace_id
        
        span_id = get_current_span_id()
        if span_id:
            context["span_id"] = span_id
        
        user_id = get_user_id()
        if user_id:
            context["user_id"] = user_id
        
        project_id = get_project_id()
        if project_id:
            context["project_id"] = project_id
        
        context.update(kwargs)
        return context
    
    def debug(self, message: str, **kwargs):
        """Log debug z kontekstem"""
        self.logger.debug(message, **self._add_context(**kwargs))
    
    def info(self, message: str, **kwargs):
        """Log info z kontekstem"""
        self.logger.info(message, **self._add_context(**kwargs))
    
    def warning(self, message: str, **kwargs):
        """Log warning z kontekstem"""
        self.logger.warning(message, **self._add_context(**kwargs))
    
    def error(self, message: str, **kwargs):
        """Log error z kontekstem"""
        self.logger.error(message, **self._add_context(**kwargs))
    
    def exception(self, message: str, **kwargs):
        """Log exception z kontekstem i traceback"""
        self.logger.exception(message, **self._add_context(**kwargs))

