# Interview Map: The Agentic Revenue Brief, Requirement by Requirement

For each requirement in the brief, this map gives three things:
- **where it lives in the code**
- **what I'd say**
- **the evidence from my earlier projects** (Week 10: Conversion Engine, Week 11: Tenacious-Bench) that I've done it before.

## The nine requirements

| # | Requirement | Where in the code | What I'd say | Earlier evidence |
|---|---|---|---|---|
| 1 | Single-responsibility agents + an orchestrator that owns deal state | [agents.py](agents.py) (6 agents), [orchestrator.py](orchestrator.py) | "Agents only *propose*; the orchestrator is the only thing that changes the world. That one decision makes safety, idempotency and audit simple." | W10 had separate modules and a channel-router state machine; this adds a real orchestrator over *deals*. |
| 2 | Core skills + per-segment config packs; new segment = no code change | [skills/](skills/), [packs/brands.yaml](packs/brands.yaml), [packs/agencies.yaml](packs/agencies.yaml) | "Scoring rules, weights, hooks, templates, SLAs and IO terms are YAML. Agencies is a new file. A test proves no agent, skill or policy file names a segment." | W11's rule-pack registry, upgraded from Python code to config. |
| 3 | Durable, idempotent triggers (webhooks, schedules, SLA timers) | [store.py](store.py), `Orchestrator.ingest/tick`, [api.py](api.py) webhooks | "UNIQUE idempotency key per event; per-action keys so a retry never re-sends; timers are rows; HMAC on webhooks; dead-letter after 3 attempts." | W10's webhooks were in memory with no idempotency. I fixed exactly that gap here. |
| 4 | Fit / intent / engagement, tier, a reason for each score | [skills/scoring.py](skills/scoring.py) | "Every point has a sentence. Signals outside their window are *ignored and explained*: 'Ignored: funding on 2024-02-01 is outside its 180-day window'." | **The W10 stale-signal bug.** My audit found the old system pitched a 2014 round as 'recent'. Recency windows are built in from day one here. |
| 5 | Autonomy policy: low-risk auto, high-risk approval | [policy.py](policy.py) | "A 10-rule ladder in code. Packs can only tighten. Approvals re-check the kill switch and opt-out at execution time, and stale queued emails expire." | W11's pre-send policy gate: 'the model proposes, policy disposes'. |
| 6 | Knowledge loop: transcripts and replies become lessons that feed outreach and briefs across segments | [skills/lessons.py](skills/lessons.py), [skills/transcripts.py](skills/transcripts.py) | "Each lesson has an evidence quote, a scope, an email line and a brief note. Emails list `lessons_used`. A brand-call lesson shapes the agency first touch." | W11's human labels became the v0.3 work list; this automates that loop. |
| 7 | Tracking: exit criteria, reminders, stalls, flags, digests | [skills/tracking.py](skills/tracking.py), `TrackerAgent` | "Stall = days *in stage* past the SLA, not days without activity. Otherwise our own follow-ups would hide a stuck deal." | W10's router had STALLED as a state but no timers. |
| 8 | IO: generate → validate → approve → e-sign → close | [skills/io_docs.py](skills/io_docs.py), `DealDeskAgent` | "The validator works like my W11 evaluator: deterministic rules, each violation with a code and evidence. A valid IO still needs a human." | W11's evaluator design: evidence per violation. |
| 9 | Guardrails: scoped tools, untrusted inbound, audit log, kill switch | [tools.py](tools.py), [sdk_runtime.py](sdk_runtime.py), `Store.audit`, `KillSwitch` | "Three layers of scoping: ToolBelt, action roles, SDK hooks. Injection is flagged, never obeyed. The audit log is hash-chained, so tampering is detectable." | W10's kill switch (`OUTBOUND_ENABLED=false`); W11's 'inbound content is data'. |

## Constraints

| Constraint | How it's met |
|---|---|
| HubSpot as system of record (mock OK) | `MockHubSpot` implements the CRM port ([ports.py](ports.py)); a real client is a drop-in. |
| Claude Agent SDK runtime | [sdk_runtime.py](sdk_runtime.py), behind `REVENUE_RUNTIME=claude`. See the details below. Deterministic agents are the default and the fallback. |
| Python, modular, SOLID | See the mapping below. |
| Mock data | [data/](data/): leads, enrichment, replies (including an injection), a Fireflies transcript; IO template in [packs/](packs/). |

