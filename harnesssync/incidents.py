"""Crash grouping without exception messages, local variables, SQL, or user data."""
import hashlib
import os
import traceback
from datetime import datetime, timezone

import sqlalchemy as sa

from harnesssync.db_store import get_db, incidents, rows
from harnesssync.support_config import require_owner
from harnesssync.support_notifications import enqueue, stamp
from harnesssync.support_store import insert_once


def record(error, area):
    frames = traceback.extract_tb(error.__traceback__)
    # Only code locations: exception messages can contain credentials or SQL parameters.
    locations = [f"{os.path.basename(f.filename)}:{f.lineno} in {f.name}" for f in frames]
    diagnostic = "\n".join([type(error).__name__, *locations])
    ref = "INC-" + hashlib.sha256(f"{area}\n{diagnostic}".encode()).hexdigest()[:20].upper()
    now = stamp(datetime.now(timezone.utc))
    with get_db() as conn:
        inserted = insert_once(conn, incidents, dict(id=ref, area=area[:40],
            error_type=type(error).__name__[:100], diagnostic=diagnostic,
            first_seen=now, last_seen=now))
        if not inserted:
            conn.execute(incidents.update().where(incidents.c.id == ref).values(
                occurrences=incidents.c.occurrences + 1, last_seen=now))
        # One alert per signature per UTC day, across all sessions and instances.
        enqueue(conn, f"crash:{ref}:{now[:10]}", f"HarnessSync crash {ref}",
                f"Area: {area}\nReference: {ref}\n{diagnostic}")
    return ref


def owner_incidents(actor):
    require_owner(actor)
    with get_db() as conn:
        return rows(conn.execute(sa.select(incidents).order_by(incidents.c.last_seen.desc()).limit(100)))
