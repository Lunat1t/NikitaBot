"""Unit tests for Apify Instagram Scraper integration."""
import os
import unittest
from unittest.mock import MagicMock, patch

from scraper.apify_scraper import ApifyInstagramScraper
from scraper.models import ScraperResult


class TestApifyInstagramScraper(unittest.TestCase):
    """Test suite for Apify actor wrapper."""

    def test_01_init_without_token(self):
        with patch.dict(os.environ, {"APIFY_TOKEN": "", "APIFY_API_TOKEN": ""}):
            scraper = ApifyInstagramScraper(token=None)
            self.assertFalse(scraper.is_configured())

    def test_02_init_with_token(self):
        scraper = ApifyInstagramScraper(token="apify_api_mock12345")
        self.assertTrue(scraper.is_configured())
        self.assertIsNotNone(scraper.client)

    def test_03_fallback_simulation(self):
        with patch.dict(os.environ, {"APIFY_TOKEN": "", "APIFY_API_TOKEN": ""}):
            scraper = ApifyInstagramScraper(token=None)
            res = scraper.scrape_profile_reels("sentimentalka_smm", limit=5)
            self.assertEqual(res.status, "success")
            self.assertEqual(len(res.reels), 5)
            first = res.reels[0]
            self.assertTrue(first.shortcode.startswith("reel_sentimentalka_smm_"))
            self.assertGreater(first.views_count, 0)
            self.assertGreater(first.likes_count, 0)
            self.assertTrue(first.video_url.startswith("/videos/"))

    def test_04_mocked_apify_client_actor_call(self):
        mock_items = [
            {
                "id": "reel_live_123",
                "shortCode": "Cu987654321",
                "type": "Video",
                "caption": "Тестируем Apify актор #reels #ai",
                "url": "https://www.instagram.com/reel/Cu987654321/",
                "videoUrl": "https://scontent.cdninstagram.com/v/test_video.mp4",
                "displayUrl": "https://scontent.cdninstagram.com/v/test_thumb.jpg",
                "videoDuration": 32.5,
                "videoPlayCount": 45000,
                "likesCount": 2100,
                "commentsCount": 150,
                "timestamp": "2026-09-20T10:00:00Z"
            }
        ]

        scraper = ApifyInstagramScraper(token="apify_api_test_valid")
        
        # Mock client.actor().call() and dataset().iterate_items()
        mock_actor = MagicMock()
        mock_actor.call.return_value = {"defaultDatasetId": "dataset_xyz123"}
        scraper.client.actor = MagicMock(return_value=mock_actor)

        mock_dataset = MagicMock()
        mock_dataset.iterate_items.return_value = mock_items
        scraper.client.dataset = MagicMock(return_value=mock_dataset)

        result = scraper.scrape_profile_reels("sentimentalka_smm", limit=10)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.reels), 1)
        reel = result.reels[0]
        self.assertEqual(reel.shortcode, "Cu987654321")
        self.assertEqual(reel.video_url, "https://scontent.cdninstagram.com/v/test_video.mp4")
        self.assertEqual(reel.views_count, 45000)
        self.assertEqual(reel.likes_count, 2100)
        self.assertEqual(reel.duration_seconds, 32.5)
        self.assertIn("ai", reel.tags)


if __name__ == "__main__":
    unittest.main()
