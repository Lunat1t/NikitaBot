#!/usr/bin/env python3
"""Local development server for NikitaBot AI Reels Agent Dashboard.

Standard library only: http.server, socketserver, json, sys, os, argparse.
Serves web UI, handles /api/health, /api/profiles (GET, POST, DELETE),
/api/profiles/<username>/audit, /api/reels, /api/logs, /api/scan,
and serves hook frame thumbnails from /thumbnails/<filename>.
"""
import os
import sys

# Auto-reexec in virtual environment if running with system python
_script_dir = os.path.dirname(os.path.abspath(__file__))
_venv_dir = os.path.join(_script_dir, ".venv")
_venv_python = os.path.join(_venv_dir, "bin", "python")
if os.path.exists(_venv_python) and sys.prefix != _venv_dir:
    os.environ["VIRTUAL_ENV"] = _venv_dir
    os.environ["PATH"] = os.path.join(_venv_dir, "bin") + os.pathsep + os.environ.get("PATH", "")
    os.execv(_venv_python, [_venv_python] + sys.argv)

import argparse
from http import HTTPStatus
import http.server
import json
import socketserver
import threading
from urllib.parse import parse_qs, urlparse

ROOT_DIR = _script_dir
sys.path.insert(0, ROOT_DIR)

from storage.database import NikitaDatabase
from ai_analyzer.profile_auditor import ProfileAuditor

DEFAULT_PORT = 8080
WEB_DIR = os.path.join(ROOT_DIR, "web")
DATA_DIR = os.path.join(ROOT_DIR, "data")
THUMBNAILS_DIR = os.path.join(DATA_DIR, "thumbnails")
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
CONFIG_TARGETS_PATH = os.path.join(ROOT_DIR, "config", "targets.json")
DEFAULT_TARGETS = [
    {"username": "sentimentalka_smm", "category": "Marketing & Growth", "followers": "Новый"},
    {"username": "TheTechDaily", "category": "Technology & AI", "followers": "2.1M"},
    {"username": "StartupHub", "category": "Startups & Business", "followers": "980K"},
]

os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

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

    def do_HEAD(self):
        self.do_GET()

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

        # Serve video files from data/videos/ with HTTP Range support (206 Partial Content)
        if path.startswith("/videos/"):
            filename = os.path.basename(path)
            file_path = os.path.join(VIDEOS_DIR, filename)
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                return

            file_size = os.path.getsize(file_path)
            range_header = self.headers.get("Range")

            if range_header and range_header.startswith("bytes="):
                try:
                    ranges = range_header.replace("bytes=", "").split("-")
                    start = int(ranges[0]) if ranges[0] else 0
                    end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
                    if start >= file_size:
                        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        self.send_header("Content-Range", f"bytes */{file_size}")
                        self.end_headers()
                        return

                    length = end - start + 1
                    self.send_response(HTTPStatus.PARTIAL_CONTENT)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        f.seek(start)
                        self.wfile.write(f.read(length))
                    return
                except Exception:
                    pass

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(file_size))
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
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
            if not targets:
                targets = [dict(p) for p in DEFAULT_TARGETS]
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

        # Web scan trigger: POST /api/scan
        if path == "/api/scan":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}
            target_user = data.get("username", "sentimentalka_smm").strip().replace("@", "")

            scan_limit = data.get("limit", None)

            # Execute watcher agent scan in background thread
            def run_scan_thread():
                from agent.watcher import ContentWatcherAgent
                agent = ContentWatcherAgent(db=db, auditor=auditor)
                db.add_log("SCAN_TRIGGERED", f"Web UI initiated full scan for @{target_user}")
                agent.watch_profile(target_user, limit=scan_limit, download_media=True, analyze_hook=True)

            t = threading.Thread(target=run_scan_thread, daemon=True)
            t.start()

            self.send_response(HTTPStatus.ACCEPTED)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "scanning",
                "message": f"Запущен просмотр контента @{target_user}",
                "username": target_user
            }, ensure_ascii=False).encode("utf-8"))
            return

        # Direct Video / Reel URL watch: POST /api/watch-url
        if path == "/api/watch-url":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}
            target_url = data.get("url", "").strip()
            if not target_url:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(b'{"error": "Missing URL parameter"}')
                return

            def run_url_thread():
                from agent.watcher import ContentWatcherAgent
                agent = ContentWatcherAgent(db=db, auditor=auditor)
                db.add_log("WATCH_URL", f"Manual inspect started for {target_url}")
                agent.watch_single_reel(target_url, analyze_hook=True)

            t = threading.Thread(target=run_url_thread, daemon=True)
            t.start()

            self.send_response(HTTPStatus.ACCEPTED)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "processing",
                "message": f"Запущен детальный просмотр видео: {target_url}"
            }, ensure_ascii=False).encode("utf-8"))
            return

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
        print(f"  Scan Trigger API:    http://localhost:{port}/api/scan (POST)")
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
