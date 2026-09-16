"""machination icon set replaces the built-in icons

Revision ID: b7e2f4a91c05
Revises: 9d4a7c2b1f30
Create Date: 2026-09-16 21:30:00.000000

The built-in stroke icons are gone; the set is now the SVG files in
static/branchwork/img/machination_icons/, starting with the bomb. None of the
old names exist any more, so every machination and routine moves onto the
bomb, which is also the new column default.

Downgrading restores the old defaults but not the old per-row icons: that
information is not kept.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e2f4a91c05'
down_revision = '9d4a7c2b1f30'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('icon', existing_type=sa.String(length=30), existing_nullable=False,
                              server_default='bomb')
    with op.batch_alter_table('routines', schema=None) as batch_op:
        batch_op.alter_column('icon', existing_type=sa.String(length=30), existing_nullable=False,
                              server_default='bomb')
    op.execute("UPDATE tasks SET icon = 'bomb'")
    op.execute("UPDATE routines SET icon = 'bomb'")


def downgrade():
    with op.batch_alter_table('routines', schema=None) as batch_op:
        batch_op.alter_column('icon', existing_type=sa.String(length=30), existing_nullable=False,
                              server_default='refresh')
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('icon', existing_type=sa.String(length=30), existing_nullable=False,
                              server_default='check')
