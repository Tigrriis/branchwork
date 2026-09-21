"""threads: sequence links between machinations

Revision ID: c5a81d3f7e20
Revises: b7e2f4a91c05
Create Date: 2026-09-21 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5a81d3f7e20'
down_revision = 'b7e2f4a91c05'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'threads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('from_task_id', sa.Integer(), nullable=False),
        sa.Column('to_task_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        # A deleted machination takes its threads with it, whoever deletes it.
        sa.ForeignKeyConstraint(['from_task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_task_id', 'to_task_id', name='uq_threads_pair'),
    )
    with op.batch_alter_table('threads', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_threads_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_threads_from_task_id'), ['from_task_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_threads_to_task_id'), ['to_task_id'], unique=False)


def downgrade():
    with op.batch_alter_table('threads', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_threads_to_task_id'))
        batch_op.drop_index(batch_op.f('ix_threads_from_task_id'))
        batch_op.drop_index(batch_op.f('ix_threads_project_id'))
    op.drop_table('threads')
