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
    # Start time of a running session timer, so it survives a page reload
    # (phones often reload a backgrounded tab mid-session). NULL when idle.
    sa.Column("active_session_started", sa.String(32), nullable=True),
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
    sa.Column("notes", sa.Text, nullable=False, default=""),
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

# Signed-in users who want a native phone app. One row per account, so the
# count is a count of real (Google-verified) people, not form submissions.
waitlist = sa.Table(
    "waitlist", metadata,
    sa.Column("user_id", sa.String(320), primary_key=True),
    sa.Column("platform", sa.String(20), nullable=False),   # iPhone / Android / Both
    sa.Column("wants", sa.String(300), nullable=False, default=""),  # comma-separated reasons
    sa.Column("note", sa.Text, nullable=False, default=""),
    sa.Column("joined_at", sa.String(32), nullable=False),  # UTC ISO timestamp
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
        return url
    os.makedirs(PROFILES_DIR, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


def _normalize_url(url):
    """Providers hand out "postgres://" or "postgresql://". Pin the driver to
    psycopg 3 explicitly - SQLAlchemy's default Postgres driver differs
    between versions (psycopg2 in 2.0, psycopg in 2.1)."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


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
    _engine = _create_engine(_normalize_url(url or _database_url()))
    _set_aside_legacy_tables(_engine)
    metadata.create_all(_engine)
    _add_missing_columns(_engine)
    return _engine


def _add_missing_columns(engine):
    """Apply small additive migrations for columns added after initial setup."""
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    additions = [
        ("climbs", "notes", "TEXT NOT NULL DEFAULT ''"),
        ("profiles", "active_session_started", "VARCHAR(32)"),
    ]
    for table, column, ddl in additions:
        if table not in tables:
            continue
        if column not in {c["name"] for c in inspector.get_columns(table)}:
            with engine.begin() as conn:
                conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


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
