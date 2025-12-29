"""
Testy dla Circuit Breaker
"""
import pytest
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState, CircuitBreakerOpenError


def test_circuit_breaker_closed_state():
    """Test circuit breakera w stanie CLOSED"""
    config = CircuitBreakerConfig(failure_threshold=3)
    cb = CircuitBreaker(config)
    
    assert cb.state == CircuitState.CLOSED
    
    # Sukces - powinno działać
    def success_func():
        return "success"
    
    result = cb.call(success_func)
    assert result == "success"
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_opens_after_failures():
    """Test że circuit breaker otwiera się po wielu błędach"""
    config = CircuitBreakerConfig(failure_threshold=3)
    cb = CircuitBreaker(config)
    
    def failing_func():
        raise ValueError("Error")
    
    # Pierwsze 3 błędy - jeszcze CLOSED
    for _ in range(3):
        try:
            cb.call(failing_func)
        except ValueError:
            pass
    
    # Po 3 błędach powinno być OPEN
    assert cb.state == CircuitState.OPEN
    
    # Kolejne wywołanie powinno rzucić CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        cb.call(failing_func)


def test_circuit_breaker_reset():
    """Test resetowania circuit breakera"""
    config = CircuitBreakerConfig(failure_threshold=2)
    cb = CircuitBreaker(config)
    
    def failing_func():
        raise ValueError("Error")
    
    # Otwieramy circuit breaker
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass
    
    assert cb.state == CircuitState.OPEN
    
    # Reset
    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0

