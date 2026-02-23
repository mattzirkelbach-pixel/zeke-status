#!/usr/bin/env python3
"""Compute activity metrics from scheduler logs for dashboard."""
import json, re, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

HOME = Path.home()
SCHED_LOG = Path("/tmp/scheduler.log")
DIAG = HOME / "zeke-status/diagnostic.json"
LOG_DIR = HOME / "zeke-status/logs"

def compute_activity():
    """Parse scheduler console log to compute today's activity."""
    activity = {
        "last_job": None,
        "last_job_time": None,
        "last_cycle": None,
        "jobs_today": 0,
        "success_today": 0,
        "timeout_today": 0,
        "fail_today": 0,
        "feed_growth_today": 0,
        "state": "unknown",
        "next_cycle_est": None,
        "cycle_count": 0,
        "sonnet_calls": 0,
        "estimated_cost": 0.0,
    }
    
    if not SCHED_LOG.exists():
        return activity
    
    today = datetime.now().strftime("%Y-%m-%d")
    lines = SCHED_LOG.read_text().strip().split("\n")
    
    # Track today's activity from log
    for line in lines:
        # Extract timestamp
        ts_match = re.match(r"\[(\d{2}:\d{2}:\d{2})\]", line)
        if not ts_match:
            continue
        
        ts = ts_match.group(1)
        
        if "job_start" in line:
            activity["jobs_today"] += 1
            m = re.search(r"name=(\S+)", line)
            if m:
                activity["last_job"] = m.group(1)
                activity["last_job_time"] = ts
                activity["state"] = "running"
        
        elif "job_done" in line or "job_empty" in line:
            activity["success_today"] += 1
            activity["state"] = "idle"
            m = re.search(r"grew=(\d+)", line)
            if m:
                activity["feed_growth_today"] += int(m.group(1))
        
        elif "job_timeout" in line:
            activity["timeout_today"] += 1
            activity["state"] = "idle"
        
        elif "job_bad_output" in line:
            activity["fail_today"] += 1
            activity["state"] = "idle"
        
        elif "cycle_done" in line:
            activity["cycle_count"] += 1
            m = re.search(r"grew=(\d+)", line)
            if m:
                pass  # Already counted per-job
            activity["last_cycle"] = ts
            activity["state"] = "between_cycles"
        
        elif "cycle_start" in line:
            activity["state"] = "cycling"
        
        elif "cycle_sleep" in line:
            activity["state"] = "sleeping"
            m = re.search(r"seconds=(\d+)", line)
            if m:
                secs = int(m.group(1))
                now = datetime.now()
                est = now + timedelta(seconds=secs)
                activity["next_cycle_est"] = est.strftime("%H:%M")
    
    return activity


def update_diagnostic():
    """Merge computed activity into diagnostic.json."""
    activity = compute_activity()
    
    diag = {}
    if DIAG.exists():
        try:
            diag = json.load(open(DIAG))
        except:
            pass
    
    diag["activity"] = activity
    
    with open(DIAG, "w") as f:
        json.dump(diag, f, indent=2)


if __name__ == "__main__":
    update_diagnostic()
    activity = json.load(open(DIAG)).get("activity", {})
    jobs = activity.get("jobs_today", 0)
    ok = activity.get("success_today", 0)
    rate = (ok / jobs * 100) if jobs > 0 else 0
    print(f"Activity: {jobs} jobs, {ok} success ({rate:.0f}%), "
          f"{activity.get('timeout_today', 0)} timeouts, "
          f"{activity.get('fail_today', 0)} fails, "
          f"state={activity.get('state', '?')}")
