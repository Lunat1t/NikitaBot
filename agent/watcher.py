"""Autonomous Content Watcher Agent for NikitaBot.

Autonomously monitors target Instagram profiles, discovers new Reels and posts,
inspects metadata/duration/metrics, and records them in the local database.
"""
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from scraper.instagram import InstagramScraper
from scraper.models import ScrapedReel
from storage.database import NikitaDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("nikitabot.watcher")


class ContentWatcherAgent:
    """Autonomous agent that watches and logs profile Reels."""

    def __init__(self, db: Optional[NikitaDatabase] = None, scraper: Optional[InstagramScraper] = None):
        self.db = db or NikitaDatabase()
        self.scraper = scraper or InstagramScraper()

    def watch_profile(self, username: str, limit: int = 10, download_media: bool = False) -> Dict[str, Any]:
        """Inspect a single profile, watch its reels, and record new content."""
        clean_user = username.strip().replace("@", "")
        print(f"\n=======================================================")
        print(f"👀 [NikitaBot] Начинаю просмотр профиля: @{clean_user}")
        print(f"=======================================================")

        self.db.add_log("WATCH_STARTED", f"Started watching @{clean_user}", {"username": clean_user})

        # Fetch reels from scraper
        result = self.scraper.fetch_profile_reels(clean_user, limit=limit)

        if result.status != "success":
            msg = f"⚠️ [NikitaBot] Не удалось просмотреть @{clean_user}: {result.error_message or result.status}"
            print(msg)
            self.db.add_log("WATCH_FAILED", msg, {"username": clean_user, "error": result.error_message})
            return {
                "username": clean_user,
                "status": result.status,
                "error": result.error_message,
                "new_watched": 0,
                "total_found": 0
            }

        new_watched_count = 0
        previously_seen_count = 0

        print(f"📥 Найдено {len(result.reels)} постов/Reels в профиле @{clean_user}.\n")

        for idx, reel in enumerate(result.reels, 1):
            shortcode = reel.shortcode
            is_already_watched = self.db.is_reel_watched(shortcode)

            if is_already_watched:
                previously_seen_count += 1
                print(f"  [{idx}/{len(result.reels)}] ⏩ [Уже просмотрен] Reel {shortcode}")
                continue

            # New Reel encountered!
            new_watched_count += 1
            duration_str = f"{int(reel.duration_seconds)} сек" if reel.duration_seconds else "N/A"
            views_str = f"{reel.views_count:,}" if reel.views_count else "N/A"
            likes_str = f"{reel.likes_count:,}" if reel.likes_count else "0"
            caption_preview = (reel.caption[:80] + "...") if len(reel.caption) > 80 else (reel.caption or "Без описания")

            print(f"  [{idx}/{len(result.reels)}] 🎬 [НОВЫЙ REEL]: {reel.url}")
            print(f"      ⏱️ Длительность: {duration_str} | 👁️ Просмотры: {views_str} | ❤️ Лайки: {likes_str}")
            print(f"      📝 Описание: {caption_preview}")
            if reel.tags:
                print(f"      🏷️ Теги: {', '.join(['#' + t for t in reel.tags[:5]])}")

            # Optional media download
            video_path = None
            if download_media:
                print(f"      📥 Загружаю MP4 поток для локального архива...")
                try:
                    dl_res = self.scraper.download_reel_media(reel.url, f"{clean_user}_{shortcode}")
                    video_path = dl_res.get("video_path")
                except Exception as e:
                    print(f"      ⚠️ Ошибка загрузки видео: {e}")

            # Save into DB
            self.db.save_watched_reel(reel.to_dict(), video_local_path=video_path)
            print(f"      ✅ Зафиксировано в базе NikitaBot (ID: {shortcode})\n")

        print(f"📊 [Итог просмотра @{clean_user}]: {new_watched_count} новых Reels просмотрено, {previously_seen_count} пропущено (ранее сохранены).")
        self.db.add_log(
            "WATCH_COMPLETED",
            f"Completed watch for @{clean_user}: {new_watched_count} new, {previously_seen_count} skipped",
            {"username": clean_user, "new_count": new_watched_count}
        )

        return {
            "username": clean_user,
            "status": "success",
            "new_watched": new_watched_count,
            "previously_seen": previously_seen_count,
            "total_found": len(result.reels)
        }

    def watch_all_targets(self, targets_config_path: str = "config/targets.json", download_media: bool = False) -> List[Dict[str, Any]]:
        """Watch all profiles configured in targets.json."""
        if not os.path.exists(targets_config_path):
            print(f"Конфигурационный файл {targets_config_path} не найден.")
            return []

        with open(targets_config_path, "r", encoding="utf-8") as f:
            targets = json.load(f)

        summaries = []
        for target in targets:
            username = target.get("username")
            if username:
                summary = self.watch_profile(username, download_media=download_media)
                summaries.append(summary)
                time.sleep(2)  # polite pause between target profiles

        return summaries

    def start_continuous_loop(self, interval_minutes: int = 15, targets_config_path: str = "config/targets.json") -> None:
        """Run continuous autonomous monitoring loop."""
        print(f"\n🚀 Запуск автономного фонового цикла NikitaBot.")
        print(f"⏱️ Интервал между циклами: {interval_minutes} мин. Нажмите Ctrl+C для остановки.\n")

        try:
            cycle = 1
            while True:
                print(f"\n--- [Цикл #{cycle}] {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
                self.watch_all_targets(targets_config_path)
                print(f"\n💤 Ожидание следующего цикла ({interval_minutes} мин)...")
                time.sleep(interval_minutes * 60)
                cycle += 1
        except KeyboardInterrupt:
            print("\n🛑 Фоновый цикл NikitaBot остановлен пользователем.")
