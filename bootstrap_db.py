"""
Bring the database schema up to date.

  * `python bootstrap_db.py` from the Render start command, and locally.
  * `run_migrations()` from the app on its first request (see app.py).

Managed by Alembic from the first row. A schema check runs after the upgrade
and raises if the tables and columns the models declare are not all present,
so a bad state is a loud failure at boot rather than a 500 later.
"""
import os
import sys

from flask_migrate import stamp, upgrade
from sqlalchemy import inspect

from extensions import db

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")


def _baseline_revision() -> str:
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    cfg = AlembicConfig()
    cfg.set_main_option("script_location", MIGRATIONS_DIR)
    bases = ScriptDirectory.from_config(cfg).get_bases()
    if len(bases) != 1:
        raise RuntimeError(
            f"expected exactly one base migration to stamp, found {bases!r}.")
    return bases[0]


def _verify_schema() -> None:
    insp = inspect(db.engine)
    existing = set(insp.get_table_names())
    problems: list[str] = []
    for table_name, table in db.metadata.tables.items():
        if table_name not in existing:
            problems.append(f"missing table {table_name!r}")
            continue
        actual = {c["name"] for c in insp.get_columns(table_name)}
        for column in table.columns:
            if column.name not in actual:
                problems.append(f"{table_name}.{column.name} missing")
    if problems:
        raise RuntimeError(
            "schema does not match the models after upgrade: " + "; ".join(problems))


def run_migrations() -> None:
    """Adopt/upgrade the schema. Requires an active app context."""
    tables = set(inspect(db.engine).get_table_names())
    already_tracked = "alembic_version" in tables
    pre_existing = "users" in tables

    if not already_tracked and pre_existing:
        baseline = _baseline_revision()
        print(f"bootstrap_db: existing schema with no migration history - "
              f"stamping the baseline ({baseline}) as applied.")
        stamp(revision=baseline)
    elif not already_tracked:
        print("bootstrap_db: empty database - migrations will build it.")
    else:
        print("bootstrap_db: migration history present.")

    upgrade()
    _verify_schema()
    print("bootstrap_db: schema up to date.")


def main() -> int:
    from app import app

    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance"),
                exist_ok=True)
    with app.app_context():
        run_migrations()
    return 0


if __name__ == "__main__":
    sys.exit(main())
