#!/usr/bin/env python3
"""
CAMEL FINANCE YOUTUBE TRANSCRIPT PIPELINE v2
=============================================
Upgraded pipeline with:
- Chunked transcript analysis (handles any length content)
- Thesis ledger integration (tracks conviction, detects contradictions)
- Full transcript ingestion (no more truncation)

Replaces camel-yt-pipeline.py (v1). Backward compatible with same
state file and feed format.

Usage:
    python3 ~/camel-yt-pipeline-v2.py              # Process new videos
    python3 ~/camel-yt-pipeline-v2.py --backfill 10 # Process last N videos
    python3 ~/camel-yt-pipeline-v2.py --test        # Dry run, no feed writes
    python3 ~/camel-yt-pipeline-v2.py --reprocess   # Reprocess all with full transcripts
"""

import json
import os
import sys
import subprocess
import datetime
import time
from pathlib import Path

# Import our modules
sys.path.insert(0, str(Path.home()))
from camel_chunked_analyzer import analyze_transcript
from camel_thesis_ledger import ThesisLedger
from spark_lock import acquire_spark, release_spark

# ============================================================
# CONFIG
# ============================================================
HOME = Path.home()
FEED = HOME / ".openclaw/workspace/memory/learning-feed.jsonl"
STATE_FILE = HOME / ".openclaw/workspace/memory/camel-yt-state.json"
TRANSCRIPT_DIR = HOME / ".openclaw/workspace/memory/camel-transcripts"
CHANNEL_ID = "UCr_DLep7UQ0B_IFhvTORu8A"
CHANNEL_URL = f"https://www.youtube.com/channel/{CHANNEL_ID}/videos"
YT_DLP = "/opt/homebrew/bin/yt-dlp"
DEFAULT_FETCH_COUNT = 5


# ============================================================
# HELPERS
# ============================================================

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"processed_ids": [], "last_check": None}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_recent_videos(count=DEFAULT_FETCH_COUNT):
    cmd = [
        YT_DLP, "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(upload_date)s",
        "--playlist-end", str(count),
        CHANNEL_URL
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"ERROR fetching video list: {result.stderr}")
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            videos.append({
                "id": parts[0],
                "title": parts[1],
                "date": parts[2] if len(parts) > 2 and parts[2] != "NA" else "unknown"
            })
    return videos


