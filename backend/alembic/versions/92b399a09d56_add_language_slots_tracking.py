"""add_language_slots_tracking

Revision ID: 92b399a09d56
Revises: 60baf276f450
Create Date: 2025-08-21 23:25:47.609692

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '92b399a09d56'
down_revision = '60baf276f450'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add language_slots_used column to users table
    op.add_column('users', sa.Column('language_slots_used', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove language_slots_used column
    op.drop_column('users', 'language_slots_used')