**Claude Agent SDK runtime, in detail:**
- `tools=[]` (no built-in tools), `setting_sources=[]` and a scoped in-process MCP server.
- `can_use_tool` and a `PreToolUse` hook deny out-of-scope calls.
- `propose_action` is checked against the agent's role.

**SOLID, mapped:**

| Principle | Where it shows |
|---|---|
| **S** Single responsibility | One agent per job; the executor does not decide policy. |
| **O** Open/closed | New segments are packs; new channels are adapters. |
| **L** Liskov substitution | Any `Agent` works with the orchestrator and with the SDK runtime. |
| **I** Interface segregation | Small ports in [ports.py](ports.py). |
| **D** Dependency inversion | Agents depend on a ToolBelt, never on adapters. |

## The 15-minute live run

Use the console's Revenue desk (`python -m dashboard.server`, then the **Revenue desk** tab), or the CLI (`python -m revenue.demo`).

| Step | What happens | Point to make |
|---|---|---|
| 1. Brand leads arrive | Three companies come in and land in tiers A, B and D. | Open PeakForm to show the stale 2024 funding was ignored. Note that the tier-A email is **queued** while tier B was auto-sent. |
| 2. Approve the tier-A email | The email goes out. | Point at the hook: it cites only an in-window signal. |
| 3. Sunny Bowl's reply | Arrives with a pricing request and a prompt-injection line. | It is classified *interested* and flagged for pricing and injection. The deal is **not** marked won. The second, duplicate delivery is ignored. |
| 4. PeakForm opts out | The prospect is marked opted out. | No agent can email them now. |
| 5. Meeting booked | A call brief is built. | It already includes lessons learned from the reply. |
| 6. Fireflies transcript | Budget, flight dates, decision maker, need, products and competitor are extracted, each with evidence. | The deal qualifies itself, and the IO is generated and validated. It then **waits for approval**. |
| 7. Approve the IO, then e-signature completed | The deal moves to closed won. | A handoff task is created. |
| 8. Agency leads arrive | The new segment works from `agencies.yaml` alone. | The first touch uses the measurement lesson learned on the **brand** call. |
| 9. Kill switch on | Approval of an external action is refused. | Even a human approval can't send while it's on. |
| 10. Eight days pass | Follow-ups fire and Northwind is flagged as stalled. | The digest summarises it. |
| Finish | Audit chain shown as intact. | |

## Likely questions, short answers

- **"How does this scale?"**
  - *Today:* one SQLite event log in one process.
  - *Production:* Postgres for the event log plus a queue or Temporal for workers, partitioned by `deal_id` so events for one deal stay ordered. The same idempotency keys keep it at most once per action.
  - *Fan-out:* the agents are stateless, so they scale horizontally.
- **"What are the failure modes?"**
  - *Duplicate webhooks:* the key makes them no-ops.
  - *Crash mid-event:* the event retries and completed actions are skipped.
  - *Poison event:* it's parked as dead.
  - *Bad LLM output:* it's only a proposal and goes through the policy.
  - *SDK or model outage:* the deterministic fallback runs, and the fallback is audited.
  - *Prompt injection:* it's flagged and routed to a human.
  - *Stale approvals:* they expire.
- **"How would you evaluate it?"** This is my Week 11 work applied here:
  - a labelled set per segment for reply classes, transcript fields and scoring tiers
  - precision and recall, plus human-vs-system agreement (κ)
  - policy-escape tests in CI
  - online, an A/B test on reply rate and meetings booked, with the minimum detectable effect computed first.

  And I'd watch the same trap I found before: offline "safe" does not mean persuasive.
- **"Why deterministic agents by default?"** They're reproducible, testable and free. The LLM goes where language quality pays off (drafting, transcript digestion), and it's fenced by the same policy, so swapping it in changes quality, not safety.
- **"What's mocked, and what's next?"**
  - *Mocked:* HubSpot, email, e-sign, Fireflies and enrichment, each behind a port.
  - *Next:* LLM transcript extraction with schema validation; real HubSpot sync with conflict handling; an approval-latency service-level target with escalation; a lessons-quality review, since lessons can be wrong too.
