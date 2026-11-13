# Agentic Revenue System: Design

**Scope:** an AI agent system that runs the revenue lifecycle (prospect → enrich → score → outreach → reply → meeting → qualify → proposal/IO → signature → handoff) for an advertising platform with several customer segments. A working vertical slice for **brands** is included. A second segment, **agencies**, is added as a config pack only.

## 1. Architecture

```
 TRIGGERS (durable, idempotent)                 ORCHESTRATOR (owns deal state)          PORTS (* = mocked)
 ─────────────────────────────                  ────────────────────────────────        ──────────────────
 webhooks: email reply, Fireflies,   ──► Store.events (UNIQUE key) ──► route by event   CRM: HubSpot*
   e-sign, booking (HMAC-verified)                 │                       │            Email: outbox*
 schedule: scheduler tick ──► due timers           ▼                       ▼            E-sign: envelopes*
 internal: deal.stage_changed           6 single-responsibility agents (scoped)   Fireflies: JSON*
                                          │  read + compute only -> ProposedActions  Enrichment*
                                          ▼
                                  AutonomyPolicy.evaluate  (code)   ── AUTO ──► Executor ──► ports
                                          │                          ── APPROVAL ─► approval queue ─► human (console)
                                          │                          ── BLOCK ────► audit only
                                          ▼
                     Audit log (append-only, SHA-256 hash chain) · Kill switch (durable setting)
 Segment packs (YAML): ICP, scoring rules/weights, messaging, hooks, templates, SLAs, exit criteria, IO terms
 Knowledge store: lessons (scope "all" or one segment) ─► retrieved into outreach + call briefs
```

**Key decision.** Agents never act; they only *propose*. The orchestrator is the only component that changes the world, and every proposal passes the autonomy policy in code first. A prompt-injected or buggy agent can at most produce a proposal that gets blocked or queued. Each stage change is itself an idempotent event, so the whole lifecycle can be replayed from the event log.

## 2. Agents (responsibility, tools, actions it may propose)

| Agent | Handles | Tools (scope) | May propose |
|---|---|---|---|
| **Prospecting** | `lead.created`, `engagement.recorded` | enrich_company, score_lead, get_* | update_deal |
| **Outreach** | stage → scored, follow-up timer | fresh_signals, retrieve_lessons, draft_email, get_* | send_email, schedule_timer |
| **Inbox** | `email.replied` | classify_reply, extract_lessons | update_deal, flag, create_task, record_lesson |
| **Knowledge** | `meeting.booked`, `transcript.ready` | build_call_brief, fetch_transcript, digest_transcript, retrieve_lessons | update_deal, create_task, record_lesson |
| **Deal Desk** | stage → qualified, `esign.completed` | propose_line_items, build_io, render_io, validate_io | generate_io, send_io_for_signature, close_deal, handoff |
| **Tracker** | stage changes, SLA timers | detect_stall | schedule_timer, flag, create_task |

Scoping is enforced twice:
- **Tools.** The ToolBelt refuses and audits any out-of-scope call.
- **Actions.** The orchestrator rejects any action type outside the agent's `emits` set.

Under the Claude runtime a third layer applies, the SDK permission hooks (§6).

## 3. Skills and segment packs

**Core skills** are pure, segment-agnostic functions, unit-tested in `revenue/skills/`:

| Skill | What it does |
|---|---|
| `scoring` | Fit, intent and engagement sub-scores, a tier, and a reason per point. Signals outside their window are ignored and explained. |
| `outreach` | Template, plus the freshest in-window signal, plus lessons. Fails on a missing placeholder. The hook may cite only an in-window signal; otherwise a neutral question. |
| `replies` | Classification and flags (pricing, contract, competitor, injection, urgency). Strips the quoted thread first. |
| `transcripts` | Fireflies JSON becomes deal fields with evidence, plus lessons. |
| `lessons` | Extraction and scoped retrieval. Content-hash IDs, so lessons are never duplicated. |
| `io_docs` | Builds an IO from deal data and validates it (12 violation codes). |
| `tracking` | Exit criteria, stall detection (days in stage vs SLA) and the digest. |
| `call_brief` | Builds the meeting brief, including relevant lessons. |

