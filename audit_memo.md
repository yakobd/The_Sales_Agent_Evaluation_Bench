# Audit Memo — What τ²-Bench Retail Fails to Grade
**Tenacious-Bench v0.1 | Yakob Dereje | TenX Academy Week 11 | April 28, 2026**

---

## The Gap in One Sentence

τ²-Bench retail measures whether an agent can complete a generic e-commerce task correctly.
It cannot measure whether an agent sends a factually grounded, tone-compliant, commercially
safe outreach email to a specific B2B prospect — which is the only thing that matters for
Tenacious.

---

## What τ²-Bench Retail Measures

τ²-Bench retail tasks cover consumer e-commerce: add to cart, apply coupon, track order,
return item. The scoring rubric rewards task completion — did the agent reach the correct
final state? The Week 10 baseline was pass@1=0.333. The confidence-aware abstention
mechanism lifted this to pass@1=0.500 (Delta A +0.167, p=0.0005).

This score is a useful reasoning baseline. It does not capture the failures that damage
Tenacious in production. Three structural gaps explain why.

---

## Gap 1 — No Grounding Requirement

τ²-Bench has no signal enrichment step, no external data dependency, and no penalty for
fabricating a plausible-sounding claim.

Probe P06 documents the email agent asserting "aggressive hiring" for a company with fewer
than 5 open roles. Probe P10 documents generic competitor gap language inserted before the
brief was generated. Probe P30 documents assertive language on confidence=very_low signals.

Trace thread_20260424_021728 shows an early run where low enrichment confidence did not
suppress assertive language. Trace thread_20260427_110356 shows the corrected behavior.
τ²-Bench scores both identically because the email was sent in both cases. Tenacious-Bench
must score them differently.

---

## Gap 2 — No Tone or Style Constraint

τ²-Bench has no banned-phrase list, no subject-line length constraint, and no prohibition
on condescending framing.

The Tenacious style guide defines 23 banned phrases, 5 positive tone markers, and a
60-character subject line limit. Probes P16 through P20 document five tone failure categories:
"bench" used with a prospect, "just circling back" language, condescending gap framing,
emojis in cold outreach, and subject line overflow.

Traces thread_20260425_211934 and thread_20260425_221859 show two same-day runs where tone
compliance varied — one passed 5/5 markers, one flagged a 63-character subject line.
A τ²-Bench-tuned agent would pass both tasks and fail every Tenacious style constraint.

---

## Gap 3 — No Commercial Safety Dimension

τ²-Bench has no concept of over-commitment, pricing exposure, or bench capacity limits.

Probes P11, P12, P13, and P14 document four categories of over-commitment. Probe P33 — the
highest-priority unresolved failure — documents sector mismatch in competitor gap briefs:
the fallback random sample can compare Yellow.ai to unrelated sectors —
a nonsensical finding τ²-Bench cannot penalize.

---

## Target Failure Mode

The highest-ROI target is signal grounding — the cluster of failures where the agent makes
claims not supported by enrichment data. This covers P05, P06, P09, P10, P30, and P33.
It is the most frequent, most measurable, and most brand-damaging failure mode in the
Week 10 probe library.

Tenacious-Bench v0.1 asks one question per task: given a hiring signal brief, does the
agent output contain only claims directly supported by the brief fields?

---

## Scoring Schema Preview

Four machine-verifiable conditions per task:
1. Every factual claim maps to a field in the supplied hiring_signal_brief.json
2. No banned phrase from the Tenacious style guide appears in subject or body
3. Subject line is 60 characters or fewer
4. Email ends with a calendar link or explicit next-step offer

Score 1 if all four pass, 0 otherwise. No human judgment required.

---

*Probes: P05, P06, P09, P10, P11-P14, P16-P20, P30, P33 | Traces: thread_20260424_021728, thread_20260425_211934, thread_20260425_221859, thread_20260427_110356, thread_20260428_174753, thread_20260428_175230*
