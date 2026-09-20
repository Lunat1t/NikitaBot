"""Autonomous Content Watcher & Hook Analyzer Agent for NikitaBot.

Autonomously monitors target Instagram profiles, discovers new Reels and posts,
downloads media stream, extracts 3 hook keyframes (0.5s, 1.5s, 3.0s),
transcribes speech via faster-whisper, performs multimodal virality analysis
via Gemini Flash, cleans up heavy MP4 videos, and records everything in SQLite.
"""
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from scraper.instagram import InstagramScraper, extract_username
from scraper.models import ScrapedReel
from storage.database import NikitaDatabase
from processor.media import extract_audio, extract_hook_frames, cleanup_video
from processor.transcriber import WhisperTranscriber
from ai_analyzer.hook_analyzer import HookAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("nikitabot.watcher")


class ContentWatcherAgent:
    """Autonomous agent that watches, transcribes, and analyzes profile Reels."""

    def __init__(
        self,
        db: Optional[NikitaDatabase] = None,
        scraper: Optional[InstagramScraper] = None,
        transcriber: Optional[WhisperTranscriber] = None,
        analyzer: Optional[HookAnalyzer] = None
    ):
        self.db = db or NikitaDatabase()
        self.scraper = scraper or InstagramScraper()
        self.transcriber = transcriber or WhisperTranscriber(model_size="base")
        self.analyzer = analyzer or HookAnalyzer()

    def watch_profile(
        self,
        username: str,
        limit: int = 10,
        download_media: bool = True,
        analyze_hook: bool = True
    ) -> Dict[str, Any]:
        """Inspect a single profile, watch its reels, transcribe, and evaluate hooks."""
        clean_user = extract_username(username)
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

        thumbnails_dir = os.path.join("data", "thumbnails")
        os.makedirs(thumbnails_dir, exist_ok=True)

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

            # Media processing & Hook Analysis
            video_path = None
            hook_frames = []
            transcript_text = ""
            analysis_data = {}

            if download_media or analyze_hook:
                print(f"      📥 Загружаю MP4 видеоряд для анализа хука...")
                try:
                    dl_res = self.scraper.download_reel_media(reel.url, f"{clean_user}_{shortcode}")
                    video_path = dl_res.get("video_path")
                except Exception as e:
                    print(f"      ⚠️ Загрузка видео не удалась ({e}), переход к мета-анализу.")

            if isinstance(video_path, str) and os.path.exists(video_path):
                # 1. Extract 3 hook keyframes (0.5s, 1.5s, 3.0s)
                print(f"      🎞️ Захват 3 кадров хука первых секунд (ffmpeg)...")
                raw_frame_paths = extract_hook_frames(
                    video_path,
                    output_dir=thumbnails_dir,
                    timestamps=(0.5, 1.5, 3.0),
                    shortcode=shortcode
                )
                # Store relative paths for Web UI
                hook_frames = [os.path.basename(p) for p in raw_frame_paths]

                # 2. Extract audio and transcribe with Whisper
                print(f"      🎙️ Извлечение звука и транскрипция речи (faster-whisper)...")
                wav_path = extract_audio(video_path)
                if wav_path:
                    trans_res = self.transcriber.transcribe(wav_path)
                    transcript_text = trans_res.get("text", "")
                    if transcript_text:
                        preview_tx = (transcript_text[:70] + "...") if len(transcript_text) > 70 else transcript_text
                        print(f"         💬 Текст речи: \"{preview_tx}\"")

                # 3. Multimodal Hook & Virality Analysis via Gemini Flash
                if analyze_hook:
                    print(f"      🧠 Мультимодальный анализ хука (Gemini Flash)...")
                    analysis_data = self.analyzer.analyze(
                        frame_paths=raw_frame_paths,
                        transcript=transcript_text,
                        caption=reel.caption,
                        tags=reel.tags,
                        likes=reel.likes_count,
                        comments=reel.comments_count
                    )
                    score = analysis_data.get("hook_score", 0.0)
                    virality = analysis_data.get("virality_score", 0)
                    htype = analysis_data.get("hook_type", "N/A")
                    print(f"         🎯 Оценка хука: {score}/10 | Виральность: {virality}% | Тип: {htype}")
                    print(f"         💡 Саммари: {analysis_data.get('summary')}")

                # 4. Cleanup heavy MP4 to save disk space
                cleanup_video(video_path)
            elif analyze_hook:
                # Metadata-only hook evaluation when video stream is not downloaded
                analysis_data = self.analyzer.analyze(
                    frame_paths=[],
                    transcript=transcript_text,
                    caption=reel.caption,
                    tags=reel.tags,
                    likes=reel.likes_count,
                    comments=reel.comments_count
                )

            # Save into SQLite DB
            self.db.save_watched_reel(
                reel_data=reel.to_dict(),
                video_local_path=None,
                transcript=transcript_text,
                analysis_data=analysis_data,
                hook_frames=hook_frames
            )
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

    def watch_all_targets(
        self,
        targets_config_path: str = "config/targets.json",
        download_media: bool = True,
        analyze_hook: bool = True
    ) -> List[Dict[str, Any]]:
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
                summary = self.watch_profile(
                    username,
                    download_media=download_media,
                    analyze_hook=analyze_hook
                )
                summaries.append(summary)
                time.sleep(2)  # polite pause between target profiles

        return summaries

    def watch_single_reel(self, reel_url: str, analyze_hook: bool = True) -> Dict[str, Any]:
        """Inspect and evaluate a single Reel directly by its URL."""
        from scraper.instagram import extract_shortcode
        shortcode = extract_shortcode(reel_url) or f"reel_{int(time.time())}"

        print(f"\n=======================================================")
        print(f"👀 [NikitaBot] Прямой просмотр и анализ Reel: {reel_url}")
        print(f"=======================================================")

        self.db.add_log("REEL_INSPECT_STARTED", f"Inspecting reel {reel_url}", {"url": reel_url, "shortcode": shortcode})

        thumbnails_dir = os.path.join("data", "thumbnails")
        os.makedirs(thumbnails_dir, exist_ok=True)

        print(f"📥 Загружаю видеоряд рилса через yt-dlp...")
        dl_res = self.scraper.download_reel_media(reel_url, f"direct_{shortcode}")
        video_path = dl_res.get("video_path")

        hook_frames = []
        transcript_text = ""
        analysis_data = {}

        if isinstance(video_path, str) and os.path.exists(video_path):
            # 1. Hook Frames (0.5s, 1.5s, 3.0s)
            print(f"🎞️ Захват 3 кадров хука первых секунд (ffmpeg)...")
            raw_frames = extract_hook_frames(video_path, output_dir=thumbnails_dir, timestamps=(0.5, 1.5, 3.0), shortcode=shortcode)
            hook_frames = [os.path.basename(p) for p in raw_frames]

            # 2. Extract audio & transcribe
            print(f"🎙️ Извлечение звука и распознавание речи (faster-whisper)...")
            wav_path = extract_audio(video_path)
            if wav_path:
                trans_res = self.transcriber.transcribe(wav_path)
                transcript_text = trans_res.get("text", "")
                if transcript_text:
                    print(f"   💬 Текст: \"{transcript_text[:100]}...\"")

            # 3. Gemini Flash Hook Analysis
            if analyze_hook:
                print(f"🧠 Мультимодальный анализ виральности (Gemini Flash)...")
                analysis_data = self.analyzer.analyze(
                    frame_paths=raw_frames,
                    transcript=transcript_text,
                    caption="",
                    tags=[]
                )
                print(f"   🎯 Хук: {analysis_data.get('hook_score')}/10 | Виральность: {analysis_data.get('virality_score')}%")
                print(f"   💡 Саммари: {analysis_data.get('summary')}")

            # 4. Cleanup MP4
            cleanup_video(video_path)

        # Save to DB
        reel_dict = {
            "shortcode": shortcode,
            "author": "@direct_reel",
            "url": reel_url,
            "caption": analysis_data.get("summary", "Direct reel inspect"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": 30.0,
            "views_count": 0,
            "likes_count": 0,
            "comments_count": 0,
            "tags": ["reel", "direct"]
        }
        self.db.save_watched_reel(
            reel_data=reel_dict,
            video_local_path=None,
            transcript=transcript_text,
            analysis_data=analysis_data,
            hook_frames=hook_frames
        )

        print(f"✅ Reel {shortcode} сохранен в базе NikitaBot и доступен на веб-дашборде!\n")
        return {
            "status": "success",
            "shortcode": shortcode,
            "hook_score": analysis_data.get("hook_score"),
            "virality_score": analysis_data.get("virality_score"),
            "transcript": transcript_text,
            "hook_frames": hook_frames
        }

    def start_continuous_loop(
        self,
        interval_minutes: int = 15,
        targets_config_path: str = "config/targets.json"
    ) -> None:
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
