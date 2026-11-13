# Memo: What to ship in the outreach email writer

**To:** Tenacious CEO and CFO · **From:** Yakob Dereje · **Re:** Week 11 results (Tenacious-Bench v0.2) · **Supersedes:** the May 2026 memo, whose numbers are retracted

---

## Decision requested

**Recommendation:** approve the **honest rule-based composer (v2)** as the production email writer now. Keep the **fine-tuned 2B model** in shadow mode until a usefulness test is done.

## What we found

**1. The current composer would embarrass us on real prospects.**

- On 204 real companies from Crunchbase, the Week 10 composer sent a safe, accurate email to **10**.
- On 54 unseen companies it managed **2**. Almost all of the other 52 called a 2014 funding round "recent", described a 2020 layoff as "your recent restructuring", or claimed funding that isn't in the data.
- A prospect who checks any of these will conclude we didn't do our research. That is the opposite of our pitch.

**2. A small fix in the rules removes almost all of it, at no cost.**

- The v2 composer only cites a signal that is inside its buying window: funding within 180 days, layoffs within 120, leadership changes within 90. Otherwise it sends a short note that asks rather than asserts.
- It passes **204/204** of the real-company briefs and **53/54** unseen companies.
- It is a deterministic template and makes no model calls.

**3. A fine-tuned small model learned the same discipline, but it is not better yet.**

- We trained a 2B open model on 512 vetted examples. It took 17 minutes on a free GPU, and the training data cost $0.31.
- It produced a safe, sendable email **87%** of the time on unseen prospects, up from **1.5%** for the same model untrained and **10%** for the same model given the full rulebook.
- Unlike the template, **it can also answer replies**. It handled 12 of 14 prospect replies safely, against 5 for the rulebook-prompted model.
- On cold first emails it is **worse than the v2 rules**: 87% vs 98%.
- In 2 of 14 replies it **promised 10 senior Go engineers when we have 4 available**. That is a commitment we could not keep.

**4. Our test measures safety, not sales.**

- A pass means the email made no false, stale or risky claim. It does not mean the email would get a reply.
- A two-sentence note with no content passes most cold tasks.
- **Neither system has been shown to book more meetings.** That needs a live A/B on real sends, which we have not run.

## Options

| Option | Cost | Risk | Upside |
|---|---|---|---|
| **A. Ship v2 rules now** *(recommended)* | ~$0 | Low. Bland emails on companies with no current signal. | Stops the factual errors today. |
| B. Ship the fine-tuned model | ~3 s per email on a small GPU, or about the cost of a hosted 2B endpoint | Medium. Over-commits engineers in some replies. | Writes replies as well as cold emails. |
| C. Keep the Week 10 composer | $0 | **High.** 96% of emails fail, almost all on a false or stale claim. | None. |

## What it would take to move to B

1. **Hard limits in code.** Add a bench-capacity check and a signal-recency check that block any draft, whoever wrote it. These are a few days of work, and they would have stopped all 5 of the model's commercial and recency errors.
2. **A usefulness score.** Add a specificity check (does the email name the actual finding?) to the evaluator. On honesty, the current evaluator agrees with our own human labels only 63% of the time, and it mostly misses vague overclaims.
3. **A two-week live test.** Run v2 and the model on a sample of real sends, and measure reply rate and meetings booked. This is the only number that justifies the switch.

## Budget

| Item | Cost |
|---|---|
| All model API spend this phase | $0.33 of a $5 cap |
| Training and evaluation | Free Colab GPU |
| Next phase, items 1–2 | Engineering time, no API spend |
| Next phase, item 3 | Sending infrastructure we already pay for |

---

*Every figure here traces to a file in the repository via evidence_graph.json. Caveats are in LIMITATIONS_AND_CORRECTIONS.md.*
