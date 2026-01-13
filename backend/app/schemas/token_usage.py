"""
Схемы для статистики использования токенов
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class TokenUsageResponse(BaseModel):
    """Схема ответа со статистикой использования токенов"""
    model_id: str
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    usage_count: int


class TokenUsageStatisticsResponse(BaseModel):
    """Схема ответа со статистикой по моделям"""
    statistics: List[TokenUsageResponse]
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_usage_count: int


class ModelPriceUpdate(BaseModel):
    """Схема для обновления цены модели"""
    input_price: Optional[Decimal] = Field(None, description="Цена за 1M входных токенов")
    output_price: Optional[Decimal] = Field(None, description="Цена за 1M выходных токенов")
