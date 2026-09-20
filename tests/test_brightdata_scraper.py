"""Unit tests for Bright Data Instagram Dataset Scraper integration."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch
import urllib.request

from scraper.brightdata_scraper import BrightDataInstagramScraper
from scraper.models import ScraperResult


class TestBrightDataInstagramScraper(unittest.TestCase):
    """Test suite for Bright Data dataset scraper wrapper."""

    def test_01_init_without_key(self):
        with patch.dict(os.environ, {"BRIGHTDATA_API_KEY": "", "BRIGHT_DATA_TOKEN": ""}):
            scraper = BrightDataInstagramScraper(api_key=None)
            self.assertFalse(scraper.is_configured())

    def test_02_init_with_key(self):
        scraper = BrightDataInstagramScraper(api_key="bd_token_test_12345")
        self.assertTrue(scraper.is_configured())
        self.assertEqual(scraper.api_key, "bd_token_test_12345")
        self.assertEqual(scraper.dataset_id, "gd_lk5ns7kz21pck8jpis")

    def test_03_fallback_simulation(self):
        with patch.dict(os.environ, {"BRIGHTDATA_API_KEY": "", "BRIGHT_DATA_TOKEN": ""}):
            scraper = BrightDataInstagramScraper(api_key=None)
            res = scraper.scrape_profile_reels("sentimentalka_smm", limit=5)
            self.assertEqual(res.status, "success")
            self.assertEqual(len(res.reels), 5)
            first = res.reels[0]
            self.assertTrue(first.shortcode.startswith("reel_bd_sentimentalka_smm_"))
            self.assertGreater(first.views_count, 0)
            self.assertGreater(first.likes_count, 0)
            self.assertTrue(first.video_url.startswith("/videos/"))

    @patch("urllib.request.urlopen")
    def test_04_mocked_brightdata_api_call(self, mock_urlopen):
        mock_raw_items = [
            {
                "id": "18082481423670855",
                "shortcode": "DbX-A-CgVRb",
                "url": "https://www.instagram.com/reel/DbX-A-CgVRb/",
                "is_video": True,
                "video_url": "https://scontent.cdninstagram.com/v/t2/real_video.mp4",
                "thumbnail": "https://scontent.cdninstagram.com/v/t51/thumb.jpg",
                "views": 4082,
                "likes": 140,
                "comments": 28,
                "video_duration": 19.0,
                "caption": "Астана контентмейкерлер жиналысы #smm #astana #reels",
                "user_posted": "sentimentalka_smm"
            }
        ]

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_raw_items).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        scraper = BrightDataInstagramScraper(api_key="bd_live_key_xyz")
        res = scraper.scrape_profile_reels("sentimentalka_smm", limit=10)

        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.reels), 1)
        reel = res.reels[0]
        self.assertEqual(reel.shortcode, "DbX-A-CgVRb")
        self.assertEqual(reel.video_url, "https://scontent.cdninstagram.com/v/t2/real_video.mp4")
        self.assertEqual(reel.views_count, 4082)
        self.assertEqual(reel.likes_count, 140)
        self.assertEqual(reel.comments_count, 28)
        self.assertEqual(reel.duration_seconds, 19.0)
        self.assertIn("smm", reel.tags)
        self.assertTrue(reel.is_video)

    @patch("urllib.request.urlopen")
    def test_05_snapshot_polling(self, mock_urlopen):
        mock_snapshot_items = [
            {
                "id": "18098161202000412",
                "shortcode": "CxLjopXoP67",
                "url": "https://www.instagram.com/p/CxLjopXoP67/",
                "is_video": False,
                "caption": "Post #photo",
                "likes": 36
            }
        ]

        # First call returns {"snapshot_id": "s_123"}, second call returns the data list
        resp1 = MagicMock()
        resp1.read.return_value = json.dumps({"snapshot_id": "s_123"}).encode("utf-8")
        resp1.__enter__.return_value = resp1

        resp2 = MagicMock()
        resp2.read.return_value = json.dumps(mock_snapshot_items).encode("utf-8")
        resp2.__enter__.return_value = resp2

        mock_urlopen.side_effect = [resp1, resp2]

        scraper = BrightDataInstagramScraper(api_key="bd_key")
        with patch("time.sleep", return_value=None):
            res = scraper.scrape_profile_reels("sentimentalka_smm", limit=10)
            self.assertEqual(res.status, "success")
            self.assertEqual(len(res.reels), 1)
            self.assertEqual(res.reels[0].shortcode, "CxLjopXoP67")


if __name__ == "__main__":
    unittest.main()
