"""remove railway fields and add container_id to sessions

Revision ID: remove_railway_fields
Revises: e2eec18c30fa
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa


revision = 'remove_railway_fields'
down_revision = 'e2eec18c30fa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove Railway fields from users table
    op.drop_column('users', 'railway_service_id')
    op.drop_column('users', 'volume_id')


def downgrade() -> None:
    # Re-add Railway fields to users table
    op.add_column('users', sa.Column('railway_service_id', sa.String(36), nullable=True))
    op.add_column('users', sa.Column('volume_id', sa.String(36), nullable=True))
