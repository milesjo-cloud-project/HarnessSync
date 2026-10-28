"""Revocable device access and atomic, account-scoped offline synchronization."""

import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from harnesssync.db_store import (
    get_db, rows, profiles, climbs, projects, offline_devices, offline_receipts,
)
from harnesssync.grades import (
    GRADES_BY_DISCIPLINE, SEND_STATUSES, PROJECT_STATUSES, ENVIRONMENTS,
    WALL_ANGLES, HOLD_TYPES,
)
from harnesssync.profile_manager import _log_climb, _log_project, ROUTE_MAX, LOCATION_MAX, NOTES_MAX


class DeviceUnauthorized(ValueError):
    pass


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def create_device(user_id):
    """Called only from the authenticated Streamlit UI. Raw tokens are never stored."""
    token = secrets.token_urlsafe(32)
    with get_db() as conn:
        if not conn.execute(sa.select(profiles.c.user_id).where(profiles.c.user_id == user_id)).first():
            raise DeviceUnauthorized("Sign in and create a profile first.")
        conn.execute(offline_devices.insert().values(
            token_hash=_hash(token), user_id=user_id,
            expires_at=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        ))
    return token


def revoke_devices(user_id):
    with get_db() as conn:
        conn.execute(offline_devices.delete().where(offline_devices.c.user_id == user_id))


def _authenticate(conn, token):
    if not isinstance(token, str) or not 20 <= len(token) <= 100:
        raise DeviceUnauthorized("Reconnect this device from the Phone App tab.")
    user_id = conn.execute(
        sa.select(offline_devices.c.user_id).join(
            profiles, profiles.c.user_id == offline_devices.c.user_id,
        ).where(
            offline_devices.c.token_hash == _hash(token),
            offline_devices.c.expires_at > datetime.now(timezone.utc).isoformat(),
        )
    ).scalar_one_or_none()
    if not user_id:
        raise DeviceUnauthorized("Device access expired or was revoked. Reconnect from the Phone App tab.")
    return user_id


def _validate(operation):
    if not isinstance(operation, dict) or set(operation) != {"id", "entry"}:
        raise ValueError("Invalid queued entry.")
    try:
        operation_id = str(UUID(operation["id"]))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid entry identifier.") from None
    entry = operation["entry"]
    allowed = {"discipline", "grade", "status", "date", "route_name", "location", "environment", "angle", "hold_type", "notes"}
    if not isinstance(entry, dict) or set(entry) != allowed or any(not isinstance(v, str) for v in entry.values()):
        raise ValueError("Invalid climb fields.")
    choices = {"discipline": GRADES_BY_DISCIPLINE, "status": SEND_STATUSES,
               "environment": ENVIRONMENTS, "angle": WALL_ANGLES, "hold_type": HOLD_TYPES}
    for field, values in choices.items():
        if entry[field] not in values:
            raise ValueError(f"Invalid {field}.")
    if entry["grade"] not in GRADES_BY_DISCIPLINE[entry["discipline"]]:
        raise ValueError("Invalid grade.")
    try:
        parsed_date = date.fromisoformat(entry["date"])
        if parsed_date.isoformat() != entry["date"] or parsed_date > datetime.now(timezone.utc).date() + timedelta(days=1):
            raise ValueError()
    except ValueError:
        raise ValueError("Invalid climb date.") from None
    for field, maximum in (("route_name", ROUTE_MAX), ("location", LOCATION_MAX), ("notes", NOTES_MAX)):
        if len(entry[field]) > maximum:
            raise ValueError(f"{field} is too long.")
    return operation_id, entry, _hash(json.dumps(entry, sort_keys=True, ensure_ascii=True))


def synchronize(token, operations, language=None):
    """Acknowledge only committed writes; a lost response is safe to retry."""
    if not isinstance(operations, list) or len(operations) > 100:
        raise ValueError("Sync accepts at most 100 entries at a time.")
    from harnesssync.i18n import LANGUAGES
    if language is not None and (not isinstance(language, str) or language not in LANGUAGES):
        raise ValueError("Unsupported language.")
    validated = [_validate(op) for op in operations]
    with get_db() as conn:
        user_id = _authenticate(conn, token)
        # Serialize device batches for the same account, including separate devices.
        if conn.dialect.name == "postgresql":
            conn.execute(sa.select(profiles.c.user_id).where(profiles.c.user_id == user_id).with_for_update())
        if language is not None:
            conn.execute(profiles.update().where(profiles.c.user_id == user_id).values(language=language))
        insert = sqlite_insert if conn.dialect.name == "sqlite" else pg_insert
        acknowledged = []
        for operation_id, entry, payload_hash in validated:
            claimed = conn.execute(insert(offline_receipts).values(
                user_id=user_id, operation_id=operation_id, payload_hash=payload_hash,
            ).on_conflict_do_nothing(index_elements=["user_id", "operation_id"]))
            if claimed.rowcount:
                kwargs = {k: v for k, v in entry.items() if k not in {"date", "status"}}
                if entry["status"] in PROJECT_STATUSES:
                    _log_project(conn, user_id, project_date=entry["date"], **kwargs)
                else:
                    _log_climb(conn, user_id, status=entry["status"], climb_date=entry["date"], **kwargs)
            else:
                previous = conn.execute(sa.select(offline_receipts.c.payload_hash).where(
                    offline_receipts.c.user_id == user_id, offline_receipts.c.operation_id == operation_id,
                )).scalar_one()
                if previous != payload_hash:
                    raise ValueError("An entry identifier was reused with different data.")
            acknowledged.append(operation_id)
        snapshot = {
            "account": user_id,
            "language": conn.execute(sa.select(profiles.c.language).where(profiles.c.user_id == user_id)).scalar_one(),
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "climbs": rows(conn.execute(sa.select(climbs).where(climbs.c.user_id == user_id).order_by(climbs.c.date.desc(), climbs.c.id.desc()))),
            "projects": rows(conn.execute(sa.select(projects).where(projects.c.user_id == user_id).order_by(projects.c.id.desc()))),
        }
        for records in (snapshot["climbs"], snapshot["projects"]):
            for record in records:
                record.pop("user_id", None)
    return {"acknowledged": acknowledged, "snapshot": snapshot}
