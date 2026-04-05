"""add_user_job_number_column

Revision ID: 60baf276f450
Revises: 7ea7d82aa472
Create Date: 2025-08-21 22:38:36.743562

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '60baf276f450'
down_revision = '7ea7d82aa472'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_job_number column to jobs table
    op.add_column('jobs', sa.Column('user_job_number', sa.Integer(), nullable=True))
    
    # Create unique index on (owner_id, user_job_number)
    op.create_index('idx_jobs_user_sequence', 'jobs', ['owner_id', 'user_job_number'], unique=True)
    
    # Populate existing jobs with user-specific job numbers
    # This will assign sequential numbers to existing jobs for each user
    op.execute("""
        UPDATE jobs 
        SET user_job_number = subquery.row_number
        FROM (
            SELECT id, 
                   ROW_NUMBER() OVER (PARTITION BY owner_id ORDER BY created_at, id) as row_number
            FROM jobs
        ) as subquery
        WHERE jobs.id = subquery.id;
    """)
    
    # Make the column non-nullable after populating existing data
    op.alter_column('jobs', 'user_job_number', nullable=False)


def downgrade() -> None:
    # Remove the index
    op.drop_index('idx_jobs_user_sequence', table_name='jobs')
    
    # Remove the column
    op.drop_column('jobs', 'user_job_number')
