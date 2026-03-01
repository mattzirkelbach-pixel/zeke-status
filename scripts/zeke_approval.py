#!/usr/bin/env python3
"""
zeke-approval.py — Human-in-the-loop approval queue
Autonomous agents queue decisions needing human sign-off.
Claude surfaces them at session start. Human decides in chat.
"""

import json, uuid, datetime
from pathlib import Path
from typing import Optional

APPROVAL_FILE = Path.home() / ".openclaw/workspace/memory/pending-approvals.json"
APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)

VALID_TYPES = {"domain_add","domain_remove","threshold_change",
               "remediation","data_action","trade_signal","script_deploy","custom"}

def _load():
    if not APPROVAL_FILE.exists(): return []
    try: return json.loads(APPROVAL_FILE.read_text())
    except: return []

def _save(approvals): APPROVAL_FILE.write_text(json.dumps(approvals, indent=2))

def _now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def _expire_stale(approvals):
    now = datetime.datetime.now(datetime.timezone.utc)
    changed = False
    for a in approvals:
        if a["status"] == "pending" and a.get("expires_at"):
            exp = datetime.datetime.fromisoformat(a["expires_at"])
            if now > exp:
                a["status"] = "expired"
                a["resolved_at"] = _now()
                a["resolved_by"] = "auto-expired"
                changed = True
    if changed: _save(approvals)
    return approvals

def request_approval(title, description, type="custom", source="unknown",
                     context=None, consequences=None, priority=5, expires_hours=72):
    if type not in VALID_TYPES:
        raise ValueError(f"Unknown type '{type}'")
    approvals = _expire_stale(_load())
    approval_id = str(uuid.uuid4())[:8]
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = (now + datetime.timedelta(hours=expires_hours)).isoformat()
    entry = {
        "id": approval_id,
        "created_at": now.isoformat(),
        "expires_at": expires_at,
        "status": "pending",
        "priority": max(1, min(10, priority)),
        "type": type,
        "source": source,
        "title": title,
        "description": description,
        "context": context or {},
        "consequences": consequences or {
            "approve": "Proceed with the proposed action.",
            "reject": "Skip. Re-evaluate next cycle."
        },
        "resolved_at": None,
        "resolution": None,
        "resolved_by": None,
        "notes": None
    }
    approvals.append(entry)
    _save(approvals)
    print(f"[APPROVAL] Queued [{approval_id}] P{priority} | {title}")
    return approval_id

def resolve_approval(approval_id, resolution, resolved_by="human", notes=None):
    if resolution not in ("approved","rejected","deferred"):
        raise ValueError("resolution must be approved/rejected/deferred")
    approvals = _load()
    for a in approvals:
        if a["id"] == approval_id:
            if a["status"] != "pending":
                print(f"[APPROVAL] {approval_id} already {a['status']}")
                return False
            a["status"] = resolution
            a["resolved_at"] = _now()
            a["resolved_by"] = resolved_by
            a["notes"] = notes
            _save(approvals)
            print(f"[APPROVAL] Resolved [{approval_id}]: {resolution} by {resolved_by}")
            return True
    print(f"[APPROVAL] Not found: {approval_id}")
    return False

def check_approved(approval_id):
    for a in _expire_stale(_load()):
        if a["id"] == approval_id:
            return a["status"] == "approved"
    return False

def check_rejected(approval_id):
    for a in _load():
        if a["id"] == approval_id:
            return a["status"] == "rejected"
    return False

def get_pending(priority_min=1):
    pending = [a for a in _expire_stale(_load()) if a["status"]=="pending" and a["priority"]>=priority_min]
    return sorted(pending, key=lambda x: -x["priority"])

def get_all(status=None):
    approvals = _expire_stale(_load())
    return [a for a in approvals if not status or a["status"]==status]

def summary():
    approvals = _expire_stale(_load())
    pending = [a for a in approvals if a["status"]=="pending"]
    return {
        "total": len(approvals),
        "pending": len(pending),
        "top_pending": [
            {"id":a["id"],"priority":a["priority"],"type":a["type"],
             "title":a["title"][:60],"source":a["source"],
             "expires_at":a.get("expires_at","")[:16]}
            for a in sorted(pending, key=lambda x: -x["priority"])[:5]
        ]
    }

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args or args[0] == "pending":
        pending = get_pending()
        if not pending:
            print("No pending approvals.")
        else:
            print(f"\n{'='*60}\nPENDING APPROVALS ({len(pending)})\n{'='*60}")
            for a in pending:
                print(f"\n[{a['id']}] P{a['priority']} | {a['type']} | from {a['source']}")
                print(f"  TITLE:   {a['title']}")
                print(f"  DESC:    {a['description'][:120]}")
                print(f"  APPROVE: {a['consequences'].get('approve','')[:80]}")
                print(f"  REJECT:  {a['consequences'].get('reject','')[:80]}")
                print(f"  EXPIRES: {a.get('expires_at','')[:16]}")
    elif args[0] == "resolve" and len(args) >= 3:
        resolve_approval(args[1], args[2], resolved_by="cli", notes=args[3] if len(args)>3 else None)
    elif args[0] == "all":
        for a in get_all(): print(f"[{a['id']}] {a['status']:10} P{a['priority']} {a['title'][:50]}")
    elif args[0] == "summary":
        print(json.dumps(summary(), indent=2))
    else:
        print("Usage: zeke-approval.py [pending|all|summary|resolve <id> <approved|rejected|deferred> [notes]]")
