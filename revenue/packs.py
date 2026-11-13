"""
Segment config packs. A pack is a YAML file in revenue/packs/ holding everything that differs
between customer segments: ICP, scoring rules and weights, messaging, templates, stage SLAs and
exit criteria, transcript lexicon, and IO terms. Agents and skills read packs through this module
only. Adding a segment means adding a YAML file; no agent code changes (tested).

Validation fails loudly at load time, so a malformed pack never reaches a live deal.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PACK_DIR = Path(__file__).resolve().parent / "packs"
FIT_OPS = {"in", "not_in", "gte", "lte", "between", "eq", "exists", "contains_any"}
REQUIRED = {
    "id": str, "label": str, "version": int, "icp": dict, "messaging": dict, "scoring": dict,
    "templates": dict, "stages": dict, "io": dict, "transcripts": dict,
}


class PackError(ValueError):
    pass


@dataclass(frozen=True)
class SegmentPack:
    raw: dict

    def __getitem__(self, k: str) -> Any:
        return self.raw[k]

    @property
    def id(self) -> str:
        return self.raw["id"]

    @property
    def label(self) -> str:
        return self.raw["label"]

    def template(self, name: str) -> dict:
        try:
            return self.raw["templates"][name]
        except KeyError:
            raise PackError(f"pack {self.id!r} has no template {name!r}")

    def sla_days(self, stage: str) -> int | None:
        return (self.raw["stages"].get("sla_days") or {}).get(stage)

    def exit_criteria(self, stage: str) -> list[str]:
        return (self.raw["stages"].get("exit_criteria") or {}).get(stage, [])


def validate(raw: dict, source: str = "<pack>") -> None:
    for k, t in REQUIRED.items():
        if k not in raw:
            raise PackError(f"{source}: missing '{k}'")
        if not isinstance(raw[k], t):
            raise PackError(f"{source}: '{k}' must be {t.__name__}")
    for k in ("sender_name", "value_props", "default_hook", "cta"):
        if k not in raw["messaging"]:
            raise PackError(f"{source}: messaging.{k} is required")
    if not raw["messaging"]["value_props"]:
        raise PackError(f"{source}: messaging.value_props must not be empty")
    sc = raw["scoring"]
    w = sc.get("weights", {})
    if set(w) != {"fit", "intent", "engagement"} or abs(sum(w.values()) - 1.0) > 1e-6:
        raise PackError(f"{source}: scoring.weights must be fit/intent/engagement summing to 1.0")
    tiers = sc.get("tiers", {})
    if not (set(tiers) == {"A", "B", "C"} and tiers["A"] > tiers["B"] > tiers["C"] >= 0):
        raise PackError(f"{source}: scoring.tiers must be A > B > C >= 0")
    for rule in sc.get("fit", []):
        if rule.get("op") not in FIT_OPS:
            raise PackError(f"{source}: unknown fit op {rule.get('op')!r} (known: {sorted(FIT_OPS)})")
        for k in ("field", "points", "reason"):
            if k not in rule:
                raise PackError(f"{source}: fit rule missing '{k}': {rule}")
    for rule in sc.get("intent", []):
        for k in ("signal", "window_days", "points", "reason"):
            if k not in rule:
                raise PackError(f"{source}: intent rule missing '{k}': {rule}")
    for rule in sc.get("engagement", []):
        for k in ("event", "points", "reason"):
            if k not in rule:
                raise PackError(f"{source}: engagement rule missing '{k}': {rule}")
    for name in ("first_touch", "follow_up", "call_brief"):
        if name not in raw["templates"]:
            raise PackError(f"{source}: templates.{name} is required")
    io = raw["io"]
    for k in ("template", "currency", "payment_terms", "min_budget", "rate_card", "max_discount_pct"):
        if k not in io:
            raise PackError(f"{source}: io.{k} is required")
    if not (PACK_DIR / io["template"]).exists():
        raise PackError(f"{source}: io.template {io['template']!r} not found in {PACK_DIR}")


def load_pack(path: Path) -> SegmentPack:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate(raw, path.name)
    if raw["id"] != path.stem:
        raise PackError(f"{path.name}: id {raw['id']!r} must match the file name")
    return SegmentPack(raw)


class PackRegistry:
    """All packs in a directory, loaded and validated once."""

    def __init__(self, directory: Path = PACK_DIR):
        self.directory = directory
        self._packs = {p.stem: load_pack(p) for p in sorted(directory.glob("*.yaml"))}
        if not self._packs:
            raise PackError(f"no packs found in {directory}")

    def get(self, segment: str) -> SegmentPack:
        if segment not in self._packs:
            raise PackError(f"no pack for segment {segment!r}; available: {sorted(self._packs)}")
        return self._packs[segment]

    def ids(self) -> list[str]:
        return sorted(self._packs)

    def all(self) -> list[SegmentPack]:
        return [self._packs[k] for k in self.ids()]
