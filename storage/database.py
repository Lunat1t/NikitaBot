"""SQLite storage for NikitaBot watched reels, profiles, agent logs, and marketing audits."""
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

                CREATE TABLE IF NOT EXISTS profile_audits (
                    username TEXT PRIMARY KEY,
                    lead_score INTEGER DEFAULT 75,
                    strengths_json TEXT DEFAULT '[]',
                    weaknesses_json TEXT DEFAULT '[]',
                    growth_points_json TEXT DEFAULT '[]',
                    sales_pitch TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
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

    def delete_profile(self, username: str) -> bool:
        """Deletes a profile from watched_profiles and removes its audit record."""
        clean_user = username.strip().replace("@", "")
        with self._get_connection() as conn:
            conn.execute("DELETE FROM watched_profiles WHERE username = ?", (clean_user,))
            conn.execute("DELETE FROM profile_audits WHERE username = ?", (clean_user,))
        self.add_log("PROFILE_DELETED", f"Deleted target @{clean_user}", {"username": clean_user})
        return True

    def save_profile_audit(self, username: str, audit_data: Dict[str, Any]) -> None:
        """Saves or updates a Sales & Marketing content audit for a profile."""
        clean_user = username.strip().replace("@", "")
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO profile_audits (
                    username, lead_score, strengths_json, weaknesses_json,
                    growth_points_json, sales_pitch, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    lead_score = excluded.lead_score,
                    strengths_json = excluded.strengths_json,
                    weaknesses_json = excluded.weaknesses_json,
                    growth_points_json = excluded.growth_points_json,
                    sales_pitch = excluded.sales_pitch,
                    updated_at = excluded.updated_at
            """, (
                clean_user,
                audit_data.get("lead_score", 75),
                json.dumps(audit_data.get("strengths", []), ensure_ascii=False),
                json.dumps(audit_data.get("weaknesses", []), ensure_ascii=False),
                json.dumps(audit_data.get("growth_points", []), ensure_ascii=False),
                audit_data.get("sales_pitch", ""),
                utcnow()
            ))
        self.add_log("AUDIT_UPDATED", f"Updated Sales & Marketing audit for @{clean_user}", {"username": clean_user})

    def get_profile_audit(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves the latest audit for a profile."""
        clean_user = username.strip().replace("@", "")
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM profile_audits WHERE username = ?", (clean_user,)).fetchone()
            if not row:
                return None
            item = dict(row)
            item["strengths"] = json.loads(item.get("strengths_json") or "[]")
            item["weaknesses"] = json.loads(item.get("weaknesses_json") or "[]")
            item["growth_points"] = json.loads(item.get("growth_points_json") or "[]")
            return item

    def get_profile_stats(self, username: str) -> Dict[str, Any]:
        """Calculates aggregated metrics for all watched reels of a specific profile."""
        clean_user = username.strip().replace("@", "")
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total_reels,
                    COALESCE(SUM(views_count), 0) as total_views,
                    COALESCE(SUM(likes_count), 0) as total_likes,
                    COALESCE(AVG(hook_score), 0.0) as avg_hook_score,
                    COALESCE(AVG(virality_score), 0.0) as avg_virality
                FROM watched_reels
                WHERE username = ?
            """, (clean_user,)).fetchone()

            if not row or row["total_reels"] == 0:
                return {
                    "username": clean_user,
                    "total_reels": 0,
                    "total_views": 0,
                    "total_likes": 0,
                    "avg_hook_score": 0.0,
                    "avg_virality": 0
                }

            return {
                "username": clean_user,
                "total_reels": row["total_reels"],
                "total_views": row["total_views"],
                "total_likes": row["total_likes"],
                "avg_hook_score": round(row["avg_hook_score"], 1),
                "avg_virality": int(row["avg_virality"])
            }

    def get_watched_reels(self, limit: int = 50, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent watched reels ordered by watched_at desc, optionally filtered by username."""
        with self._get_connection() as conn:
            if username:
                clean_user = username.strip().replace("@", "")
                rows = conn.execute("""
                    SELECT * FROM watched_reels WHERE username = ? ORDER BY watched_at DESC LIMIT ?
                """, (clean_user, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM watched_reels ORDER BY watched_at DESC LIMIT ?
                """, (limit,)).fetchall()

            result = []
            for r in rows:
                item = dict(r)
                item["tags"] = json.loads(item.get("tags_json") or "[]")
                item["hook_frames"] = json.loads(item.get("hook_frames_json") or "[]")
                # Ensure video_url is a reliable local playable stream URL
                sc = item.get("shortcode", "")
                raw_vurl = item.get("video_url") or ""
                if raw_vurl.startswith("http://") or raw_vurl.startswith("https://") or not raw_vurl:
                    item["video_url"] = f"/videos/{sc}.mp4"
                result.append(item)
            return result

    def delete_watched_reel(self, shortcode: str) -> bool:
        """Deletes a watched reel from database and cleans up associated media files on disk."""
        clean_sc = shortcode.strip()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT username, video_local_path, hook_frames_json FROM watched_reels WHERE shortcode = ?",
                (clean_sc,)
            ).fetchone()
            if not row:
                return False

            username = row["username"]
            v_path = row["video_local_path"]

            # Remove from DB
            conn.execute("DELETE FROM watched_reels WHERE shortcode = ?", (clean_sc,))

            # Update total_watched count in watched_profiles
            stats_row = conn.execute("SELECT COUNT(*) as cnt FROM watched_reels WHERE username = ?", (username,)).fetchone()
            new_cnt = stats_row["cnt"] if stats_row else 0
            conn.execute("UPDATE watched_profiles SET total_watched = ? WHERE username = ?", (new_cnt, username))

        # Cleanup specific video path if recorded
        if v_path and os.path.exists(v_path):
            try:
                os.remove(v_path)
            except Exception:
                pass

        # Also search and remove matching files in data/videos and data/thumbnails
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        videos_dir = os.path.join(base_dir, "data", "videos")
        thumbs_dir = os.path.join(base_dir, "data", "thumbnails")

        if os.path.exists(videos_dir):
            for fname in os.listdir(videos_dir):
                if clean_sc in fname:
                    try:
                        os.remove(os.path.join(videos_dir, fname))
                    except Exception:
                        pass

        if os.path.exists(thumbs_dir):
            for fname in os.listdir(thumbs_dir):
                if clean_sc in fname:
                    try:
                        os.remove(os.path.join(thumbs_dir, fname))
                    except Exception:
                        pass

        self.add_log(
            "REEL_DELETED",
            f"Deleted reel {clean_sc} for @{username} and cleaned up disk media",
            {"shortcode": clean_sc, "username": username}
        )
        return True

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
