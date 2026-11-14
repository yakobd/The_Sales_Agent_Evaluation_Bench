"""Live HTTP check against a running console: every API endpoint plus the full revenue scenario,
with approvals made the way a human would make them in the Revenue desk.

    python -m dashboard.server --port 8765 &   then   python tools/live_check.py --port 8765
(tools/check_all.sh --live does both.) Resets the revenue desk state.
"""
import argparse
import hashlib
import hmac
import json
import sys
import time

import requests

secret = __import__("os").environ.get("REVENUE_WEBHOOK_SECRET", "dev-secret").encode()

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

# Revenue desk: the full scenario exactly as in the interview (approvals done "by hand")
check("Revenue: reset", p("/api/revenue/scenario/reset").ok)
step = lambda: p("/api/revenue/scenario/next")  # noqa: E731
state = lambda: g("/api/revenue/state").json()  # noqa: E731
pend = lambda kind: [a for a in state()["approvals"] if a["status"] == "pending" and a["action"]["type"] == kind]  # noqa: E731

step()  # 1 brand leads
s = state()
tiers = {d["deal_id"]: d["tier"] for d in s["deals"]}
check("Revenue 1: leads scored and tiered", tiers == {"D-sunnybowl": "A", "D-peakform": "B", "D-crumbandco": "D"}, str(tiers))
a = pend("send_email")
check("Revenue 1: tier-A first touch queued", len(a) == 1 and a[0]["deal_id"] == "D-sunnybowl")
check("Revenue 1: approve email", p(f"/api/revenue/approvals/{a[0]['id']}", json={"decision": "approve"}).ok)
step()  # 2 reply
d = next(x for x in state()["deals"] if x["deal_id"] == "D-sunnybowl")
check("Revenue 2: injection flagged, deal not won", d["stage"] == "engaged" and "injection_attempt" in d["flags"], str(d["flags"]))
step()  # 3 opt-out
check("Revenue 3: opt-out recorded", next(x for x in state()["deals"] if x["deal_id"] == "D-peakform")["opted_out"])
step()  # 4 meeting
step()  # 5 transcript
d = next(x for x in state()["deals"] if x["deal_id"] == "D-sunnybowl")
check("Revenue 5: transcript -> fields, qualified, IO valid", d["fields"].get("budget") == 180000 and d["fields"].get("io_valid") is True, d["stage"])
check("Revenue 5: lessons learned", len(state()["lessons"]) == 3)
early = p("/api/revenue/scenario/next")
check("Revenue 6: e-sign refused before IO approval", early.status_code == 409)
io = pend("send_io_for_signature")
check("Revenue 6: approve IO", len(io) == 1 and p(f"/api/revenue/approvals/{io[0]['id']}", json={"decision": "approve"}).ok)
step()  # 6 e-sign
check("Revenue 6: closed won", next(x for x in state()["deals"] if x["deal_id"] == "D-sunnybowl")["stage"] == "closed_won")
step()  # 7 agencies
nw = [a for a in pend("send_email") if a["deal_id"] == "D-northwind"]
check("Revenue 7: agency pack works, lesson reused", len(nw) == 1 and nw[0]["action"]["payload"]["lessons_used"], str(nw[0]["action"]["payload"]["lessons_used"] if nw else ""))
p("/api/revenue/killswitch", json={"on": True})
blocked = p(f"/api/revenue/approvals/{nw[0]['id']}", json={"decision": "approve"})
check("Revenue: kill switch refuses approved send", blocked.status_code == 409)
p("/api/revenue/killswitch", json={"on": False})
check("Revenue: approve after kill switch off", p(f"/api/revenue/approvals/{nw[0]['id']}", json={"decision": "approve"}).ok)
step()  # 8 time passes
s = state()
check("Revenue 8: stall detected", "stalled" in next(x for x in s["deals"] if x["deal_id"] == "D-northwind")["flags"])
check("Revenue: no dead events, audit chain intact", not s["events"]["dead"] and s["audit"]["verify"]["ok"], f"{s['audit']['verify']['entries']} audit entries")
body = json.dumps({"deal_id": "D-sunnybowl", "booking_id": "bk-live"}).encode()
sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
check("Webhook: bad signature rejected", p("/api/revenue/webhooks/calcom", data=body, headers={"X-Cool-Signature": "nope"}).status_code == 401)
first = p("/api/revenue/webhooks/calcom", data=body, headers={"X-Cool-Signature": sig}).json()
again = p("/api/revenue/webhooks/calcom", data=body, headers={"X-Cool-Signature": sig}).json()
check("Webhook: signed accepted once, duplicate ignored", first["accepted"] and again["duplicate"])

for status, name, detail in rows:
    print(f"{status} | {name}" + (f" | {detail}" if detail else ""))
sys.exit(0 if all(r[0] == "PASS" for r in rows) else 1)
