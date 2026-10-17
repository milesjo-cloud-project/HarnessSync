"""Durable, leased email outbox. Run: python -m harnesssync.support_notifications.

SMTP delivery is at-least-once: a crash after acceptance may cause a duplicate.
Ticket and incident references make duplicates identifiable.
"""
import argparse
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import sqlalchemy as sa

from harnesssync import notifications
from harnesssync.db_store import configure, get_db, notification_outbox as outbox
from harnesssync.support_store import insert_once


def stamp(value):
    return value.isoformat(timespec="seconds")


def enqueue(conn, event_key, subject, body, user_id="", now=None):
    insert_once(conn, outbox, dict(event_key=event_key, subject=subject[:200], body=body,
                                 user_id=user_id, next_attempt=stamp(now or datetime.now(timezone.utc))))


def deliver_pending(limit=5, now=None, event_key=None, *, raise_on_failure=False):
    """Claim due messages. Failed deliveries back off up to six hours."""
    if not notifications.is_configured():
        return 0
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    due = [outbox.c.sent_at.is_(None), outbox.c.next_attempt <= stamp(now)]
    if event_key:
        due.append(outbox.c.event_key == event_key)
    with get_db() as conn:
        candidates = conn.execute(sa.select(outbox.c.event_key).where(*due)
                                  .order_by(outbox.c.next_attempt).limit(limit)).scalars().all()
    delivered = 0
    failed = 0
    for key in candidates:
        lease = uuid4().hex
        claimed_at = fixed_now or datetime.now(timezone.utc)
        with get_db() as conn:
            claimed = conn.execute(outbox.update().where(outbox.c.event_key == key, *due)
                                   .values(lease=lease, next_attempt=stamp(claimed_at + timedelta(minutes=2)),
                                           attempts=outbox.c.attempts + 1)).rowcount
            if not claimed:
                continue
            entry = conn.execute(sa.select(outbox).where(outbox.c.event_key == key)).mappings().one()
        try:
            success = notifications.send_email(subject=entry["subject"], body=entry["body"])
        except Exception:
            success = False
        finished_at = fixed_now or datetime.now(timezone.utc)
        with get_db() as conn:
            values = dict(lease="", next_attempt=stamp(finished_at + timedelta(
                minutes=min(360, 2 ** min(entry["attempts"], 9)))))
            if success:
                values.update(sent_at=stamp(finished_at), body="")
            conn.execute(outbox.update().where(outbox.c.event_key == key, outbox.c.lease == lease)
                         .values(**values))
        delivered += bool(success)
        failed += not success
    if failed and raise_on_failure:
        raise RuntimeError("Email delivery failed; notifications remain queued for retry.")
    return delivered


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scheduled", action="store_true",
                        help="Require explicit Postgres and email environment settings; fail on delivery errors.")
    args = parser.parse_args(argv)
    if args.scheduled:
        # Never silently create an empty SQLite queue or read local secrets on a
        # cloud runner. Do not print URLs, exception messages, or report bodies.
        url = os.environ.get("DATABASE_URL", "").strip()
        try:
            parsed = sa.engine.make_url(url)
            valid_database = (
                parsed.drivername in ("postgres", "postgresql", "postgresql+psycopg")
                and bool(parsed.host and parsed.database)
            )
        except Exception:
            valid_database = False
        if not valid_database or not all(os.environ.get(key, "").strip() for key in (
            "HARNESSSYNC_EMAIL_ADDRESS", "HARNESSSYNC_EMAIL_APP_PASSWORD"
        )):
            print("Retry worker configuration is incomplete: set DATABASE_URL (Postgres) and email environment secrets.")
            return 1
        try:
            configure(url)
            delivered = deliver_pending(limit=25, raise_on_failure=True)
        except Exception:
            print("Retry worker failed. Check database connectivity and email settings; unsent notifications remain queued.")
            return 1
    else:
        delivered = deliver_pending(limit=25)
    print(f"Delivered {delivered} queued notifications.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
