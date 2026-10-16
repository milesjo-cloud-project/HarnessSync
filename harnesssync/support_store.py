"""Portable upserts and per-account serialization for support operations."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from harnesssync.db_store import support_locks


def insert_once(conn, table, values):
    insert = sqlite_insert if conn.dialect.name == "sqlite" else pg_insert
    return conn.execute(insert(table).values(**values).on_conflict_do_nothing()).rowcount


def lock_account(conn, user_id):
    insert_once(conn, support_locks, {"user_id": user_id})
    # A write locks this account until commit on Postgres, and the writer on SQLite.
    conn.execute(support_locks.update().where(support_locks.c.user_id == user_id)
                 .values(user_id=user_id))
    return conn.execute(sa.select(support_locks).where(
        support_locks.c.user_id == user_id)).mappings().one()
