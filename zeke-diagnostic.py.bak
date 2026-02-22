#!/usr/bin/env python3
"""
ZEKE DIAGNOSTIC — comprehensive system state pushed to GitHub.
Run standalone or called by zeke-status-push.sh every 10 minutes.

Outputs: ~/zeke-status/diagnostic.json (pushed to GitHub)
Read:    https://github.com/mattzirkelbach-pixel/zeke-status/blob/main/diagnostic.json
"""
import json, os, subprocess, datetime, re, glob

def run(cmd, timeout=10):
    """Run shell command, return stdout."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ""

def file_lines(path):
    try:
        with open(os.path.expanduser(path)) as f:
            return sum(1 for _ in f)
    except:
        return -1

def file_tail(path, n=5):
    try:
        with open(os.path.expanduser(path)) as f:
            lines = f.readlines()
            return [l.strip() for l in lines[-n:]]
    except:
        return []

def file_age_minutes(path):
    try:
        mtime = os.path.getmtime(os.path.expanduser(path))
        return round((datetime.datetime.now().timestamp() - mtime) / 60, 1)
    except:
        return -1

# ============================================================
# 1. TIMESTAMP
# ============================================================
now = datetime.datetime.now()
now_utc = datetime.datetime.utcnow()
diag = {
    "timestamp_local": now.strftime("%Y-%m-%d %H:%M:%S ET"),
    "timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
}

# ============================================================
# 2. PROCESSES
# ============================================================
processes = {}
for name, pattern in {
    "overnight": "zeke-overnight",
    "daytime": "zeke-daytime",
    "queue": "zeke-queue",
    "reason": "zeke-reason",
    "gateway": "openclaw",
    "status_push": "zeke-status-push",
}.items():
    ps = run(f"pgrep -f '{pattern}' 2>/dev/null")
    pids = [p for p in ps.split("\n") if p.strip()] if ps else []
    processes[name] = {
        "running": len(pids) > 0,
        "pids": pids,
        "count": len(pids),
    }

diag["processes"] = processes

# ============================================================
# 3. GATEWAY
# ============================================================
gw_pid = run("pgrep -f openclaw")
diag["gateway"] = {
    "running": bool(gw_pid),
    "pid": gw_pid.split("\n")[0] if gw_pid else None,
}

# ============================================================
# 4. SPARK / GPU
# ============================================================
spark_tags = run("curl -s --max-time 5 http://10.0.0.143:11434/api/tags 2>/dev/null")
spark_ps = run("curl -s --max-time 5 http://10.0.0.143:11434/api/ps 2>/dev/null")
try:
    models_loaded = json.loads(spark_ps).get("models", [])
    loaded_names = [m.get("name", "?") for m in models_loaded]
except:
    loaded_names = []

spark_online = bool(spark_tags)
diag["spark"] = {
    "online": spark_online,
    "models_loaded": loaded_names,
}

# GPU stats via nvidia-smi on Spark
gpu_stats = run("curl -s --max-time 5 'http://10.0.0.143:11434/api/ps' 2>/dev/null")
diag["gpu"] = {
    "models_in_vram": loaded_names,
    "note": "GPU util requires nvidia-smi SSH — not available remotely",
}

# ============================================================
# 5. FEED
# ============================================================
FEED = os.path.expanduser("~/.openclaw/workspace/memory/learning-feed.jsonl")
feed_lines = file_lines(FEED)
feed_age = file_age_minutes(FEED)
feed_tail = file_tail(FEED, 5)

# Parse last entries for quality
clean_entries = 0
broken_entries = 0
last_real_timestamp = None
for line in file_tail(FEED, 50):
    if "$(date" in line:
        broken_entries += 1
    else:
        clean_entries += 1
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "")
            if ts and not ts.startswith("$(") and ts > "2026":
                last_real_timestamp = ts
        except:
            pass

diag["feed"] = {
    "total_lines": feed_lines,
    "last_modified_minutes_ago": feed_age,
    "last_real_timestamp": last_real_timestamp,
    "last_5_entries": feed_tail,
    "recent_50_clean": clean_entries,
    "recent_50_broken": broken_entries,
}

# ============================================================
# 6. CRON JOBS (OpenClaw)
# ============================================================
JOBS_PATH = os.path.expanduser("~/.openclaw/cron/jobs.json")
try:
    with open(JOBS_PATH) as f:
        jobs_data = json.load(f)
    
    enabled_jobs = []
    disabled_jobs = []
    jobs_with_date_bug = []
    duplicate_ids = []
    
    seen_ids = {}
    for j in jobs_data.get("jobs", []):
        jid = j.get("id", "?")
        name = j.get("name", "?")
        sched = j.get("schedule", {})
        cron_expr = sched.get("cron", "") or sched.get("every", "") or "none"
        msg = j.get("payload", {}).get("message", "") or ""
        
        # Check duplicates
        if jid in seen_ids:
            duplicate_ids.append({"id": jid, "name": name, "conflicts_with": seen_ids[jid]})
        seen_ids[jid] = name
        
        # Check $(date) bug (excluding "Do NOT use" instructions)
        has_date_bug = False
        for line in msg.split("\n"):
            if "$(date" in line and "Do NOT use" not in line and "Do not use" not in line:
                has_date_bug = True
                break
        
        if has_date_bug:
            jobs_with_date_bug.append(name)
        
        entry = {
            "id": jid[:8],
            "name": name,
            "schedule": cron_expr,
            "has_date_bug": has_date_bug,
            "has_absolute_paths": FEED in msg or "/Users/zekezirk" in msg,
            "prompt_length": len(msg),
        }
        
        if j.get("enabled") is False:
            disabled_jobs.append(entry)
        else:
            enabled_jobs.append(entry)
    
    diag["openclaw_crons"] = {
        "enabled": enabled_jobs,
        "enabled_count": len(enabled_jobs),
        "disabled_count": len(disabled_jobs),
        "total": len(enabled_jobs) + len(disabled_jobs),
        "jobs_with_date_bug": jobs_with_date_bug,
        "duplicate_ids": duplicate_ids,
    }
except Exception as e:
    diag["openclaw_crons"] = {"error": str(e)}

# ============================================================
# 7. CRONTAB (system)
# ============================================================
crontab = run("crontab -l 2>/dev/null")
cron_lines = [l.strip() for l in crontab.split("\n") if l.strip() and not l.strip().startswith("#")]
diag["crontab"] = {
    "active_entries": cron_lines,
    "count": len(cron_lines),
}

# ============================================================
# 8. LOCKFILES
# ============================================================
lockfiles = {}
for name, path in {
    "overnight": "/tmp/zeke-overnight.lock",
    "overnight_alt": "/tmp/overnight.lock",
    "daytime": "/tmp/zeke-daytime.lock",
    "queue": "/tmp/zeke-queue.lock",
}.items():
    exists = os.path.exists(path)
    pid = None
    stale = False
    if exists:
        try:
            with open(path) as f:
                pid = f.read().strip()
            # Check if PID is alive
            alive = run(f"kill -0 {pid} 2>/dev/null && echo alive || echo dead")
            stale = alive != "alive"
        except:
            stale = True
    lockfiles[name] = {"exists": exists, "pid": pid, "stale": stale}

diag["lockfiles"] = lockfiles

# ============================================================
# 9. LOG TAILS
# ============================================================
log_files = {
    "overnight": os.path.expanduser(f"~/logs/overnight-{now.strftime('%Y-%m-%d')}.log"),
    "daytime": os.path.expanduser(f"~/logs/daytime-{now.strftime('%Y-%m-%d')}.log"),
    "openclaw": f"/tmp/openclaw/openclaw-{now.strftime('%Y-%m-%d')}.log",
}
logs = {}
for name, path in log_files.items():
    tail = file_tail(path, 10)
    age = file_age_minutes(path)
    logs[name] = {
        "exists": os.path.exists(path),
        "last_modified_minutes_ago": age,
        "last_10_lines": tail,
    }

diag["logs"] = logs

# ============================================================
# 10. KNOWLEDGE GRAPH
# ============================================================
kg_stats = run("curl -s --max-time 5 localhost:3333/api/kg-stats 2>/dev/null")
try:
    diag["knowledge_graph"] = json.loads(kg_stats)
except:
    diag["knowledge_graph"] = {"error": "dashboard not responding or no KG stats"}

# ============================================================
# 11. OVERNIGHT SCRIPT HEALTH
# ============================================================
overnight_sh = os.path.expanduser("~/zeke-overnight.sh")
try:
    with open(overnight_sh) as f:
        content = f.read()
    has_path = "export PATH" in content and "nvm" in content
    job_ids = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', content)
    diag["overnight_script"] = {
        "has_path_export": has_path,
        "job_ids_referenced": len(set(job_ids)),
        "unique_job_ids": list(set(job_ids)),
    }
except:
    diag["overnight_script"] = {"error": "cannot read"}

# ============================================================
# 12. SCHEDULE COVERAGE
# ============================================================
# Analyze if there are gaps in the 24h schedule
diag["schedule_analysis"] = {
    "overnight": "9pm-4am (crontab 0 22, should be 0 21 after continuous.sh)",
    "queue": "4am (crontab 0 4)",
    "reason": "noon currently (crontab 0 12, should be 0 5 after continuous.sh)",
    "daytime": "8am-9pm (crontab 0 8, should be 0 6 after continuous.sh)",
    "gaps": [],
    "note": "Run zeke-continuous.sh tomorrow to close gaps. Tonight overnight is running manually.",
}

# ============================================================
# 13. HEALTH VERDICTS
# ============================================================
issues = []
if not processes["gateway"]["running"]:
    issues.append("CRITICAL: Gateway not running")
if not spark_online:
    issues.append("CRITICAL: Spark offline")
if feed_age > 60:
    issues.append(f"WARNING: Feed not updated in {feed_age:.0f} minutes")
if broken_entries > 0:
    issues.append(f"WARNING: {broken_entries} broken entries in recent feed")
if jobs_with_date_bug:
    issues.append(f"BUG: $(date) still in jobs: {', '.join(jobs_with_date_bug)}")
if duplicate_ids:
    issues.append(f"WARNING: Duplicate job IDs found")
for name, lock in lockfiles.items():
    if lock["stale"]:
        issues.append(f"WARNING: Stale lockfile: {name} (PID {lock['pid']})")
if processes["overnight"]["count"] > 1:
    issues.append(f"WARNING: {processes['overnight']['count']} overnight processes running (should be 1)")
if processes["daytime"]["count"] > 1:
    issues.append(f"WARNING: {processes['daytime']['count']} daytime processes running (should be 1)")

diag["health"] = {
    "status": "HEALTHY" if not issues else "ISSUES_FOUND",
    "issues": issues,
    "issue_count": len(issues),
}

# ============================================================
# WRITE
# ============================================================
output_path = os.path.expanduser("~/zeke-status/diagnostic.json")
with open(output_path, "w") as f:
    json.dump(diag, f, indent=2)

print(f"Diagnostic written: {output_path}")
print(f"Health: {diag['health']['status']} ({len(issues)} issues)")
for issue in issues:
    print(f"  {issue}")
print(f"Feed: {feed_lines} lines (modified {feed_age:.0f}m ago)")
print(f"Processes: " + ", ".join(f"{k}={'UP' if v['running'] else 'DOWN'}" for k, v in processes.items()))
