"""Add fast_mode field to documents

Revision ID: 2026_01_13_0500_fast_mode
Revises: 2026_01_13_0441_add_token_tracking
Create Date: 2026-01-13 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_01_13_0500_fast_mode'
down_revision = '2026_01_13_0441_add_token_tracking'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле fast_mode в таблицу documents
    # Проверяем, существует ли поле перед добавлением
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Получаем список существующих колонок
    try:
        columns = [col['name'] for col in inspector.get_columns('documents')]
        
        if 'fast_mode' not in columns:
            op.add_column('documents', sa.Column('fast_mode', sa.Boolean(), nullable=False, server_default='false'))
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Column fast_mode already exists, skipping")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not check columns, adding fast_mode anyway: {e}")
        # Пробуем добавить поле напрямую
        try:
            op.add_column('documents', sa.Column('fast_mode', sa.Boolean(), nullable=False, server_default='false'))
        except Exception as e2:
            logger.warning(f"Column might already exist: {e2}")


def downgrade():
    # Удаляем поле fast_mode
    try:
        op.drop_column('documents', 'fast_mode')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not drop column fast_mode: {e}")
