"""ultimates: a scheme's end goal below its tiers

Revision ID: d8f3a6b2c491
Revises: c5a81d3f7e20
Create Date: 2026-09-22 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8f3a6b2c491'
down_revision = 'c5a81d3f7e20'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ultimates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('icon', sa.String(length=30), server_default='bomb', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('achieved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        # A deleted scheme takes its ultimate with it, whoever deletes it.
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # One per scheme.
        sa.UniqueConstraint('branch_id', name='uq_ultimates_branch_id'),
    )


def downgrade():
    op.drop_table('ultimates')
