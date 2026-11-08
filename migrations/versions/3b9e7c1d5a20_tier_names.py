"""tier names

Revision ID: 3b9e7c1d5a20
Revises: 754451bd2ef3
Create Date: 2026-11-08 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b9e7c1d5a20'
down_revision = '754451bd2ef3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tier_names',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('branch_id', 'tier', name='uq_tier_names_branch_tier'),
    )
    with op.batch_alter_table('tier_names', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tier_names_branch_id'), ['branch_id'], unique=False)


def downgrade():
    with op.batch_alter_table('tier_names', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tier_names_branch_id'))
    op.drop_table('tier_names')
