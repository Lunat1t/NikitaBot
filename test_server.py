#!/usr/bin/env python3
"""Deterministic Moon verification test suite for NikitaBot dev server."""
import json
import os
import socketserver
import threading
import time
import unittest
import urllib.request
import urllib.error

from server import NikitaBotHTTPRequestHandler

TEST_PORT = 8094


class TestNikitaBotServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("127.0.0.1", TEST_PORT), NikitaBotHTTPRequestHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_01_index_html_served(self):
        url = f"http://127.0.0.1:{TEST_PORT}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            self.assertIn("AI REELS AGENT", body)
            self.assertIn("NikitaBot", body)
            self.assertIn("Sales & Marketing", body)

    def test_02_styles_css_served(self):
        url = f"http://127.0.0.1:{TEST_PORT}/styles.css"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            self.assertIn("--cyan-accent", body)
            self.assertIn(".reel-card", body)

    def test_03_app_js_served(self):
        url = f"http://127.0.0.1:{TEST_PORT}/app.js"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            self.assertIn("NikitaBot AI Reels Agent", body)

    def test_04_health_api(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Content-Type"), "application/json; charset=utf-8")
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("service"), "nikitabot-reels-agent")

    def test_05_profiles_api(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/profiles"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIsInstance(data, list)
            self.assertGreaterEqual(len(data), 1)
            # Check enriched stats
            first = data[0]
            self.assertIn("stats", first)

    def test_06_profile_audit_api(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/profiles/sentimentalka_smm/audit"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            audit = json.loads(resp.read().decode("utf-8"))
            self.assertIn("strengths", audit)
            self.assertIn("weaknesses", audit)
            self.assertIn("sales_pitch", audit)

    def test_07_delete_reel_api(self):
        from server import db
        test_sc = "test_del_shortcode_99"
        db.save_watched_reel({
            "shortcode": test_sc,
            "author": "@test_user",
            "url": f"https://instagram.com/reel/{test_sc}",
            "caption": "Reel to delete via API"
        })
        self.assertTrue(db.is_reel_watched(test_sc))

        url = f"http://127.0.0.1:{TEST_PORT}/api/reels/{test_sc}"
        req = urllib.request.Request(url, method="DELETE")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "deleted")
            self.assertEqual(data.get("shortcode"), test_sc)

        self.assertFalse(db.is_reel_watched(test_sc))

    def test_08_video_stream_and_range_api(self):
        # Create a self-contained sample video file to test streaming & HTTP 206 Range headers
        from server import VIDEOS_DIR
        sample_path = os.path.join(VIDEOS_DIR, "test_range_sample.mp4")
        with open(sample_path, "wb") as f:
            f.write(b"SAMPLE_H264_MP4_HEADER_DATA_1234567890_TEST_STREAMING_BYTES")

        try:
            url = f"http://127.0.0.1:{TEST_PORT}/videos/test_range_sample.mp4"
            req = urllib.request.Request(url, headers={"Range": "bytes=0-15"})
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 206)
                self.assertEqual(resp.headers.get("Content-Type"), "video/mp4")
                self.assertEqual(resp.headers.get("Accept-Ranges"), "bytes")
                chunk = resp.read()
                self.assertEqual(len(chunk), 16)
        finally:
            if os.path.exists(sample_path):
                os.remove(sample_path)


if __name__ == "__main__":
    unittest.main()
