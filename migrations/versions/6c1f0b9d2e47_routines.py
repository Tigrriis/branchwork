"""routines: maintenance actions on a tempo

Revision ID: 6c1f0b9d2e47
Revises: 53923e41872e
Create Date: 2026-09-14 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6c1f0b9d2e47'
down_revision = '53923e41872e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'routines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('icon', sa.String(length=30), server_default='refresh', nullable=False),
        sa.Column('every_days', sa.Integer(), server_default='7', nullable=False),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_done_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('routines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_routines_project_id'), ['project_id'], unique=False)


def downgrade():
    with op.batch_alter_table('routines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_routines_project_id'))
    op.drop_table('routines')
