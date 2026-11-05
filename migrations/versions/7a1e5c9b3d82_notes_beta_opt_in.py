"""notes beta: encrypted notes become opt-in under Account

New accounts start with notes off. Accounts already using notes (a master
password chosen, or any note written) are switched on, so nobody's notes
disappear from view.

Revision ID: 7a1e5c9b3d82
Revises: a6d2e9f4b318
Create Date: 2026-11-05 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a1e5c9b3d82'
down_revision = 'a6d2e9f4b318'
branch_labels = None
depends_on = None


def upgrade():
    # sa.false() rather than a literal 0: Postgres will not take an integer
    # for a boolean, and production is Postgres.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes_beta', sa.Boolean(), server_default=sa.false(),
                                      nullable=False))

    op.execute(
        "UPDATE users SET notes_beta = true "
        "WHERE vault_key IS NOT NULL "
        "OR id IN (SELECT projects.owner_id FROM projects "
        "JOIN notes ON notes.project_id = projects.id)"
    )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('notes_beta')
