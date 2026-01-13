"""
Сервис для отслеживания использования токенов LLM
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.models.token_usage import TokenUsage
from app.models.llm_model import LLMModel

logger = logging.getLogger(__name__)


class TokenUsageService:
    """Сервис для работы со статистикой использования токенов"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_token_usage(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        project_id: Optional[UUID] = None
    ) -> TokenUsage:
        """
        Записывает использование токенов
        
        Args:
            model_id: ID модели LLM
            input_tokens: Количество входных токенов
            output_tokens: Количество выходных токенов
            project_id: ID проекта (опционально)
        
        Returns:
            TokenUsage объект
        """
        total_tokens = input_tokens + output_tokens
        
        # Вычисляем стоимость на основе цен модели
        cost = await self._calculate_cost(model_id, input_tokens, output_tokens)
        
        token_usage = TokenUsage(
            model_id=model_id,
            project_id=project_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=str(cost) if cost else None
        )
        
        self.db.add(token_usage)
        await self.db.commit()
        await self.db.refresh(token_usage)
        
        logger.info(
            f"Recorded token usage: model={model_id}, "
            f"input={input_tokens}, output={output_tokens}, "
            f"total={total_tokens}, cost={cost}, project={project_id}"
        )
        
        return token_usage
    
    async def _calculate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int
    ) -> Optional[Decimal]:
        """
        Вычисляет стоимость использования токенов на основе цен модели
        
        Args:
            model_id: ID модели
            input_tokens: Количество входных токенов
            output_tokens: Количество выходных токенов
        
        Returns:
            Стоимость в Decimal или None
        """
        try:
            # Ищем модель в БД
            result = await self.db.execute(
                select(LLMModel).where(LLMModel.model_id == model_id)
            )
            model = result.scalar_one_or_none()
            
            if not model or not model.input_price or not model.output_price:
                return None
            
            # Вычисляем стоимость: цена за 1M токенов * количество токенов / 1_000_000
            input_cost = (model.input_price * Decimal(input_tokens)) / Decimal(1_000_000)
            output_cost = (model.output_price * Decimal(output_tokens)) / Decimal(1_000_000)
            
            total_cost = input_cost + output_cost
            return total_cost
        except Exception as e:
            logger.warning(f"Failed to calculate cost for model {model_id}: {e}")
            return None
    
    async def get_token_statistics(
        self,
        model_id: Optional[str] = None,
        project_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """
        Получает статистику использования токенов
        
        Args:
            model_id: Фильтр по модели (опционально)
            project_id: Фильтр по проекту (опционально)
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
        
        Returns:
            Словарь со статистикой
        """
        query = select(
            func.sum(TokenUsage.input_tokens).label('total_input_tokens'),
            func.sum(TokenUsage.output_tokens).label('total_output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.count(TokenUsage.id).label('usage_count')
        )
        
        if model_id:
            query = query.where(TokenUsage.model_id == model_id)
        if project_id:
            query = query.where(TokenUsage.project_id == project_id)
        if start_date:
            query = query.where(TokenUsage.created_at >= start_date)
        if end_date:
            query = query.where(TokenUsage.created_at <= end_date)
        
        result = await self.db.execute(query)
        stats = result.first()
        
        return {
            "total_input_tokens": stats.total_input_tokens or 0,
            "total_output_tokens": stats.total_output_tokens or 0,
            "total_tokens": stats.total_tokens or 0,
            "usage_count": stats.usage_count or 0
        }
    
    async def get_token_statistics_by_model(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> list:
        """
        Получает статистику использования токенов сгруппированную по моделям
        
        Args:
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
        
        Returns:
            Список словарей со статистикой по каждой модели
        """
        query = select(
            TokenUsage.model_id,
            func.sum(TokenUsage.input_tokens).label('total_input_tokens'),
            func.sum(TokenUsage.output_tokens).label('total_output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.count(TokenUsage.id).label('usage_count')
        ).group_by(TokenUsage.model_id)
        
        if start_date:
            query = query.where(TokenUsage.created_at >= start_date)
        if end_date:
            query = query.where(TokenUsage.created_at <= end_date)
        
        query = query.order_by(desc('total_tokens'))
        
        result = await self.db.execute(query)
        rows = result.all()
        
        statistics = []
        for row in rows:
            statistics.append({
                "model_id": row.model_id,
                "total_input_tokens": row.total_input_tokens or 0,
                "total_output_tokens": row.total_output_tokens or 0,
                "total_tokens": row.total_tokens or 0,
                "usage_count": row.usage_count or 0
            })
        
        return statistics
