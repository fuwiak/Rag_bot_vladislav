"""
Testy dla Cache Service
"""
import pytest
from unittest.mock import AsyncMock, patch
from app.services.cache_service import CacheService


@pytest.mark.asyncio
async def test_cache_service_connect_disabled():
    """Test że cache service nie łączy się gdy disabled"""
    service = CacheService()
    service.enabled = False
    await service.connect()
    assert service.redis_client is None


@pytest.mark.asyncio
async def test_cache_service_get_set_embedding():
    """Test zapisu i odczytu embedding z cache"""
    service = CacheService()
    service.enabled = True
    
    with patch('app.services.cache_service.redis') as mock_redis:
        mock_client = AsyncMock()
        mock_client.get.return_value = None
        mock_client.setex = AsyncMock()
        service.redis_client = mock_client
        
        # Test get - cache miss
        result = await service.get_embedding("test text")
        assert result is None
        
        # Test set
        embedding = [0.1, 0.2, 0.3]
        await service.set_embedding("test text", embedding)
        mock_client.setex.assert_called_once()


@pytest.mark.asyncio
async def test_cache_service_get_cache_stats():
    """Test pobierania statystyk cache"""
    service = CacheService()
    service.enabled = True
    
    with patch.object(service, 'redis_client', new_callable=AsyncMock) as mock_client:
        mock_client.info.return_value = {"keyspace_hits": 10, "keyspace_misses": 5}
        mock_client.dbsize.return_value = 100
        
        stats = await service.get_cache_stats()
        assert stats["enabled"] is True
        assert stats["keys"] == 100

