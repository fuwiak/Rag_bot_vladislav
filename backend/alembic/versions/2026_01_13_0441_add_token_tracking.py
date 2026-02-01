"""add_token_tracking

Revision ID: 2026_01_13_0441_add_token_tracking
Revises: 2025_12_24_add_telegram_id_to_users
Create Date: 2026-01-13 04:41:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026_01_13_0441_add_token_tracking'
down_revision = '2025_12_24_telegram_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Проверяем, существует ли таблица перед созданием
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Получаем список существующих таблиц
    existing_tables = inspector.get_table_names()
    
    # Добавляем поля цены в llm_models
    if 'llm_models' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('llm_models')]
        if 'input_price' not in columns:
            op.add_column('llm_models', sa.Column('input_price', sa.Numeric(20, 10), nullable=True))
        if 'output_price' not in columns:
            op.add_column('llm_models', sa.Column('output_price', sa.Numeric(20, 10), nullable=True))
    
    # Создаем таблицу token_usage
    if 'token_usage' not in existing_tables:
        op.create_table('token_usage',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('model_id', sa.String(length=255), nullable=False),
            sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('cost', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        # Создаем индексы
        op.create_index('ix_token_usage_model_id', 'token_usage', ['model_id'])
        op.create_index('ix_token_usage_project_id', 'token_usage', ['project_id'])
        op.create_index('ix_token_usage_created_at', 'token_usage', ['created_at'])


def downgrade() -> None:
    # Удаляем таблицу token_usage
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'token_usage' in existing_tables:
        op.drop_index('ix_token_usage_created_at', table_name='token_usage')
        op.drop_index('ix_token_usage_project_id', table_name='token_usage')
        op.drop_index('ix_token_usage_model_id', table_name='token_usage')
        op.drop_table('token_usage')
    
    # Удаляем поля цены из llm_models
    if 'llm_models' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('llm_models')]
        if 'output_price' in columns:
            op.drop_column('llm_models', 'output_price')
        if 'input_price' in columns:
            op.drop_column('llm_models', 'input_price')
