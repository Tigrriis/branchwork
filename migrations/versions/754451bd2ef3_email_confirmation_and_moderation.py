"""email confirmation, last sign-in, and moderators

Adds to users: when the email was confirmed, when a confirmation link was
last sent, when the account last signed in, and whether it is a moderator.
Existing accounts start unconfirmed, with no sign-in recorded.

The account named Roobs becomes the one moderator. Display names are not
unique, so if more than one account carries it the oldest wins, which is
the one made before anyone else could have copied it. With no such name,
an account whose email starts "roobs@" is used instead. The deploy log says
which account it picked, or that it found none; either way `flask
set-moderator` changes it afterwards.

Revision ID: 754451bd2ef3
Revises: 7a1e5c9b3d82
Create Date: 2026-11-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '754451bd2ef3'
down_revision = '7a1e5c9b3d82'
branch_labels = None
depends_on = None

MODERATOR_NAME = 'roobs'


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(timezone=True),
                                      nullable=True))
        batch_op.add_column(sa.Column('verification_sent_at', sa.DateTime(timezone=True),
                                      nullable=True))
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(timezone=True),
                                      nullable=True))
        # sa.false() rather than a literal 0: Postgres will not take an
        # integer for a boolean, and production is Postgres.
        batch_op.add_column(sa.Column('is_moderator', sa.Boolean(), server_default=sa.false(),
                                      nullable=False))

    conn = op.get_bind()
    row = conn.execute(sa.text(
        "SELECT id FROM users WHERE lower(trim(display_name)) = :name "
        "ORDER BY created_at, id LIMIT 1"), {"name": MODERATOR_NAME}).first()
    if row is None:
        row = conn.execute(sa.text(
            "SELECT id FROM users WHERE lower(email) LIKE :prefix "
            "ORDER BY created_at, id LIMIT 1"), {"prefix": MODERATOR_NAME + "@%"}).first()
    if row is None:
        print("migration 754451bd2ef3: no account named Roobs, so no moderator was set. "
              "Run `flask --app app set-moderator <email>` to choose one.")
        return
    conn.execute(sa.text("UPDATE users SET is_moderator = :on WHERE id = :id"),
                 {"on": True, "id": row[0]})
    print(f"migration 754451bd2ef3: account #{row[0]} (Roobs) is now the moderator.")


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_moderator')
        batch_op.drop_column('last_login_at')
        batch_op.drop_column('verification_sent_at')
        batch_op.drop_column('email_verified_at')
