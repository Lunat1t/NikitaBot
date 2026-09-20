#!/usr/bin/env python3
"""Deterministic Moon verification test suite for NikitaBot dev server."""
import json
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
            self.assertIn("Scanned Instagram Reels", body)

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
            self.assertIn("triggerAgentSimulation", body)

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


if __name__ == "__main__":
    unittest.main()
