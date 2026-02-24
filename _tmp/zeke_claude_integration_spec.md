# ZEKE ↔ CLAUDE Integration Spec
## Portfolio Intelligence Module — Architecture & MCP Design
### Prepared: Feb 24, 2026

---

## 1. THE ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│                    MATT (Human)                          │
│              claude.ai / Claude app                      │
│         "Where are we on the trade?"                     │
└──────────────┬──────────────────────┬────────────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────────┐
│   CLAUDE (Reasoning) │  │  ZEKE (Autonomous Engine)     │
│                      │  │                                │
│  • Thesis refinement │  │  • Real-time data pipeline     │
│  • Trade recs        │◄─┤  • Cycle counting algorithm    │
│  • Risk assessment   │  │  • Confirmation signal scoring │
│  • Opportunity scan  │  │  • Options Greeks/valuation    │
│  • Natural language  │──►  • Alert rules engine          │
│    analysis          │  │  • Dashboard rendering         │
│                      │  │  • Position tracking           │
└──────────────────────┘  │  • Macro data aggregation      │
                          └──────────────────────────────┘
```

**Two data flows:**

**Flow A — Zeke calls Claude API:**
Zeke autonomously calls Claude when it needs reasoning beyond computation.
Examples: "Daily cycle just confirmed with score 3 during timing window — generate
trade recommendation with sizing." Or: "Unusual divergence between gold and DXY —
interpret macro implications."

**Flow B — Claude calls Zeke via MCP:**
When Matt chats in claude.ai, Claude calls Zeke as a live tool to get real-time state.
Instead of relying on stale memory or web searches, Claude pulls live P&L, cycle
counts, confirmation scores, alert status directly from Zeke. This makes every
conversation data-informed.

---

## 2. FLOW A — ZEKE CALLING CLAUDE API

### When to call
Zeke should call Claude when:
- A trade signal fires and needs natural language recommendation + sizing logic
- Market conditions are ambiguous and pure rule logic is insufficient
- Matt asks Zeke a question that requires reasoning beyond data lookup
- Weekly thesis review (automated Sunday evening batch)
- New opportunity detected that needs macro context analysis

### How to call
Standard Anthropic Messages API. Use claude-sonnet-4-5-20250929 for routine
calls (fast, cheap), escalate to claude-opus-4-6 for complex thesis work.

```python
import anthropic

client = anthropic.Anthropic()  # ANTHROPIC_API_KEY in env

message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    system=open("zeke_system_context.md").read(),  # The file I already built
    messages=[
        {
            "role": "user",
            "content": f"""
            CURRENT STATE:
            {json.dumps(current_portfolio_state)}

            CYCLE DATA:
            {json.dumps(current_cycle_state)}

            MARKET DATA:
            {json.dumps(latest_prices_and_indicators)}

            SIGNAL FIRED: {signal_name}

            Generate trade recommendation with specific sizing,
            strike selection, and risk parameters.
            """
        }
    ]
)
```

### System prompt
Use the `zeke_system_context.md` file as the system prompt. It contains all the
cycle theory rules, portfolio context, tax optimization requirements, and the
"trading partner" behavioral instructions.

### Cost management
- Routine signals: Sonnet (~$0.003-0.015 per call)
- Complex thesis: Opus (~$0.015-0.075 per call)
- Budget ~$5-10/month covers hundreds of signal calls
- Cache the system prompt (it's static) to reduce token costs

---

## 3. FLOW B — CLAUDE CALLING ZEKE VIA MCP

### What is MCP
Model Context Protocol. It lets Claude use external tools as if they were native.
When Matt asks me "what's the P&L on the GLD position?" in claude.ai, instead
of guessing or searching the web, I call Zeke's MCP server and get the real answer.

### MCP Server Design for Zeke

Zeke exposes itself as an MCP server with the following tools. Claude discovers
these tools when the MCP connection is established, and can call them as needed
during any conversation.

**Transport:** SSE (Server-Sent Events) — works with claude.ai connectors
**URL pattern:** `https://your-local-or-tunneled-endpoint/mcp/sse`
**Auth:** API key or OAuth token in header

### Tool Definitions

