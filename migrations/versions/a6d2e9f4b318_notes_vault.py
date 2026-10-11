"""notes vault: notes encrypted in the browser under a master password

Adds the encrypted notes key to each account and widens note titles, which
now hold ciphertext. Existing notes are left as they are: the next visit to
Notes asks for a master password and encrypts them in the browser.

Revision ID: a6d2e9f4b318
Revises: f3b8d1c6a274
Create Date: 2026-10-12 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6d2e9f4b318'
down_revision = 'f3b8d1c6a274'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vault_salt', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('vault_rounds', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('vault_key', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('vault_set_at', sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.alter_column('title', existing_type=sa.String(length=200), type_=sa.Text(),
                              existing_nullable=False)


def downgrade():
    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.alter_column('title', existing_type=sa.Text(), type_=sa.String(length=200),
                              existing_nullable=False)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('vault_set_at')
        batch_op.drop_column('vault_key')
        batch_op.drop_column('vault_rounds')
        batch_op.drop_column('vault_salt')
