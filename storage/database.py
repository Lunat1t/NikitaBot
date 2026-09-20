"""SQLite storage for NikitaBot watched reels, profiles, and agent logs."""
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class NikitaDatabase:
    """Thread-safe SQLite database manager for NikitaBot."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = Path(os.getcwd()) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "nikitabot.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS watched_profiles (
                    username TEXT PRIMARY KEY,
                    name TEXT,
                    followers TEXT,
                    status TEXT DEFAULT 'active',
                    category TEXT,
                    last_watched_at TEXT,
                    total_watched INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS watched_reels (
                    shortcode TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    url TEXT NOT NULL,
                    caption TEXT,
                    timestamp TEXT,
                    duration_seconds REAL,
                    views_count INTEGER DEFAULT 0,
                    likes_count INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    video_url TEXT,
                    thumbnail_url TEXT,
                    video_local_path TEXT,
                    tags_json TEXT,
                    watched_at TEXT NOT NULL,
                    transcript TEXT DEFAULT '',
                    hook_score REAL DEFAULT 0.0,
                    virality_score INTEGER DEFAULT 0,
                    hook_type TEXT DEFAULT '',
                    hook_dynamics TEXT DEFAULT '',
                    hook_summary TEXT DEFAULT '',
                    hook_frames_json TEXT DEFAULT '[]',
                    FOREIGN KEY (username) REFERENCES watched_profiles (username)
                );

                CREATE INDEX IF NOT EXISTS idx_reels_username ON watched_reels (username);
                CREATE INDEX IF NOT EXISTS idx_reels_watched_at ON watched_reels (watched_at DESC);

                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata_json TEXT
                );
            """)

            # Safe migration for existing databases: check and add new columns if missing
            cursor = conn.execute("PRAGMA table_info(watched_reels)")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            
            new_columns = [
                ("transcript", "TEXT DEFAULT ''"),
                ("hook_score", "REAL DEFAULT 0.0"),
                ("virality_score", "INTEGER DEFAULT 0"),
                ("hook_type", "TEXT DEFAULT ''"),
                ("hook_dynamics", "TEXT DEFAULT ''"),
                ("hook_summary", "TEXT DEFAULT ''"),
                ("hook_frames_json", "TEXT DEFAULT '[]'")
            ]

            for col_name, col_def in new_columns:
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE watched_reels ADD COLUMN {col_name} {col_def}")

    def is_reel_watched(self, shortcode: str) -> bool:
        """Check if reel was already watched and recorded."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT 1 FROM watched_reels WHERE shortcode = ?", (shortcode,)).fetchone()
            return row is not None

    def save_watched_reel(
        self,
        reel_data: Dict[str, Any],
        video_local_path: Optional[str] = None,
        transcript: str = "",
        analysis_data: Optional[Dict[str, Any]] = None,
        hook_frames: Optional[List[str]] = None
    ) -> bool:
        """Record a newly watched reel. Returns True if inserted, False if already existed."""
        shortcode = reel_data.get("shortcode")
        if not shortcode:
            return False

        if self.is_reel_watched(shortcode):
            return False

        watched_at = utcnow()
        tags_json = json.dumps(reel_data.get("tags", []), ensure_ascii=False)
        username = reel_data.get("author", "").replace("@", "")
        analysis = analysis_data or {}
        hook_frames_json = json.dumps(hook_frames or [], ensure_ascii=False)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO watched_reels (
                    shortcode, username, url, caption, timestamp,
                    duration_seconds, views_count, likes_count, comments_count,
                    video_url, thumbnail_url, video_local_path, tags_json, watched_at,
                    transcript, hook_score, virality_score, hook_type, hook_dynamics,
                    hook_summary, hook_frames_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                shortcode,
                username,
                reel_data.get("url", ""),
                reel_data.get("caption", ""),
                reel_data.get("timestamp", watched_at),
                reel_data.get("duration_seconds"),
                reel_data.get("views_count", 0),
                reel_data.get("likes_count", 0),
                reel_data.get("comments_count", 0),
                reel_data.get("video_url"),
                reel_data.get("thumbnail_url"),
                video_local_path,
                tags_json,
                watched_at,
                transcript,
                analysis.get("hook_score", 0.0),
                analysis.get("virality_score", 0),
                analysis.get("hook_type", ""),
                analysis.get("hook_dynamics", ""),
                analysis.get("summary", ""),
                hook_frames_json
            ))

            # Increment profile total_watched
            conn.execute("""
                INSERT INTO watched_profiles (username, last_watched_at, total_watched)
                VALUES (?, ?, 1)
                ON CONFLICT(username) DO UPDATE SET
                    last_watched_at = excluded.last_watched_at,
                    total_watched = total_watched + 1
            """, (username, watched_at))

        self.add_log(
            "REEL_WATCHED",
            f"Watched & analyzed reel {shortcode} from @{username} (Hook: {analysis.get('hook_score', 'N/A')}/10)",
            {"shortcode": shortcode, "author": username, "virality": analysis.get("virality_score")}
        )
        return True

    def update_reel_analysis(
        self,
        shortcode: str,
        transcript: str,
        analysis_data: Dict[str, Any],
        hook_frames: Optional[List[str]] = None
    ) -> bool:
        """Update analysis and transcript for an existing reel."""
        hook_frames_json = json.dumps(hook_frames or [], ensure_ascii=False)
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE watched_reels SET
                    transcript = ?,
                    hook_score = ?,
                    virality_score = ?,
                    hook_type = ?,
                    hook_dynamics = ?,
                    hook_summary = ?,
                    hook_frames_json = ?
                WHERE shortcode = ?
            """, (
                transcript,
                analysis_data.get("hook_score", 0.0),
                analysis_data.get("virality_score", 0),
                analysis_data.get("hook_type", ""),
                analysis_data.get("hook_dynamics", ""),
                analysis_data.get("summary", ""),
                hook_frames_json,
                shortcode
            ))
            return True

    def get_watched_reels(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent watched reels ordered by watched_at desc."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM watched_reels ORDER BY watched_at DESC LIMIT ?
            """, (limit,)).fetchall()

            result = []
            for r in rows:
                item = dict(r)
                item["tags"] = json.loads(item.get("tags_json") or "[]")
                item["hook_frames"] = json.loads(item.get("hook_frames_json") or "[]")
                result.append(item)
            return result

    def add_log(self, event_type: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add an autonomous agent log entry."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_logs (timestamp, event_type, message, metadata_json)
                VALUES (?, ?, ?, ?)
            """, (
                utcnow(),
                event_type,
                message,
                json.dumps(metadata or {}, ensure_ascii=False)
            ))

    def get_recent_logs(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get latest agent logs."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM agent_logs ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
