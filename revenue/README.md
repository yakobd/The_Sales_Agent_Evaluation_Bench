# Agentic Revenue System

This system takes a lead all the way to a signed insertion order (IO). It is built for an AI advertising platform that sells to brands, agencies, publishers and demand partners.

- **Single-responsibility agents** propose actions.
- **An orchestrator** owns deal state.
- **An autonomy policy in code** decides whether each action runs automatically, waits for a human, or is blocked.
- **Segment packs** (YAML) hold everything that differs per segment.

| Document | What it is |
|---|---|
| **[DESIGN.md](DESIGN.md)** ([PDF](DESIGN.pdf), 3 pages) | The architecture: agents, skills, triggers, data model, autonomy policy and rollout |
| **[INTERVIEW_MAP.md](INTERVIEW_MAP.md)** | Every requirement mapped to code, plus the demo script and Q&A |

## Setup

Run these from the repository root:

```bash
python -m venv venv && source venv/bin/activate      # Windows Git Bash: source venv/Scripts/activate
pip install -r requirements.txt
```

## Run

```bash
python -m revenue.demo                      # full vertical slice in the terminal (brands, then agencies, then controls)
python -m revenue.demo --segment brands     # one segment only
python -m dashboard.server                  # console at http://127.0.0.1:8000, "Revenue desk" tab
pytest tests/test_revenue.py -q             # 67 tests for core skills, policy, durability, extensibility and SDK wiring
```

In the console, **Run next step** feeds in the scripted inputs: leads, replies, a meeting, a transcript, the e-signature, agency leads, and time passing. **You** approve or reject queued actions. The kill switch, the pipeline, deal timelines, lessons, the digest and the audit-chain status all update live.

**Webhooks:** `POST /api/revenue/webhooks/{email-reply|fireflies|esign|calcom}`.
- **Signature:** send `X-Cool-Signature` as the hex HMAC-SHA256 of the request body, keyed with `REVENUE_WEBHOOK_SECRET`.
- **Retries are safe:** a re-delivered webhook is accepted but ignored.

## Claude Agent SDK runtime (optional)

```bash
REVENUE_RUNTIME=claude REVENUE_MODEL=claude-opus-5-5 python -m revenue.demo
```

This runs the outreach and knowledge agents as Claude Agent SDK sessions.

**Requirements:**
- Anthropic credentials that the bundled Claude Code CLI can find (`ANTHROPIC_API_KEY` or a logged-in profile).
- Real API spend, capped at `max_budget_usd=0.25` per session.

**What each agent can do:** it sees only its own tools, through an in-process MCP server.
- Built-in tools are off (`tools=[]`), and local settings and MCP configs are ignored.
- Out-of-scope tool calls are denied by both `can_use_tool` and a `PreToolUse` hook.
- The model can only *propose* actions, and those go through the same policy.

**If a session can't start,** the deterministic agent runs instead and the fallback is written to the audit log.

## Layout

| Path | What |
|---|---|
| `domain.py` · `ports.py` | Dataclasses (deal, action, lesson, …) and the Protocols adapters implement |
| `packs.py` · `packs/*.yaml` | Pack loader and validator; `brands.yaml`, `agencies.yaml`, `io_template.md` |
| `skills/` | Scoring, outreach, replies, transcripts, lessons, io_docs, tracking, call_brief: pure and tested |
| `agents.py` · `tools.py` | Six agents, each with declared tools (scope) and allowed actions (emits); the scoped ToolBelt |
| `policy.py` | Autonomy policy and kill switch |
| `orchestrator.py` | Event processing, policy application, executor, approvals, stale-approval expiry |
| `store.py` | SQLite event log (idempotent), timers, approvals, lessons, hash-chained audit |
| `adapters/mocks.py` | HubSpot, email, e-sign, Fireflies and enrichment mocks |
| `sdk_runtime.py` | Claude Agent SDK runtime |
| `api.py` · `demo.py` · `system.py` | Console API and webhooks, the CLI demo, and the composition root |
| `data/` | Mock leads, enrichment, replies and the transcript (fictional companies, `.example` domains) |
