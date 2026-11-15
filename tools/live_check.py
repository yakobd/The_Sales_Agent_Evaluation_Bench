"""Live HTTP check against a running console: every API endpoint.

    python -m dashboard.server --port 8765 &   then   python tools/live_check.py --port 8765
(tools/check_all.sh --live does both.)
"""
import argparse
import sys
import time

import requests

_ap = argparse.ArgumentParser()
_ap.add_argument("--port", type=int, default=8765)
B = f"http://127.0.0.1:{_ap.parse_args().port}"
rows = []


def check(name, ok, detail=""):
    rows.append(("PASS" if ok else "FAIL", name, detail))


for _ in range(30):
    try:
        requests.get(B + "/api/meta", timeout=2)
        break
    except requests.ConnectionError:
        time.sleep(1)

g = lambda p, **k: requests.get(B + p, timeout=60, **k)  # noqa: E731
p = lambda path, **k: requests.post(B + path, timeout=60, **k)  # noqa: E731

m = g("/api/meta").json()
check("Console: meta / packs", m["counts"]["sales_email"] == 293 and m["counts"]["ad_creative"] == 12, str(m["counts"]))
check("Console: held-out tasks never served", g("/api/tasks/sales_email/TB-H001").status_code == 404)
r = p("/api/score", json={"pack": "sales_email", "task_id": "TB-HA001", "output": {"subject": "Hi", "body": "[First Name], 40 Go engineers ready."}}).json()
check("Live check: sales email scored + gated", not r["all_pass"] and r["gate"]["action"] == "block", ", ".join(v["code"] for v in r["violations"]))
r = p("/api/score", json={"pack": "ad_creative", "task_id": "AD-002", "output": {"headlines": ["Best Rates Anywhere", "Earn 5% APY", "No Fees"], "descriptions": ["Beats Harbor Bank.", "Open an account today."], "final_url": "https://lumensavings.example/x"}}).json()
check("Live check: search ad scored", not r["all_pass"], ", ".join(sorted({v["code"] for v in r["violations"]})))
res = g("/api/results").json()
check("Experiments: results load", res["ablation"]["conditions"]["trained"]["pass_at_1"] == 0.8676 and res["gated"] is not None)
tr = g("/api/traces", params={"condition": "trained", "outcome": "fail"}).json()
check("Traces: held-out outputs (local)", tr["available"] and tr["total"] == 9, f"{tr['total']} failing trained traces")
check("Cost: spend", abs(g("/api/cost").json()["total_usd"] - 0.3302) < 1e-3)
ab = p("/api/abtest/proportions", json={"successes_a": 120, "trials_a": 10000, "successes_b": 150, "trials_b": 10000}).json()
check("A/B: CTR test", ab["relative_lift"] == 0.25 and not ab["significant_at_0.05"], f"p={ab['p_two_sided']}")
pr = p("/api/abtest/paired", json={"condition_a": "trained", "condition_b": "prompt_engineered"}).json()
check("A/B: paired test", pr["delta"] == 0.7647)
ag = g("/api/review/agreement", params={"source": "round2"}).json()
check("Review: round-2 agreement", ag["overall"]["agreement"] == 0.833, f"kappa {ag['overall']['cohen_kappa']}")

for status, name, detail in rows:
    print(f"{status} | {name}" + (f" | {detail}" if detail else ""))
sys.exit(0 if all(r[0] == "PASS" for r in rows) else 1)
