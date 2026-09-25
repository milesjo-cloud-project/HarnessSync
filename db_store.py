"""Database storage engine for HarnessSync.

Runs on SQLAlchemy so the same code works against:
  - a local SQLite file (default - Docker, local dev, tests), and
  - a hosted Postgres database (Neon, Supabase, ...) in production.

Streamlit Community Cloud wipes the container's disk on every reboot and
redeploy, so a deployed app must point at a hosted database. Set it in
`.streamlit/secrets.toml` (or the Cloud "Secrets" box):

    [database]
    url = "postgresql://user:password@host/dbname?sslmode=require"

or via the DATABASE_URL environment variable. With neither set, data goes to
climber_profiles/harnesssync.db.
"""

import os
from contextlib import contextmanager

import sqlalchemy as sa

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "climber_profiles")
DEFAULT_SQLITE_PATH = os.path.join(PROFILES_DIR, "harnesssync.db")

metadata = sa.MetaData()

# One row per signed-in account. user_id is the login email (or "dev:<name>"
# in local dev mode); display_name is what other people see.
profiles = sa.Table(
    "profiles", metadata,
    sa.Column("user_id", sa.String(320), primary_key=True),
    sa.Column("display_name", sa.String(40), nullable=False),
    sa.Column("show_on_leaderboard", sa.Boolean, nullable=False, default=True),
    sa.Column("created_at", sa.String(32), nullable=False),
)

climbs = sa.Table(
    "climbs", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.String(320), nullable=False, index=True),
    sa.Column("date", sa.String(10), nullable=False),
    sa.Column("discipline", sa.String(20), nullable=False),
    sa.Column("grade", sa.String(10), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("route_name", sa.String(100), nullable=False, default=""),
    sa.Column("location", sa.String(100), nullable=False, default=""),
    sa.Column("environment", sa.String(20), nullable=False, default="Gym"),
    sa.Column("angle", sa.String(20), nullable=False, default="Vertical"),
    sa.Column("hold_type", sa.String(20), nullable=False, default="Mixed"),
)

projects = sa.Table(
    "projects", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.String(320), nullable=False, index=True),
    sa.Column("date", sa.String(10), nullable=False),
    sa.Column("discipline", sa.String(20), nullable=False),
    sa.Column("grade", sa.String(10), nullable=False),
    sa.Column("route_name", sa.String(100), nullable=False, default=""),
    sa.Column("location", sa.String(100), nullable=False, default=""),
    sa.Column("environment", sa.String(20), nullable=False, default="Gym"),
    sa.Column("angle", sa.String(20), nullable=False, default="Vertical"),
    sa.Column("hold_type", sa.String(20), nullable=False, default="Mixed"),
    sa.Column("attempts", sa.Integer, nullable=False, default=1),
    sa.Column("notes", sa.Text, nullable=False, default=""),
)

sessions = sa.Table(
    "sessions", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.String(320), nullable=False, index=True),
    sa.Column("date", sa.String(10), nullable=False),
    sa.Column("started_at", sa.String(32), nullable=False),
    sa.Column("ended_at", sa.String(32), nullable=False),
    sa.Column("duration_min", sa.Float, nullable=False),
)

feedback = sa.Table(
    "feedback", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.String(320), nullable=False, index=True),
    sa.Column("display_name", sa.String(40), nullable=False),
    sa.Column("submitted_at", sa.String(32), nullable=False),  # UTC ISO timestamp
    sa.Column("category", sa.String(20), nullable=False),
    sa.Column("rating", sa.Integer, nullable=False),
    sa.Column("message", sa.Text, nullable=False),
)

_engine = None


def _database_url():
    try:
        import streamlit as st
        url = st.secrets.get("database", {}).get("url")
    except Exception:
        url = None
    url = url or os.environ.get("DATABASE_URL")
    if url:
        # Neon/Supabase/Heroku hand out "postgres://", which SQLAlchemy doesn't accept
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url
    os.makedirs(PROFILES_DIR, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


def _create_engine(url):
    if url.startswith("sqlite"):
        engine = sa.create_engine(url, connect_args={"timeout": 30})

        @sa.event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            # WAL lets concurrent Streamlit sessions read while another writes
            dbapi_conn.execute("PRAGMA journal_mode=WAL;")
    else:
        # pre_ping: hosted Postgres (esp. Neon) drops idle connections
        engine = sa.create_engine(url, pool_pre_ping=True, pool_recycle=300)
    return engine


def configure(url=None):
    """(Re)point the app at a database and create any missing tables.
    Called lazily on first use; tests call it directly with a temp SQLite URL."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = _create_engine(url or _database_url())
    _set_aside_legacy_tables(_engine)
    metadata.create_all(_engine)
    return _engine


def _set_aside_legacy_tables(engine):
    """Pre-login databases keyed rows by a free-text climber_name. Those rows
    can't be tied to an account, so rename the old tables out of the way
    (kept, not dropped) and let create_all build the new schema."""
    inspector = sa.inspect(engine)
    existing = set(inspector.get_table_names())
    if "climbs" not in existing:
        return
    if "user_id" in {c["name"] for c in inspector.get_columns("climbs")}:
        return
    with engine.begin() as conn:
        for name in ("climbs", "projects", "sessions", "feedback"):
            if name in existing:
                conn.execute(sa.text(f'ALTER TABLE "{name}" RENAME TO "{name}_legacy"'))


def get_engine():
    if _engine is None:
        configure()
    return _engine


@contextmanager
def get_db():
    """A connection inside a transaction - commits on success, rolls back on error."""
    with get_engine().begin() as conn:
        yield conn


def rows(result):
    """Convert a SQLAlchemy result into a list of plain dicts."""
    return [dict(r._mapping) for r in result]
