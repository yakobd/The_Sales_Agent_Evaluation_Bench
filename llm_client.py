"""
Single gateway for every paid LLM call in this repo.

- Logs each call to cost_log.jsonl: timestamp, bucket, purpose, model, tokens,
  and the exact cost OpenRouter reports (usage.cost). This file is the cost log.
- Refuses any call once the logged spend reaches TB_BUDGET_USD (default 5.00).
- Caches responses in .llm_cache.jsonl (gitignored) keyed by the full request,
  so re-running a script is free and gives identical outputs.

Buckets follow the challenge's cost envelope:
    dataset_authoring | training | held_out_eval | reserve

Usage:
    from llm_client import chat
    text = chat("deepseek/deepseek-chat", [{"role": "user", "content": "..."}],
                bucket="dataset_authoring", purpose="judge filter TB-H001")
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import config

COST_LOG = config.REPO_ROOT / "cost_log.jsonl"
CACHE = config.REPO_ROOT / ".llm_cache.jsonl"
BUDGET_USD = float(os.getenv("TB_BUDGET_USD", "5.00"))
BUCKETS = {"dataset_authoring", "training", "held_out_eval", "reserve"}
URL = "https://openrouter.ai/api/v1/chat/completions"

import threading

_cache: dict | None = None
_lock = threading.Lock()  # cost log + cache are shared by worker threads


class BudgetExceeded(RuntimeError):
    pass


def spent_usd() -> float:
    if not COST_LOG.exists():
        return 0.0
    return round(sum(json.loads(l).get("cost_usd", 0.0) for l in COST_LOG.read_text(encoding="utf-8").splitlines() if l.strip()), 6)


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE.exists():
            for line in CACHE.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    _cache[rec["key"]] = rec["response"]
    return _cache


def chat(model: str, messages: list[dict], *, bucket: str, purpose: str,
         temperature: float = 0.0, max_tokens: int = 600, seed: int | None = None,
         response_format: dict | None = None, retries: int = 3) -> str:
    """Return the assistant text. Raises BudgetExceeded before spending past the cap."""
    if bucket not in BUCKETS:
        raise ValueError(f"bucket must be one of {sorted(BUCKETS)}")
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if seed is not None:
        body["seed"] = seed
    if response_format:
        body["response_format"] = response_format
    key = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    with _lock:
        cache = _load_cache()
        if key in cache:
            return cache[key]["content"]
        if spent_usd() >= BUDGET_USD:
            raise BudgetExceeded(f"logged spend ${spent_usd():.4f} >= budget ${BUDGET_USD:.2f} (TB_BUDGET_USD)")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set (see .env.example)")

    last_err = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            r = requests.post(URL, headers={"Authorization": f"Bearer {api_key}"}, json=body, timeout=120)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage", {}) or {}
            rec = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "bucket": bucket, "purpose": purpose, "model": model,
                "provider_model": data.get("model"),
                "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                "cost_usd": float(usage.get("cost") or 0.0), "latency_s": round(time.time() - t0, 2),
            }
            with _lock:
                with COST_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
                cache[key] = {"content": content, "usage": usage}
                with CACHE.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"key": key, "response": cache[key]}, ensure_ascii=False) + "\n")
            return content
        except (requests.RequestException, KeyError, ValueError) as e:  # network / malformed reply
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"OpenRouter call failed after {retries} attempts: {last_err}")


def summary() -> dict:
    """Spend per bucket and model, for the cost report."""
    out: dict = {"total_usd": 0.0, "calls": 0, "by_bucket": {}, "by_model": {}}
    if not COST_LOG.exists():
        return out
    for line in COST_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out["calls"] += 1
        out["total_usd"] += r["cost_usd"]
        out["by_bucket"][r["bucket"]] = out["by_bucket"].get(r["bucket"], 0.0) + r["cost_usd"]
        out["by_model"][r["model"]] = out["by_model"].get(r["model"], 0.0) + r["cost_usd"]
    out["total_usd"] = round(out["total_usd"], 6)
    out["budget_usd"] = BUDGET_USD
    return out


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
