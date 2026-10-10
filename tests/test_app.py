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

    def _run(self, at=None):
        if at is None:
            at = AppTest.from_file(APP_PATH, default_timeout=30)
            # Blank out a local .streamlit/secrets.toml so the run is the same
            # on a dev machine as in CI: dev mode, no Google sign-in, no email.
            at.secrets["auth"] = {}
            at.secrets["email"] = {}
        at.run()
        self.assertEqual([e.value for e in at.exception], [])
        return at

    def _button(self, at, label):
        return next(b for b in at.button if b.label == label)

    def test_page_renders(self):
        at = self._run()
        self.assertEqual(
            [t.label for t in at.tabs][:7],
            ["🧗 Log a climb", "📊 Progress", "🎯 Projects", "🏆 Leaderboard", "📱 Phone App", "💬 Feedback", "📖 Guide & Reference"],
        )

    def test_log_climb_from_main_flow(self):
        at = self._run()
        self._button(at, "Save climb").click()
        at = self._run(at)
        self.assertEqual(len(profile_manager.get_climbs(USER)), 1)
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
        self.assertEqual(len(at.get("vega_lite_chart")), 3)  # pyramid, send styles, progression
        self.assertIn("🎉 SENT IT! (Graduate)", [b.label for b in at.button])

    def test_unhandled_error_is_emailed_and_still_surfaced(self):
        """A crash in production should reach the developer, without changing
        what Streamlit shows and logs."""
        sent = []
        with mock.patch("harnesssync.notifications.send_email",
                        side_effect=lambda **kw: sent.append(kw) or True), \
             mock.patch("harnesssync.ui.guide.render", side_effect=RuntimeError("boom")):
            at = AppTest.from_file(APP_PATH, default_timeout=30)
            at.secrets["auth"] = {}
            at.secrets["email"] = {}
            at.run()

        self.assertTrue(any("boom" in (call.get("body") or "") for call in sent),
                        f"traceback was not emailed; calls: {sent}")
        # Still raised, so Streamlit reports it rather than swallowing it
        self.assertTrue([e.value for e in at.exception])

    def test_charts_have_table_text_alternatives(self):
        """Altair renders to canvas, which assistive tech can't read. Every chart
        needs the same numbers available as a table, so don't let those drop out."""
        self._run()  # creates the dev profile
        profile_manager.log_climb(USER, "Boulder", "V3", "Sent", "2026-09-01")
        profile_manager.log_climb(USER, "Boulder", "V2", "Flash", "2026-09-10")
        at = self._run()
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
        self.assertEqual(at.selectbox(key=f"edit_status_{climb_id}").options, SENT_STATUSES)


if __name__ == "__main__":
    unittest.main()
