"""Add TRANSLATION_TXT to ResultType enum

Revision ID: a415838074bf
Revises: f6d536f952fb
Create Date: 2025-10-10 21:41:45.895335

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a415838074bf'
down_revision = 'f6d536f952fb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add TRANSLATION_TXT to the ResultType enum
    op.execute("ALTER TYPE resulttype ADD VALUE 'translation_txt'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave the enum value in place
    pass
