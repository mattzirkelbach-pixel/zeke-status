#!/usr/bin/env python3
"""
morning_briefing.py — Local replacement for Cowork morning-alpha-briefing task.
Reads: latest_prices, cycle_state, positions, tv_signals_latest, deferred-alerts,
options-risk-dashboard. Generates briefing using templates + data logic. No LLM.
Sends via Telegram.

v2 rebuild 2026-08-18 (Matt: "this is still garbage — real alpha, actionable
setups"). Principles enforced by tests/test_morning_briefing_v2.py:
  1. Every section earns its place — empty sections render NOTHING, not
     "No new hypotheses today." filler.
  2. Deterministic SETUPS & TRIGGERS section is the core: CF signal + price
     vs 10-SMA + cycle-day gate + overnight top-fires, each line ending in an
     explicit action verb, tied to actual holdings from positions.json.
  3. Overnight digest is deduped on a digit-stripped key (the old first-90-chars
     key let 11 near-identical PRE-MARKET ALL CLEARs through because the gold
     price differed), HTML-stripped, and never repeats content promoted into
     SETUPS or POSITION RISK.
  4. Stale cycle anchors (SPX day 155 of a 36-44 window) say "count stale",
     not "PAST WINDOW" — a day count 3x past the window is a broken anchor,
     not information.
  5. Camel theses truncate at sentence/word boundaries, never mid-word.
  6. OTM watch lines are filtered against positions.json closed status
     (the AMZN $265C "EXIT still recommended" was a closed position).
"""
import json
import re
import sys
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

# ── Alert dispatcher (central send + cooldown gateway) ──────────────────
_PORTFOLIO_DIR = Path.home() / "zeke-portfolio"
_SCRIPTS_DIR = _PORTFOLIO_DIR / "scripts"
if str(_PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(_PORTFOLIO_DIR))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from alert_dispatcher import send_alert

# ── Paths ───────────────────────────────────────────────────────────────
HOME = Path.home()
PORTFOLIO = HOME / "zeke-portfolio"
STATE = PORTFOLIO / "state"
LOGS = HOME / "zeke-status" / "logs"

LATEST_PRICES  = STATE / "latest_prices.json"
CYCLE_STATE    = STATE / "cycle_state.json"
ALPHA_IDEAS    = STATE / "alpha-ideas.json"
POSITIONS      = STATE / "positions.json"
SIGNALS_LATEST = STATE / "tv_signals_latest.json"
BRIEFING_STATE = STATE / "morning-briefing-state.json"
BRIEFING_MD    = STATE / "morning-alpha.md"
ESCALATIONS    = STATE / "morning-briefing-escalations.jsonl"
DEFERRED       = STATE / "deferred-alerts.jsonl"
OPTIONS_RISK   = STATE / "options-risk-dashboard.json"
OTM_SUPPRESS   = STATE / "otm-suppression.json"
RESEARCH_QUEUE = STATE / "research-briefing-queue.jsonl"

LOG_FILE = LOGS / "morning-briefing.log"

