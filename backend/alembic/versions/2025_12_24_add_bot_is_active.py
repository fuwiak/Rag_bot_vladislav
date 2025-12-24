"""Add bot_is_active field to projects

Revision ID: 2025_12_24_bot_is_active
Revises: 2025_12_13_1637
Create Date: 2025-12-24 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2025_12_24_bot_is_active'
down_revision = '6b1a79c454ff'  # Используем правильный revision ID из предыдущей миграции
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле bot_is_active в таблицу projects
    # Проверяем, существует ли поле перед добавлением
    from sqlalchemy import inspect, text
    from alembic import context
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Получаем список существующих колонок
    columns = [col['name'] for col in inspector.get_columns('projects')]
    
    if 'bot_is_active' not in columns:
        op.add_column('projects', sa.Column('bot_is_active', sa.String(length=10), nullable=False, server_default='false'))
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Column bot_is_active already exists, skipping")


def downgrade():
    # Удаляем поле bot_is_active
    op.drop_column('projects', 'bot_is_active')

