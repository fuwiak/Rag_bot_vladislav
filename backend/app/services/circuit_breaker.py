"""
Circuit Breaker dla LLM API calls z graceful degradation
"""
import time
import logging
from typing import Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Stany circuit breakera"""
    CLOSED = "closed"  # Normalne działanie
    OPEN = "open"  # Blokada - zwraca błąd natychmiast
    HALF_OPEN = "half_open"  # Testowanie - pozwala na ograniczoną liczbę requestów


@dataclass
class CircuitBreakerConfig:
    """Konfiguracja circuit breakera"""
    failure_threshold: int = 5  # Liczba błędów przed otwarciem
    success_threshold: int = 2  # Liczba sukcesów przed zamknięciem
    timeout: int = 60  # Czas w sekundach przed próbą zamknięcia
    expected_exception: type = Exception


class CircuitBreaker:
    """
    Circuit Breaker pattern dla ochrony przed przeciążeniem API
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Wywołuje funkcję z ochroną circuit breakera
        
        Args:
            func: Funkcja do wywołania
            *args, **kwargs: Argumenty funkcji
        
        Returns:
            Wynik funkcji
        
        Raises:
            CircuitBreakerOpenError: Jeśli circuit breaker jest otwarty
        """
        if self.state == CircuitState.OPEN:
            # Sprawdzamy czy minął timeout
            if self.last_failure_time and time.time() - self.last_failure_time >= self.config.timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker: OPEN -> HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. Last failure: {self.last_failure_time}"
                )
        
        # Próbujemy wywołać funkcję
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise e
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Asynchroniczna wersja call
        
        Args:
            func: Async funkcja do wywołania
            *args, **kwargs: Argumenty funkcji
        
        Returns:
            Wynik funkcji
        """
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and time.time() - self.last_failure_time >= self.config.timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker: OPEN -> HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. Last failure: {self.last_failure_time}"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Obsługa sukcesu"""
        self.last_success_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker: HALF_OPEN -> CLOSED")
        elif self.state == CircuitState.CLOSED:
            # Resetujemy licznik błędów przy sukcesie
            self.failure_count = 0
    
    def _on_failure(self):
        """Obsługa błędu"""
        self.last_failure_time = time.time()
        self.failure_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            # Błąd w HALF_OPEN - wracamy do OPEN
            self.state = CircuitState.OPEN
            self.success_count = 0
            logger.warning("Circuit breaker: HALF_OPEN -> OPEN (failure in test)")
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker: CLOSED -> OPEN "
                    f"(failure_count: {self.failure_count})"
                )
    
    def reset(self):
        """Resetuje circuit breaker do stanu początkowego"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        logger.info("Circuit breaker reset")


class CircuitBreakerOpenError(Exception):
    """Błąd gdy circuit breaker jest otwarty"""
    pass


# Globalne circuit breakery dla różnych serwisów
llm_circuit_breaker = CircuitBreaker(
    CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=60,
        expected_exception=Exception
    )
)

embedding_circuit_breaker = CircuitBreaker(
    CircuitBreakerConfig(
        failure_threshold=10,
        success_threshold=3,
        timeout=30,
        expected_exception=Exception
    )
)

