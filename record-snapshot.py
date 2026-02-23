#!/usr/bin/env python3
"""
Zeke Snapshot Recorder — append to daily-snapshots.jsonl
Run via cron alongside build-status.py, or add to end of build-status.py

Usage: python3 ~/zeke-status/record-snapshot.py
"""
import json, subprocess
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

HOME = Path.home()
FEED = HOME / ".openclaw/workspace/memory/learning-feed.jsonl"
SNAPS = HOME / "zeke-status/daily-snapshots.jsonl"
DIAG = HOME / "zeke-status/diagnostic.json"

def main():
    now = datetime.now(timezone.utc)

    # Rate limit: max 1 snapshot per 15 minutes
    if SNAPS.exists():
        lines = [l for l in SNAPS.read_text().strip().split('\n') if l.strip()]
        if lines:
            try:
                last = json.loads(lines[-1])
                last_ts = datetime.fromisoformat(last['timestamp'].replace('Z','+00:00'))
                if (now - last_ts).total_seconds() < 900:
                    return  # Too soon
            except:
                pass

    # Count feed
    feed_total = 0
    topics = Counter()
    if FEED.exists():
        for line in FEED.read_text().strip().split('\n'):
            if line.strip():
                feed_total += 1
                try:
                    e = json.loads(line)
                    topics[e.get('topic', 'unknown')] += 1
                except:
                    pass

    # Pull activity from diagnostic.json if available
    jobs_today = 0
    success_today = 0
    feed_growth = 0
    cycles = 0
    if DIAG.exists():
        try:
            d = json.load(open(DIAG))
            a = d.get('activity', {})
            jobs_today = a.get('jobs_today', 0)
            success_today = a.get('success_today', 0)
            feed_growth = a.get('feed_growth_today', 0)
            cycles = a.get('cycle_count', 0)
        except:
            pass

    snap = {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "hour": now.strftime("%H:%M"),
        "feed_total": feed_total,
        "feed_unique_topics": len(topics),
        "topic_counts": dict(topics.most_common(8)),
        "jobs_today": jobs_today,
        "success_today": success_today,
        "feed_growth_today": feed_growth,
        "cycles_today": cycles,
        "event": "auto"
    }

    with open(SNAPS, 'a') as f:
        f.write(json.dumps(snap) + '\n')

if __name__ == "__main__":
    main()
