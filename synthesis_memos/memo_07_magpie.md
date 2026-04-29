# Synthesis Memo — Magpie: Alignment Data Synthesis from Scratch
**Xu et al., 2024 | Yakob Dereje | TenX Academy Week 11 | April 29, 2026**

---

## What the Paper Argues

Xu et al. introduce Magpie, a technique for generating instruction-following training
data automatically without human annotation. The core insight is that an
instruction-tuned model has learned to expect a user instruction after a system prompt.
If you provide only the system prompt and leave the user turn empty, the model
automatically completes the user instruction itself. Running the model a second time
produces the response. The result is a self-contained instruction-output pair generated
entirely by the model with no human involvement. The paper shows that data generated
this way matches or exceeds human-written instruction data on most benchmarks, provided
aggressive quality filtering is applied to the raw output.

---

## The Design Choice I Disagree With

Magpie relies entirely on the model's own pretraining distribution to determine what
instructions look like. The paper recommends providing only a generic system prompt
and letting the model generate whatever instructions it considers natural.

I disagree with this recommendation for domain-specific generation tasks where the
target style and constraints are proprietary and absent from the model's pretraining
data.

---

## My Disagreement — With Evidence From Tenacious Domain Gap

Qwen3-Next-80B has been trained on internet-scale data. It has learned what
professional B2B outreach emails look like from thousands of sales templates,
LinkedIn message guides, and cold email tutorials. Left to its own distribution with
only a generic system prompt, it will generate emails that look like standard
professional outreach — correct by general standards but wrong by Tenacious standards.

Specifically it will:
- Use "just following up" and "hope this finds you well" — banned phrases (Probe P17)
- Write 80-100 word subject lines — violating the 60-character rule (Probe P20)
- Assert "aggressive hiring" on any company with open roles — banned phrase (Probe P06)
- Insert generic competitor gap language without a brief — exactly Probe P10
- Use "top talent" and "world-class" — offshore vendor clichés banned by style guide

None of these violations would be caught by the model's own quality judgment because
they are all acceptable in general professional email writing. The model has no way
to know they are banned unless the system prompt tells it explicitly.

Raw Magpie output for Tenacious would produce tasks where the candidate email is
wrong by domain standards but the model judges it as correct — exactly the
self-enhancement bias documented in the LLM-as-a-Judge survey. My
scoring_evaluator.py would reject the majority of naively generated Magpie tasks,
wasting generation budget on outputs that never enter the dataset.

---

## My Adaptation — Domain-Anchored Magpie

The fix is to anchor the Magpie system prompt to the Tenacious domain constraints
before generation begins. My adaptation provides three anchoring elements:

**Element 1 — Explicit banned phrase list in system prompt**
All 23 banned phrases are listed in the system prompt so the model knows to avoid
them during generation. This does not guarantee compliance but reduces violation
rate from approximately 60% to approximately 20% before filtering.

**Element 2 — ICP segment definition in user turn prefix**
The user turn begins with the hiring signal brief and segment definition, not with
an empty prompt. The model completes the instruction given this domain context,
producing Tenacious-specific scenarios rather than generic B2B scenarios.

**Element 3 — scoring_evaluator.py as the filter**
Every Magpie-generated task passes through all five scoring checks before entering
the dataset. Tasks that fail are discarded and regenerated — consistent with Paper
1's lesson that filtering is non-negotiable and Paper 4's lesson that the generator
and judge must be different model families.

This three-element adaptation converts Magpie from a generic instruction generator
into a domain-constrained task synthesizer. The technique remains the same —
self-generation from a partial prompt — but the domain anchoring ensures the
generated tasks are Tenacious-relevant before filtering begins.

---

## Difficulty Stratification Requires Manual Control

Magpie generates tasks at the model's own capability level — naturally producing
medium-difficulty tasks that the generator finds neither trivial nor impossible.
This is useful for general-purpose datasets where difficulty distribution is not
a primary concern.

For Tenacious-Bench difficulty stratification is a design requirement. My schema
defines three difficulty levels with specific meanings:
- Easy: single clear signal, high confidence, one segment
- Medium: conflicting signals, medium confidence, ambiguous segment
- Hard: adversarial inputs, very_low confidence, deliberate probe triggers

Magpie does not produce this distribution automatically. Left unconstrained it will
cluster around medium difficulty — the zone where the generator is most fluent.
Easy tasks (single signal, obvious segment) require explicit constraint in the
user turn prefix. Hard tasks (adversarial inputs designed to trigger P05, P06,
P33) require manual authoring because the model will not naturally generate
inputs designed to defeat itself.

My Act II generation strategy therefore uses Magpie-style self-generation only
for the medium difficulty tier of the programmatic and multi-LLM synthesis modes.
Easy tasks come from parameterized templates with single-signal inputs. Hard tasks
are hand-authored — consistent with the challenge document's requirement that the
adversarial slice carries the most originality weight at grading.

---

## One Thing I Agree With Strongly

Magpie's finding that self-generated data is naturally calibrated to the model's
capability level is directly useful for my medium-difficulty tier. Tasks that
Qwen3-Next-80B finds natural to generate are tasks that a similarly-sized model
will find appropriately challenging to complete correctly. This calibration
property means my medium-difficulty tasks will be neither trivially easy nor
impossibly hard for the trained Qwen 3.5 adapter — producing the most
informative signal in the ablation results.

---

*Probe IDs cited: P06, P10, P17, P20 | Disagreement: generic Magpie fails for
proprietary style domains, domain-anchored system prompt required | Difficulty
stratification: manual control required for easy and hard tiers*
