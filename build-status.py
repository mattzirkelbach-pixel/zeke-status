#!/usr/bin/env python3
"""Build status.json from Zeke's workspace data sources."""

import json
import os
import glob
import subprocess
import datetime

STATUS_DIR = os.path.expanduser("~/zeke-status")
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
MEMORY = os.path.join(WORKSPACE, "memory")


def safe_read_lines(path):
    try:
        with open(path) as f:
            return f.readlines()
    except (FileNotFoundError, PermissionError):
        return []


def safe_read_text(path, limit=None):
    try:
        with open(path) as f:
            text = f.read(limit) if limit else f.read()
            return text
    except (FileNotFoundError, PermissionError):
        return ""


def safe_mtime_iso(path):
    try:
        ts = os.path.getmtime(path)
        return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
    except (FileNotFoundError, OSError):
        return ""


def build_status():
    status = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # Learning feed: line count + last 15 lines
    feed_path = os.path.join(MEMORY, "learning-feed.jsonl")
    feed_lines = safe_read_lines(feed_path)
    status["feed_lines"] = len(feed_lines)
    status["recent_feed"] = [l.strip() for l in feed_lines[-15:]]

    # KG stats via subprocess
    kg_script = os.path.join(WORKSPACE, "tools/kg/kg-query.py")
    try:
        result = subprocess.run(
            ["python3", kg_script, "--stats"],
            capture_output=True, text=True, timeout=15
        )
        status["kg_stats"] = result.stdout.strip()
    except Exception:
        status["kg_stats"] = ""

    # Latest daily synthesis
    synths = sorted(glob.glob(os.path.join(MEMORY, "daily-synthesis-*.md")))
    if synths:
        latest = synths[-1]
        status["last_synthesis"] = os.path.basename(latest)
        status["synthesis_content"] = safe_read_text(latest, 3000)
    else:
        status["last_synthesis"] = ""
        status["synthesis_content"] = ""

    # Research priorities
    pri_path = os.path.join(MEMORY, "research-priorities.md")
    status["priorities_updated"] = safe_mtime_iso(pri_path)
    status["priorities_content"] = safe_read_text(pri_path, 2000)

    # Research evaluations: count + last 10 lines
    eval_path = os.path.join(MEMORY, "research-evaluations.jsonl")
    eval_lines = safe_read_lines(eval_path)
    status["evaluation_count"] = len(eval_lines)
    status["recent_evaluations"] = [l.strip() for l in eval_lines[-10:]]

    # Self-heal log: last 2000 chars
    heal_path = os.path.join(MEMORY, "self-heal-log.md")
    status["self_heal_log"] = safe_read_text(heal_path, 2000)

    # Ops status
    ops_path = os.path.join(MEMORY, "ops-status.md")
    status["ops_status"] = safe_read_text(ops_path)

    # Log tails: last 15 lines each
    for log_path in ["/tmp/zeke-queue.log", "/tmp/zeke-reason-error.log"]:
        key = os.path.basename(log_path).replace(".log", "_tail")
        lines = safe_read_lines(log_path)
        status[key] = [l.strip() for l in lines[-15:]]

    # Cron job count
    cron_path = os.path.expanduser("~/.openclaw/cron/jobs.json")
    try:
        with open(cron_path) as f:
            data = json.load(f)
            jobs = data if isinstance(data, list) else data.get("jobs", data.get("cron", []))
            status["cron_job_count"] = len(jobs) if isinstance(jobs, list) else 0
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        status["cron_job_count"] = 0

    # Write output
    out_path = os.path.join(STATUS_DIR, "status.json")
    with open(out_path, "w") as f:
        json.dump(status, f, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    build_status()