def fetch_full_transcript(video_id):
    """Fetch FULL transcript — no truncation."""
    try:
        code = f"""
from youtube_transcript_api import YouTubeTranscriptApi
api = YouTubeTranscriptApi()
transcript = api.fetch('{video_id}')
text = ' '.join([t.text for t in transcript])
print(text)
"""
        result = subprocess.run(
            ["/opt/homebrew/bin/python3", "-c", code],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()  # NO TRUNCATION — full text
        else:
            print(f"  Transcript fetch failed: {result.stderr[:200]}")
            return None
    except Exception as e:
        print(f"  Transcript error: {e}")
        return None


def _build_finding(analysis: dict, title: str) -> str:
    """
    Synthesize a rich structured finding from extracted fields.
    Never falls back to raw transcript text — only uses structured extractions.
    Result is dense, action-oriented, and specific enough to score 3.5+.
    """
    parts = []

    bias = analysis.get("overall_bias", "")
    instruments = analysis.get("instruments_discussed", [])
    if bias and instruments:
        parts.append(f"[{bias.upper()}] {', '.join(instruments)}: {title}")

    for cr in analysis.get("cycle_readings", [])[:3]:
        inst = cr.get("instrument", "")
        ctype = cr.get("cycle_type", "")
        day_or_week = cr.get("current_day_or_week", "")
        phase = cr.get("phase", "")
        key_level = cr.get("key_level", "")
        translation = cr.get("translation", "")
        if inst and phase:
            line = f"{inst} {ctype} cycle"
            if day_or_week: line += f" day/wk {day_or_week}"
            line += f" — {phase}"
            if translation and translation != "unknown": line += f" ({translation} translated)"
            if key_level: line += f". Key level: {key_level}"
            parts.append(line)

    for tc in analysis.get("trade_calls", [])[:2]:
        inst = tc.get("instrument", "")
        direction = tc.get("direction", "")
        entry_trigger = tc.get("entry_trigger", "")
        target = tc.get("target", "")
        if inst and direction:
            line = f"Trade: {direction.upper()} {inst}"
            if entry_trigger: line += f" — entry: {entry_trigger}"
            if target: line += f". Target: {target}"
            parts.append(line)

    for ts in analysis.get("thesis_statements", [])[:2]:
        claim = ts.get("claim", "")
        strength = ts.get("thesis_strength", 0)
        conditional = ts.get("conditional", False)
        condition = ts.get("condition", "")
        if claim and strength >= 6:
            line = f"Thesis (conviction {strength}/10): {claim}"
            if conditional and condition: line += f" IF {condition}"
            parts.append(line)

    for ins in analysis.get("key_insights", [])[:3]:
        if ins and len(ins) > 20:
            parts.append(f"→ {ins}")

    if not parts:
        # Last resort: use summary if populated
        return analysis.get("summary", "") or f"[no structured extraction] {title}"

    return " | ".join(parts)


def append_to_feed(video_id, title, date, analysis):
    """Append structured findings to the research feed."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    finding = _build_finding(analysis, title)

    entry = {
        "timestamp": now,
        "topic": "camel-finance-cycle-analysis",
        "finding": finding,
        "source": f"youtube/{video_id}",
        "source_url": f"https://youtube.com/watch?v={video_id}",
        "video_title": title,
        "video_date": date,
        "instruments": analysis.get("instruments_discussed", []),
        "overall_bias": analysis.get("overall_bias", "unknown"),
        "cycle_readings": analysis.get("cycle_readings", []),
        "trade_calls": analysis.get("trade_calls", []),
        "key_insights": analysis.get("key_insights", []),
        "thesis_statements": analysis.get("thesis_statements", []),
        "content_type": analysis.get("content_type", "unknown"),
        "chunk_count": analysis.get("chunk_count", 1),
        "extraction_meta": analysis.get("_extraction_meta", {})
    }

    with open(FEED, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def save_transcript(video_id, title, transcript, analysis):
    """Save full transcript and analysis."""
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    doc = {
        "video_id": video_id,
        "title": title,
        "transcript": transcript,
        "analysis": analysis,
        "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pipeline_version": "v2"
    }
    outpath = TRANSCRIPT_DIR / f"{video_id}.json"
    with open(outpath, "w") as f:
        json.dump(doc, f, indent=2)


# ============================================================
# MAIN
# ============================================================

def main():
    test_mode = "--test" in sys.argv
    reprocess = "--reprocess" in sys.argv
    backfill = None

    for i, arg in enumerate(sys.argv):
        if arg == "--backfill" and i + 1 < len(sys.argv):
            backfill = int(sys.argv[i + 1])

    fetch_count = backfill or DEFAULT_FETCH_COUNT

    print(f"[CAMEL-YT-v2] Starting pipeline {'(TEST MODE)' if test_mode else ''}")
    print(f"[CAMEL-YT-v2] Fetching last {fetch_count} videos from channel...")

    state = load_state()
    videos = fetch_recent_videos(fetch_count)

    if not videos:
        print("[CAMEL-YT-v2] No videos found. Exiting.")
        return

    print(f"[CAMEL-YT-v2] Found {len(videos)} videos")

    # Initialize thesis ledger
    ledger = ThesisLedger()

    new_count = 0
    conflict_count = 0

    for video in videos:
        vid_id = video["id"]

        if vid_id in state["processed_ids"] and not reprocess:
            print(f"  SKIP (already processed): {video['title']}")
            continue

        print(f"\n  PROCESSING: {video['title']} ({vid_id})")
        print(f"  {'=' * 60}")

        # Acquire Spark lock (wait up to 5 min for scheduler to finish)
        if not acquire_spark("camel-pipeline-v2", timeout=300):
            print(f"  SKIP (Spark busy, could not acquire lock after 5min)")
            continue

        try:
            # Step 1: Fetch FULL transcript
            transcript = fetch_full_transcript(vid_id)
            if not transcript:
                print(f"  SKIP (no transcript available)")
                continue

            print(f"    Full transcript: {len(transcript)} chars (~{len(transcript)//4} tokens)")

            # Step 2: Chunked analysis via Spark
            print(f"    Sending to chunked analyzer...")
            analysis = analyze_transcript(video["title"], video["date"], transcript)
            if not analysis:
                print(f"    SKIP (analysis failed completely)")
                continue

            parse_ok = not analysis.get("parse_error", False)
            chunk_count = analysis.get("chunk_count", analysis.get("_extraction_meta", {}).get("chunks_attempted", 1))
            success_rate = analysis.get("_extraction_meta", {}).get("success_rate", 0)

            print(f"    Analysis: {'structured' if parse_ok else 'FAILED'} | "
                  f"Chunks: {chunk_count} | "
                  f"Instruments: {analysis.get('instruments_discussed', [])} | "
                  f"Bias: {analysis.get('overall_bias', 'unknown')}")

            # Step 3: Feed into thesis ledger
            if parse_ok:
                conflicts = ledger.ingest_analysis(
                    vid_id, video["title"], video["date"], analysis
                )
                if conflicts:
                    conflict_count += len(conflicts)
                    print(f"    THESIS CONFLICTS DETECTED: {len(conflicts)}")
                    for c in conflicts:
                        print(f"      {c['instrument']}: was {c['active_direction']} -> "
                              f"now {c['new_direction']} (severity: {c['severity']})")
                else:
                    for inst in analysis.get("instruments_discussed", []):
                        inst_data = ledger.data["instruments"].get(inst.upper(), {})
                        active = inst_data.get("active_thesis", {})
                        if active:
                            print(f"      {inst}: {active.get('direction', '?')} "
                                  f"(strength: {active.get('strength', 0):.0%})")

            if test_mode:
                print(f"    TEST MODE - would write to feed")
                print(f"    Summary: {analysis.get('summary', '')[:200]}")
                thesis_stmts = analysis.get("thesis_statements", [])
                if thesis_stmts:
                    print(f"    Thesis statements: {len(thesis_stmts)}")
                    for ts in thesis_stmts[:3]:
                        print(f"      {ts.get('instrument', '?')}: {ts.get('claim', '')[:100]}")
            else:
                # Step 4: Write to feed
                entry = append_to_feed(vid_id, video["title"], video["date"], analysis)
                print(f"    Written to feed: {entry['finding'][:100]}...")

                # Step 5: Save full transcript + analysis
                save_transcript(vid_id, video["title"], transcript, analysis)

                # Step 6: Update state
                if vid_id not in state["processed_ids"]:
                    state["processed_ids"].append(vid_id)
                state["last_check"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                save_state(state)

            new_count += 1

        except Exception as e:
            print(f"  CRASH on {vid_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            release_spark()
            time.sleep(30)  # breathing gap for scheduler

    # Save ledger
    if not test_mode:
        ledger.save()
        print(f"\n[CAMEL-YT-v2] Thesis ledger saved")

    # Print summary
    print(f"\n[CAMEL-YT-v2] {'=' * 60}")
    print(f"[CAMEL-YT-v2] Done. Processed {new_count} videos. Conflicts: {conflict_count}")

    # Print thesis state summary
    report = ledger.get_report()
    if report["instruments"]:
        print(f"\n[CAMEL-YT-v2] THESIS STATE:")
        for inst_name, inst_data in report["instruments"].items():
            status = inst_data.get("status", "NO_DATA")
            obs = inst_data.get("observation_count", 0)
            consistency = inst_data.get("consistency_score", 0)
            drift_data = inst_data.get("conviction_drift")
            drift_str = f" | drift: {drift_data['trend']}" if drift_data else ""
            print(f"  {inst_name:10s} | {status:40s} | obs: {obs:2d} | "
                  f"consistency: {consistency:.0%}{drift_str}")


if __name__ == "__main__":
    main()
