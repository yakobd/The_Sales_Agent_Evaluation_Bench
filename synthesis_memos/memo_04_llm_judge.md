# Synthesis Memo — A Survey on LLM-as-a-Judge
**Gu et al., 2024-2025 | Yakob Dereje | TenX Academy Week 11 | April 29, 2026**

---

## What the Paper Argues

Gu et al. survey the emerging practice of using LLMs to automatically evaluate other
LLM outputs — replacing or augmenting human annotators with a model judge. The paper
documents that LLM judges achieve high correlation with human judgment on many tasks,
but consistently exhibit four failure modes that must be designed around: position bias
(preferring whichever output appears first in the prompt), verbosity bias (preferring
longer outputs regardless of quality), self-enhancement bias (scoring one's own outputs
higher), and preference leakage (favoring outputs that match the judge's own training
distribution). The core recommendation is to use a strong frontier model as a single
judge, with careful prompt engineering to mitigate the four biases.

---

## The Design Choice I Disagree With

The paper recommends using a single strong frontier model as the judge for all
evaluation tasks, on the grounds that frontier models have the best calibration with
human judgment and the most consistent scoring behavior.

I disagree with this recommendation for domain-specific benchmarks where the frontier
model's training distribution conflicts with the domain's style requirements.

---

## My Disagreement — With Evidence From Tenacious-Bench

The Tenacious style guide values brevity and directness above elaboration. A good
Tenacious outreach email is 50-80 words, opens with a specific signal, and ends with
a single low-friction call to action. It does not explain Tenacious's history, list
services, or use transitional phrases.

A frontier model judge trained on internet-scale business writing has learned that
longer, more elaborate emails signal professionalism and effort. This is verbosity
bias applied to a domain where verbosity is explicitly a failure mode. My
scoring_evaluator.py demo confirmed this risk: TB-002, the intentionally bad email
with 7 banned phrases and a 76-character subject line, still received a CTA check
pass because it contained the word "call" — the judge's pattern matching rewarded
surface-level compliance while missing the deeper style violation.

A single frontier model judge would score a 200-word Tenacious email that uses no
banned phrases higher than a 60-word email that perfectly matches the style guide,
simply because the longer email contains more positive signals (more specificity, more
explicit next steps, more context). The style guide's preference for brevity would be
systematically penalized.

My solution is a hybrid judge: rule-based checks run first and are not overrideable
by the LLM component. Subject line length, banned phrases, signal grounding, and CTA
presence are scored deterministically. The LLM judge scores only the five tone markers
where human-like judgment is genuinely needed and rule-based checks cannot capture
nuance. If the rule-based checks fail, the overall score is 0 regardless of what the
LLM judge says. This prevents verbosity bias from rescuing a banned-phrase violation.

This is a direct disagreement with the paper's single-judge recommendation: for
domains with explicit mechanical constraints, a hybrid deterministic-plus-LLM scorer
is more reliable than any frontier model judge operating alone.

---

## The Two Failure Modes Most Relevant to My Implementation

**Verbosity bias** is my primary risk. My `check_llm_judge()` function scores five
tone markers on a 1-5 scale. A longer email with more elaborate language will
naturally score higher on "Specific" and "Action-oriented" even when brevity is the
correct Tenacious response. I mitigate this by capping the LLM judge's contribution
to overall score at 1 of 5 checks — a verbosity-biased LLM judge that scores 5/5 on
tone markers cannot rescue a task that fails the subject length or banned phrase checks.

**Preference leakage** is my secondary risk. My judge model (DeepSeek V3.2) has seen
generic business email templates during pretraining. It may prefer corporate formal
language over the direct Tenacious style — scoring "I hope this message finds you well,
I am reaching out because..." higher than "Yellow.ai's recent restructuring creates a
specific opening." I mitigate this by including the Tenacious style guide's five
positive tone markers explicitly in the judge prompt, anchoring the judge to domain
criteria rather than its generic preference.

---

## Model Family Rotation for My Pipeline

To satisfy the paper's requirement that generator and judge come from different model
families:

- **Generator:** Qwen3-Next-80B via OpenRouter (cheap dev-tier, Alibaba family)
- **Dataset judge:** DeepSeek V3.2 via OpenRouter (cheap dev-tier, DeepSeek family)
- **Held-out evaluator:** Claude Sonnet 4.6 (eval-tier, Anthropic family)

Three different model families across three different pipeline roles. No model judges
its own outputs at any stage. This satisfies both the paper's contamination prevention
guidance and the Week 11 cost discipline rules — the eval-tier model is reserved
exclusively for the sealed held-out slice and is never used during dataset authoring.

---

## One Thing I Agree With Strongly

The paper's finding that pointwise scoring (score this output 1-5) is more reliable
than pairwise comparison (which of these two outputs is better) for automated
evaluation pipelines directly validates my implementation choice. My
`check_llm_judge()` function scores each email independently on five dimensions rather
than comparing it to a reference output. This avoids position bias entirely — there
is no "first" output to prefer when scoring a single email in isolation.

---

*Failure modes addressed: verbosity bias, preference leakage | Model families: Qwen3
(generate), DeepSeek (judge), Claude (eval) | Probe context: TB-002 CTA false positive*
