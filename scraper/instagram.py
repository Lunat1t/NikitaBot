"""Instagram free scraper engine utilizing Instaloader and yt-dlp."""
import logging
import os
from pathlib import Path
import re
from typing import List, Optional

import instaloader
import yt_dlp

from .models import ScrapedReel, ScraperResult
from .session_manager import SessionManager

logger = logging.getLogger("nikitabot.scraper")


class InstagramScraper:
    """Free, open-source Instagram Reel & Post extractor."""

    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = Path(download_dir or os.path.join(os.getcwd(), "downloads"))
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session_manager = SessionManager()
        
        # Configure Instaloader
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            user_agent=self.session_manager.get_random_user_agent(),
            quiet=True,
        )

    def fetch_profile_reels(self, username: str, limit: int = 10) -> ScraperResult:
        """Fetch recent reels and posts from a public profile."""
        clean_user = username.strip().replace("@", "")
        self.session_manager.polite_delay()

        reels: List[ScrapedReel] = []
        try:
            profile = instaloader.Profile.from_username(self.loader.context, clean_user)
            
            if profile.is_private:
                return ScraperResult(
                    status="error",
                    target_username=clean_user,
                    error_message=f"Профиль @{clean_user} является приватным.",
                    reels=[],
                )

            count = 0
            for post in profile.get_posts():
                if count >= limit:
                    break

                # Extract hashtag tags from caption
                caption = post.caption or ""
                tags = re.findall(r"#([\w\u0400-\u04FF]+)", caption)

                reel = ScrapedReel(
                    shortcode=post.shortcode,
                    url=f"https://www.instagram.com/reel/{post.shortcode}/" if post.is_video else f"https://www.instagram.com/p/{post.shortcode}/",
                    author=f"@{clean_user}",
                    caption=caption,
                    timestamp=post.date_utc.isoformat() + "Z",
                    video_url=post.video_url if post.is_video else None,
                    thumbnail_url=post.url,
                    likes_count=post.likes,
                    comments_count=post.comments,
                    views_count=post.video_view_count if post.is_video and post.video_view_count else 0,
                    duration_seconds=float(post.video_duration) if post.is_video and post.video_duration else None,
                    is_video=post.is_video,
                    tags=tags,
                )
                reels.append(reel)
                count += 1

            return ScraperResult(
                status="success",
                target_username=clean_user,
                reels=reels,
                count=len(reels),
            )

        except instaloader.exceptions.ProfileNotExistsException:
            return ScraperResult(
                status="error",
                target_username=clean_user,
                error_message=f"Профиль @{clean_user} не найден в Instagram.",
                reels=[],
            )
        except instaloader.exceptions.QueryReturnedBadRequestException:
            return ScraperResult(
                status="rate_limited",
                target_username=clean_user,
                error_message="Instagram вернул 400 Bad Request (возможен временный rate-limit).",
                reels=[],
            )
        except Exception as e:
            logger.error("Scraping error for @%s: %s", clean_user, e)
            return ScraperResult(
                status="error",
                target_username=clean_user,
                error_message=str(e),
                reels=[],
            )

    def extract_direct_video_info(self, reel_url: str) -> dict:
        """Extract media streams and metadata using yt-dlp."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "best",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(reel_url, download=False)
            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "duration": info.get("duration"),
                "url": info.get("url"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
            }

    def download_reel_media(self, reel_url: str, output_name: str) -> dict:
        """Download MP4 video and extract MP3/WAV audio for Whisper."""
        out_template = str(self.download_dir / f"{output_name}.%(ext)s")
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": out_template,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([reel_url])

        video_path = self.download_dir / f"{output_name}.mp4"
        return {
            "video_path": str(video_path) if video_path.exists() else None,
            "output_dir": str(self.download_dir),
        }
