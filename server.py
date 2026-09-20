#!/usr/bin/env python3
"""Local development server for NikitaBot AI Reels Agent Dashboard.

Standard library only: http.server, socketserver, json, sys, os, argparse.
Serves web UI, handles /api/health, /api/profiles, /api/reels, /api/logs.
"""
import argparse
from http import HTTPStatus
import http.server
import json
import os
import socketserver
import sys
from urllib.parse import parse_qs, urlparse

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from storage.database import NikitaDatabase

DEFAULT_PORT = 8080
WEB_DIR = os.path.join(ROOT_DIR, "web")
CONFIG_TARGETS_PATH = os.path.join(ROOT_DIR, "config", "targets.json")

# Shared database instance
db = NikitaDatabase()


class NikitaBotHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Health check endpoint
        if path in ("/api/health", "/health"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            response = {
                "status": "ok",
                "service": "nikitabot-reels-agent",
                "version": "1.0.0",
                "mode": "autonomous-watcher",
                "database": "sqlite3",
                "scrapers": {
                    "instagram": "ready (Instaloader + yt-dlp)",
                    "whisper": "ready"
                }
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode("utf-8"))
            return

        # Target profiles API
        if path == "/api/profiles":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            targets = []
            if os.path.exists(CONFIG_TARGETS_PATH):
                with open(CONFIG_TARGETS_PATH, "r", encoding="utf-8") as f:
                    try:
                        targets = json.load(f)
                    except Exception:
                        targets = []
            self.wfile.write(json.dumps(targets, ensure_ascii=False).encode("utf-8"))
            return

        # Live Watched Reels API
        if path == "/api/reels":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            reels = db.get_watched_reels(limit=50)
            self.wfile.write(json.dumps(reels, ensure_ascii=False).encode("utf-8"))
            return

        # Live Agent Logs API
        if path == "/api/logs":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            logs = db.get_recent_logs(limit=30)
            self.wfile.write(json.dumps(logs, ensure_ascii=False).encode("utf-8"))
            return

        # Fallback to index.html for root
        if path in ("", "/"):
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/profiles":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                new_target = json.loads(body)
                targets = []
                if os.path.exists(CONFIG_TARGETS_PATH):
                    with open(CONFIG_TARGETS_PATH, "r", encoding="utf-8") as f:
                        targets = json.load(f)
                targets.insert(0, new_target)
                with open(CONFIG_TARGETS_PATH, "w", encoding="utf-8") as f:
                    json.dump(targets, f, ensure_ascii=False, indent=2)

                db.add_log("PROFILE_ADDED", f"Added target @{new_target.get('username')}", new_target)

                self.send_response(HTTPStatus.CREATED)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "created", "target": new_target}).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()


def run_server(port: int = DEFAULT_PORT):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), NikitaBotHTTPRequestHandler) as httpd:
        print(f"============================================================")
        print(f"  🎬 NikitaBot AI Reels Dashboard running at http://localhost:{port}")
        print(f"  Serving web UI from: {WEB_DIR}")
        print(f"  Health check API:    http://localhost:{port}/api/health")
        print(f"  Watched Reels API:   http://localhost:{port}/api/reels")
        print(f"  Agent Logs API:      http://localhost:{port}/api/logs")
        print(f"  Press Ctrl+C to stop dev server")
        print(f"============================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dev server...")
            httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NikitaBot Dev Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind (default: 8080)")
    args = parser.parse_args()
    run_server(args.port)
