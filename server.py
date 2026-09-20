#!/usr/bin/env python3
"""Local development server for NikitaBot AI Reels Agent Dashboard.

Standard library only: http.server, socketserver, json, sys, os, argparse.
Serves web UI, handles /api/health, /api/profiles (GET, POST, DELETE),
/api/profiles/<username>/audit, /api/reels, /api/logs,
and serves hook frame thumbnails from /thumbnails/<filename>.
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
from ai_analyzer.profile_auditor import ProfileAuditor

DEFAULT_PORT = 8080
WEB_DIR = os.path.join(ROOT_DIR, "web")
DATA_DIR = os.path.join(ROOT_DIR, "data")
THUMBNAILS_DIR = os.path.join(DATA_DIR, "thumbnails")
CONFIG_TARGETS_PATH = os.path.join(ROOT_DIR, "config", "targets.json")

os.makedirs(THUMBNAILS_DIR, exist_ok=True)

# Shared database and auditor instances
db = NikitaDatabase()
auditor = ProfileAuditor()


class NikitaBotHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Serve hook thumbnails from data/thumbnails/
        if path.startswith("/thumbnails/"):
            filename = os.path.basename(path)
            file_path = os.path.join(THUMBNAILS_DIR, filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_response(HTTPStatus.OK)
                if filename.endswith(".jpg") or filename.endswith(".jpeg"):
                    self.send_header("Content-Type", "image/jpeg")
                elif filename.endswith(".png"):
                    self.send_header("Content-Type", "image/png")
                else:
                    self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(os.path.getsize(file_path)))
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                return

        # Health check endpoint
        if path in ("/api/health", "/health"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            response = {
                "status": "ok",
                "service": "nikitabot-reels-agent",
                "version": "2.0.0",
                "mode": "sales-marketer-assistant",
                "database": "sqlite3",
                "engines": {
                    "scraper": "Instaloader + yt-dlp",
                    "whisper": "faster-whisper (base model, offline)",
                    "hook_analyzer": "Google Gemini Flash (multimodal) + local heuristic",
                    "profile_auditor": "Sales & Marketing Content Auditor",
                    "media_processor": "FFmpeg keyframes (0.5s, 1.5s, 3.0s)"
                }
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode("utf-8"))
            return

        # Profile Audit endpoint: /api/profiles/<username>/audit
        if path.startswith("/api/profiles/") and path.endswith("/audit"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                user = parts[2].replace("@", "")
                audit = db.get_profile_audit(user)
                if not audit:
                    reels = db.get_watched_reels(limit=20, username=user)
                    audit = auditor.audit_profile(user, reels)
                    db.save_profile_audit(user, audit)

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(audit, ensure_ascii=False, indent=2).encode("utf-8"))
                return

        # Target profiles API with live statistics
        if path in ("/api/profiles", "/api/profiles/"):
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

            # Enrich with real stats from SQLite
            for t in targets:
                uname = t.get("username", "")
                stats = db.get_profile_stats(uname)
                t["stats"] = stats
                t["audit_exists"] = db.get_profile_audit(uname) is not None

            self.wfile.write(json.dumps(targets, ensure_ascii=False).encode("utf-8"))
            return

        # Live Watched Reels API (supports ?username=...)
        if path == "/api/reels":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            filter_user = query.get("username", [None])[0]
            reels = db.get_watched_reels(limit=50, username=filter_user)
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

        # Add profile
        if path == "/api/profiles":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                new_target = json.loads(body)
                targets = []
                if os.path.exists(CONFIG_TARGETS_PATH):
                    with open(CONFIG_TARGETS_PATH, "r", encoding="utf-8") as f:
                        targets = json.load(f)

                # Avoid duplicate entries in targets.json
                existing_users = {t.get("username", "").lower() for t in targets}
                uname = new_target.get("username", "").strip().replace("@", "")
                if uname.lower() not in existing_users:
                    new_target["username"] = uname
                    targets.insert(0, new_target)
                    with open(CONFIG_TARGETS_PATH, "w", encoding="utf-8") as f:
                        json.dump(targets, f, ensure_ascii=False, indent=2)

                db.add_log("PROFILE_ADDED", f"Added target @{uname}", new_target)

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

        # Force regenerate audit: POST /api/profiles/<username>/audit
        if path.startswith("/api/profiles/") and path.endswith("/audit"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                user = parts[2].replace("@", "")
                reels = db.get_watched_reels(limit=20, username=user)
                audit = auditor.audit_profile(user, reels)
                db.save_profile_audit(user, audit)

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(audit, ensure_ascii=False, indent=2).encode("utf-8"))
                return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # DELETE /api/profiles/<username>
        if path.startswith("/api/profiles/"):
            username = path.replace("/api/profiles/", "").strip().replace("@", "")
            if username:
                if os.path.exists(CONFIG_TARGETS_PATH):
                    try:
                        with open(CONFIG_TARGETS_PATH, "r", encoding="utf-8") as f:
                            targets = json.load(f)
                        targets = [t for t in targets if t.get("username", "").lower() != username.lower()]
                        with open(CONFIG_TARGETS_PATH, "w", encoding="utf-8") as f:
                            json.dump(targets, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

                db.delete_profile(username)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "deleted", "username": username}).encode("utf-8"))
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
        print(f"  Target Profiles API: http://localhost:{port}/api/profiles (GET, POST, DELETE)")
        print(f"  Profile Audit API:   http://localhost:{port}/api/profiles/<user>/audit")
        print(f"  Agent Logs API:      http://localhost:{port}/api/logs")
        print(f"  Thumbnails route:    http://localhost:{port}/thumbnails/")
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
