"""Autonomous Content Watcher & Hook Analyzer Agent for NikitaBot.

Autonomously monitors target Instagram profiles, discovers new Reels and posts,
downloads media stream, extracts 3 hook keyframes (0.5s, 1.5s, 3.0s),
transcribes speech via faster-whisper, performs multimodal virality analysis
via Gemini Flash, cleans up heavy MP4 videos, and records everything in SQLite.
"""
import concurrent.futures
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional

from scraper.instagram import InstagramScraper, extract_username
from scraper.models import ScrapedReel
from storage.database import NikitaDatabase
from processor.media import extract_audio, extract_hook_frames, cleanup_video
from processor.transcriber import WhisperTranscriber
from ai_analyzer.hook_analyzer import HookAnalyzer
from ai_analyzer.profile_auditor import ProfileAuditor

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
        analyzer: Optional[HookAnalyzer] = None,
        auditor: Optional[ProfileAuditor] = None
    ):
        self.db = db or NikitaDatabase()
        self.scraper = scraper or InstagramScraper()
        self.transcriber = transcriber or WhisperTranscriber(model_size="base")
        self.analyzer = analyzer or HookAnalyzer()
        self.auditor = auditor or ProfileAuditor()

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

        # Filter out already watched reels
        reels_to_process = []
        for idx, reel in enumerate(result.reels, 1):
            shortcode = reel.shortcode
            if self.db.is_reel_watched(shortcode):
                previously_seen_count += 1
                print(f"  [{idx}/{len(result.reels)}] ⏩ [Уже просмотрен] Reel {shortcode}")
            else:
                reels_to_process.append((idx, reel))

        total_to_process = len(reels_to_process)
        if total_to_process > 0:
            max_workers = min(5, total_to_process)
            print(f"⚡ [Fast Batch Scanning] Запуск одновременной обработки {total_to_process} новых Reels (потоков: {max_workers})...\n")
            self.db.add_log(
                "BATCH_SCAN_STARTED",
                f"Запущена параллельная обработка {total_to_process} рилсов для @{clean_user} ({max_workers} воркеров)",
                {"username": clean_user, "total": total_to_process, "workers": max_workers}
            )

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_reel = {
                    executor.submit(
                        self._process_single_reel,
                        reel,
                        clean_user,
                        thumbnails_dir,
                        download_media,
                        analyze_hook,
                        idx,
                        len(result.reels)
                    ): (idx, reel) for idx, reel in reels_to_process
                }

                for future in concurrent.futures.as_completed(future_to_reel):
                    idx, reel = future_to_reel[future]
                    try:
                        success = future.result()
                        if success:
                            new_watched_count += 1
                    except Exception as e:
                        logger.error("Ошибка при обработке Reel %s: %s", reel.shortcode, e)

        print(f"📊 [Итог просмотра @{clean_user}]: {new_watched_count} новых Reels просмотрено, {previously_seen_count} пропущено (ранее сохранены).")
        self.db.add_log(
            "WATCH_COMPLETED",
            f"Completed watch for @{clean_user}: {new_watched_count} new, {previously_seen_count} skipped",
            {"username": clean_user, "new_count": new_watched_count}
        )

        # Generate & save Sales & Marketing Content Audit
        watched_reels = self.db.get_watched_reels(limit=20, username=clean_user)
        audit_res = self.auditor.audit_profile(clean_user, watched_reels)
        self.db.save_profile_audit(clean_user, audit_res)
        print(f"💼 [Sales & Marketing Audit]: Сформирован аудит для @{clean_user} (Lead Score: {audit_res.get('lead_score')}/100)")

        return {
            "username": clean_user,
            "status": "success",
            "new_watched": new_watched_count,
            "previously_seen": previously_seen_count,
            "total_found": len(result.reels),
            "audit": audit_res
        }

    def _process_single_reel(
        self,
        reel: ScrapedReel,
        clean_user: str,
        thumbnails_dir: str,
        download_media: bool = True,
        analyze_hook: bool = True,
        idx: int = 1,
        total: int = 1
    ) -> bool:
        """Process a single reel concurrently: download, hook frames, whisper, Gemini, and persist."""
        shortcode = reel.shortcode
        duration_str = f"{int(reel.duration_seconds)} сек" if reel.duration_seconds else "N/A"
        views_str = f"{reel.views_count:,}" if reel.views_count else "N/A"
        likes_str = f"{reel.likes_count:,}" if reel.likes_count else "0"
        caption_preview = (reel.caption[:80] + "...") if len(reel.caption) > 80 else (reel.caption or "Без описания")

        print(f"  [{idx}/{total}] 🎬 [ПОТОК REEL]: {reel.url}")
        print(f"      ⏱️ {duration_str} | 👁️ {views_str} | ❤️ {likes_str} | {caption_preview}")

        video_path = None
        hook_frames = []
        transcript_text = ""
        analysis_data = {}

        if download_media or analyze_hook:
            try:
                dl_res = self.scraper.download_reel_media(
                    reel.url,
                    f"{clean_user}_{shortcode}",
                    direct_video_url=reel.video_url
                )
                video_path = dl_res.get("video_path")
            except Exception as e:
                logger.warning(f"Загрузка видео {shortcode} не удалась ({e}), переход к мета-анализу.")

        if isinstance(video_path, str) and os.path.exists(video_path):
            # 1. Extract 3 hook keyframes (0.5s, 1.5s, 3.0s)
            raw_frame_paths = extract_hook_frames(
                video_path,
                output_dir=thumbnails_dir,
                timestamps=(0.5, 1.5, 3.0),
                shortcode=shortcode
            )
            hook_frames = [os.path.basename(p) for p in raw_frame_paths]

            # 2. Extract audio and transcribe with Whisper
            wav_path = extract_audio(video_path)
            if wav_path:
                trans_res = self.transcriber.transcribe(wav_path, hint_text=reel.caption)
                transcript_text = trans_res.get("text", "")

            # 3. Multimodal Hook & Virality Analysis via Gemini Flash
            if analyze_hook:
                analysis_data = self.analyzer.analyze(
                    frame_paths=raw_frame_paths,
                    transcript=transcript_text,
                    caption=reel.caption,
                    tags=reel.tags,
                    likes=reel.likes_count,
                    comments=reel.comments_count
                )
        elif analyze_hook:
            analysis_data = self.analyzer.analyze(
                frame_paths=[],
                transcript=transcript_text,
                caption=reel.caption,
                tags=reel.tags,
                likes=reel.likes_count,
                comments=reel.comments_count
            )

        reel_dict = reel.to_dict()
        if hook_frames and not reel_dict.get("thumbnail_url"):
            reel_dict["thumbnail_url"] = f"/thumbnails/{hook_frames[0]}"
        valid_video_path = video_path if isinstance(video_path, str) and os.path.exists(video_path) else None
        if valid_video_path:
            reel_dict["video_url"] = f"/videos/{os.path.basename(valid_video_path)}"

        # Save into SQLite DB
        inserted = self.db.save_watched_reel(
            reel_data=reel_dict,
            video_local_path=valid_video_path,
            transcript=transcript_text,
            analysis_data=analysis_data,
            hook_frames=hook_frames
        )

        score = analysis_data.get("hook_score", 0.0)
        virality = analysis_data.get("virality_score", 0)
        htype = analysis_data.get("hook_type", "N/A")
        print(f"      ✅ [Готово] Reel {shortcode} | Hook: {score}/10 | Virality: {virality}% | {htype}")

        self.db.add_log(
            "REEL_PROCESSED",
            f"Готов Reel {shortcode} для @{clean_user} ({idx}/{total})",
            {"shortcode": shortcode, "username": clean_user, "hook_score": score, "virality_score": virality}
        )
        return inserted

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

        direct_video_url = None
        reel_meta = None
        if self.scraper.brightdata_scraper.is_configured():
            try:
                bd_res = self.scraper.brightdata_scraper.scrape_profile_reels(reel_url, limit=1)
                if bd_res.status == "success" and bd_res.reels:
                    reel_meta = bd_res.reels[0]
                    direct_video_url = reel_meta.video_url
                    print(f"   🎯 Bright Data нашел Reel: {reel_meta.author} (Likes: {reel_meta.likes_count})")
            except Exception as e:
                logger.warning("Bright Data direct reel lookup notice: %s", e)

        print(f"📥 Загружаю видеоряд рилса...")
        dl_res = self.scraper.download_reel_media(reel_url, f"direct_{shortcode}", direct_video_url=direct_video_url)
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
                    caption=reel_meta.caption if reel_meta and reel_meta.caption else "",
                    tags=reel_meta.tags if reel_meta and reel_meta.tags else []
                )
                print(f"   🎯 Хук: {analysis_data.get('hook_score')}/10 | Виральность: {analysis_data.get('virality_score')}%")
                print(f"   💡 Саммари: {analysis_data.get('summary')}")

        # Save to DB
        valid_vp = video_path if isinstance(video_path, str) and os.path.exists(video_path) else None
        reel_dict = {
            "shortcode": shortcode,
            "author": reel_meta.author if reel_meta and reel_meta.author else "@direct_reel",
            "url": reel_url,
            "caption": (reel_meta.caption if reel_meta and reel_meta.caption else "") or analysis_data.get("summary", "Direct reel inspect"),
            "timestamp": reel_meta.timestamp if reel_meta and reel_meta.timestamp else time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": reel_meta.duration_seconds if reel_meta and reel_meta.duration_seconds else 30.0,
            "views_count": reel_meta.views_count if reel_meta else 0,
            "likes_count": reel_meta.likes_count if reel_meta else 0,
            "comments_count": reel_meta.comments_count if reel_meta else 0,
            "tags": reel_meta.tags if reel_meta and reel_meta.tags else ["reel", "direct"],
            "thumbnail_url": f"/thumbnails/{hook_frames[0]}" if hook_frames else (reel_meta.thumbnail_url if reel_meta else None),
            "video_url": f"/videos/{os.path.basename(valid_vp)}" if valid_vp else None
        }
        self.db.save_watched_reel(
            reel_data=reel_dict,
            video_local_path=valid_vp,
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
