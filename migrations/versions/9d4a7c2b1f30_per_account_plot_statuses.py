"""per-account plot statuses

Revision ID: 9d4a7c2b1f30
Revises: 6c1f0b9d2e47
Create Date: 2026-09-14 12:00:00.000000

Replaces the fixed phases with a status list per account. Every existing
account gets the seven it already had, named as they were, and its Building
cap moves off the user row onto the Building status. Plots already on a
shelf are marked as shelved from Exploring, which is where picking one up
used to send it, so nothing about existing data changes behaviour.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d4a7c2b1f30'
down_revision = '6c1f0b9d2e47'
branch_labels = None
depends_on = None

DEFAULTS = (
    ("idea", "Idea", "violet", "active"),
    ("exploring", "Exploring", "blue", "active"),
    ("building", "Building", "green", "active"),
    ("maintaining", "Maintaining", "teal", "active"),
    ("done", "Done", "grey", "closed"),
    ("parked", "Parked", "amber", "parked"),
    ("dropped", "Dropped", "red", "closed"),
)


def upgrade():
    statuses = op.create_table(
        'statuses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=40), nullable=False),
        sa.Column('hue', sa.String(length=20), server_default='grey', nullable=False),
        sa.Column('kind', sa.String(length=10), server_default='active', nullable=False),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('wip_limit', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'key', name='uq_statuses_user_key'),
    )
    with op.batch_alter_table('statuses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_statuses_user_id'), ['user_id'], unique=False)
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shelved_from', sa.String(length=20), nullable=True))

    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id, wip_building_limit FROM users")).fetchall()
    rows = [{"user_id": user_id, "key": key, "name": name, "hue": hue, "kind": kind,
             "position": position, "wip_limit": (cap or 0) if key == "building" else 0}
            for user_id, cap in users
            for position, (key, name, hue, kind) in enumerate(DEFAULTS)]
    if rows:
        op.bulk_insert(statuses, rows)
    op.execute("UPDATE projects SET shelved_from = 'exploring' "
               "WHERE phase IN ('parked', 'done', 'dropped')")

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('wip_building_limit')


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wip_building_limit', sa.Integer(), server_default='3', nullable=False))
    op.execute("UPDATE users SET wip_building_limit = COALESCE((SELECT wip_limit FROM statuses "
               "WHERE statuses.user_id = users.id AND statuses.key = 'building'), 3)")
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('shelved_from')
    with op.batch_alter_table('statuses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_statuses_user_id'))
    op.drop_table('statuses')
