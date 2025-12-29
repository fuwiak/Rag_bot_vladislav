"""
Testy dla Adaptive Retrieval
"""
import pytest
from app.services.adaptive_retrieval import AdaptiveRetrieval


def test_detect_query_complexity_simple():
    """Test wykrywania prostych zapytań"""
    adapter = AdaptiveRetrieval()
    complexity = adapter.detect_query_complexity("Что это?")
    assert complexity == "simple"


def test_detect_query_complexity_complex():
    """Test wykrywania złożonych zapytań"""
    adapter = AdaptiveRetrieval()
    complexity = adapter.detect_query_complexity("Объясни подробно как работает система и сравни с другими")
    assert complexity == "complex"


def test_adjust_top_k():
    """Test dostosowania top_k"""
    adapter = AdaptiveRetrieval()
    
    # Simple query - zmniejsza top_k
    adjusted = adapter.adjust_top_k(5, "simple", None)
    assert adjusted <= 5
    
    # Complex query - zwiększa top_k
    adjusted = adapter.adjust_top_k(5, "complex", None)
    assert adjusted >= 5


def test_calculate_results_quality():
    """Test obliczania jakości wyników"""
    adapter = AdaptiveRetrieval()
    
    chunks = [
        {"score": 0.8},
        {"score": 0.7},
        {"score": 0.6}
    ]
    
    quality = adapter.calculate_results_quality(chunks)
    assert 0.0 <= quality <= 1.0
    assert quality > 0.5  # Powinno być dobre dla takich scores

