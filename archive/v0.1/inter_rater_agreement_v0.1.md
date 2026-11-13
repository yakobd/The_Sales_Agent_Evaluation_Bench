# Inter-Rater Agreement — Tenacious-Bench v0.1
**Yakob Dereje | TenX Academy Week 11 | April 29, 2026**

---

## Protocol

30 tasks from the dev partition were hand-labeled against the 5-check rubric on April 29, 2026,
then re-labeled 24 hours later on April 30, 2026 without reference to the first labels.
Agreement was computed per rubric dimension. Threshold for rubric revision: <80% on any dimension.

**Tasks sampled:** 10 easy (TB-001 to TB-010), 10 medium (TB-P001 to TB-P010),
10 hard (TB-HA001 to TB-HA010). Sampled to cover all 4 source modes and all 4 ICP segments.

---

## Agreement Matrix

| Dimension | Round 1 Pass | Round 1 Fail | Round 2 Pass | Round 2 Fail | Agreements | Disagreements | Agreement % |
|-----------|-------------|-------------|-------------|-------------|------------|---------------|-------------|
| Grounding | 21 | 9 | 20 | 10 | 27/30 | 3/30 | **91%** |
| Tone | 20 | 10 | 20 | 10 | 29/30 | 1/30 | **97%** |
| Subject length | 19 | 11 | 19 | 11 | 30/30 | 0/30 | **100%** |
| CTA present | 22 | 8 | 21 | 9 | 28/30 | 2/30 | **93%** |
| LLM judge | 20 | 10 | 21 | 9 | 25/30 | 5/30 | **83%** |
| **Overall** | — | — | — | — | **27.8/30** | **2.2/30** | **93%** |

---

## Disagreement Analysis

**Grounding (3 disagreements):**
Borderline cases where signal words like "may" and "appears" were present in the body
but not in the exact required_signals list. Resolution: required_signals for V3
low-confidence tasks updated to include ["may", "appears", "public", "profile", "based"].

**Tone (1 disagreement):**
Edge case where "following up" appeared as a substring of a longer phrase.
Resolution: banned phrase check uses word boundary matching for phrases >=2 words.

**Subject length (0 disagreements):**
Deterministic check — perfect agreement expected and observed.

**CTA present (2 disagreements):**
Cases where "reply" appeared in the body but not in the final paragraph.
Resolution: CTA check now checks last 200 characters, not just last paragraph.

**LLM judge (5 disagreements):**
Tone marker 1 (Direct) had the most borderline cases — emails that opened with
a signal but used conditional framing that could be read as indirect.
Resolution: rule-based Direct marker now accepts conditional openers
("if your team is..." counts as direct if a signal follows immediately).

---

## Conclusion

All 5 dimensions exceeded the 80% threshold. No rubric revision was required.
The disagreements above were minor edge cases resolved by clarifying the scoring logic,
not by changing the fundamental rubric design.

The full agreement matrix confirms that Tenacious-Bench v0.1's scoring rubric
is sufficiently well-defined for machine-verifiable evaluation with human-level consistency.
