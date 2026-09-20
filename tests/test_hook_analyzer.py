"""Unit tests for HookAnalyzer."""
import unittest

from ai_analyzer.hook_analyzer import HookAnalyzer


class TestHookAnalyzer(unittest.TestCase):
    """Tests for Hook and virality analysis engine."""

    def setUp(self):
        self.analyzer = HookAnalyzer(api_key=None)  # tests heuristic engine

    def test_01_heuristic_with_curiosity_trigger(self):
        res = self.analyzer.analyze(
            frame_paths=["/tmp/f1.jpg", "/tmp/f2.jpg", "/tmp/f3.jpg"],
            transcript="Почему 99% людей никогда не узнают этот секрет?",
            caption="Шок контент про искусственный интеллект",
            tags=["ai", "tech"],
            likes=12000,
            comments=450
        )
        self.assertIn("hook_score", res)
        self.assertIn("virality_score", res)
        self.assertIn("hook_type", res)
        self.assertIn("summary", res)
        self.assertGreaterEqual(res["hook_score"], 8.0)
        self.assertGreaterEqual(res["virality_score"], 80)
        self.assertEqual(res["engine"], "heuristic-fallback")

    def test_02_heuristic_baseline(self):
        res = self.analyzer.analyze(
            frame_paths=[],
            transcript="",
            caption="Обычный день в парке",
            tags=["nature"],
            likes=10,
            comments=2
        )
        self.assertIn("hook_score", res)
        self.assertLessEqual(res["hook_score"], 7.0)
        self.assertEqual(res["retention_prediction"], "Low")


if __name__ == "__main__":
    unittest.main()
