"""Automated unit test suite for HarnessSync core logic (unittest compatible)."""

import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from grades import grade_rank, YDS_GRADES
import db_store
import profile_manager
import feedback_manager
import leaderboard_engine

TODAY = "2026-09-25"


class TestHarnessSync(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_harness.db")
        db_store.configure(f"sqlite:///{self.db_path}")

    def tearDown(self):
        db_store.get_engine().dispose()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _user(self, user_id, name=None, show=True):
        profile_manager.save_profile(user_id, name or user_id, show)
        return user_id

    def test_grade_rank(self):
        self.assertEqual(grade_rank("Boulder", "VB"), 0)
        self.assertEqual(grade_rank("Boulder", "V0"), 1)
        self.assertEqual(grade_rank("Boulder", "V17"), 18)
        self.assertEqual(grade_rank("Boulder", "V99"), -1)

        self.assertEqual(grade_rank("Rope", "5.0"), 0)
        self.assertEqual(grade_rank("Rope", "5.15d"), len(YDS_GRADES) - 1)
        self.assertEqual(grade_rank("Rope", "NonExistent"), -1)

    def test_climb_crud_operations(self):
        user = self._user("alice@example.com", "Alice")

        # 1. Log climb & check PR alert
        alerts1 = profile_manager.log_climb(user, "Boulder", "V3", "Sent", TODAY, route_name="The Slab")
        self.assertEqual(len(alerts1), 1)
        self.assertIn("New Boulder personal best: V3", alerts1[0])

        # 2. Log easier climb - no PR alert
        alerts2 = profile_manager.log_climb(user, "Boulder", "V1", "Sent", TODAY, route_name="Warmup")
        self.assertEqual(len(alerts2), 0)

        # 3. Fetch climbs
        climbs = profile_manager.get_climbs(user)
        self.assertEqual(len(climbs), 2)
        self.assertEqual(profile_manager.best_climb(user, "Boulder")["grade"], "V3")

        # 4. Update climb
        climb_to_edit = climbs[0]
        profile_manager.update_climb(
            user, climb_to_edit["id"], "Boulder", "V4", "Flash", TODAY,
            route_name="The Slab Updated", location="Main Gym",
        )
        edited = next(c for c in profile_manager.get_climbs(user) if c["id"] == climb_to_edit["id"])
        self.assertEqual(edited["grade"], "V4")
        self.assertEqual(edited["status"], "Flash")
        self.assertEqual(edited["route_name"], "The Slab Updated")

        # 5. Delete climb
        profile_manager.delete_climb(user, climb_to_edit["id"])
        self.assertEqual(len(profile_manager.get_climbs(user)), 1)

    def test_empty_user_sees_nothing(self):
        user = self._user("alice@example.com")
        profile_manager.log_climb(user, "Boulder", "V3", "Sent", TODAY)
        profile_manager.log_project(user, "Boulder", "V6", TODAY)
        self.assertEqual(profile_manager.get_climbs(""), [])
        self.assertEqual(profile_manager.get_climbs(None), [])
        self.assertEqual(profile_manager.get_projects(""), [])

    def test_users_cannot_touch_each_others_data(self):
        alice = self._user("alice@example.com")
        mallory = self._user("mallory@example.com")
        profile_manager.log_climb(alice, "Boulder", "V3", "Sent", TODAY)
        profile_manager.log_project(alice, "Boulder", "V6", TODAY)
        climb_id = profile_manager.get_climbs(alice)[0]["id"]
        project_id = profile_manager.get_projects(alice)[0]["id"]

        self.assertEqual(profile_manager.get_climbs(mallory), [])
        profile_manager.update_climb(mallory, climb_id, "Boulder", "V17", "Sent", TODAY)
        profile_manager.delete_climb(mallory, climb_id)
        profile_manager.delete_project(mallory, project_id)
        self.assertEqual(profile_manager.graduate_project(mallory, project_id, TODAY), [])

        self.assertEqual(profile_manager.get_climbs(alice)[0]["grade"], "V3")
        self.assertEqual(len(profile_manager.get_projects(alice)), 1)
        self.assertEqual(profile_manager.get_climbs(mallory), [])

    def test_non_sends_do_not_count_as_best(self):
        user = self._user("alice@example.com")
        profile_manager.log_climb(user, "Boulder", "V2", "Sent", TODAY)
        alerts = profile_manager.log_climb(user, "Boulder", "V9", "Attempt", TODAY)
        self.assertEqual(alerts, [])
        self.assertEqual(profile_manager.best_climb(user, "Boulder")["grade"], "V2")

    def test_leaderboard_engine(self):
        a = self._user("a@example.com", "ClimberA")
        b = self._user("b@example.com", "ClimberB")
        c = self._user("c@example.com", "ClimberC")
        hidden = self._user("h@example.com", "Hidden", show=False)
        profile_manager.log_climb(a, "Rope", "5.10a", "Sent", TODAY)
        profile_manager.log_climb(b, "Rope", "5.12a", "Flash", TODAY)
        profile_manager.log_climb(a, "Rope", "5.11a", "Redpoint", TODAY)
        profile_manager.log_climb(c, "Rope", "5.11b", "Onsight", TODAY)
        profile_manager.log_climb(c, "Rope", "5.14a", "Attempt", TODAY)  # not a send
        profile_manager.log_climb(hidden, "Rope", "5.15a", "Sent", TODAY)

        lb_df = leaderboard_engine.compile_leaderboard("Rope")
        self.assertEqual(list(lb_df["Climber"]), ["ClimberB", "ClimberC", "ClimberA"])
        self.assertEqual(list(lb_df["Best Grade"]), ["5.12a", "5.11b", "5.11a"])
        self.assertEqual(list(lb_df["Sends"]), [1, 1, 2])
        self.assertNotIn("email", " ".join(lb_df.columns).lower())

    def test_display_names_are_unique(self):
        self._user("a@example.com", "Alex")
        self.assertTrue(profile_manager.display_name_taken("  alex "))
        self.assertFalse(profile_manager.display_name_taken("Alex", exclude_user_id="a@example.com"))

    def test_delete_account_removes_everything(self):
        user = self._user("alice@example.com")
        profile_manager.log_climb(user, "Boulder", "V3", "Sent", TODAY)
        profile_manager.log_project(user, "Boulder", "V6", TODAY)
        feedback_manager.submit_feedback(user, "alice", "Bug", 3, "hi")
        profile_manager.delete_account(user)
        self.assertIsNone(profile_manager.get_profile(user))
        self.assertEqual(profile_manager.get_climbs(user), [])
        self.assertEqual(profile_manager.get_projects(user), [])
        self.assertEqual(feedback_manager.load_feedback(), [])

    def test_feedback_manager(self):
        entry = feedback_manager.submit_feedback("bob@example.com", "Bob", "Feature Idea", 5, "Add route tags!")
        self.assertEqual(entry["display_name"], "Bob")
        all_fb = feedback_manager.load_feedback()
        self.assertEqual(len(all_fb), 1)
        self.assertEqual(all_fb[0]["message"], "Add route tags!")

    def test_feedback_rate_limit(self):
        user = "bob@example.com"
        now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
        self.assertIsNone(feedback_manager.feedback_block_reason(user, now))
        feedback_manager.submit_feedback(user, "Bob", "Bug", 3, "one", now=now)
        self.assertIsNotNone(feedback_manager.feedback_block_reason(user, now + timedelta(seconds=30)))
        self.assertIsNone(feedback_manager.feedback_block_reason(user, now + timedelta(minutes=5)))

        for i in range(1, feedback_manager.DAILY_LIMIT):
            feedback_manager.submit_feedback(user, "Bob", "Bug", 3, "more", now=now + timedelta(minutes=5 * i))
        later = now + timedelta(hours=2)
        self.assertIn("tomorrow", feedback_manager.feedback_block_reason(user, later))
        self.assertIsNone(feedback_manager.feedback_block_reason(user, now + timedelta(days=1, hours=1)))

    def test_projects_crud(self):
        user = self._user("dave@example.com")
        profile_manager.log_project(
            user, "Boulder", "V6", TODAY, route_name="The Overhang Crux", location="Gym",
            angle="Overhang", attempts=3, notes="Need high heel hook",
        )
        projs = profile_manager.get_projects(user)
        self.assertEqual(len(projs), 1)
        self.assertEqual(projs[0]["route_name"], "The Overhang Crux")
        self.assertEqual(projs[0]["attempts"], 3)

        # Logging another attempt on the same route bumps it instead of duplicating
        self.assertEqual(profile_manager.log_project(user, "Boulder", "V6", TODAY, route_name="the overhang crux"), "bumped")
        profile_manager.add_project_attempt(user, projs[0]["id"])
        projs = profile_manager.get_projects(user)
        self.assertEqual(len(projs), 1)
        self.assertEqual(projs[0]["attempts"], 5)

        # Graduate project to send
        profile_manager.graduate_project(user, projs[0]["id"], TODAY, send_status="Redpoint")
        self.assertEqual(len(profile_manager.get_projects(user)), 0)
        climbs = profile_manager.get_climbs(user)
        self.assertEqual(len(climbs), 1)
        self.assertEqual(climbs[0]["grade"], "V6")
        self.assertEqual(climbs[0]["status"], "Redpoint")

    def test_text_is_trimmed_and_capped(self):
        user = self._user("alice@example.com")
        profile_manager.log_climb(user, "Boulder", "V1", "Sent", TODAY, route_name="  a   b  " + "x" * 500)
        route = profile_manager.get_climbs(user)[0]["route_name"]
        self.assertTrue(route.startswith("a b x"))
        self.assertEqual(len(route), profile_manager.ROUTE_MAX)

    def test_legacy_tables_are_set_aside(self):
        legacy_path = os.path.join(self.test_dir, "legacy.db")
        conn = sqlite3.connect(legacy_path)
        conn.execute("CREATE TABLE climbs (id INTEGER PRIMARY KEY, climber_name TEXT, grade TEXT)")
        conn.execute("INSERT INTO climbs (climber_name, grade) VALUES ('Guest', 'V0')")
        conn.commit()
        conn.close()

        db_store.configure(f"sqlite:///{legacy_path}")
        user = self._user("alice@example.com")
        profile_manager.log_climb(user, "Boulder", "V3", "Sent", TODAY)
        self.assertEqual(len(profile_manager.get_climbs(user)), 1)

        conn = sqlite3.connect(legacy_path)
        self.assertEqual(conn.execute("SELECT grade FROM climbs_legacy").fetchall(), [("V0",)])
        conn.close()


if __name__ == "__main__":
    unittest.main()
