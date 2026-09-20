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

    def test_06_reels_dataset_schema_normalization(self):
        raw_reels_item = {
            "url": "https://www.instagram.com/reel/DNpnMNTR7aM/",
            "user_posted": "nato.humor",
            "description": "챌린지 라인업이 너무 짱짱한거 아닌가요? #앳하트 #AtHeart",
            "hashtags": ["#앳하트", "#AtHeart", "#신인"],
            "num_comments": 0,
            "date_posted": "2025-08-22T08:14:20.000Z",
            "likes": 117,
            "views": 57005,
            "video_play_count": 57005,
            "post_id": "3704664531218708108",
            "thumbnail": "https://scontent-lax7-1.cdninstagram.com/thumb.jpg",
            "shortcode": "DNpnMNTR7aM",
            "product_type": "clips",
            "length": "14.066667",
            "video_url": "https://scontent-lax7-1.cdninstagram.com/o1/v/t2/video.mp4"
        }
        scraper = BrightDataInstagramScraper()
        reels = scraper._normalize_items([raw_reels_item], "test_user")
        self.assertEqual(len(reels), 1)
        r = reels[0]
        self.assertEqual(r.shortcode, "DNpnMNTR7aM")
        self.assertEqual(r.author, "@nato.humor")
        self.assertEqual(r.views_count, 57005)
        self.assertEqual(r.likes_count, 117)
        self.assertAlmostEqual(r.duration_seconds, 14.066667)
        self.assertEqual(r.tags, ["앳하特".replace("特", "트"), "AtHeart", "신인"])
        self.assertTrue(r.is_video)
        self.assertEqual(r.video_url, "https://scontent-lax7-1.cdninstagram.com/o1/v/t2/video.mp4")


if __name__ == "__main__":
    unittest.main()