```json
{
  "tools": [
    {
      "name": "get_portfolio_state",
      "description": "Returns current portfolio positions across all accounts with live P&L, Greeks, and cost basis. Use whenever Matt asks about positions, P&L, or portfolio status.",
      "input_schema": {
        "type": "object",
        "properties": {
          "account": {
            "type": "string",
            "enum": ["etrade_brokerage", "robinhood_401k", "all"],
            "description": "Which account to query"
          },
          "include_greeks": {
            "type": "boolean",
            "default": true
          }
        }
      }
    },
    {
      "name": "get_cycle_state",
      "description": "Returns current cycle timing for specified instrument — day/week count, translation status, cycle phase, and whether in timing window. Use whenever discussing cycle positioning or timing.",
      "input_schema": {
        "type": "object",
        "properties": {
          "instrument": {
            "type": "string",
            "enum": ["XAUUSD", "GLD", "SLV", "SPX", "GDX", "SILJ"],
            "description": "Instrument to get cycle data for"
          },
          "cycle_level": {
            "type": "string",
            "enum": ["daily", "weekly", "all"],
            "default": "all"
          }
        },
        "required": ["instrument"]
      }
    },
    {
      "name": "get_confirmation_score",
      "description": "Returns the current confirmation signal composite score (0-4) for a suspected cycle low. Checks swing low, SMA cross, oscillator reversal, trendline break. Use when evaluating entry timing.",
      "input_schema": {
        "type": "object",
        "properties": {
          "instrument": {
            "type": "string",
            "description": "Symbol to check"
          }
        },
        "required": ["instrument"]
      }
    },
    {
      "name": "get_active_signals",
      "description": "Returns all currently active trade signals (entries, exits, warnings, stops) with their conditions and whether they're triggered. Use at the start of every conversation to brief Matt.",
      "input_schema": {
        "type": "object",
        "properties": {}
      }
    },
    {
      "name": "get_scenario_analysis",
      "description": "Returns options P&L projections across price/time scenarios for current positions. Use when Matt asks 'what if gold hits X' or 'what's the position worth at expiry'.",
      "input_schema": {
        "type": "object",
        "properties": {
          "target_prices": {
            "type": "array",
            "items": {"type": "number"},
            "description": "GLD prices to model (e.g. [450, 470, 500, 520, 550])"
          },
          "target_date": {
            "type": "string",
            "description": "ISO date to model (e.g. '2026-06-01')"
          },
          "iv_shift_pct": {
            "type": "number",
            "default": 0,
            "description": "IV change to model (e.g. -20 for 20% IV decline)"
          }
        }
      }
    },
    {
      "name": "get_macro_scorecard",
      "description": "Returns the 5-factor macro assessment (Fed policy, inflation, growth, USD, global flows) with per-factor and composite scores. Use for thesis validation.",
      "input_schema": {
        "type": "object",
        "properties": {}
      }
    },
    {
      "name": "get_alerts_log",
      "description": "Returns recent alerts fired by the rules engine, sorted by severity. Use to catch Matt up on what happened since last conversation.",
      "input_schema": {
        "type": "object",
        "properties": {
          "since": {
            "type": "string",
            "description": "ISO datetime to filter from (e.g. last 24h, last week)"
          },
          "severity": {
            "type": "string",
            "enum": ["all", "info", "warning", "high", "critical"],
            "default": "all"
          }
        }
      }
    },
    {
      "name": "get_options_chain",
      "description": "Returns live options chain data for a symbol with bid/ask/IV/Greeks. Use when evaluating new entries or rolling positions.",
      "input_schema": {
        "type": "object",
        "properties": {
          "symbol": {"type": "string"},
          "expiry": {"type": "string", "description": "Target expiry date"},
          "strike_range": {
            "type": "object",
            "properties": {
              "min": {"type": "number"},
              "max": {"type": "number"}
            }
          },
          "type": {
            "type": "string",
            "enum": ["calls", "puts", "both"],
            "default": "calls"
          }
        },
        "required": ["symbol"]
      }
    },
    {
      "name": "get_price_history",
      "description": "Returns OHLCV candle data with technical indicators computed. Use for cycle analysis, chart interpretation, or pattern recognition.",
      "input_schema": {
        "type": "object",
        "properties": {
          "symbol": {"type": "string"},
          "period": {
            "type": "string",
            "enum": ["30d", "90d", "6m", "1y"],
            "default": "90d"
          },
          "indicators": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Which indicators to include (e.g. ['SMA10', 'RSI14', 'MACD'])"
          }
        },
        "required": ["symbol"]
      }
    }
  ]
}
```

### How Claude uses these tools in practice

When Matt opens a conversation in this project, Claude's behavior should be:

```
1. Call get_active_signals() → see if anything needs attention
2. Call get_portfolio_state(account="all") → current P&L snapshot
3. Call get_cycle_state(instrument="XAUUSD", cycle_level="all") → where are we
4. Synthesize into: "Here's where we stand, here's what's happening, here's what to do"
```

If Matt asks a specific question like "should I add Tranche 2 today?":
```
1. Call get_cycle_state("XAUUSD") → check day count
2. Call get_confirmation_score("GLD") → are signals firing?
3. Call get_options_chain("GLD", expiry="2026-12-18") → current pricing
4. Call get_portfolio_state("etrade_brokerage") → current exposure
5. Synthesize: "Day 25, confirmation score 3, here are the fills available, sizing rec is X"
```

