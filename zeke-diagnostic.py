#!/usr/bin/env python3
"""Zeke diagnostic — pushes system state to GitHub for dashboard."""
import json, os, subprocess, time, datetime

HOME = os.path.expanduser("~")
FEED = os.path.join(HOME, ".openclaw/workspace/memory/learning-feed.jsonl")
JOBS_JSON = os.path.join(HOME, ".openclaw/cron/jobs.json")
SPARK = "http://10.0.0.143:11434"

def check_process(name):
    """Check if a process matching name is running."""
    try:
        r = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True, timeout=5)
        pids = [p.strip() for p in r.stdout.strip().split("\n") if p.strip()]
        return {"running": len(pids) > 0, "pids": pids, "count": len(pids)}
    except:
        return {"running": False, "pids": [], "count": 0}

def check_spark():
    """Check Spark GPU status."""
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "10", f"{SPARK}/api/ps"],
                          capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return {"online": False, "models_loaded": [], "inference_active": False, "detail": "unreachable"}
        data = json.loads(r.stdout)
        models = [m.get("name", "?") for m in data.get("models", [])]
        
        # Check for stuck models
        stuck = False
        stuck_model = None
        for m in data.get("models", []):
            expires = m.get("expires_at", "")
            if expires:
                try:
                    exp = datetime.datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if exp < now - datetime.timedelta(minutes=20):
                        stuck = True
                        stuck_model = m.get("name", "?")
                except: pass
        
        return {
            "online": True,
            "models_loaded": models,
            "model_stuck": stuck,
            "stuck_model": stuck_model,
            "inference_active": len(models) > 0,
            "detail": f"loaded: {', '.join(models)}" if models else "idle"
        }
    except:
        return {"online": False, "models_loaded": [], "inference_active": False, "detail": "error"}

def check_feed():
    """Feed stats."""
    try:
        with open(FEED) as f:
            lines = f.readlines()
        total = len(lines)
        
        # Parse last entries
        last_entries = []
        clean = 0
        broken = 0
        for line in lines[-50:]:
            try:
                e = json.loads(line.strip())
                ts = e.get("timestamp", "")
                if ts and "$(date" not in ts and ts.startswith("202"):
                    clean += 1
                else:
                    broken += 1
            except:
                broken += 1
        
        # Format last 5
        for line in lines[-5:]:
            try:
                e = json.loads(line.strip())
                ts = (e.get("timestamp", "?"))[:19]
                topic = e.get("topic", "?")
                finding = e.get("finding", e.get("insights", ""))
                if isinstance(finding, list):
                    finding = finding[0] if finding else ""
                finding = str(finding)[:80]
                last_entries.append(f"[{ts}] {topic} — {finding}")
            except:
                last_entries.append(line.strip()[:80])
        
        mtime = os.path.getmtime(FEED)
        age = (time.time() - mtime) / 60
        
        return {
            "total_lines": total,
            "last_modified_minutes_ago": round(age, 1),
            "last_entries": last_entries,
            "recent_50_clean": clean,
            "recent_50_broken": broken,
        }
    except Exception as e:
        return {"total_lines": 0, "error": str(e)}

