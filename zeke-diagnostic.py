#!/usr/bin/env python3
"""Zeke diagnostic v3 — hardware probing, feed history, cost tracking."""
import json, os, subprocess, time, datetime

HOME = os.path.expanduser("~")
FEED = os.path.join(HOME, ".openclaw/workspace/memory/learning-feed.jsonl")
JOBS_JSON = os.path.join(HOME, ".openclaw/cron/jobs.json")
SPARK = "http://10.0.0.143:11434"
DIAG_OUT = os.path.join(HOME, "zeke-status/diagnostic.json")
HISTORY_FILE = os.path.join(HOME, "zeke-status/feed-history.json")

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
        return r.stdout.strip()
    except:
        return ""

def check_process(name):
    try:
        r = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True, timeout=5)
        pids = [p.strip() for p in r.stdout.strip().split("\n") if p.strip()]
        return {"running": len(pids) > 0, "pids": pids, "count": len(pids)}
    except:
        return {"running": False, "pids": [], "count": 0}

def utc_to_et(ts_str):
    """Convert UTC timestamp string to ET display."""
    try:
        if not ts_str or "$(date" in ts_str:
            return ts_str
        # Parse various formats
        for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S+00:00"]:
            try:
                dt = datetime.datetime.strptime(ts_str[:19], fmt[:len(ts_str[:19])+2].replace("Z",""))
                # UTC to ET (EST = -5, EDT = -4) — use -5 for Feb
                et = dt - datetime.timedelta(hours=5)
                return et.strftime("%m/%d %I:%M%p ET").lstrip("0").replace(" 0", " ")
            except:
                continue
        return ts_str[:19]
    except:
        return ts_str

def check_spark():
    """Deep Spark probe — models, VRAM estimate, response time."""
    result = {
        "online": False,
        "models_loaded": [],
        "model_stuck": False,
        "inference_active": False,
        "detail": "unreachable",
        "response_ms": None,
        "vram_estimate_gb": None,
        "model_params": None,
        "model_quant": None,
    }
    try:
        # Probe /api/ps with timing
        start = time.time()
        r = subprocess.run(
            ["curl", "-s", "--max-time", "10", f"{SPARK}/api/ps"],
            capture_output=True, text=True, timeout=15
        )
        latency = round((time.time() - start) * 1000)
        
        if r.returncode != 0:
            return result
        
        data = json.loads(r.stdout)
        models = data.get("models", [])
        model_names = [m.get("name", "?") for m in models]
        
        result["online"] = True
        result["models_loaded"] = model_names
        result["response_ms"] = latency
        result["inference_active"] = len(models) > 0
        
        # Extract model details
        for m in models:
            size_bytes = m.get("size", 0)
            size_vram = m.get("size_vram", 0)
            details = m.get("details", {})
            
            if size_vram > 0:
                result["vram_estimate_gb"] = round(size_vram / (1024**3), 1)
            elif size_bytes > 0:
                result["vram_estimate_gb"] = round(size_bytes / (1024**3), 1)
            
            result["model_params"] = details.get("parameter_size", "")
            result["model_quant"] = details.get("quantization_level", "")
            
            # Check stuck
            expires = m.get("expires_at", "")
            if expires:
                try:
                    exp = datetime.datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if exp < now - datetime.timedelta(minutes=20):
                        result["model_stuck"] = True
                except: pass
        
        detail_parts = []
        if model_names:
            detail_parts.append(", ".join(model_names))
        if result["vram_estimate_gb"]:
            detail_parts.append(f"{result['vram_estimate_gb']}GB VRAM")
        if result["model_params"]:
            detail_parts.append(result["model_params"])
        if result["model_quant"]:
            detail_parts.append(result["model_quant"])
        detail_parts.append(f"{latency}ms")
        result["detail"] = " • ".join(detail_parts)
        
    except Exception as e:
        result["detail"] = f"error: {str(e)[:50]}"
    
    return result

