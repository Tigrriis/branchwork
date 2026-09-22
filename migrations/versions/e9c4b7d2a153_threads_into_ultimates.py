"""threads can end at an ultimate

Revision ID: e9c4b7d2a153
Revises: d8f3a6b2c491
Create Date: 2026-09-22 12:00:00.000000

A thread now ends at a machination or at a scheme's ultimate: exactly one
of to_task_id and to_ultimate_id is set.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9c4b7d2a153'
down_revision = 'd8f3a6b2c491'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('threads', schema=None) as batch_op:
        batch_op.add_column(sa.Column('to_ultimate_id', sa.Integer(), nullable=True))
        batch_op.alter_column('to_task_id', existing_type=sa.Integer(), nullable=True)
        batch_op.create_index(batch_op.f('ix_threads_to_ultimate_id'), ['to_ultimate_id'], unique=False)
        # A deleted ultimate takes the threads into it, whoever deletes it.
        batch_op.create_foreign_key('fk_threads_to_ultimate_id', 'ultimates',
                                    ['to_ultimate_id'], ['id'], ondelete='CASCADE')
        batch_op.create_unique_constraint('uq_threads_ultimate_pair', ['from_task_id', 'to_ultimate_id'])
        batch_op.create_check_constraint('ck_threads_one_target',
                                         '(to_task_id IS NULL) <> (to_ultimate_id IS NULL)')


def downgrade():
    # Threads into ultimates have nowhere to go without the column.
    op.execute("DELETE FROM threads WHERE to_ultimate_id IS NOT NULL")
    with op.batch_alter_table('threads', schema=None) as batch_op:
        batch_op.drop_constraint('ck_threads_one_target', type_='check')
        batch_op.drop_constraint('uq_threads_ultimate_pair', type_='unique')
        batch_op.drop_constraint('fk_threads_to_ultimate_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_threads_to_ultimate_id'))
        batch_op.alter_column('to_task_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('to_ultimate_id')
