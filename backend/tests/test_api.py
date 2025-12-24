"""
Тесты API endpoints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(test_client: AsyncClient):
    """Тест health check endpoint"""
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_ready_check(test_client: AsyncClient):
    """Тест readiness check endpoint"""
    response = await test_client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


# Дополнительные тесты API можно добавить здесь














