#!/usr/bin/env python3
"""CLI utility to run the NikitaBot Autonomous Content Watcher."""
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
from agent.watcher import ContentWatcherAgent
from storage.database import NikitaDatabase


def main():
    parser = argparse.ArgumentParser(description="NikitaBot Autonomous Reels Watcher")
    parser.add_argument("target", nargs="?", help="Instagram username or Reel URL to watch (e.g. sentimentalka_smm or https://instagram.com/reel/...)")
    parser.add_argument("--reel", help="Direct URL of a specific reel to download, transcribe and analyze")
    parser.add_argument("--all", action="store_true", help="Watch all profiles from config/targets.json")
    parser.add_argument("--limit", type=int, default=10, help="Max posts/reels to scan per profile (default: 10)")
    parser.add_argument("--all-reels", action="store_true", help="Watch ALL available reels of the profile without limit")
    parser.add_argument("--download", action="store_true", default=True, help="Download video stream for analysis (default: True)")
    parser.add_argument("--no-download", dest="download", action="store_false", help="Skip media download (metadata only)")
    parser.add_argument("--no-analyze", action="store_true", help="Skip multimodal hook analysis")
    parser.add_argument("--loop", action="store_true", help="Run continuous background monitoring loop")
    parser.add_argument("--interval", type=int, default=15, help="Loop interval in minutes (default: 15)")
    parser.add_argument("--list", action="store_true", help="List recent watched reels from database")

    args = parser.parse_args()
    db = NikitaDatabase()
    agent = ContentWatcherAgent(db=db)

    effective_limit = None if args.all_reels else (None if args.limit <= 0 else args.limit)

    if args.list:
        reels = db.get_watched_reels(limit=25)
        print(f"\n📚 Всего просмотрено и сохранено: {len(reels)} Reels в базе NikitaBot:")
        print("---------------------------------------------------------------------")
        for r in reels:
            hook_str = f"{r.get('hook_score', 0)}/10" if r.get('hook_score') else "N/A"
            virality_str = f"{r.get('virality_score', 0)}%" if r.get('virality_score') else "N/A"
            print(f"• @{r['username']} [{r['shortcode']}]: {r['url']}")
            print(f"  🎯 Хук: {hook_str} | 🔥 Виральность: {virality_str} | 🏷️ Тип: {r.get('hook_type') or 'N/A'}")
            print(f"  ⏱️ Длительность: {r.get('duration_seconds')}s | ❤️ Лайки: {r.get('likes_count')} | 👁️ Просмотры: {r.get('views_count')}")
            if r.get('transcript'):
                print(f"  🎙️ Whisper: \"{r['transcript'][:80]}...\"")
            if r.get('hook_summary'):
                print(f"  💡 Инсайт: {r['hook_summary']}")
            print(f"  📅 Дата: {r['watched_at']}\n")
        return

    if args.loop:
        agent.start_continuous_loop(interval_minutes=args.interval)
        return

    if args.all:
        agent.watch_all_targets(download_media=args.download, analyze_hook=not args.no_analyze)
        return

    target = args.reel or args.target
    if target:
        if "/reel/" in target or "/p/" in target:
            agent.watch_single_reel(target, analyze_hook=not args.no_analyze)
            return
        else:
            agent.watch_profile(
                target,
                limit=effective_limit,
                download_media=args.download,
                analyze_hook=not args.no_analyze
            )
            return

    parser.print_help()


if __name__ == "__main__":
    main()
