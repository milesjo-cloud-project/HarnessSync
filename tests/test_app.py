"""Runs app.py itself, so a crash anywhere in the page fails CI.

The Docker smoke test only proves the server starts: Streamlit's health check
answers before app.py has run once.
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from streamlit.testing.v1 import AppTest

from harnesssync import db_store, profile_manager
from harnesssync.grades import SENT_STATUSES

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
USER = "dev:guest"  # dev mode's default "Guest" climber


class TestApp(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        db_store.configure(f"sqlite:///{os.path.join(self.test_dir, 'app.db')}")
        self._old_dev_mode = os.environ.get("HARNESSSYNC_DEV_MODE")
        os.environ["HARNESSSYNC_DEV_MODE"] = "1"

    def tearDown(self):
        if self._old_dev_mode is None:
            os.environ.pop("HARNESSSYNC_DEV_MODE", None)
        else:
            os.environ["HARNESSSYNC_DEV_MODE"] = self._old_dev_mode
        db_store.get_engine().dispose()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, at=None, allow_error=False):
        if at is None:
            at = AppTest.from_file(APP_PATH, default_timeout=30)
            # Blank out a local .streamlit/secrets.toml so the run is the same
            # on a dev machine as in CI: dev mode, no Google sign-in, no email.
            at.secrets["auth"] = {}
            at.secrets["email"] = {}
            at.secrets["support"] = {}
        # AppTest does not yet serialize tracked tabs as widgets. Re-apply the
        # selected label to emulate the browser sending it with each rerun.
        if "main_tabs" in at.session_state:
            at.session_state["main_tabs"] = at.session_state["main_tabs"]
        at.run()
        self.assertEqual([e.value for e in at.exception], [])
        if not allow_error:
            self.assertEqual([e.value for e in at.error], [])
        return at

    def _button(self, at, label):
        return next(b for b in at.button if b.label == label)

    def _tab(self, at, label, allow_error=False):
        at.session_state["main_tabs"] = label
        return self._run(at, allow_error=allow_error)

    def test_page_renders(self):
        at = self._run()
        self.assertEqual(
            [t.label for t in at.tabs][:7],
            ["🧗 Log a climb", "📊 Progress", "🎯 Projects", "🏆 Leaderboard", "📱 Phone App", "💬 Help & report a problem", "📖 Guide & Reference"],
        )
        at = self._tab(at, "💬 Help & report a problem")
        self.assertNotIn("Ask the support assistant", [e.label for e in at.expander])
        self.assertFalse(any("OpenAI" in w.label or "Ollama" in w.label for w in at.checkbox))

    def test_log_climb_from_main_flow(self):
        at = self._run()
        self._button(at, "Save climb").click()
        at = self._run(at)
        self.assertEqual(len(profile_manager.get_climbs(USER)), 1)
        at = self._tab(at, "📊 Progress")
        total = next(m for m in at.metric if m.label == "Total Climbs Logged")
        self.assertEqual(total.value, "1")

    def test_session_timer(self):
        at = self._run()
        self._button(at, "▶️ Start Session").click()
        at = self._run(at)
        self.assertIsNotNone(profile_manager.active_session_start(USER))
        self._button(at, "⏹ End Session").click()
        self._run(at)
        self.assertIsNone(profile_manager.active_session_start(USER))
        self.assertEqual(len(profile_manager.get_sessions(USER)), 1)

    def test_every_tab_renders_with_data(self):
        self._run()  # creates the dev profile
        profile_manager.log_climb(USER, "Boulder", "V3", "Sent", "2026-09-01")
        profile_manager.log_climb(USER, "Rope", "5.10a", "Flash", "2026-09-20")
        profile_manager.log_project(USER, "Boulder", "V6", "2026-09-20", route_name="Crux", notes="heel hook")
        at = self._run()
        at = self._tab(at, "📊 Progress")
        self.assertEqual(len(at.get("vega_lite_chart")), 3)  # pyramid, send styles, progression
        at = self._tab(at, "🎯 Projects")
        self.assertIn("🎉 SENT IT! (Graduate)", [b.label for b in at.button])
        for label in ["🏆 Leaderboard", "📱 Phone App", "💬 Help & report a problem", "📖 Guide & Reference"]:
            self._tab(at, label)

    def test_feature_crash_is_recorded_and_other_tabs_still_work(self):
        sent = []
        with mock.patch("harnesssync.notifications.send_email", side_effect=lambda **kw: sent.append(kw) or True), mock.patch("harnesssync.notifications.is_configured", return_value=True), mock.patch("harnesssync.ui.guide.render", side_effect=RuntimeError("secret boom")):
            at = self._run()
            self.assertEqual(sent, [])
            at = self._tab(at, "📖 Guide & Reference", allow_error=True)
            self.assertTrue(at.error)
            self.assertTrue(any("INC-" in call["body"] for call in sent))
            self.assertNotIn("secret boom", str(sent))
            at = self._tab(at, "💬 Help & report a problem")
            self.assertIn("Send report", [b.label for b in at.button])

    def test_report_submission_and_failed_validation_preserve_draft(self):
        from harnesssync.feedback_manager import load_feedback
        at = self._tab(self._run(), "💬 Help & report a problem")
        next(w for w in at.text_area if w.label.startswith("What happened")).set_value("My save button stopped working")
        self._button(at, "Send report").click()
        at = self._run(at)
        self.assertEqual(len(load_feedback(USER)), 1,
                         ([e.value for e in at.error], [w.value for w in at.warning]))
        self.assertTrue(any("HS-000001" in e.label for e in at.expander))
        next(w for w in at.text_area if w.label.startswith("What happened")).set_value("A second draft")
        self._button(at, "Send report").click()
        at = self._run(at)
        self.assertTrue(at.warning)
        self.assertEqual(next(w for w in at.text_area if w.label.startswith("What happened")).value, "A second draft")
        self.assertEqual(len(load_feedback(USER)), 1)

    def test_owner_reply_is_visible_to_reporter(self):
        from harnesssync.feedback_manager import submit_feedback, load_feedback
        submit_feedback(USER, "Guest", "Bug", 2, "Can't save a climb")
        owner = AppTest.from_string(
            "from harnesssync.ui.feedback import render\nrender('owner@example.com', 'Owner')",
            default_timeout=30,
        )
        owner.secrets["support"] = {"owner_emails": ["owner@example.com"]}
        owner.secrets["email"] = {}
        owner.run()
        self.assertEqual([e.value for e in owner.exception], [])
        self.assertIn("Prepare a fix with Codex Cloud", [e.label for e in owner.expander])
        brief = next(w for w in owner.text_area if w.label == "Review repair brief before sharing")
        self.assertIn("Can't save a climb", brief.value)
        next(w for w in owner.selectbox if w.label == "Report status").set_value("Investigating")
        next(w for w in owner.text_area if w.label == "Reply visible to the reporter").set_value("Checking this now.")
        self._button(owner, "Save status and reply").click().run()
        self.assertEqual([e.value for e in owner.exception], [])
        self.assertEqual(load_feedback(USER)[0]["status"], "Investigating")
        at = self._tab(self._run(), "💬 Help & report a problem")
        self.assertTrue(any(w.value == "Checking this now." for w in at.text))
        self.assertFalse(any(e.label == "Owner support dashboard" for e in at.expander))

    def test_charts_have_table_text_alternatives(self):
        """Altair renders to canvas, which assistive tech can't read. Every chart
        needs the same numbers available as a table, so don't let those drop out."""
        self._run()  # creates the dev profile
        profile_manager.log_climb(USER, "Boulder", "V3", "Sent", "2026-09-01")
        profile_manager.log_climb(USER, "Boulder", "V2", "Flash", "2026-09-10")
        at = self._run()
        at = self._tab(at, "📊 Progress")
        tables = [tuple(str(c) for c in df.value.columns) for df in at.dataframe]
        self.assertIn(("Grade", "Sends"), tables)                 # volume pyramid
        self.assertIn(("Send style", "Sends"), tables)            # style breakdown
        self.assertIn(
            ("Date", "Discipline", "Grade", "Status", "Difficulty rank"), tables
        )                                                         # grade progression

    def test_climb_editor_offers_only_sends_and_handles_future_dates(self):
        self._run()  # creates the dev profile
        profile_manager.log_climb(USER, "Boulder", "V3", "Sent", "2099-01-01")
        climb_id = profile_manager.get_climbs(USER)[0]["id"]
        at = self._run()  # a stored future date must not crash the date picker
        at = self._tab(at, "📊 Progress")
        self.assertEqual(at.selectbox(key=f"edit_status_{climb_id}").options, SENT_STATUSES)


if __name__ == "__main__":
    unittest.main()
