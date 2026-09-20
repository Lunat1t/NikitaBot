"""Unit tests for ProfileAuditor (Sales & Marketing Content Audit)."""
import unittest

from ai_analyzer.profile_auditor import ProfileAuditor


class TestProfileAuditor(unittest.TestCase):
    """Tests for Profile Content Auditor."""

    def setUp(self):
        self.auditor = ProfileAuditor(api_key=None)  # test heuristic engine

    def test_01_audit_heuristic(self):
        sample_reels = [
            {
                "shortcode": "reel_1",
                "views_count": 15000,
                "likes_count": 800,
                "hook_score": 8.5,
                "hook_type": "Curiosity Gap",
                "transcript": "3 причины почему ваш бизнес не растет",
                "caption": "Полезный пост про маркетинг"
            },
            {
                "shortcode": "reel_2",
                "views_count": 45000,
                "likes_count": 2200,
                "hook_score": 9.0,
                "hook_type": "Visual Shock",
                "transcript": "Смотри как запустить рекламу",
                "caption": "Лайфхак"
            }
        ]

        res = self.auditor.audit_profile("sentimentalka_smm", sample_reels, category="Marketing & SMM")
        self.assertEqual(res["username"], "sentimentalka_smm")
        self.assertIn("lead_score", res)
        self.assertGreaterEqual(res["lead_score"], 50)
        self.assertGreaterEqual(len(res["strengths"]), 3)
        self.assertGreaterEqual(len(res["weaknesses"]), 3)
        self.assertGreaterEqual(len(res["growth_points"]), 3)
        self.assertTrue(len(res["sales_pitch"]) > 50)
        self.assertIn("sentimentalka_smm", res["sales_pitch"])
        self.assertEqual(res["engine"], "heuristic-marketer")


if __name__ == "__main__":
    unittest.main()