def check_feed():
    """Feed analysis with ET-converted timestamps."""
    try:
        with open(FEED) as f:
            lines = f.readlines()
        total = len(lines)
        
        clean = 0
        broken = 0
        trivial = 0
        topics = {}
        
        for line in lines[-50:]:
            try:
                e = json.loads(line.strip())
                ts = e.get("timestamp", "")
                finding = str(e.get("finding", e.get("insights", "")))
                topic = e.get("topic", "unknown")
                
                if not ts or "$(date" in ts or not ts.startswith("202"):
                    broken += 1
                elif "no new" in finding.lower() or "no developments" in finding.lower() or len(finding) < 20:
                    trivial += 1
                else:
                    clean += 1
                
                topics[topic] = topics.get(topic, 0) + 1
            except:
                broken += 1
        
        # Format last 5 with ET timestamps
        last_entries = []
        for line in lines[-5:]:
            try:
                e = json.loads(line.strip())
                ts_raw = e.get("timestamp", "?")
                ts_et = utc_to_et(ts_raw)
                topic = e.get("topic", "?")
                finding = e.get("finding", e.get("insights", ""))
                if isinstance(finding, list):
                    finding = finding[0] if finding else ""
                finding = str(finding)[:80]
                is_trivial = "no new" in finding.lower() or len(finding) < 20
                marker = " ⚠" if is_trivial else ""
                last_entries.append(f"[{ts_et}] {topic} — {finding}{marker}")
            except:
                last_entries.append(line.strip()[:80])
        
        mtime = os.path.getmtime(FEED)
        age = (time.time() - mtime) / 60
        
        return {
            "total_lines": total,
            "last_modified_minutes_ago": round(age, 1),
            "last_entries": last_entries,
            "recent_50_clean": clean,
            "recent_50_trivial": trivial,
            "recent_50_broken": broken,
            "topic_distribution": dict(sorted(topics.items(), key=lambda x: -x[1])[:6]),
        }
    except Exception as e:
        return {"total_lines": 0, "error": str(e)}

def read_scheduler_log():
    """Parse scheduler log for activity + cost tracking."""
    today = datetime.date.today().isoformat()
    log_path = os.path.join(HOME, "logs", f"scheduler-{today}.jsonl")
    
    activity = {
        "last_job": None, "last_job_time": None, "last_cycle": None,
        "jobs_today": 0, "success_today": 0, "timeout_today": 0, "fail_today": 0,
        "feed_growth_today": 0, "state": "unknown", "next_cycle_est": None,
        "cycle_count": 0, "sonnet_calls": 0, "estimated_cost": 0.0,
    }
    
    job_events = set()
    
    try:
        with open(log_path) as f:
            for line in f:
                try:
                    e = json.loads(line.strip())
                    event = e.get("event", "")
                    
                    # Track unique jobs (not double-count start+done)
                    job_key = e.get("name", "") + "-" + str(e.get("ts", ""))[:16]
                    
                    if event == "job_start":
                        activity["last_job"] = e.get("name", "?")
                        activity["last_job_time"] = utc_to_et(e.get("ts", "?")[:19])
                    if event == "job_done":
                        if job_key not in job_events:
                            activity["success_today"] += 1
                            job_events.add(job_key)
                        activity["feed_growth_today"] += e.get("grew", 0)
                    if event == "job_timeout":
                        if job_key not in job_events:
                            activity["timeout_today"] += 1
                            job_events.add(job_key)
                    if event in ("job_fail", "job_bad_output"):
                        if job_key not in job_events:
                            activity["fail_today"] += 1
                            job_events.add(job_key)
                    if event == "cycle_sleep":
                        secs = e.get("seconds", 0)
                        ts = e.get("ts", "")
                        activity["state"] = f"sleeping ({secs//60}min)"
                        try:
                            sleep_start = datetime.datetime.fromisoformat(ts.replace("Z","+00:00"))
                            wake = sleep_start + datetime.timedelta(seconds=secs)
                            wake_et = wake - datetime.timedelta(hours=5)
                            activity["next_cycle_est"] = wake_et.strftime("%I:%M%p").lstrip("0")
                        except: pass
                    if event == "cycle_start":
                        activity["state"] = "running"
                        activity["cycle_count"] += 1
                        activity["last_cycle"] = utc_to_et(e.get("ts", "?")[:19])
                    if event == "cycle_done":
                        activity["state"] = "cycle complete"
                    if event == "heartbeat":
                        if activity["state"] not in ("running",):
                            activity["state"] = "idle (heartbeat)"
                except: pass
    except FileNotFoundError:
        pass
    
    activity["jobs_today"] = len(job_events)
    
    # Cost: count any Sonnet usage in gateway logs
    try:
        gw_log = os.path.join(HOME, ".openclaw/logs/gateway.log")
        if os.path.exists(gw_log):
            today_str = datetime.date.today().isoformat()
            sonnet_count = 0
            with open(gw_log) as f:
                for line in f:
                    if today_str in line and "sonnet" in line.lower():
                        sonnet_count += 1
            activity["sonnet_calls"] = sonnet_count
            activity["estimated_cost"] = round(sonnet_count * 0.12, 2)
    except: pass
    
    return activity

