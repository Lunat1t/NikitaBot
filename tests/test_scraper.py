#!/usr/bin/env python3
"""Unit tests for the free Instagram scraper module."""
import unittest
from unittest.mock import MagicMock, patch

from scraper.models import ScrapedReel, ScraperResult
from scraper.session_manager import SessionManager
from scraper.instagram import InstagramScraper, extract_username


class TestExtractUsername(unittest.TestCase):
    def test_extract_from_various_inputs(self):
        url1 = "https://www.instagram.com/sentimentalka_smm?utm_source=ig_web_button_share_sheet&stkn=ZDNlZDc0MzIxNw=="
        self.assertEqual(extract_username(url1), "sentimentalka_smm")

        url2 = "https://instagram.com/sentimentalka_smm/"
        self.assertEqual(extract_username(url2), "sentimentalka_smm")

        handle1 = "@sentimentalka_smm"
        self.assertEqual(extract_username(handle1), "sentimentalka_smm")

        raw = "sentimentalka_smm"
        self.assertEqual(extract_username(raw), "sentimentalka_smm")


class TestScraperModels(unittest.TestCase):
    def test_scraped_reel_model(self):
        reel = ScrapedReel(
            shortcode="C_abc123",
            url="https://www.instagram.com/reel/C_abc123/",
            author="@testcreator",
            caption="Amazing AI agent #tech #automation",
            timestamp="2026-09-20T12:00:00Z",
            video_url="https://cdn.instagram.com/video.mp4",
            likes_count=1500,
            comments_count=45,
            views_count=25000,
            duration_seconds=32.5,
            is_video=True,
            tags=["tech", "automation"]
        )
        d = reel.to_dict()
        self.assertEqual(d["shortcode"], "C_abc123")
        self.assertEqual(d["views_count"], 25000)
        self.assertIn("tech", d["tags"])
        self.assertTrue(d["is_video"])

    def test_scraper_result_model(self):
        res = ScraperResult(
            status="success",
            target_username="testcreator",
            reels=[
                ScrapedReel(
                    shortcode="s1",
                    url="url1",
                    author="@testcreator",
                    caption="Post 1",
                    timestamp="2026-09-20T12:00:00Z",
                )
            ]
        )
        d = res.to_dict()
        self.assertEqual(d["status"], "success")
        self.assertEqual(d["count"], 1)
        self.assertEqual(len(d["reels"]), 1)


class TestSessionManager(unittest.TestCase):
    def test_random_user_agent(self):
        sm = SessionManager()
        ua = sm.get_random_user_agent()
        self.assertIsInstance(ua, str)
        self.assertTrue("Mozilla" in ua or "Instagram" in ua)

    def test_public_headers(self):
        sm = SessionManager()
        headers = sm.get_public_headers()
        self.assertIn("X-IG-App-ID", headers)
        self.assertIn("User-Agent", headers)
        self.assertEqual(headers["X-IG-App-ID"], "936619743392459")


class TestInstagramScraperMocked(unittest.TestCase):
    def setUp(self):
        self.scraper = InstagramScraper(download_dir="/tmp/nikitabot_test_downloads")

    def test_profile_not_exists(self):
        with patch("instaloader.Profile.from_username") as mock_profile:
            import instaloader
            mock_profile.side_effect = instaloader.exceptions.ProfileNotExistsException("Not found")
            res = self.scraper.fetch_profile_reels("definitely_non_existing_user_9999")
            self.assertEqual(res.status, "error")
            self.assertIn("не найден", res.error_message)

    def test_profile_private(self):
        with patch("instaloader.Profile.from_username") as mock_profile:
            mock_inst = MagicMock()
            mock_inst.is_private = True
            mock_profile.return_value = mock_inst

            res = self.scraper.fetch_profile_reels("private_user")
            self.assertEqual(res.status, "error")
            self.assertIn("приватным", res.error_message)


if __name__ == "__main__":
    unittest.main()
