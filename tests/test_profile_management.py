"""Unit tests for profile database operations and server profile management."""
import json
import os
import tempfile
import unittest
from urllib.request import Request, urlopen

from storage.database import NikitaDatabase
from server import run_server


class TestProfileDatabaseOps(unittest.TestCase):
    """Tests for Profile DB operations (stats, audit, deletion)."""

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db = NikitaDatabase(db_path=self.temp_db_file.name)

    def tearDown(self):
        if os.path.exists(self.temp_db_file.name):
            os.remove(self.temp_db_file.name)

    def test_01_save_and_get_audit(self):
        audit_data = {
            "lead_score": 85,
            "strengths": ["Плюс 1", "Плюс 2", "Плюс 3"],
            "weaknesses": ["Минус 1", "Минус 2"],
            "growth_points": ["Рост 1", "Рост 2"],
            "sales_pitch": "Привет, мы сделаем вам лучшие рилсы!"
        }
        self.db.save_profile_audit("test_client", audit_data)
        loaded = self.db.get_profile_audit("test_client")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["lead_score"], 85)
        self.assertEqual(len(loaded["strengths"]), 3)
        self.assertEqual(len(loaded["weaknesses"]), 2)
        self.assertIn("Привет", loaded["sales_pitch"])

    def test_02_profile_stats_calculation(self):
        # Save two reels for creator
        reel_1 = {
            "shortcode": "r1",
            "author": "@creator_x",
            "url": "https://instagram.com/reel/r1",
            "caption": "Reel 1",
            "views_count": 10000,
            "likes_count": 500,
            "duration_seconds": 25.0
        }
        reel_2 = {
            "shortcode": "r2",
            "author": "@creator_x",
            "url": "https://instagram.com/reel/r2",
            "caption": "Reel 2",
            "views_count": 20000,
            "likes_count": 1500,
            "duration_seconds": 35.0
        }
        self.db.save_watched_reel(reel_1, analysis_data={"hook_score": 8.0, "virality_score": 80})
        self.db.save_watched_reel(reel_2, analysis_data={"hook_score": 9.0, "virality_score": 90})

        stats = self.db.get_profile_stats("creator_x")
        self.assertEqual(stats["total_reels"], 2)
        self.assertEqual(stats["total_views"], 30000)
        self.assertEqual(stats["total_likes"], 2000)
        self.assertEqual(stats["avg_hook_score"], 8.5)
        self.assertEqual(stats["avg_virality"], 85)

    def test_03_delete_profile(self):
        audit_data = {"lead_score": 70, "strengths": [], "weaknesses": [], "growth_points": [], "sales_pitch": ""}
        self.db.save_profile_audit("to_delete", audit_data)
        self.assertIsNotNone(self.db.get_profile_audit("to_delete"))

        res = self.db.delete_profile("to_delete")
        self.assertTrue(res)
        self.assertIsNone(self.db.get_profile_audit("to_delete"))


if __name__ == "__main__":
    unittest.main()
