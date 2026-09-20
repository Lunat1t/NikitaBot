#!/usr/bin/env python3
"""Unit tests for ContentWatcherAgent and NikitaDatabase."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from agent.watcher import ContentWatcherAgent
from scraper.models import ScrapedReel, ScraperResult
from storage.database import NikitaDatabase


class TestNikitaDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_nikitabot.db")
        self.db = NikitaDatabase(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_save_and_deduplicate_reel(self):
        reel_data = {
            "shortcode": "TEST_REEL_001",
            "url": "https://instagram.com/reel/TEST_REEL_001/",
            "author": "@startup_daily",
            "caption": "Testing reel watcher #ai #growth",
            "timestamp": "2026-09-20T12:00:00Z",
            "duration_seconds": 45.2,
            "views_count": 54000,
            "likes_count": 3200,
            "tags": ["ai", "growth"]
        }

        # First save should succeed
        inserted = self.db.save_watched_reel(reel_data)
        self.assertTrue(inserted)
        self.assertTrue(self.db.is_reel_watched("TEST_REEL_001"))

        # Second save with same shortcode must be deduplicated (return False)
        inserted_again = self.db.save_watched_reel(reel_data)
        self.assertFalse(inserted_again)

        # Verify retrieval
        reels = self.db.get_watched_reels(limit=10)
        self.assertEqual(len(reels), 1)
        self.assertEqual(reels[0]["shortcode"], "TEST_REEL_001")
        self.assertEqual(reels[0]["views_count"], 54000)
        self.assertEqual(reels[0]["tags"], ["ai", "growth"])

    def test_agent_logs(self):
        self.db.add_log("TEST_EVENT", "Agent initiated test", {"step": 1})
        logs = self.db.get_recent_logs(limit=5)
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]["event_type"], "TEST_EVENT")
        self.assertIn("Agent initiated test", logs[0]["message"])


class TestContentWatcherAgent(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_nikitabot.db")
        self.db = NikitaDatabase(self.db_path)
        self.mock_scraper = MagicMock()
        self.agent = ContentWatcherAgent(db=self.db, scraper=self.mock_scraper)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_watch_profile_flow(self):
        # Mock scraper returns 2 reels
        mock_reels = [
            ScrapedReel(
                shortcode="REEL_A",
                url="https://instagram.com/reel/REEL_A/",
                author="@techguru",
                caption="First reel #tech",
                timestamp="2026-09-20T10:00:00Z",
                views_count=10000,
                duration_seconds=30.0,
                tags=["tech"]
            ),
            ScrapedReel(
                shortcode="REEL_B",
                url="https://instagram.com/reel/REEL_B/",
                author="@techguru",
                caption="Second reel #ai",
                timestamp="2026-09-20T11:00:00Z",
                views_count=20000,
                duration_seconds=45.0,
                tags=["ai"]
            )
        ]
        self.mock_scraper.fetch_profile_reels.return_value = ScraperResult(
            status="success",
            target_username="techguru",
            reels=mock_reels
        )

        # First watch cycle: both reels should be new
        summary1 = self.agent.watch_profile("techguru", limit=10)
        self.assertEqual(summary1["status"], "success")
        self.assertEqual(summary1["new_watched"], 2)
        self.assertEqual(summary1["previously_seen"], 0)

        # Second watch cycle: both reels should be skipped as previously seen!
        summary2 = self.agent.watch_profile("techguru", limit=10)
        self.assertEqual(summary2["status"], "success")
        self.assertEqual(summary2["new_watched"], 0)
        self.assertEqual(summary2["previously_seen"], 2)


if __name__ == "__main__":
    unittest.main()