def update_feed_history(feed_count):
    """Append to persistent feed history file."""
    now = datetime.datetime.now()
    point = {
        "t": int(now.timestamp() * 1000),
        "v": feed_count,
        "l": now.strftime("%I:%M%p").lstrip("0"),
    }
    
    history = []
    try:
        with open(HISTORY_FILE) as f:
            history = json.load(f)
    except: pass
    
    # Don't add duplicate if same value within 2 min
    if history and abs(history[-1]["t"] - point["t"]) < 120000 and history[-1]["v"] == point["v"]:
        return history
    
    history.append(point)
    # Keep last 288 points (24 hours at 5-min intervals)
    history = history[-288:]
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)
    
    return history

# ============================================================
# BUILD DIAGNOSTIC
# ============================================================
now = datetime.datetime.now()
now_utc = datetime.datetime.utcnow()

spark = check_spark()
feed = check_feed()
activity = read_scheduler_log()
scheduler = check_process("zeke-scheduler")
gateway_proc = check_process("openclaw")
feed_history = update_feed_history(feed.get("total_lines", 0))

diag = {
    "timestamp_local": now.strftime("%Y-%m-%d %I:%M:%S%p ET").replace(" 0", " "),
    "timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "scheduler": {**scheduler, "type": "python"},
    "gateway": {"running": gateway_proc["running"]},
    "spark": spark,
    "feed": feed,
    "activity": activity,
    "feed_history": feed_history,
    "cost": {
        "model": "spark/qwen3-32b-32k (local, $0)",
        "sonnet_calls_today": activity["sonnet_calls"],
        "estimated_cost_today": activity["estimated_cost"],
        "is_zero_cost": activity["estimated_cost"] == 0,
    },
    "automation": {
        "layer1": {
            "name": "Execution",
            "status": "DEPLOYED",
            "items": [
                {"name": "Python scheduler", "done": True},
                {"name": "Guardian auto-restart", "done": True},
                {"name": "Quality gate (feed validation)", "done": True},
                {"name": "Spark health probe", "done": True},
                {"name": "Structured JSON logging", "done": True},
                {"name": "5-min diagnostic push", "done": True},
            ],
        },
        "layer2": {
            "name": "Oversight",
            "status": "IN PROGRESS",
            "items": [
                {"name": "Dashboard with live metrics", "done": True},
                {"name": "Feed history tracking", "done": True},
                {"name": "Health issue detection", "done": True},
                {"name": "Prompt quality supervisor", "done": False},
                {"name": "Auto-dedup feed cleaner", "done": False},
                {"name": "Performance trend analysis", "done": False},
            ],
        },
        "layer3": {
            "name": "Intelligence",
            "status": "PLANNED",
            "items": [
                {"name": "Cross-topic synthesis", "done": False},
                {"name": "Research priority optimization", "done": False},
                {"name": "Autonomous prompt evolution", "done": False},
                {"name": "Insight quality scoring", "done": False},
                {"name": "Telegram digest generation", "done": False},
            ],
        },
    },
    "health": {"status": "HEALTHY", "issues": []},
}

# Health checks
issues = []
if not scheduler["running"]:
    issues.append("WARNING: Scheduler not running")
if not gateway_proc["running"]:
    issues.append("CRITICAL: Gateway not running")
if not spark["online"]:
    issues.append("CRITICAL: Spark offline")
if spark.get("model_stuck"):
    issues.append("WARNING: Model stuck on Spark")
if feed.get("last_modified_minutes_ago", 999) > 120:
    issues.append(f"WARNING: Feed stale ({int(feed['last_modified_minutes_ago'])}m)")
if feed.get("recent_50_broken", 0) > 5:
    issues.append(f"WARNING: {feed['recent_50_broken']} broken entries in recent feed")
if feed.get("recent_50_trivial", 0) > 10:
    issues.append(f"WARNING: {feed['recent_50_trivial']} trivial entries in recent feed")
if spark.get("response_ms") and spark["response_ms"] > 5000:
    issues.append(f"WARNING: Spark slow ({spark['response_ms']}ms)")

diag["health"]["status"] = "HEALTHY" if not issues else ("CRITICAL" if any("CRITICAL" in i for i in issues) else "ISSUES_FOUND")
diag["health"]["issues"] = issues
diag["health"]["issue_count"] = len(issues)

with open(DIAG_OUT, "w") as f:
    json.dump(diag, f, indent=2)

print(f"Diagnostic written: {DIAG_OUT}")
print(f"Health: {diag['health']['status']}")
print(f"Feed: {feed.get('total_lines', '?')} | Spark: {spark.get('detail','?')} | Cost: ${activity['estimated_cost']}")
