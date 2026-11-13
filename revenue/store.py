"""
Durable store (SQLite): event log, timers, approval queue, lessons, settings and the audit log.

Durability + idempotency
  - Every trigger (webhook, schedule, internal step) becomes a row in `events` with a UNIQUE
    idempotency key. Re-delivered webhooks hit the constraint and are ignored.
  - Events are processed from the table, marked done only after their actions are applied;
    failures are retried up to MAX_ATTEMPTS, then parked as 'dead' for a human.
  - Timers (SLA checks, follow-ups) are rows with a due time; the scheduler turns due timers into
    events, so a restart loses nothing.

Audit log
  - Append-only and hash-chained: each entry stores sha256(prev_hash + entry). `verify_audit()`
    detects any edited or deleted row.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

from revenue.domain import Event, Lesson, utcnow

MAX_ATTEMPTS = 3
SCHEMA = """
CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL, type TEXT NOT NULL,
  payload TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT, created_at TEXT NOT NULL, processed_at TEXT);
CREATE TABLE IF NOT EXISTS timers (key TEXT PRIMARY KEY, due_at TEXT NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL,
  fired INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, deal_id TEXT NOT NULL, action TEXT NOT NULL, verdict TEXT NOT NULL,
  status TEXT NOT NULL, created_at TEXT NOT NULL, decided_by TEXT, decided_at TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS lessons (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS actions_done (key TEXT PRIMARY KEY, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL, kind TEXT NOT NULL,
  data TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
"""
GENESIS = "0" * 64


def _j(x) -> str:
    return json.dumps(x, sort_keys=True, default=str, ensure_ascii=False)


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL" if self.path != ":memory:" else "PRAGMA journal_mode=MEMORY")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()

    # ── events ──────────────────────────────────────────────────────────────
    def add_event(self, e: Event, now: datetime | None = None) -> bool:
        """Insert unless the idempotency key was already seen. Returns True if new."""
        with self.lock:
            cur = self.db.execute("INSERT OR IGNORE INTO events (key, type, payload, source, created_at) VALUES (?,?,?,?,?)",
                                  (e.key, e.type, _j(e.payload), e.source, (now or utcnow()).isoformat()))
            return cur.rowcount == 1

    def pending_events(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM events WHERE status='pending' ORDER BY seq").fetchall()
        return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]

    def mark_event(self, seq: int, ok: bool, error: str | None = None) -> str:
        with self.lock:
            if ok:
                self.db.execute("UPDATE events SET status='done', processed_at=? WHERE seq=?", (utcnow().isoformat(), seq))
                return "done"
            attempts = self.db.execute("SELECT attempts FROM events WHERE seq=?", (seq,)).fetchone()[0] + 1
            status = "dead" if attempts >= MAX_ATTEMPTS else "pending"
            self.db.execute("UPDATE events SET attempts=?, status=?, error=? WHERE seq=?", (attempts, status, error, seq))
            return status

    def events(self) -> list[dict]:
        return [dict(r) | {"payload": json.loads(r["payload"])} for r in self.db.execute("SELECT * FROM events ORDER BY seq")]

    # ── timers ──────────────────────────────────────────────────────────────
    def add_timer(self, key: str, due_at: datetime, event_type: str, payload: dict) -> bool:
        with self.lock:
            cur = self.db.execute("INSERT OR IGNORE INTO timers (key, due_at, event_type, payload) VALUES (?,?,?,?)",
                                  (key, due_at.isoformat(), event_type, _j(payload)))
            return cur.rowcount == 1

    def due_timers(self, now: datetime) -> list[dict]:
        rows = self.db.execute("SELECT * FROM timers WHERE fired=0 AND due_at<=? ORDER BY due_at", (now.isoformat(),)).fetchall()
        return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]

    def fire_timer(self, key: str) -> None:
        self.db.execute("UPDATE timers SET fired=1 WHERE key=?", (key,))

    def timers(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM timers ORDER BY due_at")]

    # ── approvals ───────────────────────────────────────────────────────────
    def add_approval(self, deal_id: str, action: dict, verdict: dict, key: str | None = None) -> str:
        """Approval ids derive from the action key, so a retried event never queues the same action twice."""
        aid = "AP-" + (hashlib.sha256(key.encode()).hexdigest()[:8] if key else uuid.uuid4().hex[:8])
        self.db.execute("INSERT OR IGNORE INTO approvals (id, deal_id, action, verdict, status, created_at) VALUES (?,?,?,?,?,?)",
                        (aid, deal_id, _j(action), _j(verdict), "pending", utcnow().isoformat()))
        return aid

    # ── per-action idempotency (at-least-once events, at-most-once effects) ──
    def action_done(self, key: str) -> bool:
        return self.db.execute("SELECT 1 FROM actions_done WHERE key=?", (key,)).fetchone() is not None

    def mark_action(self, key: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO actions_done (key, ts) VALUES (?,?)", (key, utcnow().isoformat()))

    def approval(self, aid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM approvals WHERE id=?", (aid,)).fetchone()
        return self._approval(r) if r else None

    def approvals(self, status: str | None = None) -> list[dict]:
        q = "SELECT * FROM approvals" + (" WHERE status=?" if status else "") + " ORDER BY created_at"
        return [self._approval(r) for r in self.db.execute(q, (status,) if status else ())]

    def decide_approval(self, aid: str, status: str, by: str, note: str = "") -> bool:
        """Atomic compare-and-set so an approval can't be executed twice."""
        with self.lock:
            cur = self.db.execute("UPDATE approvals SET status=?, decided_by=?, decided_at=?, note=? WHERE id=? AND status='pending'",
                                  (status, by, utcnow().isoformat(), note, aid))
            return cur.rowcount == 1

    @staticmethod
    def _approval(r) -> dict:
        return dict(r) | {"action": json.loads(r["action"]), "verdict": json.loads(r["verdict"])}

    # ── lessons ─────────────────────────────────────────────────────────────
    def add(self, lesson: Lesson) -> bool:
        cur = self.db.execute("INSERT OR IGNORE INTO lessons (id, data) VALUES (?,?)", (lesson.lesson_id, _j(lesson.__dict__)))
        return cur.rowcount == 1

    def all(self) -> list[Lesson]:
        return [Lesson(**json.loads(r["data"])) for r in self.db.execute("SELECT data FROM lessons ORDER BY id")]

    def mark_used(self, lesson_ids: list[str]) -> None:
        with self.lock:
            for lid in lesson_ids:
                r = self.db.execute("SELECT data FROM lessons WHERE id=?", (lid,)).fetchone()
                if r:
                    d = json.loads(r["data"])
                    d["uses"] = d.get("uses", 0) + 1
                    self.db.execute("UPDATE lessons SET data=? WHERE id=?", (_j(d), lid))

    # ── settings ────────────────────────────────────────────────────────────
    def get_setting(self, k: str, default: str | None = None) -> str | None:
        r = self.db.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
        return r[0] if r else default

    def set_setting(self, k: str, v: str) -> None:
        self.db.execute("INSERT INTO settings (k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ── audit ───────────────────────────────────────────────────────────────
    def audit(self, actor: str, kind: str, data: dict) -> None:
        with self.lock:
            last = self.db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            prev = last[0] if last else GENESIS
            ts = utcnow().isoformat()
            h = hashlib.sha256((prev + _j({"ts": ts, "actor": actor, "kind": kind, "data": data})).encode()).hexdigest()
            self.db.execute("INSERT INTO audit (ts, actor, kind, data, prev_hash, hash) VALUES (?,?,?,?,?,?)",
                            (ts, actor, kind, _j(data), prev, h))

    def audit_log(self, limit: int | None = None) -> list[dict]:
        q = "SELECT * FROM audit ORDER BY seq DESC" + (f" LIMIT {int(limit)}" if limit else "")
        return [dict(r) | {"data": json.loads(r["data"])} for r in self.db.execute(q)]

    def verify_audit(self) -> dict:
        prev = GENESIS
        n = 0
        for r in self.db.execute("SELECT * FROM audit ORDER BY seq"):
            expect = hashlib.sha256((prev + _j({"ts": r["ts"], "actor": r["actor"], "kind": r["kind"],
                                                "data": json.loads(r["data"])})).encode()).hexdigest()
            if r["prev_hash"] != prev or r["hash"] != expect:
                return {"ok": False, "broken_at": r["seq"], "entries": n}
            prev, n = r["hash"], n + 1
        return {"ok": True, "entries": n}