---

## 4. MCP IMPLEMENTATION NOTES FOR ZEKE

### Hosting
Since Zeke runs on local hardware, you'll need to expose the MCP endpoint.
Options:
- **Cloudflare Tunnel** — easiest. `cloudflared tunnel` maps localhost to a public URL
- **ngrok** — same idea, quick setup
- **Tailscale Funnel** — if you're already on Tailscale
- **Direct hosting** — if Zeke has a public IP

The MCP server itself can be built in Python (FastMCP) or Node (MCP SDK).
Given your local hardware setup, Python with FastMCP is probably the path of
least resistance.

### Connecting to claude.ai
Once the MCP server is running and exposed via URL:
1. Go to claude.ai Settings → Connectors
2. Add new MCP connector
3. Enter your SSE endpoint URL
4. Claude will discover the tools and they become available in conversations

### State management
Zeke should maintain a persistent state store (SQLite, Redis, or even flat JSON)
that gets updated by the data pipeline. MCP tool calls read from this store.
The tools should be fast — Claude expects responses within a few seconds.
Don't do heavy computation on the MCP call path; pre-compute and cache.

### Data freshness
- Price data: update every 1-5 minutes during market hours
- Cycle counts: recompute on each new daily close
- Confirmation signals: recompute on each new daily close
- Greeks: recompute every 5-15 minutes (or on price change > 0.5%)
- Macro scorecard: recompute on data releases (use FRED release calendar)
- Alerts: evaluate continuously, log when triggered

---

## 5. DASHBOARD QUICK SPEC

Zeke should render a web dashboard (React + D3/Plotly recommended) with these panels:

### Panel 1: Portfolio Overview
- Table: position, qty, cost, current price, P&L ($), P&L (%), Greeks
- Aggregate row: total value, total P&L, net delta, daily theta burn
- Color coding: green = profit, red = loss, yellow = near breakeven
- 1256 vs non-1256 breakdown with estimated tax impact

### Panel 2: Cycle Timeline
- Horizontal bars for each tracked instrument
- Bar shows: [DCL] ——— current day ——— [midpoint] ——— [timing window] ——— [max]
- Badge overlay: RT/LT/MT/Pending
- Cycle failure indicator: red flash if detected
- Nested: daily cycles within weekly cycle visualization

### Panel 3: Confirmation Scanner
- Per-instrument grid showing 4 confirmation methods
- Each cell: green (firing), gray (not firing), yellow (approaching)
- Composite score prominently displayed: 0-4
- Historical accuracy: % of signals that led to profitable entries

### Panel 4: Scenario Heatmap
- X-axis: GLD price ($400-600)
- Y-axis: Date (now through expiry)
- Cell color: P&L from deep red (max loss) to deep green (max profit)
- Breakeven line highlighted
- Current price + date crosshair

### Panel 5: Macro Scorecard
- 5 cards, one per factor
- Each card: factor name, current reading, trend arrow, bullish/neutral/bearish badge
- Composite score bar: -5 to +5

### Panel 6: Action Engine
- Current active signal (if any) with full conditions checklist
- Each condition: checkbox (met/not met)
- Recommended action in bold
- Historical signals log below

### Panel 7: Alerts Feed
- Reverse chronological list
- Severity color coding: blue (info), yellow (warning), orange (high), red (critical)
- Timestamp, event, action taken/recommended

---

## 6. FILES IN THIS PACKAGE

```
zeke_integration/
├── zeke_portfolio_intelligence_spec.json   # Full machine-readable state + config
├── zeke_system_context.md                  # System prompt for Claude API calls
├── zeke_claude_integration_spec.md         # This file — architecture + MCP design
└── GLD_Metals_Roadmap.md                   # The human-readable trade plan
```

### Tonight's workflow:
1. Drop all 4 files into the Zeke project
2. Have Zeke parse the JSON spec first — that's the structured data
3. Feed the system context as the operating manual
4. Use this integration spec for the MCP and API architecture
5. The roadmap is reference — Zeke can use it for validation

---

## 7. PRIORITIES

**Build first (gets you live dashboard):**
1. Data pipeline — price feeds for GLD, XAUUSD, SPX, etc.
2. Cycle counting algorithm on daily OHLCV data
3. Portfolio tracker with live P&L from E*TRADE
4. Dashboard rendering (panels 1, 2, 4)

**Build second (gets you autonomous signals):**
5. Confirmation signal scanner
6. Alert rules engine
7. Claude API integration for natural language recs
8. Dashboard panels 3, 5, 6, 7

**Build third (closes the loop):**
9. MCP server so Claude in this project can call Zeke live
10. Automated cycle low detection + entry recommendation pipeline
11. Opportunity scanner across watch list instruments
12. Backtest engine to validate cycle timing accuracy on historical data
