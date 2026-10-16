"""Support access boundaries, durable failure handling, migration, and repair handoffs."""
import os
import shutil
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest import mock

import sqlalchemy as sa

from harnesssync import db_store, feedback_manager as tickets, incidents, profile_manager
from harnesssync import support_notifications as mail
from harnesssync.support_config import is_owner

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
OWNER = "owner@example.com"


class TestSupport(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        db_store.configure(f"sqlite:///{os.path.join(self.directory, 'support.db')}")
        self.config = mock.patch("harnesssync.support_config.settings", return_value={"owner_emails": [OWNER]})
        self.config.start()

    def tearDown(self):
        self.config.stop()
        db_store.get_engine().dispose()
        shutil.rmtree(self.directory, ignore_errors=True)

    def report(self, user="alice@example.com", **kwargs):
        return tickets.submit_feedback(user, "Alice", "Bug", 2, "Save climb button does not work",
                                       now=NOW, area="Log a climb", **kwargs)

    def test_private_tickets_and_owner_reply(self):
        ticket = self.report()
        self.assertEqual(tickets.load_feedback("outsider@example.com"), [])
        self.assertEqual(tickets.load_feedback(None), [])
        self.assertFalse(is_owner("dev:" + OWNER))
        for action in [lambda: tickets.owner_tickets("outsider@example.com"),
                       lambda: tickets.update_ticket("outsider@example.com", ticket["id"], "Fixed", "lie"),
                       lambda: incidents.owner_incidents("outsider@example.com")]:
            with self.assertRaises(PermissionError):
                action()
        tickets.update_ticket(OWNER, ticket["id"], "Investigating", "Checking the save flow.")
        mine = tickets.load_feedback("alice@example.com")[0]
        self.assertEqual(mine["status"], "Investigating")
        self.assertEqual(mine["owner_reply"], "Checking the save flow.")
        with self.assertRaises(ValueError):
            tickets.update_ticket(OWNER, ticket["id"], "Fixed", "")

    def test_direct_calls_cannot_bypass_limits_and_concurrent_submissions(self):
        def attempt(_):
            try:
                return self.report()["id"]
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, [0, 1]))
        self.assertEqual(sum(value is not None for value in results), 1)
        with self.assertRaises(ValueError):
            self.report()
        self.assertEqual(len(tickets.load_feedback("alice@example.com")), 1)

    def test_report_and_outbox_are_atomic(self):
        with mock.patch("harnesssync.feedback_manager.enqueue", side_effect=RuntimeError("db fail")):
            with self.assertRaises(RuntimeError):
                self.report()
        self.assertEqual(tickets.load_feedback("alice@example.com"), [])

    def test_failed_mail_retries_then_stops_after_success(self):
        self.report()
        with mock.patch("harnesssync.notifications.is_configured", return_value=True), \
             mock.patch("harnesssync.notifications.send_email", side_effect=[False, True]) as send:
            self.assertEqual(mail.deliver_pending(now=NOW), 0)
            self.assertEqual(mail.deliver_pending(now=NOW + timedelta(seconds=30)), 0)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(mail.deliver_pending(now=NOW + timedelta(minutes=3)), 1)
            self.assertEqual(mail.deliver_pending(now=NOW + timedelta(hours=1)), 0)
            self.assertEqual(send.call_count, 2)
        with db_store.get_db() as conn:
            entry = conn.execute(sa.select(db_store.notification_outbox)).mappings().one()
        self.assertTrue(entry["sent_at"])
        self.assertEqual(entry["body"], "")

    def test_incidents_are_grouped_without_private_exception_content(self):
        refs = []
        for _ in range(2):
            try:
                raise RuntimeError("password=secret alice@example.com")
            except RuntimeError as error:
                refs.append(incidents.record(error, "Progress"))
        self.assertEqual(refs[0], refs[1])
        entry = incidents.owner_incidents(OWNER)[0]
        self.assertEqual(entry["occurrences"], 2)
        self.assertNotIn("secret", entry["diagnostic"])
        with db_store.get_db() as conn:
            self.assertEqual(conn.execute(sa.select(sa.func.count()).select_from(db_store.notification_outbox)).scalar(), 1)

    def test_account_deletion_covers_support_data(self):
        self.report()
        profile_manager.delete_account("alice@example.com")
        self.assertEqual(tickets.load_feedback("alice@example.com"), [])
        with db_store.get_db() as conn:
            for table in (db_store.notification_outbox, db_store.support_locks):
                self.assertEqual(conn.execute(sa.select(sa.func.count()).select_from(table)).scalar(), 0)

    def test_upgrade_preserves_old_feedback(self):
        old = os.path.join(self.directory, "old.db")
        with sqlite3.connect(old) as conn:
            conn.execute("CREATE TABLE feedback (id INTEGER PRIMARY KEY, user_id VARCHAR(320), display_name VARCHAR(40), submitted_at VARCHAR(32), category VARCHAR(20), rating INTEGER, message TEXT)")
            conn.execute("INSERT INTO feedback VALUES (7, 'old@example.com', 'Old', '2026-01-01', 'Bug', 2, 'Original message')")
        db_store.configure(f"sqlite:///{old}")
        entry = tickets.load_feedback("old@example.com")[0]
        self.assertEqual(entry["id"], 7)
        self.assertEqual(entry["message"], "Original message")
        self.assertEqual(entry["status"], "Received")
        self.assertFalse(entry["ai_consent"])

    def test_repair_handoff_requires_owner_and_excludes_private_metadata(self):
        from harnesssync.repair_brief import build_repair_brief
        ticket = self.report(steps="Email alice@example.com with password=secret123 or sk-privatekey. Database postgresql://user:pass@private.host/db")
        with self.assertRaises(PermissionError):
            build_repair_brief("outsider@example.com", ticket["id"])
        brief = build_repair_brief(OWNER, ticket["id"])
        for private in ("alice@example.com", "secret123", "sk-privatekey", "private.host", "user_id", "display_name"):
            self.assertNotIn(private, brief)
        self.assertIn("Save climb button does not work", brief)
        self.assertIn("HS-000001", brief)
        self.assertIn("Do not merge, deploy", brief)
        self.assertIn("python -m pytest", brief)
        self.assertEqual(tickets.load_feedback("alice@example.com")[0]["status"], "Received")

    def test_repair_handoff_is_scoped_to_selected_ticket_and_missing_is_clear(self):
        from harnesssync.repair_brief import build_repair_brief
        first = self.report()
        tickets.submit_feedback("bob@example.com", "Bob", "General", 4, "Unrelated confidential report", now=NOW)
        brief = build_repair_brief(OWNER, first["id"])
        self.assertNotIn("Unrelated confidential report", brief)
        with self.assertRaisesRegex(ValueError, "not found"):
            build_repair_brief(OWNER, 999)
