"""notes: an Obsidian-style notebook per plot, foldered by scheme and machination

Revision ID: f3b8d1c6a274
Revises: e9c4b7d2a153
Create Date: 2026-10-11 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b8d1c6a274'
down_revision = 'e9c4b7d2a153'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        # A deleted machination or scheme drops its notes a folder, not away.
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notes_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notes_branch_id'), ['branch_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notes_task_id'), ['task_id'], unique=False)


def downgrade():
    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notes_task_id'))
        batch_op.drop_index(batch_op.f('ix_notes_branch_id'))
        batch_op.drop_index(batch_op.f('ix_notes_project_id'))
    op.drop_table('notes')