**A segment pack** is one YAML file holding:
- ICP and scoring rules (`field / op / value / points / reason`)
- signal windows and weights
- tier thresholds
- value props, hooks and templates
- stage SLAs and exit criteria
- the transcript lexicon
- IO terms: rate card, minimum budget, maximum discount, payment terms
- optional *stricter* autonomy settings

Packs are validated at load time. **A new segment is a new file.** A test copies a brands-only pack directory, shows that an agency lead is rejected, adds `agencies.yaml`, and the agency lead then scores, tiers and gets outreach. Another test asserts that no agent, skill, policy or orchestrator file names a segment.

## 4. Triggers (durable and idempotent)

| Trigger | Event | Idempotency key |
|---|---|---|
| Lead import / form webhook | `lead.created` | `lead:{deal_id}` |
| Email provider reply webhook | `email.replied` | provider message id |
| Booking webhook | `meeting.booked` | booking id |
| Fireflies webhook | `transcript.ready` | transcript id |
| E-sign webhook | `esign.completed` | envelope id |
| Scheduler tick (cron) | `timer.fired` (follow-ups, SLA checks) | timer key |
| Executor | `deal.stage_changed` | `stage:{deal}:{from}->{to}` |

**Delivery guarantees:** events are processed at least once, and each action takes effect at most once.
- **Duplicate events.** Every event has a UNIQUE key, so a re-delivered webhook is ignored.
- **Retries.** Events retry up to 3 times, then are parked as `dead` for a human.
- **Duplicate effects.** Each action has a key (`event | agent | index | type`) recorded once it completes. A retried event never re-sends an email or re-queues an approval (approval IDs derive from the key).
- **Signatures.** Webhooks are HMAC-verified.
- **Timers.** Timers are rows in the database, so a restart loses nothing.

## 5. Data model

The system of record is HubSpot (mocked). Deal state is mirrored through the CRM port.

- **Company:** id, name, domain, segment, attributes (firmographics), signals `[{type, date, detail}]`.
- **Contact:** id, company_id, name, email, title.
- **Deal:** id, company_id, contact_id, segment, stage, tier, score `{fit, intent, engagement, total, tier, reason}`, fields (budget, timeline, decision_maker, need, products, flight dates, line items, io_*), flags, touches, opted_out, stage_since, last_activity.
- **Store:** `events(key UNIQUE, type, payload, status, attempts)` · `timers(key, due_at, payload)` · `approvals(id, action, verdict, status)` · `lessons(id, text, tags, scope, evidence, outreach_line, brief_note, uses)` · `audit(seq, actor, kind, data, prev_hash, hash)` · `actions_done(key)` · `settings` (kill switch).

## 6. Autonomy policy (enforced in code)

The policy is a single ladder in `policy.py`: the first matching rule decides.

| # | Rule | Decision |
|---|---|---|
| 1 | Kill switch on, and the action is external (send email, send pricing, send IO) | **Block** |
| 2 | Prospect opted out | **Block** |
| 3 | Placeholder or banned phrase in the email | **Block** |
| 4 | Follow-up cap reached | **Block** |
| 5 | IO for signature, or pricing | **Approval** (always) |
| 6 | Close without a verified e-sign event | **Approval** |
| 7 | Email mentions pricing or contract terms | **Approval** |
| 8 | First touch to a tier-A lead (floor; a pack may add tiers) | **Approval** |
| 9 | Deal flagged for a human (pricing, contract or injection) | **Approval** |
| 10 | Anything else | **Auto** |

