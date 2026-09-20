#!/usr/bin/env python3
"""CLI utility to run the NikitaBot Autonomous Content Watcher."""
import argparse
import sys

from agent.watcher import ContentWatcherAgent
from storage.database import NikitaDatabase


def main():
    parser = argparse.ArgumentParser(description="NikitaBot Autonomous Reels Watcher")
    parser.add_argument("username", nargs="?", help="Instagram username to watch (e.g. startup_hub)")
    parser.add_argument("--all", action="store_true", help="Watch all profiles from config/targets.json")
    parser.add_argument("--limit", type=int, default=10, help="Max posts/reels to scan per profile (default: 10)")
    parser.add_argument("--download", action="store_true", help="Download MP4 video media locally")
    parser.add_argument("--loop", action="store_true", help="Run continuous background monitoring loop")
    parser.add_argument("--interval", type=int, default=15, help="Loop interval in minutes (default: 15)")
    parser.add_argument("--list", action="store_true", help="List recent watched reels from database")

    args = parser.parse_args()
    db = NikitaDatabase()
    agent = ContentWatcherAgent(db=db)

    if args.list:
        reels = db.get_watched_reels(limit=25)
        print(f"\n📚 Всего просмотрено и сохранено: {len(reels)} Reels в базе NikitaBot:")
        print("---------------------------------------------------------------------")
        for r in reels:
            print(f"• @{r['username']} [{r['shortcode']}]: {r['url']}")
            print(f"  Длительность: {r['duration_seconds']}s | Лайки: {r['likes_count']} | Просмотры: {r['views_count']}")
            print(f"  Дата просмотра: {r['watched_at']}")
            print(f"  Описание: {r['caption'][:70]}...\n")
        return

    if args.loop:
        agent.start_continuous_loop(interval_minutes=args.interval)
        return

    if args.all:
        agent.watch_all_targets(download_media=args.download)
        return

    if args.username:
        agent.watch_profile(args.username, limit=args.limit, download_media=args.download)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
