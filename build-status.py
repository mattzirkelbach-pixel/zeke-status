#!/usr/bin/env python3
"""Zeke Status Bridge v3 — gateway diagnostics + feed quality + closed-loop checks."""
import json, subprocess, os, glob, sqlite3
from datetime import datetime, timezone
from pathlib import Path

# --- GPU MONITORING (added by fix-dashboard.py) ---
def probe_gpu():
    """Get GPU metrics from Spark via SSH."""
    import subprocess
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
             "zirkai@spark-7027",
             "nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,power.draw --format=csv,noheader,nounits 2>/dev/null || echo ERR"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        if output and output != 'ERR' and ',' in output:
            parts = [p.strip() for p in output.split(',')]
            temp = int(parts[0]) if parts[0].isdigit() else None
            util = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            power = parts[2] if len(parts) > 2 else None
            status = "healthy"
            if temp and temp > 85: status = "HOT"
            elif temp and temp > 75: status = "warm"
            return {"temperature_c": temp, "utilization_pct": util, "power_w": power, "status": status}
        return {"status": "unreachable", "error": output[:100]}
    except Exception as e:
        return {"status": "probe_failed", "error": str(e)[:100]}
# --- END GPU MONITORING ---


HOME = Path.home()
WORKSPACE = HOME / ".openclaw" / "workspace"
MEMORY = WORKSPACE / "memory"
STATUS_DIR = HOME / "zeke-status"
FEED = MEMORY / "learning-feed.jsonl"

def run(cmd, default=""):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else default
    except: return default

def read_file(path, default=""):
    try: return Path(path).read_text()
    except: return default

def tail_lines(path, n=15):
    try:
        lines = Path(path).read_text().strip().split('\n')
        return lines[-n:]
    except: return []

def get_gateway_config():
    try:
        with open(HOME / ".openclaw" / "openclaw.json") as f:
            cfg = json.load(f)
        gw = cfg.get('gateway', {})
        tools = cfg.get('tools', {})
        bp = tools.get('byProvider', {})
        return {
            'sessionTimeoutMs': gw.get('sessionTimeoutMs', 'NOT SET'),
            'timeoutMs': gw.get('timeoutMs', 'NOT SET'),
            'elevated': tools.get('elevated', {}),
            'byProvider': {k: {'allow': v.get('allow', []), 'count': len(v.get('allow', []))} for k, v in bp.items()},
        }
    except: return {'error': 'could not read config'}

def get_gateway_process():
    pid = run("pgrep -f 'openclaw'")
    if pid:
        return {'pid': pid, 'memory_pct': run(f"ps -p {pid} -o %mem=").strip(),
                'uptime': run(f"ps -p {pid} -o etime=").strip(), 'status': 'RUNNING'}
    return {'pid': None, 'status': 'NOT RUNNING'}

