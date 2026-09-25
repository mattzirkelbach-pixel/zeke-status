#!/usr/bin/env python3
"""Tests for the 2026-08-18 morning_briefing.py v2 rebuild.

Encodes the failure modes Matt flagged in the 08-18 send so they can never
ship again:
  - 4x duplicate PRE-MARKET ALL CLEAR lines (price-varying dedup key)
  - raw truncated HTML fragments in the deferred digest
  - "No new hypotheses today." / "(no samples yet)" filler sections
  - Camel thesis chopped mid-word ("September 21st wit")
  - closed AMZN $265C still pushed as "EXIT still recommended"
  - "day 155/36-44 PAST WINDOW" stale-anchor noise

Run: /opt/homebrew/bin/python3 -m unittest tests.test_morning_briefing_v2 -v
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path.home() / "zeke-portfolio" / "scripts"))
import morning_briefing as mb


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


NOW = datetime.now(timezone.utc)

ALLCLEAR_TMPL = ("✅ <b>PRE-MARKET — ALL CLEAR</b>  ✅ Gold ${g} above 10-SMA "
                 "$4,359 ✅ Crude $84 (below $95) ✅ VIX 16 (below 30)")

FIXTURE_PRICES = {"tickers": {
    "GLD": {"last_close": 401.48, "prev_close": 398.96, "daily_change_pct": 0.63,
            "sma_10": 393.25, "rsi_14": 63.2},
    "SLV": {"last_close": 58.48, "daily_change_pct": 0.55, "sma_10": 57.1,
            "rsi_14": 61.0},
    "GDX": {"last_close": 89.97, "daily_change_pct": 1.93, "sma_10": 86.0,
            "rsi_14": 66.0},
    "SPX": {"last_close": 7785.76, "daily_change_pct": -0.17, "sma_10": 7800.0,
            "rsi_14": 55.0},
    "BTC": {"last_close": 64134.68, "daily_change_pct": -0.58, "sma_10": 66000.0,
            "rsi_14": 44.0},
    "TLT": {"last_close": 82.04, "daily_change_pct": -0.67, "sma_10": 83.0,
            "rsi_14": 41.0},
    "VIX": {"last_close": 16.2}, "DXY": {"last_close": 97.3},
    "CRUDE": {"last_close": 84.0},
}}

FIXTURE_CS = {
    "XAUUSD": {"daily_day": 10, "dcl_confirmed": False,
               "camel_read": ("Phase: approaching_low. Thesis (7/10): Gold will "
                              "reject and head lower into a weekly cycle low "
                              "around September 21st with higher low setup")},
    "SLV": {"daily_day": 14, "dcl_confirmed": False},
    "GDX": {"daily_day": 29, "dcl_confirmed": False},
    "SPX": {"daily_day": 155, "dcl_confirmed": False,
            "camel_read": ("Phase: approaching_low. Thesis (6/10): Market will "
                           "experience blow-off top to all-time highs followed "
                           "by tumble into global bear market and beyond")},
    "BTC": {"daily_day": 137, "dcl_confirmed": False},
    "TLT": {"daily_day": 2, "dcl_confirmed": False,
            "camel_read": ("Phase: approaching_high. Thesis (6/10): Weekly cycle "
                           "top and 7.5 year cycle convergence will create a "
                           "contrarian trade opportunity")},
}

FIXTURE_POS = {"etrade_brokerage": {"positions": [
    {"symbol": "GLD", "type": "call_option", "quantity": 5},
    {"symbol": "AMZN", "type": "call_option", "quantity": 0, "status": "closed"},
]}, "robinhood_401k": {"positions": [
    {"symbol": "TLT", "type": "call_option", "quantity": 4400},
    {"symbol": "TLT", "type": "shares", "quantity": 1868},
]}}

FIXTURE_SIGNALS = {
    "XAUUSD": {"1D": {"signal": "dcl", "price": None,
                      "raw_message": "PENDING DCL Future DCL Zone Reached",
                      "received_at": _iso(NOW - timedelta(days=3))},
               "1W": {"signal": "dcl", "price": 3942.1,
                      "raw_message": "New DCL event",
                      "received_at": _iso(NOW - timedelta(days=11))}},
    "TLT": {"1D": {"signal": "dcl", "price": None,
                   "raw_message": "PENDING DCL zone",
                   "received_at": _iso(NOW - timedelta(days=2))}},
    "_last_received": "x", "_total_count": 63,
    "TEST": {"1D": {"signal": "connectivity_check", "received_at": _iso(NOW)}},
}

def fixture_deferred():
    out = []
    for i in range(11):
        g = f"4,4{40 + i}"
        out.append({"timestamp": _iso(NOW - timedelta(hours=i)),
                    "urgency": "",
                    "message": ALLCLEAR_TMPL.format(g=g)})
    out.append({"timestamp": _iso(NOW - timedelta(hours=14)),
                "urgency": "correlation_regime",
                "message": ("📊 <b>CORRELATION REGIME CHANGE</b> • GLD/SPY: "
                            "30d=+0.18 vs 90d=+0.52 (BREAKDOWN)")})
    out.append({"timestamp": _iso(NOW - timedelta(hours=14)),
                "urgency": "multi_scale_top_fire",
                "message": ("⚠️ <b>TOP SIGNAL — EXIT/REDUCE</b> <b>SPX</b>: EXIT "
                            "why: daily=FIRE(AT_TOP) | weekly=WARN(AT_TOP)")})
    out.append({"timestamp": _iso(NOW - timedelta(hours=14)),
                "urgency": "options_risk_critical",
                "message": "⚠️ <b>OPTIONS RISK — CRITICAL</b> GLD $470.0C"})
    return out


class TestWordTrunc(unittest.TestCase):
    def test_no_midword_cut(self):
        s = ("Gold will reject and head lower into a weekly cycle low around "
             "September 21st with higher low setup and more words here")
        out = mb.word_trunc(s, 100)
        self.assertNotIn("wit…", out)
        # every token before the ellipsis must be a whole word from the source
        self.assertTrue(all(w in s.split() or w.endswith("…")
                            for w in out.split()))

    def test_short_passthrough_no_ellipsis(self):
        self.assertEqual(mb.word_trunc("short text", 50), "short text")

    def test_sentence_preference(self):
        # sentence boundary is used when it lands past 50% of the budget
        s = ("First sentence is quite a bit longer here. Second sentence "
             "that runs long " + "x" * 100)
        out = mb.word_trunc(s, 60)
        self.assertEqual(out, "First sentence is quite a bit longer here.")


class TestOvernightDigest(unittest.TestCase):
    def test_allclear_collapses_to_one_line(self):
        lines = mb.build_overnight_digest(fixture_deferred(), {})
        allclear = [l for l in lines if "ALL CLEAR" in l]
        self.assertEqual(len(allclear), 1)
        self.assertIn("×11", allclear[0])

    def test_no_raw_html_and_no_promoted_urgencies(self):
        lines = mb.build_overnight_digest(fixture_deferred(), {})
        joined = "\n".join(lines)
        self.assertNotIn("&lt;b&gt;", joined)
        self.assertNotIn("OPTIONS RISK", joined)   # lives in POSITION RISK
        self.assertNotIn("TOP SIGNAL", joined)     # promoted to SETUPS
        self.assertIn("CORRELATION REGIME", joined)

    def test_normalize_key_ignores_prices(self):
        a = mb.normalize_key(ALLCLEAR_TMPL.format(g="4,444"))
        b = mb.normalize_key(ALLCLEAR_TMPL.format(g="4,450"))
        self.assertEqual(a, b)


class TestExposureAndOTM(unittest.TestCase):
    def test_closed_positions_excluded(self):
        exp = mb.open_exposure(FIXTURE_POS)
        self.assertNotIn("AMZN", exp)
        self.assertEqual(exp["TLT"], {"contracts": 4400, "shares": 1868})

    def test_otm_watch_drops_closed_symbol(self):
        with tempfile.TemporaryDirectory() as td:
            supp = Path(td) / "otm.json"
            supp.write_text(json.dumps({
                "AMZN_265.0C": {"injection_count": 3,
                                "detail": "AMZN $265.0C x40 expires in 18d."},
                "GLD_470.0C": {"injection_count": 4,
                               "detail": "GLD $470.0C x5 deep OTM."},
            }))
            old = mb.OTM_SUPPRESS
            mb.OTM_SUPPRESS = supp
            try:
                lines = mb.build_otm_watch(FIXTURE_POS)
            finally:
                mb.OTM_SUPPRESS = old
        joined = "\n".join(lines)
        self.assertNotIn("AMZN", joined)
        self.assertIn("GLD", joined)


class TestDayStatus(unittest.TestCase):
    def test_stale_anchor_labeled_stale(self):
        if mb._cycle_params is None:
            self.skipTest("cycle_theory unavailable")
        out = mb.day_status("SPX", 155, FIXTURE_CS)
        self.assertIn("stale", out)
        self.assertNotIn("PAST WINDOW", out)

    def test_in_window(self):
        if mb._cycle_params is None:
            self.skipTest("cycle_theory unavailable")
        w = mb._window_for("XAUUSD")
        out = mb.day_status("XAUUSD", w[0], FIXTURE_CS)
        self.assertIn("IN WINDOW", out)


class TestSetups(unittest.TestCase):
    def _setups(self):
        sigs = mb.signals_with_age(FIXTURE_SIGNALS)
        exp = mb.open_exposure(FIXTURE_POS)
        fires = mb.summarize_top_fires(fixture_deferred(), exp)
        return mb.build_setups(FIXTURE_PRICES, FIXTURE_CS, sigs, exp, fires)

    def test_gld_early_no_chase(self):
        # GLD above 10SMA at day 10 with a pending DCL zone → NO CHASE
        gld = [l for l in self._setups() if l.startswith("• GLD:")]
        self.assertTrue(any("NO CHASE" in l for l in gld), gld)

    def test_tlt_below_sma_waits(self):
        tlt = [l for l in self._setups() if l.startswith("• TLT:")]
        self.assertTrue(any("WAIT" in l for l in tlt), tlt)

    def test_top_fire_promoted_with_position_context(self):
        exp = mb.open_exposure(FIXTURE_POS)
        fires = mb.summarize_top_fires(fixture_deferred(), exp)
        spx = [l for l in fires if l.startswith("SPX")]
        self.assertTrue(spx and "no position" in spx[0], fires)

    def test_signal_age_filter(self):
        stale = {"XAUUSD": {"1D": {
            "signal": "dcl", "raw_message": "PENDING",
            "received_at": _iso(NOW - timedelta(days=40))}}}
        self.assertEqual(mb.signals_with_age(stale), {})


class TestFillerElimination(unittest.TestCase):
    def test_empty_alpha_v3_renders_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            old = mb.STATE
            mb.STATE = Path(td)
            try:
                self.assertEqual(mb.build_alpha_v3_hypotheses(), [])
            finally:
                mb.STATE = old

    def test_political_alpha_absent_when_no_catalysts(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "political-catalyst-status.json"
            p.write_text(json.dumps({
                "generated_at": _iso(NOW), "tickers": [
                    {"ticker": "LMT", "days_until": 60, "status_flags": []}]}))
            old = mb.STATE
            mb.STATE = Path(td)
            try:
                self.assertEqual(mb.build_political_alpha(), [])
            finally:
                mb.STATE = old


class TestFullMessage(unittest.TestCase):
    def test_smoke(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "deferred-alerts.jsonl").write_text(
                "\n".join(json.dumps(e) for e in fixture_deferred()) + "\n")
            (td / "options-risk-dashboard.json").write_text(json.dumps({
                "timestamp": _iso(NOW), "positions_analyzed": 19,
                "alerts": [
                    {"severity": "CRITICAL", "pos": "GLD $470.0C exp 2026-12-18",
                     "msg": "Down -98% from cost, BE prob 0%",
                     "action": "Evaluate cut-loss vs roll-down"},
                    {"severity": "ACTION", "pos": "ALM $12.5C exp 2026-11-20",
                     "msg": "50% time value decay in 37 days",
                     "action": "Consider rolling"}]}))
            (td / "otm.json").write_text("{}")
            saved = (mb.STATE, mb.DEFERRED, mb.OPTIONS_RISK, mb.OTM_SUPPRESS,
                     mb.RESEARCH_QUEUE, mb.POSITIONS, mb.ALPHA_IDEAS)
            mb.STATE = td
            mb.DEFERRED = td / "deferred-alerts.jsonl"
            mb.OPTIONS_RISK = td / "options-risk-dashboard.json"
            mb.OTM_SUPPRESS = td / "otm.json"
            mb.RESEARCH_QUEUE = td / "rq.jsonl"
            mb.POSITIONS = td / "positions.json"
            mb.ALPHA_IDEAS = td / "alpha-ideas.json"
            (td / "positions.json").write_text(json.dumps(FIXTURE_POS))
            try:
                msg = mb.build_message(FIXTURE_PRICES, FIXTURE_CS, [],
                                       FIXTURE_POS, FIXTURE_SIGNALS)
            finally:
                (mb.STATE, mb.DEFERRED, mb.OPTIONS_RISK, mb.OTM_SUPPRESS,
                 mb.RESEARCH_QUEUE, mb.POSITIONS, mb.ALPHA_IDEAS) = saved

        self.assertLessEqual(len(msg), 4096)
        self.assertIn("SETUPS &amp; TRIGGERS", msg)
        self.assertIn("POSITION RISK", msg)
        self.assertNotIn("No new hypotheses", msg)
        self.assertNotIn("No imminent political catalysts", msg)
        self.assertNotIn("NaN", msg)
        self.assertNotIn("PAST WINDOW", msg)
        # exactly one ALL CLEAR line
        self.assertEqual(msg.count("ALL CLEAR"), 1)
        # camel thesis not chopped mid-word
        self.assertNotIn("21st wit\n", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
