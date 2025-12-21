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
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_constraint('projects_bot_token_key', type_='unique')


def downgrade() -> None:
    # SQLite не поддерживает ALTER для constraints, используем batch mode
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_unique_constraint('projects_bot_token_key', ['bot_token'])