def read_scheduler_log():
    """Read recent scheduler log entries for activity tracking."""
    today = datetime.date.today().isoformat()
    log_path = os.path.join(HOME, "logs", f"scheduler-{today}.jsonl")
    log_path_txt = os.path.join(HOME, "logs", f"scheduler-{today}.log")
    
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
    }
    
    # Try JSON log first
    try:
        with open(log_path) as f:
            for line in f:
                try:
                    e = json.loads(line.strip())
                    event = e.get("event", "")
                    if event == "job_done" or event == "job_start":
                        activity["last_job"] = e.get("name", "?")
                        activity["last_job_time"] = e.get("ts", "?")[:19]
                    if "job" in event:
                        activity["jobs_today"] += 1
                    if event == "job_done":
                        activity["success_today"] += 1
                        activity["feed_growth_today"] += e.get("grew", 0)
                    if event == "job_timeout":
                        activity["timeout_today"] += 1
                    if event == "job_fail" or event == "job_bad_output":
                        activity["fail_today"] += 1
                    if event == "cycle_sleep":
                        secs = e.get("seconds", 0)
                        ts = e.get("ts", "")
                        activity["state"] = f"sleeping {secs}s"
                        try:
                            sleep_start = datetime.datetime.fromisoformat(ts)
                            wake = sleep_start + datetime.timedelta(seconds=secs)
                            activity["next_cycle_est"] = wake.strftime("%H:%M")
                        except: pass
                    if event == "cycle_start":
                        activity["state"] = "running cycle"
                        activity["last_cycle"] = e.get("ts", "?")[:19]
                    if event == "cycle_done":
                        activity["state"] = "cycle complete"
                except: pass
    except FileNotFoundError:
        pass
    
    # Fallback: text log
    if activity["last_job"] is None:
        try:
            with open(log_path_txt) as f:
                for line in f:
                    if "job_start" in line or "job_done" in line:
                        activity["last_job_time"] = line[:8]  # HH:MM:SS
                    if "cycle_sleep" in line:
                        activity["state"] = "sleeping between cycles"
                    if "cycle_start" in line:
                        activity["state"] = "running"
        except: pass
    
    return activity

now = datetime.datetime.now()
now_utc = datetime.datetime.utcnow()

# Build diagnostic
diag = {
    "timestamp_local": now.strftime("%Y-%m-%d %H:%M:%S ET"),
    "timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "scheduler": {
        **check_process("zeke-scheduler"),
        "type": "python",
    },
    "processes": {
        "scheduler": check_process("zeke-scheduler"),
        "guardian": {"note": "cron every 60s"},
        "gateway": check_process("openclaw"),
        "status_push": check_process("zeke-status-push"),
    },
    "gateway": {"running": check_process("openclaw")["running"]},
    "spark": check_spark(),
    "feed": check_feed(),
    "activity": read_scheduler_log(),
    "health": {"status": "HEALTHY", "issues": []},
}

# Health checks
issues = []
if not diag["scheduler"]["running"]:
    issues.append("WARNING: Python scheduler not running (guardian should restart)")
if not diag["gateway"]["running"]:
    issues.append("CRITICAL: Gateway not running")
if not diag["spark"]["online"]:
    issues.append("CRITICAL: Spark GPU offline")
if diag["spark"].get("model_stuck"):
    issues.append(f"WARNING: Stuck model: {diag['spark'].get('stuck_model')}")
feed_age = diag["feed"].get("last_modified_minutes_ago", 999)
if feed_age > 120:
    issues.append(f"WARNING: Feed not updated in {int(feed_age)}m")
broken = diag["feed"].get("recent_50_broken", 0)
if broken > 10:
    issues.append(f"WARNING: {broken} broken entries in recent feed")

diag["health"]["status"] = "HEALTHY" if not issues else "ISSUES_FOUND"
diag["health"]["issues"] = issues
diag["health"]["issue_count"] = len(issues)

# Write
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnostic.json")
with open(out, "w") as f:
    json.dump(diag, f, indent=2)

print(f"Diagnostic written: {out}")
print(f"Health: {diag['health']['status']} ({len(issues)} issues)")
if issues:
    for i in issues:
        print(f"  {i}")
print(f"Feed: {diag['feed'].get('total_lines', '?')} lines (modified {diag['feed'].get('last_modified_minutes_ago', '?')}m ago)")
sched = diag["scheduler"]
act = diag["activity"]
print(f"Scheduler: {'UP' if sched['running'] else 'DOWN'} | state={act.get('state','?')} | next={act.get('next_cycle_est','?')}")
print(f"Today: {act.get('success_today',0)} ok / {act.get('timeout_today',0)} timeout / {act.get('fail_today',0)} fail / +{act.get('feed_growth_today',0)} entries")
