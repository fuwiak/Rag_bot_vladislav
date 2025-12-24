"""Add telegram_id to users

Revision ID: 2025_12_24_telegram_id
Revises: 2025_12_24_bot_is_active
Create Date: 2025-12-24 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2025_12_24_telegram_id'
down_revision = '2025_12_24_bot_is_active'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле telegram_id в таблицу users
    # Проверяем, существует ли поле перед добавлением
    from sqlalchemy import inspect, text
    from alembic import context
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Получаем список существующих колонок
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'telegram_id' not in columns:
        op.add_column('users', sa.Column('telegram_id', sa.String(length=50), nullable=True))
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Column telegram_id already exists, skipping")


def downgrade():
    # Удаляем поле telegram_id
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'telegram_id' in columns:
        op.drop_column('users', 'telegram_id')

