"""
Statistics shared by the ablation scorer, the gate evaluation and the dashboard's A/B tab.

paired()          same units scored under two variants (offline eval: same tasks, two systems)
two_proportion()  independent traffic split (online A/B: clicks / impressions per variant)
"""
import math

import numpy as np
from scipy.stats import binomtest, norm

N_BOOT = 10_000


def paired(a: dict, b: dict, ids: list, rng: np.random.Generator, n_boot: int = N_BOOT) -> dict:
    """a, b: unit_id -> 0/1 outcome. Paired-bootstrap CI of the mean difference, one-sided
    bootstrap p (share of resampled deltas <= 0) and an exact one-sided McNemar test."""
    x = np.array([a[i] for i in ids], float)
    y = np.array([b[i] for i in ids], float)
    d = x - y
    idx = rng.integers(0, len(ids), size=(n_boot, len(ids)))
    boots = d[idx].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    wins, losses = int(((x == 1) & (y == 0)).sum()), int(((x == 0) & (y == 1)).sum())
    mcnemar = binomtest(wins, wins + losses, 0.5, alternative="greater").pvalue if wins + losses else 1.0
    return {"n": len(ids), "a_pass_at_1": round(x.mean(), 4), "b_pass_at_1": round(y.mean(), 4),
            "delta": round(d.mean(), 4), "ci95": [round(lo, 4), round(hi, 4)],
            "p_bootstrap_one_sided": round(float((boots <= 0).mean()), 5),
            "mcnemar_exact_one_sided": round(float(mcnemar), 6),
            "discordant": {"a_only_pass": wins, "b_only_pass": losses},
            "significant_at_0.05": bool(lo > 0 and (boots <= 0).mean() < 0.05)}


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, c - h), 6), round(min(1.0, c + h), 6)]


def two_proportion(k_a: int, n_a: int, k_b: int, n_b: int) -> dict:
    """Unpaired A/B (e.g. CTR = clicks / impressions). Two-sided pooled z-test,
    Wilson CI per arm, Wald CI for the difference, relative lift."""
    if min(n_a, n_b) <= 0 or not (0 <= k_a <= n_a and 0 <= k_b <= n_b):
        raise ValueError("need 0 <= successes <= trials and trials > 0 for both arms")
    pa, pb = k_a / n_a, k_b / n_b
    pool = (k_a + k_b) / (n_a + n_b)
    se0 = math.sqrt(pool * (1 - pool) * (1 / n_a + 1 / n_b))
    z = (pb - pa) / se0 if se0 > 0 else 0.0
    p = 2 * (1 - norm.cdf(abs(z)))
    se = math.sqrt(pa * (1 - pa) / n_a + pb * (1 - pb) / n_b)
    diff = pb - pa
    return {"rate_a": round(pa, 6), "rate_b": round(pb, 6), "ci95_a": wilson(k_a, n_a), "ci95_b": wilson(k_b, n_b),
            "diff_b_minus_a": round(diff, 6), "diff_ci95": [round(diff - 1.96 * se, 6), round(diff + 1.96 * se, 6)],
            "relative_lift": round(diff / pa, 4) if pa > 0 else None,
            "z": round(z, 3), "p_two_sided": round(float(p), 6), "significant_at_0.05": bool(p < 0.05)}


def min_detectable_effect(n_per_arm: int, base_rate: float, alpha: float = 0.05, power: float = 0.8) -> float:
    """Approximate absolute MDE for a two-arm test with equal traffic (normal approximation)."""
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
    return round((za + zb) * math.sqrt(2 * base_rate * (1 - base_rate) / n_per_arm), 6)


def cohen_kappa(a: list, b: list):
    """Cohen's kappa for two label sequences (same as tools/labeling.py)."""
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 3)
