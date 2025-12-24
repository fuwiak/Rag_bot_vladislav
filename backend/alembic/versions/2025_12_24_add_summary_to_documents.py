"""Add summary field to documents

Revision ID: 2025_12_24_summary
Revises: 2025_12_24_bot_is_active
Create Date: 2025-12-24 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2025_12_24_summary'
down_revision = '2025_12_24_bot_is_active'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле summary в таблицу documents
    # Проверяем, существует ли поле перед добавлением
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Получаем список существующих колонок
    try:
        columns = [col['name'] for col in inspector.get_columns('documents')]
        
        if 'summary' not in columns:
            op.add_column('documents', sa.Column('summary', sa.Text(), nullable=True))
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Column summary already exists, skipping")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not check columns, adding summary anyway: {e}")
        # Пробуем добавить поле напрямую
        try:
            op.add_column('documents', sa.Column('summary', sa.Text(), nullable=True))
        except Exception as e2:
            logger.warning(f"Column might already exist: {e2}")


def downgrade():
    # Удаляем поле summary
    try:
        op.drop_column('documents', 'summary')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not drop column summary: {e}")