def get_spark_status():
    try:
        r = subprocess.run(['curl', '-sf', '--connect-timeout', '5', 'http://10.0.0.143:11434/api/ps'],
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            return {'status': 'ONLINE',
                    'loaded_models': [{'name': m.get('name'), 'size_gb': round(m.get('size',0)/1e9,1)}
                                     for m in data.get('models', [])]}
    except: pass
    return {'status': 'UNREACHABLE', 'loaded_models': []}

def get_feed_quality():
    issues = {'malformed_json': 0, 'literal_timestamps': 0, 'duplicates': 0, 'no_new_dev': 0, 'total': 0}
    seen = set()
    try:
        with open(FEED) as f:
            for line in f:
                line = line.strip()
                if not line: continue
                issues['total'] += 1
                if '$(date' in line: issues['literal_timestamps'] += 1
                if '"No new developments"' in line: issues['no_new_dev'] += 1
                try:
                    d = json.loads(line)
                    ins = d.get('insights', d.get('finding', d.get('content', '')))
                    ins_str = json.dumps(ins) if isinstance(ins, list) else str(ins)
                    key = f"{d.get('topic','')}|{ins_str[:200]}"
                    if key in seen: issues['duplicates'] += 1
                    seen.add(key)
                except json.JSONDecodeError: issues['malformed_json'] += 1
    except: pass
    issues['error_rate'] = round((issues['malformed_json'] + issues['literal_timestamps'] + issues['duplicates']) / max(issues['total'], 1) * 100, 1)
    return issues

def get_crontab_status():
    crontab = run("crontab -l")
    lines = crontab.split('\n')
    active = [l for l in lines if l.strip() and not l.strip().startswith('#')]
    disabled = [l for l in lines if 'MAINT_DISABLED' in l]
    return {
        'total_entries': len([l for l in lines if l.strip()]),
        'active': len(active),
        'disabled_for_maint': len(disabled),
        'has_queue': any('zeke-queue' in l for l in active),
        'has_overnight': any('overnight' in l for l in active),
        'has_reason': any('zeke-reason' in l for l in active),
        'has_status_push': any('status'  in l for l in active),
    }

def get_last_jobs():
    """Get recent jobs from cycle-history.jsonl, grouped by cycle."""
    history_file = STATUS_DIR / "cycle-history.jsonl"
    if not history_file.exists():
        return [], []

    # Read last 4 cycles that have job_details
    cycles = []
    try:
        lines = history_file.read_text().strip().split('\n')
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if "job_details" in entry and entry["job_details"]:
                    cycles.append(entry)
                    if len(cycles) >= 4:
                        break
            except:
                continue
    except:
        return [], []

    cycles.reverse()  # oldest first

    # Build flat job list (backward compat) and cycle-grouped list
    flat_jobs = []
    cycle_groups = []
    for cyc in cycles:
        ts = cyc.get("timestamp", "")
        # Parse timestamp for display
        try:
            from datetime import datetime as dt
            if "T" in ts:
                parsed = dt.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
                time_str = parsed.strftime("%-I:%M %p")
            else:
                time_str = ts
        except:
            time_str = ts[:16] if ts else "?"

        cycle_info = {
            "cycle": cyc.get("cycle", "?"),
            "window": cyc.get("window", "?"),
            "timestamp": ts,
            "time_display": time_str,
            "feed_growth": cyc.get("feed_growth", cyc.get("feed_after", 0) - cyc.get("feed_before", 0)),
            "jobs": []
        }

        for job in cyc.get("job_details", []):
            j = {
                "name": job.get("name", "?"),
                "status": job.get("status", "?"),
                "duration": job.get("duration_s", job.get("duration", 0)),
                "grew": job.get("feed_grew", job.get("feed_added", 0)),
                "issues": job.get("issues", []),
                "valid_entries": job.get("valid_entries", None),
                "broken_entries": job.get("broken_entries", None),
                "cycle_time": time_str,
                "cycle_num": cyc.get("cycle", "?"),
            }
            flat_jobs.append(j)
            cycle_info["jobs"].append(j)

        cycle_groups.append(cycle_info)

    return flat_jobs[-20:], cycle_groups

def get_kg_graph():
    """Export KG as node/link graph for D3 force-directed visualization."""
    try:
        db = sqlite3.connect(str(WORKSPACE / "memory" / "knowledge.db"))
        domain_map = {
            'treasury': 'treasury-bonds', 'treasury-bounds': 'treasury-bonds',
            '10-year_Treasury_yield': 'treasury-bonds',
            '10-year_Treasury_yield_adjustment_intervals': 'treasury-bonds',
            'senolytics': 'longevity', 'circadian biology': 'longevity', 'Longevity': 'longevity',
            'local model inference': 'tool-calling', 'tool-calling-improvements': 'tool-calling',
            'self_improvement': 'self-improvement', 'compound-synthesis': 'cross-domain',
            'cross-domain-associations': 'cross-domain', 'AI development': 'ai-agents',
            'ai-agents,longevity': 'cross-domain', 'finance-cycles': 'cross-domain',
            'spaced_repetition_intervals': 'self-improvement',
        }
        ents = db.execute('SELECT id, name, entity_type, domain, confidence FROM entities').fetchall()
        rels = db.execute('SELECT entity_a_id, entity_b_id, relationship_type, strength FROM relationships').fetchall()
        db.close()
        node_ids = {e[0] for e in ents}
        nodes = [{'id': e[0], 'name': e[1][:45], 'type': e[2] or 'concept',
                  'domain': domain_map.get(e[3], e[3] or 'unknown'), 'conf': round(e[4] or 0.8, 2)}
                 for e in ents]
        links = [{'source': r[0], 'target': r[1], 'type': r[2], 'strength': round(r[3] or 0.7, 2)}
                 for r in rels if r[0] in node_ids and r[1] in node_ids and r[0] != r[1]]
        return {'nodes': nodes, 'links': links}
    except Exception as e:
        return {'nodes': [], 'links': [], 'error': str(e)}

def get_kg_stats():
    try:
        db = sqlite3.connect(str(WORKSPACE / "memory" / "knowledge.db"))
        ent = db.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        rel = db.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
        assoc = db.execute("SELECT COUNT(*) FROM associations").fetchone()[0]
        tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        ins = db.execute("SELECT COUNT(*) FROM insights").fetchone()[0] if 'insights' in tables else 0
        domains = {}
        for row in db.execute("SELECT domain, COUNT(*) FROM entities GROUP BY domain ORDER BY COUNT(*) DESC"):
            domains[row[0]] = row[1]
        db.close()
        # GPU monitoring
        try:
            if isinstance(status, dict) and "gpu" not in status:
                status["gpu"] = probe_gpu()
        except: pass

        return f"Entities: {ent}\nRelationships: {rel}\nAssociations: {assoc}\nInsights: {ins}\nDomains: {json.dumps(domains, indent=2)}"
    except Exception as e:
        return f"Error: {e}"



def get_gpu_stats():
    """Get GPU stats from DGX Spark via SSH. Handles unified memory [N/A] fields."""
    try:
        r = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes', 'zirkai@10.0.0.143',
             'nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,power.draw,name --format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [x.strip() for x in r.stdout.strip().split(',')]
            def sf(v):
                try: return float(v)
                except: return None
            return {
                'status': 'OK',
                'gpu_util_pct': sf(parts[0]) if len(parts) > 0 else None,
                'temp_c': sf(parts[1]) if len(parts) > 1 else None,
                'power_w': sf(parts[2]) if len(parts) > 2 else None,
                'gpu_name': parts[3].strip() if len(parts) > 3 else 'unknown',
            }
        return {'status': 'SSH_OK_NO_DATA', 'raw': r.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {'status': 'SSH_TIMEOUT'}
    except Exception as e:
        return {'status': 'ERROR', 'error': str(e)[:200]}

now = datetime.now(timezone.utc)

_flat_jobs, _cycle_groups = get_last_jobs()

status = {
    'timestamp': now.isoformat(),
    'feed_lines': int(run(f"wc -l < '{FEED}'", "0")),
    'recent_feed': tail_lines(FEED, 15),
    'kg_stats': get_kg_stats(),
    'last_synthesis': sorted(glob.glob(str(MEMORY / "daily-synthesis-*.md")))[-1].split('/')[-1] if glob.glob(str(MEMORY / "daily-synthesis-*.md")) else None,
    'synthesis_content': read_file(sorted(glob.glob(str(MEMORY / "daily-synthesis-*.md")))[-1])[:3000] if glob.glob(str(MEMORY / "daily-synthesis-*.md")) else "",
    'priorities_updated': datetime.fromtimestamp(os.path.getmtime(MEMORY / "research-priorities.md"), tz=timezone.utc).isoformat() if (MEMORY / "research-priorities.md").exists() else None,
    'priorities_content': read_file(MEMORY / "research-priorities.md")[:2000],
    'gpu_stats': get_gpu_stats(),
    'gateway_config': get_gateway_config(),
    'gateway_process': get_gateway_process(),
    'spark_status': get_spark_status(),
    'feed_quality': get_feed_quality(),
    'crontab_status': get_crontab_status(),
    'last_jobs': _flat_jobs,
    'recent_cycles': _cycle_groups,
    'evaluation_count': int(run(f"wc -l < '{MEMORY}/research-evaluations.jsonl'", "0")),
    'recent_evaluations': tail_lines(MEMORY / "research-evaluations.jsonl", 10),
    'self_heal_log': read_file(MEMORY / "self-heal-log.md")[:2000],
    'ops_status': read_file(MEMORY / "ops-status.md")[:2000],
    'zeke-queue_tail': tail_lines('/tmp/zeke-queue.log', 15),
    'zeke-reason-error_tail': tail_lines('/tmp/zeke-reason-error.log', 10),
    'cron_job_count': int(run("crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$' | wc -l", "0")),
    'strategic_context': read_file(MEMORY / "claude-strategic-context.md")[:3000],
}

with open(STATUS_DIR / "status.json", 'w') as f:
    json.dump(status, f, indent=2)

with open(STATUS_DIR / "kg_graph.json", 'w') as f:
    json.dump(get_kg_graph(), f)


history_entry = {
    'timestamp': now.isoformat(),
    'feed_lines': status['feed_lines'],
    'gateway_status': status['gateway_process']['status'],
    'gateway_timeout_ms': status['gateway_config'].get('sessionTimeoutMs', 'unknown'),
    'spark_status': status['spark_status']['status'],
    'gpu_util_pct': status.get('gpu_stats',{}).get('gpu_util_pct', None),
    'gpu_temp_c': status.get('gpu_stats',{}).get('temp_c', None),
    'feed_error_rate': status['feed_quality']['error_rate'],
    'kg_entities': int(status['kg_stats'].split('Entities: ')[1].split('\n')[0]) if 'Entities: ' in str(status['kg_stats']) else 0,
}
with open(STATUS_DIR / "history.jsonl", 'a') as f:
    f.write(json.dumps(history_entry) + '\n')

print(f"Status built. Feed: {status['feed_lines']} | Gateway: {status['gateway_process']['status']} (timeout: {status['gateway_config'].get('sessionTimeoutMs','?')}ms) | Spark: {status['spark_status']['status']} | Feed errors: {status['feed_quality']['error_rate']}%")
