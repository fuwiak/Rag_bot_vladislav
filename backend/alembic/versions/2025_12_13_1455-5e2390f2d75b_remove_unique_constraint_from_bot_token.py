"""remove_unique_constraint_from_bot_token

Revision ID: 5e2390f2d75b
Revises: 
Create Date: 2025-12-13 14:55:31.744604

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e2390f2d75b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite не поддерживает ALTER для constraints, используем batch mode
    # Проверяем, существует ли constraint перед удалением (для PostgreSQL)
    try:
        from sqlalchemy import inspect
        
        conn = op.get_bind()
        inspector = inspect(conn)
        
        # Для PostgreSQL проверяем constraints
        if hasattr(inspector, 'get_unique_constraints'):
            try:
                constraints = inspector.get_unique_constraints('projects')
                constraint_names = [c['name'] for c in constraints]
                
                if 'projects_bot_token_key' in constraint_names:
                    with op.batch_alter_table('projects', schema=None) as batch_op:
                        batch_op.drop_constraint('projects_bot_token_key', type_='unique')
            except Exception as e:
                # Если constraint уже удален или не существует, просто пропускаем
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Constraint projects_bot_token_key not found or already removed: {e}")
        else:
            # Для SQLite просто пытаемся удалить
            with op.batch_alter_table('projects', schema=None) as batch_op:
                try:
                    batch_op.drop_constraint('projects_bot_token_key', type_='unique')
                except Exception:
                    pass  # Игнорируем ошибку если constraint не существует
    except Exception as e:
        # Если проверка не удалась, просто пропускаем удаление constraint
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not check/remove constraint projects_bot_token_key: {e}")


def downgrade() -> None:
    # SQLite не поддерживает ALTER для constraints, используем batch mode
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_unique_constraint('projects_bot_token_key', ['bot_token'])

