"""
Mock adapters for the ports in revenue/ports.py. They persist to the same SQLite file as the store,
so the demo state survives restarts and the console can read it. Swap any of them for a real
client (HubSpot, SendGrid/Gmail, DocuSign, Fireflies) without touching agents or the orchestrator.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from revenue.domain import utcnow

DATA = Path(__file__).resolve().parents[1] / "data"

CRM_SCHEMA = """
CREATE TABLE IF NOT EXISTS crm_companies (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS crm_contacts (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS crm_deals (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS crm_activities (seq INTEGER PRIMARY KEY AUTOINCREMENT, deal_id TEXT, kind TEXT, body TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS crm_tasks (seq INTEGER PRIMARY KEY AUTOINCREMENT, deal_id TEXT, title TEXT, due TEXT, owner TEXT, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, deal_id TEXT, recipient TEXT, subject TEXT, body TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS envelopes (id TEXT PRIMARY KEY, deal_id TEXT, signer TEXT, document TEXT, status TEXT, ts TEXT);
"""


def _j(x) -> str:
    return json.dumps(x, sort_keys=True, default=str)


class MockHubSpot:
    """CRM port. Objects are stored as JSON so new properties need no migration."""

    def __init__(self, store):
        self.db = store.db
        self.db.executescript(CRM_SCHEMA)

    def _put(self, table: str, oid: str, obj: dict) -> None:
        self.db.execute(f"INSERT INTO {table} (id, data) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (oid, _j(obj)))

    def _get(self, table: str, oid: str) -> dict | None:
        r = self.db.execute(f"SELECT data FROM {table} WHERE id=?", (oid,)).fetchone()
        return json.loads(r[0]) if r else None

    def upsert_company(self, company: dict) -> None:
        self._put("crm_companies", company["company_id"], company)

    def upsert_contact(self, contact: dict) -> None:
        self._put("crm_contacts", contact["contact_id"], contact)

    def upsert_deal(self, deal: dict) -> None:
        self._put("crm_deals", deal["deal_id"], deal)

    def get_deal(self, deal_id: str) -> dict | None:
        return self._get("crm_deals", deal_id)

    def get_company(self, company_id: str) -> dict | None:
        return self._get("crm_companies", company_id)

    def get_contact(self, contact_id: str) -> dict | None:
        return self._get("crm_contacts", contact_id)

    def list_deals(self) -> list[dict]:
        return [json.loads(r[0]) for r in self.db.execute("SELECT data FROM crm_deals ORDER BY id")]

    def log_activity(self, deal_id: str, kind: str, body: dict) -> None:
        self.db.execute("INSERT INTO crm_activities (deal_id, kind, body, ts) VALUES (?,?,?,?)",
                        (deal_id, kind, _j(body), utcnow().isoformat()))

    def activities(self, deal_id: str) -> list[dict]:
        return [{"kind": r[0], "body": json.loads(r[1]), "ts": r[2]} for r in
                self.db.execute("SELECT kind, body, ts FROM crm_activities WHERE deal_id=? ORDER BY seq", (deal_id,))]

    def create_task(self, deal_id: str, title: str, due: str, owner: str = "ae") -> None:
        self.db.execute("INSERT INTO crm_tasks (deal_id, title, due, owner) VALUES (?,?,?,?)", (deal_id, title, due, owner))

    def tasks(self) -> list[dict]:
        return [dict(zip(("deal_id", "title", "due", "owner", "done"), r)) for r in
                self.db.execute("SELECT deal_id, title, due, owner, done FROM crm_tasks ORDER BY seq")]


class MockEnricher:
    """Enrichment port: firmographics and dated buying signals from a fixture file
    (stands in for Clearbit/Apollo + news/intent providers)."""

    def __init__(self, path: Path = DATA / "enrichment.json"):
        self.db = json.loads(path.read_text(encoding="utf-8"))

    def enrich(self, company: dict) -> dict:
        rec = self.db.get(company["domain"], {})
        return {"attributes": rec.get("attributes", {}), "signals": rec.get("signals", [])}


class MockEmail:
    def __init__(self, store):
        self.db = store.db
        self.db.executescript(CRM_SCHEMA)

    def send(self, to: str, subject: str, body: str, deal_id: str) -> str:
        mid = "MSG-" + uuid.uuid4().hex[:8]
        self.db.execute("INSERT INTO outbox VALUES (?,?,?,?,?,?)", (mid, deal_id, to, subject, body, utcnow().isoformat()))
        return mid

    def outbox(self) -> list[dict]:
        return [dict(zip(("id", "deal_id", "to", "subject", "body", "ts"), r)) for r in self.db.execute("SELECT * FROM outbox ORDER BY ts")]


class MockESign:
    """E-signature port (stands in for DocuSign / Dropbox Sign). Completion arrives as a webhook."""

    def __init__(self, store):
        self.db = store.db
        self.db.executescript(CRM_SCHEMA)

    def send_envelope(self, deal_id: str, document: str, signer_email: str) -> str:
        eid = "ENV-" + uuid.uuid4().hex[:8]
        self.db.execute("INSERT INTO envelopes VALUES (?,?,?,?,?,?)", (eid, deal_id, signer_email, document, "sent", utcnow().isoformat()))
        return eid

    def complete(self, envelope_id: str) -> None:
        self.db.execute("UPDATE envelopes SET status='completed' WHERE id=?", (envelope_id,))

    def envelopes(self) -> list[dict]:
        return [dict(zip(("id", "deal_id", "signer", "document", "status", "ts"), r)) for r in
                self.db.execute("SELECT * FROM envelopes ORDER BY ts")]


class MockFireflies:
    """Transcript port: Fireflies-shaped JSON files in revenue/data/transcripts/."""

    def __init__(self, directory: Path = DATA / "transcripts"):
        self.directory = directory

    def fetch(self, transcript_id: str) -> dict:
        p = self.directory / f"{transcript_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"transcript {transcript_id} not found")
        return json.loads(p.read_text(encoding="utf-8"))
