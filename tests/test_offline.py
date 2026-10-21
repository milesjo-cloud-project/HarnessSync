"""Offline synchronization never uses real accounts, credentials or hosted data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from starlette.applications import Starlette
from starlette.testclient import TestClient

from harnesssync import db_store as db, profile_manager as pm, offline_manager as offline
from harnesssync.offline_routes import routes


@pytest.fixture
def device(tmp_path):
    db.configure(f"sqlite:///{tmp_path / 'offline.db'}")
    pm.save_profile("fictional:alex", "Alex")
    pm.save_profile("fictional:blair", "Blair")
    token = offline.create_device("fictional:alex")
    yield token
    db.get_engine().dispose()


def operation(status="Sent", **changes):
    entry = dict(discipline="Boulder", grade="V4", status=status, date="2026-01-01",
                 route_name="Fictional ridge", location="Imaginary crag", environment="Outdoor",
                 angle="Vertical", hold_type="Mixed", notes="")
    entry.update(changes)
    return {"id": str(uuid4()), "entry": entry}


def test_retry_does_not_duplicate_send_or_attempt(device):
    ops = [operation(), operation("Attempt")]
    result = offline.synchronize(device, ops)
    assert result["acknowledged"] == [o["id"] for o in ops]
    assert offline.synchronize(device, ops)["acknowledged"] == result["acknowledged"]
    assert len(pm.get_climbs("fictional:alex")) == 1
    assert pm.get_projects("fictional:alex")[0]["attempts"] == 1
    offline.synchronize(device, [operation("Attempt")])
    assert pm.get_projects("fictional:alex")[0]["attempts"] == 2


def test_concurrent_retries_are_safe(device):
    op = operation("Attempt")
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: offline.synchronize(device, [op]), range(3)))
    assert all(r["acknowledged"] == [op["id"]] for r in results)
    assert pm.get_projects("fictional:alex")[0]["attempts"] == 1


def test_private_snapshot_and_writes_use_token_account(device):
    pm.log_climb("fictional:blair", "Rope", "5.9", "Sent", "2026-01-01")
    pm.log_project("fictional:blair", "Rope", "5.10a", "2026-01-01")
    result = offline.synchronize(device, [operation()])
    assert result["snapshot"]["account"] == "fictional:alex"
    assert result["snapshot"]["projects"] == []
    assert all(c["discipline"] == "Boulder" for c in result["snapshot"]["climbs"])
    assert all("user_id" not in c for c in result["snapshot"]["climbs"])
    op = operation(user_id="fictional:blair")
    with pytest.raises(ValueError):
        offline.synchronize(device, [op])
    assert len(pm.get_climbs("fictional:blair")) == 1


def test_identifier_reuse_with_changed_payload_rolls_back_batch(device):
    old = operation()
    offline.synchronize(device, [old])
    changed = {"id": old["id"], "entry": {**old["entry"], "grade": "V5"}}
    with pytest.raises(ValueError, match="reused"):
        offline.synchronize(device, [operation(), changed])
    assert len(pm.get_climbs("fictional:alex")) == 1


def test_receipt_and_climb_commit_together(device):
    op = operation()
    with patch.object(offline, "_log_climb", side_effect=RuntimeError("fictional failure")):
        with pytest.raises(RuntimeError):
            offline.synchronize(device, [op])
    with db.get_db() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(db.offline_receipts)).scalar_one() == 0
    offline.synchronize(device, [op])
    assert len(pm.get_climbs("fictional:alex")) == 1


@pytest.mark.parametrize("changes", [{"grade": "V900"}, {"discipline": "Other"},
    {"date": "garbage"}, {"status": "unknown"}, {"notes": "x" * 501}, {"environment": "unknown"}])
def test_invalid_entries_do_not_partially_sync(device, changes):
    with pytest.raises(ValueError):
        offline.synchronize(device, [operation(), operation(**changes)])
    assert pm.get_climbs("fictional:alex") == []


def test_revocation_expiry_and_account_deletion(device):
    other_token = offline.create_device("fictional:blair")
    offline.revoke_devices("fictional:alex")
    with pytest.raises(offline.DeviceUnauthorized):
        offline.synchronize(device, [])
    offline.synchronize(other_token, [])
    with db.get_db() as conn:
        conn.execute(db.offline_devices.update().values(
            expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat()))
    with pytest.raises(offline.DeviceUnauthorized):
        offline.synchronize(other_token, [])
    token = offline.create_device("fictional:alex")
    offline.synchronize(token, [operation()])
    pm.delete_account("fictional:alex")
    with pytest.raises(offline.DeviceUnauthorized):
        offline.synchronize(token, [])
    with db.get_db() as conn:
        assert conn.execute(sa.select(db.offline_receipts).where(db.offline_receipts.c.user_id == "fictional:alex")).first() is None


def test_routes_auth_assets_and_cache_policy(device):
    with TestClient(Starlette(routes=routes)) as client:
        response = client.get("/offline/")
        assert response.status_code == 200
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert client.get("/offline/sw.js").headers["content-type"].startswith("text/javascript")
        assert client.get("/offline/unknown").status_code == 404
        assert client.post("/offline/api/sync", json={"operations": []}).status_code == 401
        headers = {"Authorization": f"Bearer {device}"}
        response = client.post("/offline/api/sync", json={"operations": [operation()]}, headers=headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert len(response.json()["snapshot"]["climbs"]) == 1
        assert client.post("/offline/api/sync", content="{", headers=headers).status_code == 400
        assert client.post("/offline/api/sync", content="x" * 250001, headers=headers).status_code == 413


def test_additive_tables_preserve_existing_climbs(device):
    pm.log_climb("fictional:alex", "Boulder", "V3", "Sent", "2026-01-01")
    db.configure(str(db.get_engine().url))
    assert len(pm.get_climbs("fictional:alex")) == 1
    offline.synchronize(device, [])
