"""Automated unit test suite for HarnessSync core logic (unittest compatible)."""

import os
import shutil
import tempfile
import unittest

from grades import grade_rank, V_GRADES, YDS_GRADES
import db_store
import profile_manager
import feedback_manager
import leaderboard_engine


class TestHarnessSync(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_db = os.path.join(self.test_dir, "test_harness.db")
        db_store.DB_PATH = self.test_db
        db_store.PROFILES_DIR = self.test_dir
        db_store.init_db()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_grade_rank(self):
        self.assertEqual(grade_rank("Boulder", "VB"), 0)
        self.assertEqual(grade_rank("Boulder", "V0"), 1)
        self.assertEqual(grade_rank("Boulder", "V17"), 18)
        self.assertEqual(grade_rank("Boulder", "V99"), -1)

        self.assertEqual(grade_rank("Rope", "5.0"), 0)
        self.assertEqual(grade_rank("Rope", "5.15d"), len(YDS_GRADES) - 1)
        self.assertEqual(grade_rank("Rope", "NonExistent"), -1)

    def test_climb_crud_operations(self):
        user = "TesterAlice"

        # 1. Log climb & check PR alert
        alerts1 = profile_manager.log_climb(user, "Boulder", "V3", "Sent", route_name="The Slab")
        self.assertEqual(len(alerts1), 1)
        self.assertIn("New Boulder personal best: V3", alerts1[0])

        # 2. Log easier climb - no PR alert
        alerts2 = profile_manager.log_climb(user, "Boulder", "V1", "Sent", route_name="Warmup")
        self.assertEqual(len(alerts2), 0)

        # 3. Fetch climbs
        climbs = profile_manager.get_climbs(user)
        self.assertEqual(len(climbs), 2)
        best = profile_manager.best_climb(user, "Boulder")
        self.assertEqual(best["grade"], "V3")

        # 4. Update climb
        climb_to_edit = climbs[0]
        profile_manager.update_climb(
            climb_to_edit["id"], "Boulder", "V4", "Flash", route_name="The Slab Updated", location="Main Gym"
        )
        updated_climbs = profile_manager.get_climbs(user)
        edited = next(c for c in updated_climbs if c["id"] == climb_to_edit["id"])
        self.assertEqual(edited["grade"], "V4")
        self.assertEqual(edited["status"], "Flash")
        self.assertEqual(edited["route_name"], "The Slab Updated")

        # 5. Delete climb
        profile_manager.delete_climb(climb_to_edit["id"])
        remaining = profile_manager.get_climbs(user)
        self.assertEqual(len(remaining), 1)

    def test_leaderboard_engine(self):
        profile_manager.log_climb("ClimberA", "Rope", "5.10a", "Sent")
        profile_manager.log_climb("ClimberB", "Rope", "5.12a", "Flash")
        profile_manager.log_climb("ClimberA", "Rope", "5.11a", "Redpoint")

        lb_df = leaderboard_engine.compile_leaderboard("Rope")
        self.assertFalse(lb_df.empty)
        self.assertEqual(list(lb_df["Climber"]), ["ClimberB", "ClimberA"])
        self.assertEqual(list(lb_df["Best Grade"]), ["5.12a", "5.11a"])

    def test_feedback_manager(self):
        entry = feedback_manager.submit_feedback("Bob", "Feature Idea", 5, "Add route tags!")
        self.assertEqual(entry["climber_name"], "Bob")

        all_fb = feedback_manager.load_feedback()
        self.assertEqual(len(all_fb), 1)
        self.assertEqual(all_fb[0]["message"], "Add route tags!")

    def test_projects_crud(self):
        user = "ProjectorDave"
        profile_manager.log_project(
            user, "Boulder", "V6", route_name="The Overhang Crux", location="Gym", angle="Overhang", attempts=3, notes="Need high heel hook"
        )
        projs = profile_manager.get_projects(user)
        self.assertEqual(len(projs), 1)
        self.assertEqual(projs[0]["route_name"], "The Overhang Crux")
        self.assertEqual(projs[0]["attempts"], 3)

        # Graduate project to send
        alerts = profile_manager.graduate_project(projs[0]["id"], send_status="Redpoint")
        self.assertEqual(len(profile_manager.get_projects(user)), 0)
        climbs = profile_manager.get_climbs(user)
        self.assertEqual(len(climbs), 1)
        self.assertEqual(climbs[0]["grade"], "V6")
        self.assertEqual(climbs[0]["status"], "Redpoint")


if __name__ == "__main__":
    unittest.main()
