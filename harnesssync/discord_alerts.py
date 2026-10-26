"""Deterministic outbound Discord uptime alerts. No AI, inbound webhooks or app DB.

Run as one independent background worker with its own persistent SQLite file.
Only the configured Discord webhook can receive notifications.
"""

import argparse
import json
import os
import re
import math
import signal
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from harnesssync.site_health import NoRedirect, SITE_URL, check_public_site


@dataclass(frozen=True)
class Settings:
    webhook_url: str = field(repr=False)
    state_path: Path
    interval: int = 300

    @classmethod
    def from_env(cls):
        url = os.environ.get("DISCORD_ALERTS_WEBHOOK_URL", "").strip()
        validate_webhook_url(url)
        path = Path(os.environ.get("DISCORD_ALERTS_STATE_PATH", ""))
        if not path.is_absolute():
            raise ValueError("Set DISCORD_ALERTS_STATE_PATH to an absolute path on the worker's persistent disk.")
        return cls(url, path)


def validate_webhook_url(url):
    """Only Discord's direct HTTPS webhook endpoint; never a redirect target."""
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.hostname == "discord.com"
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and not parsed.query and not parsed.fragment
                 and re.fullmatch(r"/api(?:/v10)?/webhooks/[0-9]{5,25}/[A-Za-z0-9._-]{20,200}", parsed.path))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Set DISCORD_ALERTS_WEBHOOK_URL to a direct HTTPS Discord webhook URL without query parameters.")


class SendFailure(Exception):
    """Safe reason code only: never retain provider bodies or credentials."""
    def __init__(self, reason, retryable=True, retry_after=None):
        super().__init__(reason)
        self.retryable = retryable
        self.retry_after = retry_after


def send_discord(settings, body, opener=None):
    """wait=true confirms a saved message, not delivery of a phone notification."""
    validate_webhook_url(settings.webhook_url)
    if not body or len(body) > 2000:
        raise SendFailure("invalid_message", retryable=False)
    request = Request(
        settings.webhook_url + "?wait=true",
        data=json.dumps({"content": body, "allowed_mentions": {"parse": []}, "flags": 4}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "HarnessSync-uptime-monitor/1.0"},
        method="POST",
    )
    try:
        with (opener or build_opener(NoRedirect())).open(request, timeout=15) as response:
            data = response.read(65537)
            if response.status != 200 or len(data) > 65536:
                raise SendFailure("invalid_provider_response")
            payload = json.loads(data)
            message_id = payload.get("id", "")
            if not isinstance(message_id, str) or not re.fullmatch(r"[0-9]{5,25}", message_id):
                raise SendFailure("invalid_provider_response")
            return message_id
    except HTTPError as error:
        retry_after = None
        if error.code == 429:
            try:
                retry_after = float(error.headers.get("Retry-After", "nan"))
                if not math.isfinite(retry_after) or retry_after < 0:
                    retry_after = float(json.loads(error.read(65536)).get("retry_after", 0))
                if not math.isfinite(retry_after) or retry_after < 0:
                    retry_after = None
            except (ValueError, TypeError, AttributeError, OSError):
                retry_after = None
        raise SendFailure(f"provider_http_{error.code}", retryable=error.code == 429 or error.code >= 500,
                          retry_after=retry_after) from None
    except (TimeoutError, URLError, OSError):
        raise SendFailure("provider_unavailable") from None
    except (ValueError, TypeError, AttributeError):
        raise SendFailure("invalid_provider_response") from None


class AlertStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.conn = sqlite3.connect(path, timeout=20, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS discord_alert_state (
                id INTEGER PRIMARY KEY CHECK (id=1), failures INTEGER NOT NULL DEFAULT 0,
                successes INTEGER NOT NULL DEFAULT 0, incident TEXT NOT NULL DEFAULT '', last_check REAL
            );
            INSERT OR IGNORE INTO discord_alert_state(id) VALUES (1);
            CREATE TABLE IF NOT EXISTS discord_alert_outbox (
                id TEXT PRIMARY KEY, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL,
                message_id TEXT, error_code TEXT
            );
        """)

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def record(self, checks, now):
        healthy = all(check.ok for check in checks) and bool(checks)
        with self.transaction():
            state = self.conn.execute("SELECT * FROM discord_alert_state WHERE id=1").fetchone()
            failures = 0 if healthy else state["failures"] + 1
            successes = state["successes"] + 1 if healthy else 0
            incident, event, body = state["incident"], None, None
            stamp = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="minutes")
            if not incident and failures >= 3:
                incident = uuid.uuid4().hex[:12]
                event = "outage"
                paths = ", ".join(check.path for check in checks if not check.ok)
                body = f"HarnessSync OUTAGE [{incident}] at {stamp}: 3 consecutive public checks failed. Affected: {paths}. {SITE_URL}"
            elif incident and successes >= 2:
                event = "recovery"
                body = f"HarnessSync RECOVERED [{incident}] at {stamp}: public checks passed twice after an outage. Sign-in and saving are not verified. {SITE_URL}"
            if event:
                # Never deliver a stale DOWN text after recovery, or an old
                # recovery after a new incident. Keep superseded rows for audit.
                self.conn.execute("UPDATE discord_alert_outbox SET status='superseded' WHERE status IN ('pending','blocked')")
                self.conn.execute("INSERT INTO discord_alert_outbox(id,body,next_attempt) VALUES (?,?,?)",
                                  (f"{incident}:{event}", body, now))
                if event == "recovery":
                    incident = ""
            self.conn.execute("UPDATE discord_alert_state SET failures=?,successes=?,incident=?,last_check=? WHERE id=1",
                              (failures, successes, incident, now))
        return event

    def deliver(self, settings, now, sender=send_discord):
        # Lock the row through the bounded provider request so two workers
        # cannot send it concurrently. A lost acknowledgement can still repeat
        # a Discord message; the stable incident reference identifies the same event.
        with self.transaction():
            row = self.conn.execute("SELECT * FROM discord_alert_outbox WHERE status='pending' AND next_attempt<=? ORDER BY next_attempt LIMIT 1", (now,)).fetchone()
            if not row:
                return "quiet"
            attempts = row["attempts"] + 1
            try:
                sid = sender(settings, row["body"])
            except SendFailure as error:
                blocked = not error.retryable or attempts >= 5
                self.conn.execute("UPDATE discord_alert_outbox SET attempts=?,status=?,next_attempt=?,error_code=? WHERE id=?",
                                  (attempts, "blocked" if blocked else "pending", now + max(min(3600, 60 * 2 ** attempts), error.retry_after or 0), str(error), row["id"]))
                return "blocked" if blocked else "retry_pending"
            self.conn.execute("UPDATE discord_alert_outbox SET attempts=?,status='posted',message_id=?,error_code=NULL WHERE id=?",
                              (attempts, sid, row["id"]))
            return "posted"

    def retry_blocked(self):
        self.conn.execute("UPDATE discord_alert_outbox SET status='pending',attempts=0,next_attempt=0 WHERE status='blocked'")

    def status(self):
        state = dict(self.conn.execute("SELECT * FROM discord_alert_state WHERE id=1").fetchone())
        state["notifications"] = [dict(row) for row in self.conn.execute("SELECT id,status,attempts,error_code FROM discord_alert_outbox ORDER BY rowid DESC LIMIT 10")]
        return state

    def close(self):
        self.conn.close()


def run_once(settings, store, checker=check_public_site, sender=send_discord, now=None):
    now = time.time() if now is None else now
    checks = checker()
    event = store.record(checks, now)
    notification = store.deliver(settings, now, sender)
    return {"public_endpoints_ok": bool(checks) and all(check.ok for check in checks),
            "authenticated_flows_checked": False, "event": event, "notification": notification}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--once", action="store_true")
    modes.add_argument("--test-message", action="store_true", help="Post one setup test to the configured channel")
    modes.add_argument("--status", action="store_true", help="Inspect local monitor state without posting messages")
    parser.add_argument("--retry-blocked", action="store_true", help="Retry current blocked alert after fixing provider settings")
    args = parser.parse_args()
    if args.status:
        path = os.environ.get("DISCORD_ALERTS_STATE_PATH")
        if not path or not Path(path).is_absolute() or not Path(path).is_file():
            print("Set DISCORD_ALERTS_STATE_PATH to an existing absolute monitor-state file.")
            return 1
        store = AlertStore(path)
        try:
            print(json.dumps(store.status()))
        finally:
            store.close()
        return 0
    if os.environ.get("DISCORD_ALERTS_ENABLED") != "true":
        print("Discord alerts are disabled. Configure the worker, then set DISCORD_ALERTS_ENABLED=true.")
        return 0
    try:
        settings = Settings.from_env()
    except ValueError as error:
        print(str(error))
        return 1
    if args.test_message:
        try:
            send_discord(settings, f"HarnessSync Discord alerts test. Monitoring target: {SITE_URL}. No AI or automatic coding is enabled.")
            print("Test message saved by Discord; verify it appears in your channel.")
            return 0
        except SendFailure as error:
            print(f"Test message not confirmed: {error}")
            return 1
    store = AlertStore(settings.state_path)
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_args: stopped.set())
    try:
        if args.retry_blocked:
            store.retry_blocked()
        while not stopped.is_set():
            started = time.monotonic()
            result = run_once(settings, store)
            print(json.dumps(result), flush=True)
            if args.once:
                return 1 if result["notification"] == "blocked" else 0
            stopped.wait(max(1, settings.interval - (time.monotonic() - started)))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