Supporting rules:
- **Packs can only tighten.** Fields a pack might use to relax the policy are never read (tested).
- **Approvals re-check at execution time.** The kill switch and opt-out are checked again when an approval runs.
- **Queued cold emails expire** when the deal moves past outreach.
- **Inbound text is data.** Replies and transcripts are only labelled. Injection attempts are flagged and routed to a human; the deal is never moved by their content.

**Claude runtime.** Each agent gets an in-process MCP server exposing only its tools.
- Built-in tools and local settings are off: `tools=[]`, `setting_sources=[]`, `strict_mcp_config`.
- `can_use_tool` and a `PreToolUse` hook deny anything out of scope.
- `propose_action` rejects action types outside the agent's role.
- Outputs still go through the same policy.
- If the SDK session fails, the deterministic agent runs instead, and the fallback is audited.

## 7. Knowledge loop

Replies and transcripts are scanned for objection and resonance patterns, using a core lexicon shared by every segment plus pack extensions.

Each lesson stores the evidence quote, a scope (`all` crosses segments), an `outreach_line`, a `brief_note` and a value prop to lead with.

Retrieval ranks lessons by tag overlap with the prospect's signals and interests, then by reuse count. **Visible use:**
- every email carries `lessons_used`
- every call brief lists its lessons
- `uses` counts are shown.

In the demo, a measurement-proof lesson learned on a *brand* call shapes the *agency* first touch.

## 8. Tracking and IO automation

**Tracking:**
- Exit criteria per stage come from the pack (e.g. *qualified* needs budget, timeline, decision maker and need).
- When the transcript fills them, the deal advances automatically; otherwise a task names what's missing.
- SLA timers flag deals that stay in a stage past the SLA. Days in stage are counted, so our own follow-ups can't hide a stalled deal.
- A daily digest summarises stages, tiers, pending approvals, stalls and flags.

**IO automation:** generate from deal data (rate-card line items) → validate → approval → e-sign → the signed webhook closes the deal → handoff task.

The validator checks required fields, flight dates (valid, not in the past), currency, known products and CPMs within the rate card, the minimum budget, the discount cap, totals matching the agreed budget, the signatory's email domain against the company's, and unfilled placeholders.

## 9. Phased rollout

| Phase | Scope | Autonomy | Exit gate |
|---|---|---|---|
| 0 Shadow | All agents run on live data; nothing is sent | None: drafts only | Human edit rate on drafts < 20%; reply and transcript labels ≥ 90% correct vs humans |
| 1 Assist | One segment (brands), one team | Internal actions auto; every send needs approval | No policy escapes in 4 weeks; approval latency < 4 h |
| 2 Guarded autonomy | Tier B/C follow-ups auto; tier-A first touch, pricing and IO stay human | As in §6 | Reply rate ≥ human baseline (A/B test, MDE set up front); unsubscribe rate ≤ baseline |
| 3 Scale | Agencies, publishers and demand partners via packs | Per-pack tightening | Per-segment evaluation sets pass before go-live |

## 10. Trade-offs and what is mocked

**Trade-offs:**
- **Deterministic first, LLM optional.** The default agents are rule-based, so the demo and tests are reproducible and cost nothing. The Claude runtime is used where language quality matters (drafting, transcript digestion), and its output is bounded by the same policy. *Cost:* the rules miss nuance; the LLM path is less predictable. Both are measured against the same tests.
- **SQLite event log.** It is enough for one process and keeps the design honest about durability. *Production:* Postgres plus a queue or workflow engine (e.g. Temporal), with the same keys.
- **Regex extraction** of budgets, dates and roles is transparent but brittle. It is the first candidate for an LLM with schema validation.

**Mocked:** HubSpot, email, e-sign, Fireflies and enrichment, each behind a port. Swapping in a real client changes no agent.

**Evaluation plan:** a per-segment labelled set for scoring, reply labels and transcript fields (precision and recall); policy-escape tests; and online A/B tests on reply rate and meetings booked.