# ── Logging ─────────────────────────────────────────────────────────────
def is_weekend():
    return datetime.now().weekday() >= 5

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── Helpers ─────────────────────────────────────────────────────────────
def esc(s: str) -> str:
    """HTML-escape for Telegram HTML parse mode."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception as e:
        log(f"WARN: could not load {path.name}: {e}")
        return {}

def fmt_price(p) -> str:
    if p is None:
        return "N/A"
    return f"${float(p):,.2f}"

def fmt_pct(p) -> str:
    if p is None:
        return ""
    return f"{float(p):+.2f}%"

def strip_html(s: str) -> str:
    """Flatten alert HTML to plain text: drop tags, collapse whitespace."""
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()

def word_trunc(s: str, limit: int) -> str:
    """Truncate at a word boundary, preferring a sentence boundary, with
    ellipsis only when something was actually cut. Never mid-word (the old
    [:120] slice printed 'September 21st wit')."""
    s = (s or "").strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    dot = cut.rfind(". ")
    if dot >= int(limit * 0.5):
        return cut[: dot + 1]
    sp = cut.rfind(" ")
    if sp > 0:
        cut = cut[:sp]
    return cut.rstrip(",;:") + "…"

def normalize_key(msg: str) -> str:
    """Dedup key for deferred alerts: HTML-stripped, digits removed.
    Two ALL CLEARs that differ only by gold trading $4,444 vs $4,450 must
    collapse to one key (the 2026-08-18 briefing carried 4 of them)."""
    return re.sub(r"\d+", "#", strip_html(msg)).lower()[:120]

# ── Rate limit — delegated to dispatcher STATUS 24 h cooldown ────────────
_BRIEFING_COOLDOWN_KEY = "morning_briefing_daily"

def already_sent_today() -> bool:
    """True if morning_briefing already sent on today's local calendar date.

    Date-based, not a plain elapsed-minutes check against the dispatcher's
    generic 1440-min (24h) STATUS cooldown: this cron fires at a fixed clock
    time every weekday, so if yesterday's send was delayed even a few
    seconds past today's fire time (retries, an oversized-payload trim, a
    slow build), elapsed-since-last-send falls just under 24h and
    check_cooldown() reports "still on cooldown" -- a false-positive skip.
    Confirmed root cause of 5 silent misses in 30 days (2026-07-21, 07-23,
    07-29, 08-07, 08-11): every one had a prior-day send timestamped
    later-in-second than the next fire, e.g. 07-22 10:36:01 (retried after a
    4096-char Telegram cap failure) starved 07-23's 10:30:00 cron of a few
    seconds. Comparing calendar dates instead of elapsed minutes is immune
    to that jitter while still enforcing one send per day.
    """
    try:
        cd = json.loads((STATE / "alert-cooldowns.json").read_text())
    except Exception:
        return False
    ts = cd.get(_BRIEFING_COOLDOWN_KEY)
    if not ts:
        return False
    try:
        last = datetime.fromisoformat(ts)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        last_local_date = last.astimezone().date()
    except Exception:
        return False
    return last_local_date == datetime.now().date()

# ── Cycle theory windows ────────────────────────────────────────────────
# Timing windows come from decisions/cycle_theory.py — the ONE canonical source
# (PDF Table 1 + Camel's ±10% tolerance). TLT/GDX/SILJ have NO Camel-specified
# window, so they render without a fabricated one.
_CT_IMPORT_ERR = None
try:
    sys.path.insert(0, str(_PORTFOLIO_DIR / "decisions"))
    from cycle_theory import cycle_params as _cycle_params
except Exception as _e:  # pragma: no cover - degrade gracefully, never crash
    _CT_IMPORT_ERR = _e
    _cycle_params = None

# A count this far past the window's high edge is a broken anchor, not a
# late cycle. SPX "day 155/36-44" carries zero timing information.
STALE_COUNT_GRACE = 15

def day_status(inst: str, day: int, cs: dict) -> str:
    entry = cs.get(inst, {})
    if entry.get("dcl_confirmed", False):
        return "DCL CONFIRMED"
    if _cycle_params is None:
        log(f"WARN: cycle_theory import failed ({_CT_IMPORT_ERR}); day-count only")
        return f"d{day}"
    p = _cycle_params(inst)
    w = p.get("daily_window")
    if not w:
        return f"d{day} (no CF window)"
    lo, hi = w
    if day > hi + STALE_COUNT_GRACE:
        return f"count stale ({day}d)"
    if day > hi:
        return f"LATE d{day}/{lo}-{hi}"
    if day >= lo:
        return f"IN WINDOW d{day}/{lo}-{hi}"
    return f"d{day}/{lo}-{hi}"

def _window_for(inst: str):
    if _cycle_params is None:
        return None
    try:
        return _cycle_params(inst).get("daily_window")
    except Exception:
        return None

# ── Section builders ────────────────────────────────────────────────────
SNAPSHOT_ROWS = [
    ("XAUUSD", "GLD"), ("SLV", "SLV"), ("GDX", "GDX"),
    ("SPX", "SPX"), ("BTC", "BTC"), ("TLT", "TLT"),
]

def snapshot_line(inst: str, tick: str, prices: dict, cs: dict) -> str:
    p = prices.get("tickers", {}).get(tick, {})
    price = p.get("last_close")
    sma10 = p.get("sma_10")
    rsi = p.get("rsi_14")
    ci = cs.get(inst, cs.get(tick, {}))
    day = int(ci.get("daily_day", 0) or 0)
    parts = [f"{tick} {fmt_price(price)} ({fmt_pct(p.get('daily_change_pct'))})",
             day_status(inst, day, cs)]
    if price is not None and sma10:
        arrow = "↑" if float(price) >= float(sma10) else "↓"
        parts.append(f"{arrow}10SMA {fmt_price(sma10)}")
    if rsi is not None:
        parts.append(f"RSI {float(rsi):.0f}")
    return "• " + esc(" | ".join(parts))

def build_snapshot(prices: dict, cs: dict) -> list:
    lines = [snapshot_line(inst, tick, prices, cs) for inst, tick in SNAPSHOT_ROWS]
    t = prices.get("tickers", {})
    macro = []
    vix = t.get("VIX", {}).get("last_close")
    dxy = t.get("DXY", {}).get("last_close")
    crude = t.get("CRUDE", {}).get("last_close")
    if vix is not None:
        macro.append(f"VIX {float(vix):.1f}")
    if dxy is not None:
        macro.append(f"DXY {float(dxy):.1f}")
    if crude is not None:
        macro.append(f"Crude ${float(crude):.0f}")
    if macro:
        lines.append("• " + esc(" | ".join(macro)))
    return lines

_THESIS_INSTRUMENTS = [("XAUUSD", "Gold"), ("SPX", "SPX"), ("TLT", "TLT")]

def build_camel_theses(cs: dict) -> list:
    lines = []
    for inst, label in _THESIS_INSTRUMENTS:
        read = (cs.get(inst, {}) or {}).get("camel_read", "")
        if not read:
            continue
        m = re.match(r"Phase:\s*(\w+)\.?\s*(.*)", read, re.DOTALL)
        if m:
            phase = m.group(1).replace("_", " ")
            rest = m.group(2).strip()
            text = f"{label} ({phase}): {rest}" if rest else f"{label}: {phase}"
        else:
            text = f"{label}: {read}"
        text = word_trunc(text, 220)
        # Upstream camel_read is sometimes stored pre-truncated mid-clause
        # ("…global bear market and"); mark the cut instead of dangling.
        if text and text[-1] not in ".!?…":
            text = text.rstrip(",;: ") + "…"
        lines.append("• " + esc(text))
    return lines

# Signals older than this are history, not setups.
SIGNAL_MAX_AGE = {"1D": 21, "1W": 60}
_SIG_TO_TICK = {"XAUUSD": "GLD", "XAGUSD": "SLV"}

def signals_with_age(signals: dict, now=None) -> dict:
    """{display_ticker: {tf: {'signal':..., 'price':..., 'age_days': int}}}
    filtered to dcl/wcl within SIGNAL_MAX_AGE."""
    now = now or datetime.now(timezone.utc)
    out = {}
    skip = {"TEST", "VERIFY", "_last_received", "_total_count"}
    for inst, tfs in signals.items():
        if inst in skip or not isinstance(tfs, dict):
            continue
        tick = _SIG_TO_TICK.get(inst, inst)
        for tf, sig in tfs.items():
            if not isinstance(sig, dict):
                continue
            stype = sig.get("signal", "")
            if stype not in ("dcl", "wcl"):
                continue
            try:
                ts = datetime.fromisoformat(
                    sig.get("received_at", "").replace("Z", "+00:00"))
                age = (now - ts).days
            except Exception:
                continue
            if age > SIGNAL_MAX_AGE.get(tf, 21):
                continue
            pending = "PENDING" in (sig.get("raw_message") or "").upper() \
                      or "Future" in (sig.get("raw_message") or "")
            out.setdefault(tick, {})[tf] = {
                "signal": stype, "price": sig.get("price"),
                "age_days": age, "pending": pending,
            }
    return out

def open_exposure(pos: dict) -> dict:
    """{SYMBOL: {'contracts': n, 'shares': n}} for open positions only."""
    exp = {}
    for acct in ("etrade_brokerage", "robinhood_401k", "robinhood_brokerage"):
        for p in (pos.get(acct, {}) or {}).get("positions", []) or []:
            sym = (p.get("symbol") or "").upper()
            qty = p.get("quantity") or 0
            if not sym or sym == "VARIOUS":
                continue
            if (p.get("status") or "").lower() == "closed" or qty == 0:
                continue
            slot = exp.setdefault(sym, {"contracts": 0, "shares": 0})
            if p.get("type") == "shares":
                slot["shares"] += qty
            else:
                slot["contracts"] += qty
    return exp

def _held_str(exp: dict, sym: str) -> str:
    e = exp.get(sym)
    if not e:
        return "no position"
    bits = []
    if e["contracts"]:
        bits.append(f"{e['contracts']:,} calls")
    if e["shares"]:
        bits.append(f"{e['shares']:,} sh")
    return "hold " + " + ".join(bits)

# Gold-family DCL confirmation needs day 18+ (Camel rule). Applied only when
# the instrument HAS a Camel daily window; windowless tickers skip the gate.
_CONFIRM_MIN_DAY = 18

def build_setups(prices: dict, cs: dict, sigs: dict, exp: dict,
                 top_fires: list) -> list:
    """Deterministic setup engine. Each line = instrument, state, trigger,
    ACTION VERB. Sources: CF signals (aged), price vs 10-SMA, cycle day,
    overnight top-signal fires."""
    lines = []
    tick_to_inst = {t: i for i, t in SNAPSHOT_ROWS}
    for tick in ("GLD", "SLV", "GDX", "TLT", "SPX", "BTC"):
        inst = tick_to_inst.get(tick, tick)
        p = prices.get("tickers", {}).get(tick, {})
        price, sma10 = p.get("last_close"), p.get("sma_10")
        ci = cs.get(inst, cs.get(tick, {}))
        day = int(ci.get("daily_day", 0) or 0)
        confirmed = bool(ci.get("dcl_confirmed"))
        s = sigs.get(tick, {})
        d1 = s.get("1D")
        w1 = s.get("1W")
        held = _held_str(exp, tick)
        window = _window_for(inst)

        if d1 and price is not None and sma10 and not confirmed:
            above = float(price) >= float(sma10)
            day_known = bool(window) and day <= (window[1] + STALE_COUNT_GRACE)
            if not above:
                lines.append(
                    f"{tick}: DCL zone (sig {d1['age_days']}d old), below 10SMA "
                    f"{fmt_price(sma10)}. Trigger = swing low + reclaim. WAIT.")
            elif day_known and day < _CONFIRM_MIN_DAY:
                lines.append(
                    f"{tick}: reclaimed 10SMA {fmt_price(sma10)} but day {day} "
                    f"(needs {_CONFIRM_MIN_DAY}+) — early, likely still pre-DCL. "
                    f"NO CHASE ({held}).")
            else:
                daypart = f"day {day}" if day_known else "day count unreliable"
                lines.append(
                    f"{tick}: above 10SMA {fmt_price(sma10)}, {daypart}, DCL "
                    f"zone flagged — confirmation candidate. VERIFY swing low "
                    f"before adds ({held}).")
        if w1:
            wk_price = fmt_price(w1["price"]) if w1.get("price") else "n/a"
            lines.append(
                f"{tick}: weekly cycle low marked {wk_price} "
                f"({w1['age_days']}d ago) — weekly cycle young. Context for "
                f"dip-buys, not a trigger.")

    for tf in top_fires:
        lines.append(tf)

    if lines:
        lines.append("Rule: no system GO alert = no entry (anti-FOMO).")
    return ["• " + esc(l) for l in lines]

_FIRE_URGENCIES = {"multi_scale_top_fire", "top_confluence_fire",
                   "weekly_top_confluence"}
_KNOWN_TICKS = ("SPX", "NASDAQ", "TLT", "GLD", "SLV", "GDX", "SILJ", "BTC",
                "XAUUSD", "XAGUSD")

def summarize_top_fires(deferred: list, exp: dict) -> list:
    """Collapse overnight top-signal fires into per-instrument action lines."""
    per_tick = {}
    for d in deferred:
        if d.get("urgency") not in _FIRE_URGENCIES:
            continue
        txt = strip_html(d.get("message", ""))
        for tk in _KNOWN_TICKS:
            if re.search(rf"\b{tk}\b", txt):
                per_tick.setdefault(tk, set()).add(d.get("urgency"))
    lines = []
    for tk, kinds in per_tick.items():
        scope = "weekly+daily" if len(kinds) > 1 else \
                ("weekly" if "weekly_top_confluence" in kinds else "daily")
        if exp.get(tk):
            tail = f"{_held_str(exp, tk)}. EXIT-REVIEW today."
        else:
            tail = "no position — supports top thesis. WATCH."
        lines.append(f"{tk}: overnight TOP-SIGNAL fire ({scope} confluence) — "
                     f"{tail}")
    return lines

def build_position_risk(exp: dict) -> list:
    """Summarize options-risk-dashboard.json (fresh ≤36h): severity counts +
    worst offenders + pending decision. Replaces the information-free
    'E*Trade: 5 positions / 401k: 19 positions' lines."""
    d = load_json(OPTIONS_RISK)
    alerts = d.get("alerts") or []
    lines = []
    fresh = False
    try:
        ts = datetime.fromisoformat(
            str(d.get("timestamp", "")).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        fresh = (datetime.now(timezone.utc) - ts) <= timedelta(hours=36)
    except Exception:
        pass
    if fresh and alerts:
        crit = [a for a in alerts if a.get("severity") == "CRITICAL"]
        act = [a for a in alerts if a.get("severity") == "ACTION"]
        n = d.get("positions_analyzed", len(alerts))
        lines.append(esc(f"• {n} options analyzed: {len(crit)} CRITICAL, "
                         f"{len(act)} ACTION"))
        def _pct(a):
            m = re.search(r"-(\d+)%", a.get("msg", ""))
            return int(m.group(1)) if m else 0
        worst = sorted(crit, key=_pct, reverse=True)[:3]
        if worst:
            frag = " | ".join(
                f"{a.get('pos','?').replace(' exp ', ' ')} {_pct(a)}% down"
                for a in worst)
            lines.append(esc(f"• Worst: {frag}"))
            lines.append(esc("• Standing decision: cut-loss vs roll-down on "
                             "deep-OTM strikes — capital dead at BE≈0%."))
        for a in act[:2]:
            lines.append(esc(f"• {a.get('pos','?')}: {word_trunc(a.get('msg',''), 70)}"
                             f" → {word_trunc(a.get('action',''), 60)}"))
    # Fallback so the section is never empty: futures stops if any exist.
    if not lines:
        pos = load_json(POSITIONS)
        for p in (pos.get("etrade_brokerage", {}) or {}).get("positions", []) or []:
            if p.get("type") == "futures" and p.get("stop") and \
               (p.get("status") or "").lower() != "closed":
                lines.append(esc(f"• {p['symbol']} x{p.get('quantity','')} "
                                 f"@{fmt_price(p.get('avg_entry', p.get('entry_price')))}"
                                 f" | STOP {fmt_price(p['stop'])}"))
    return lines

def build_otm_watch(pos: dict) -> list:
    """Suppressed OTM alerts — but only for positions that are still OPEN.
    2026-08-18: AMZN $265C rendered 'EXIT still recommended' for 16 days
    after the position was closed, with a stale 'expires in 18d' detail."""
    supp = load_json(OTM_SUPPRESS)
    if not supp:
        return []
    exp = open_exposure(pos)
    lines = []
    for key, entry in supp.items():
        if entry.get("injection_count", 0) < 3:
            continue
        sym = key.split("_")[0].upper()
        if sym and sym not in exp:
            log(f"OTM watch: dropping {key} — position closed")
            continue
        lines.append("• " + esc(f"[x{entry['injection_count']}] "
                                f"{entry.get('detail', key)} — EXIT still recommended"))
    return lines

def build_overnight_digest(deferred: list, exp: dict) -> list:
    """Cleaned digest of deferred overnight alerts.
    - ALL CLEARs collapse to one counted line (digit-stripped dedup key).
    - Urgencies promoted elsewhere (top fires → SETUPS, options risk →
      POSITION RISK) are excluded here; no double rendering.
    - Everything is HTML-stripped and word-truncated."""
    consumed = set(_FIRE_URGENCIES) | {"options_risk_critical"}
    allclear = []
    others = {}   # norm_key -> (count, latest_entry)
    for d in deferred:
        if d.get("urgency") in consumed:
            continue
        txt = strip_html(d.get("message", ""))
        if "ALL CLEAR" in txt.upper():
            allclear.append(d)
            continue
        k = normalize_key(txt)
        cnt, _ = others.get(k, (0, None))
        others[k] = (cnt + 1, d)
    lines = []
    for k, (cnt, d) in others.items():
        txt = word_trunc(strip_html(d.get("message", "")), 150)
        tag = f" (x{cnt})" if cnt > 1 else ""
        lines.append("• " + esc(txt + tag))
    if allclear:
        latest = strip_html(allclear[-1].get("message", ""))
        latest = re.sub(r"[✅⚠️🚨📊]", "", latest)
        detail = word_trunc(latest.replace("PRE-MARKET — ALL CLEAR", "").strip(),
                            110)
        lines.append("• " + esc(f"Pre-market checks ALL CLEAR ×{len(allclear)} "
                                f"overnight — latest: {detail}"))
    return lines

def load_deferred(hours: int = 20) -> list:
    """Read deferred-alerts.jsonl (recent window), filtering entries that
    reference closed-position symbols. Truncates the file to last 50 lines."""
    if not DEFERRED.exists():
        return []
    closed = set()
    try:
        pjson = load_json(POSITIONS)
        for ak in ("etrade_brokerage", "robinhood_401k", "robinhood_brokerage"):
            for pp in (pjson.get(ak, {}) or {}).get("positions", []) or []:
                sym = (pp.get("symbol") or "").upper()
                qty = pp.get("quantity")
                if (pp.get("status") or "").lower() == "closed" or \
                   (qty is not None and qty == 0):
                    if sym:
                        closed.add(sym)
    except Exception:
        pass
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    try:
        all_lines = DEFERRED.read_text().splitlines()
    except Exception:
        return []
    for line in all_lines:
        try:
            e = json.loads(line)
            ts = datetime.fromisoformat(
                e.get("timestamp", "").replace("Z", "+00:00"))
            if ts < cutoff:
                continue
            hay = (e.get("message", "") + " " + e.get("cooldown_key", "") +
                   " " + e.get("urgency", "")).upper()
            if any(re.search(rf"\b{re.escape(c)}\b", hay) for c in closed):
                continue
            out.append(e)
        except Exception:
            continue
    try:
        if len(all_lines) > 50:
            DEFERRED.write_text("\n".join(all_lines[-50:]) + "\n")
    except Exception:
        pass
    return out

def build_alpha_v3_hypotheses() -> list:
    """Read decisions.jsonl + edge-weights.json → ALPHA V3 HYPOTHESES lines.

    v2: returns [] when there are neither hypotheses nor track-record samples
    (the old version rendered 'No new hypotheses today.' + '(no samples yet)'
    — two lines of nothing, every day).
    """
    decisions_path = STATE / "decisions.jsonl"
    edges_path = STATE / "edge-weights.json"

    per_ticker = {}
    if decisions_path.exists():
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        try:
            for raw in decisions_path.read_text().splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except Exception:
                    continue
                if rec.get("type") != "hypothesis" or rec.get("status") != "open":
                    continue
                subj = rec.get("subject", "")
                if not subj.startswith("alpha_v3_"):
                    continue
                try:
                    ts = datetime.fromisoformat(
                        rec.get("written_at", "").replace("Z", "+00:00"))
                except Exception:
                    continue
                if ts < cutoff:
                    continue
                parts = subj.split("_")
                ticker = parts[2] if len(parts) >= 3 else subj
                prev = per_ticker.get(ticker)
                if (prev is None) or (ts > prev[0]):
                    per_ticker[ticker] = (ts, rec)
        except Exception as e:
            log(f"WARN: decisions.jsonl parse failed: {e}")

    lines = []
    for ticker, (_ts, rec) in sorted(per_ticker.items(),
                                     key=lambda kv: kv[1][0], reverse=True):
        alts = rec.get("alternatives", []) or []
        labels = {a.get("label", "") for a in alts}
        direction = "long" if "take_long" in labels else \
                    ("short" if "take_short" in labels else "flat")
        rationale = rec.get("rationale", "") or ""
        conv_match = re.search(r"Conviction\s+(\d+)\s*/\s*10", rationale)
        conviction = conv_match.group(1) if conv_match else "?"
        edges_match = re.search(r"Aligned edges:\s*([^.]+?)\.(?:\s|$)", rationale)
        aligned = edges_match.group(1).strip() if edges_match else "none"
        kc = rec.get("kill_criteria") or []
        kill = str(kc[0]) if kc else ""
        lines.append(esc(f"• {ticker} | {direction} | {conviction}/10 | "
                         f"{aligned} | {kill}"))

    # Track record — schema fallbacks cover both writer schemas:
    #   parser default: {n|sample_count, hit_rate|win_rate, wins}
    #   alpha_v3_review.py: {total_seen, total_correct, hit_rate_rolling}
    tr_line = None
    try:
        if edges_path.exists():
            ew = json.loads(edges_path.read_text())
            rows = []
            for name, stats in (ew.get("edges", {}) or {}).items():
                if not isinstance(stats, dict):
                    continue
                n = int(stats.get("n", stats.get("sample_count",
                                                 stats.get("total_seen", 0))) or 0)
                hr = stats.get("hit_rate",
                               stats.get("win_rate", stats.get("hit_rate_rolling")))
                if hr is None and n > 0:
                    c = stats.get("wins", stats.get("total_correct"))
                    if c is not None:
                        hr = float(c) / n
                if hr is None:
                    continue
                pct = int(round(float(hr) * 100)) if float(hr) <= 1.0 \
                    else int(round(float(hr)))
                rows.append((name, pct, n))
            rows.sort(key=lambda r: r[2], reverse=True)
            if rows:
                parts = [f"{nm} {p}% n={c}" for (nm, p, c) in rows[:4]]
                tr_line = "Edge track record: " + ", ".join(parts)
    except Exception as e:
        log(f"WARN: edge-weights parse failed: {e}")

    if tr_line:
        lines.append(esc(tr_line))
    return lines

def build_chronic_escalations(days: int = 7, max_rows: int = 5) -> list:
    """Chronic-loop escalations — NOT rendered in the briefing (system noise,
    removed 2026-05-08). Preserved for the separate operator channel."""
    if not ESCALATIONS.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    seen = set()
    rows = []
    try:
        for line in ESCALATIONS.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            try:
                ts = datetime.fromisoformat(
                    e.get("ts", "").replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if ts < cutoff:
                continue
            key = (e.get("action_type"), e.get("utc_date"))
            if key in seen:
                continue
            seen.add(key)
            rows.append((ts, e))
    except Exception:
        return []
    if not rows:
        return []
    rows.sort(key=lambda x: x[0], reverse=True)
    out = ["", "<b>⚠ CHRONIC LOOPS (orchestrator suppressed, needs operator)</b>"]
    for _, e in rows[:max_rows]:
        action = e.get("action_type", "?")
        count = e.get("count_24h", "?")
        utc_date = e.get("utc_date", "?")
        target = ""
        task_ids = e.get("last_task_ids", [])
        if task_ids:
            parts = task_ids[0].split(":")
            if len(parts) >= 3:
                target = parts[2][:40]
        target_part = f" on {esc(target)}" if target else ""
        out.append(f"• {esc(action)}{target_part} — {count}× in 24h on {utc_date}")
    return out

def build_political_alpha() -> list:
    """Imminent political catalysts. v2: returns [] when there are none —
    'No imminent political catalysts.' is not information."""
    status_path = STATE / "political-catalyst-status.json"
    if not status_path.exists():
        return []
    try:
        data = json.loads(status_path.read_text())
    except Exception as e:
        log(f"WARN: political-catalyst-status parse failed: {e}")
        return []
    try:
        gen_ts = datetime.fromisoformat(
            data.get("generated_at", "").replace("Z", "+00:00"))
        if gen_ts.tzinfo is None:
            gen_ts = gen_ts.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - gen_ts) > timedelta(hours=24):
            return []
    except Exception:
        return []

    qualifying = []
    for t in data.get("tickers", []) or []:
        flags = t.get("status_flags") or []
        du = t.get("days_until")
        if not flags and (du is None or du > 14):
            continue
        qualifying.append(t)
    qualifying.sort(key=lambda x: (x.get("days_until") is None,
                                   x.get("days_until") if x.get("days_until")
                                   is not None else 9999))
    lines = []
    for t in qualifying[:5]:
        nc = t.get("next_catalyst") or {}
        du = t.get("days_until")
        flags = t.get("status_flags") or []
        line = (f"{t.get('ticker','?')} {fmt_price(t.get('price'))} "
                f"({fmt_pct(t.get('daily_pct'))}) | {nc.get('event','n/a')[:50]} "
                f"in {f'{du}d' if du is not None else 'n/a'} | "
                f"{', '.join(flags) if flags else 'ok'}")
        lines.append("• " + esc(line))
    return lines

def _alpha_ideas_stale(max_age_days: int = 7) -> bool:
    """True if alpha-ideas.json is missing or older than max_age_days.
    Generator (alpha-scanner.py) RETIRED 2026-04-18; successor is alpha_v3.
    If the file ever revives, TOP ALPHA renders again automatically."""
    try:
        d = json.loads(ALPHA_IDEAS.read_text())
        gen = d.get("generated_at") or d.get("cleaned_at")
        if not gen:
            return True
        ts = datetime.fromisoformat(str(gen).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts) > timedelta(days=max_age_days)
    except Exception:
        return True

def build_top_alpha(ideas: list, n: int = 2) -> list:
    if _alpha_ideas_stale():
        return []
    lines = []
    new_ideas = [i for i in ideas if i.get("status") == "NEW"]
    top = sorted(new_ideas, key=lambda x: x.get("conviction", 0),
                 reverse=True)[:n]
    for idea in top:
        inst = esc(idea.get("instrument", "?")[:50])
        conv = idea.get("conviction", 0)
        what = esc(word_trunc(idea.get("what_matt_doesnt_know",
                                       idea.get("thesis", "")), 150))
        lines.append(f"• <b>[{conv}/10]</b> {inst}: {what}")
    return lines

# ── Message assembly ────────────────────────────────────────────────────
def _section(lines: list, header: str, body: list):
    if body:
        lines.append(f"\n<b>{header}</b>")
        lines.extend(body)

def build_message(prices: dict, cs: dict, ideas: list, pos: dict,
                  signals: dict) -> str:
    today = datetime.now().strftime("%a %b %-d")
    lines = [f"<b>Morning Briefing — {esc(today)}</b>", ""]

    lines.append("<b>CYCLE POSITION</b>")
    lines.extend(build_snapshot(prices, cs))

    _section(lines, "CAMEL THESES", build_camel_theses(cs))

    exp = open_exposure(pos)
    deferred = load_deferred()
    sigs = signals_with_age(signals)
    top_fires = summarize_top_fires(deferred, exp)
    _section(lines, "SETUPS &amp; TRIGGERS",
             build_setups(prices, cs, sigs, exp, top_fires))

    _section(lines, "POSITION RISK", build_position_risk(exp))
    _section(lines, "OTM WATCH", build_otm_watch(pos))
    _section(lines, "ALPHA V3", build_alpha_v3_hypotheses())
    _section(lines, "POLITICAL ALPHA", build_political_alpha())
    _section(lines, "TOP ALPHA", build_top_alpha(ideas))
    _section(lines, "OVERNIGHT", build_overnight_digest(deferred, exp))

    # Research queue: consume + truncate only (telemetry stays out of the
    # briefing — system-internal, removed 2026-05-08).
    try:
        if RESEARCH_QUEUE.exists():
            all_lines = RESEARCH_QUEUE.read_text().splitlines()
            if len(all_lines) > 500:
                RESEARCH_QUEUE.write_text("\n".join(all_lines[-500:]) + "\n")
    except Exception as _e:
        log(f"WARN: research queue truncate failed: {_e}")

    # ── Final length guard ──────────────────────────────────────────────
    # Telegram hard cap = 4096 chars; keep safe margin at 3900. Trim tail
    # sections in reverse-priority order. SETUPS and POSITION RISK are never
    # trimmed — they are the reason the briefing exists.
    LIMIT = 3900
    TRIM_ORDER = [
        "POLITICAL ALPHA",
        "TOP ALPHA",
        "OVERNIGHT",
        "OTM WATCH",
        "ALPHA V3",
        "CAMEL THESES",
    ]

    def _msg_len(ls):
        return sum(len(l) + 1 for l in ls)

    def _drop_section(ls, header_text):
        start = None
        for i, ln in enumerate(ls):
            if ln.lstrip("\n") == f"<b>{header_text}</b>":
                start = i
                break
        if start is None:
            return ls, False
        end = len(ls)
        for j in range(start + 1, len(ls)):
            stripped = ls[j].lstrip("\n")
            if stripped.startswith("<b>") and stripped.endswith("</b>"):
                end = j
                break
        return ls[:start] + ls[end:], True

    for hdr in TRIM_ORDER:
        if _msg_len(lines) <= LIMIT:
            break
        lines, dropped = _drop_section(lines, hdr)
        if dropped:
            log(f"Length guard: dropped {hdr} (msg_len now {_msg_len(lines)})")

    if _msg_len(lines) > LIMIT:
        joined = "\n".join(lines)
        return joined[: LIMIT - 20].rstrip() + "\n... [truncated]"

    return "\n".join(lines)

# ── Main ────────────────────────────────────────────────────────────────
def main():
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    if is_weekend() and not dry_run:
        log("Weekend - skipping")
        return
    log("morning_briefing.py starting"
        + (" (dry-run)" if dry_run else "") + (" (force)" if force else ""))

    if not dry_run and not force and already_sent_today():
        log("Already sent today — skipping")
        return 0

    prices  = load_json(LATEST_PRICES)
    cs      = load_json(CYCLE_STATE)
    alpha   = load_json(ALPHA_IDEAS)
    pos     = load_json(POSITIONS)
    signals = load_json(SIGNALS_LATEST)

    ideas = alpha.get("ideas", [])

    msg = build_message(prices, cs, ideas, pos, signals)

    if dry_run:
        print("----- DRY RUN: briefing message follows -----")
        print(msg)
        print(f"----- END DRY RUN ({len(msg)} chars) -----")
        return 0

    # Save markdown copy
    try:
        today_str = date.today().isoformat()
        md_header = (f"# Morning Alpha Briefing — {today_str}\n"
                     f"**Source: morning_briefing.py (local)**\n\n")
        BRIEFING_MD.write_text(
            md_header + msg.replace("<b>", "**").replace("</b>", "**") + "\n")
        log("Wrote morning-alpha.md")
    except Exception as e:
        log(f"WARN: could not write morning-alpha.md: {e}")

    ok = send_alert("CRITICAL", msg, urgency="morning_briefing",
                    cooldown_key=_BRIEFING_COOLDOWN_KEY)
    if ok:
        log("Briefing sent via dispatcher (STATUS / 24 h cooldown)")
    else:
        log("ERROR: Telegram send failed or suppressed by dispatcher")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
