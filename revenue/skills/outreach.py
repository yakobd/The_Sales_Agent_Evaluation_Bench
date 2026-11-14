"""
Outreach drafting skill: pack template + freshest in-window signal + retrieved lessons -> email.

Honesty rule (from the Tenacious-Bench work): the hook may only cite an in-window signal. With no
fresh signal the pack's neutral hook is used: it asks instead of asserting.

The draft lists the lesson ids it used, so the knowledge loop is visible in every email.
Rendering fails loudly on a missing placeholder instead of sending "{first_name}".
"""
from __future__ import annotations

import re
import string

from revenue.domain import Lesson


class TemplateError(ValueError):
    pass


class _Strict(dict):
    def __missing__(self, key):
        raise TemplateError(f"template placeholder {{{key}}} has no value")


def render(template: str, ctx: dict) -> str:
    try:
        out = string.Formatter().vformat(template, (), _Strict(ctx))
    except (IndexError, ValueError) as e:
        raise TemplateError(str(e))
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", out)).strip() + "\n"


def choose_hook(pack, signals_fresh: list[dict], company: dict) -> tuple[str, str]:
    hooks = pack["messaging"].get("hooks", {})
    for s in signals_fresh:
        if s["type"] in hooks:
            return hooks[s["type"]].format(detail=s.get("detail", ""), company=company["name"]), f"signal:{s['type']}:{s['date']}"
    return pack["messaging"]["default_hook"].format(company=company["name"]), "no in-window signal (neutral hook)"


def draft(pack, kind: str, company: dict, contact: dict, signals_fresh: list[dict], lessons: list[Lesson],
          extra: dict | None = None) -> dict:
    msg = pack["messaging"]
    vps = msg["value_props"]
    keys = list(vps)
    lead = next((l for l in lessons if l.value_prop in vps), None)
    primary = lead.value_prop if lead else keys[0]
    secondary = next(k for k in keys if k != primary) if len(keys) > 1 else primary
    # one coherent lesson drives both the value prop and the supporting line when it can
    line_lesson = lead if (lead and lead.outreach_line) else next((l for l in lessons if l.outreach_line), None)
    hook, hook_basis = choose_hook(pack, signals_fresh, company)
    ctx = {**company.get("attributes", {}), **(extra or {}),
           "company": company["name"], "first_name": contact["name"].split()[0], "hook": hook,
           "lesson_line": line_lesson.outreach_line if line_lesson else "",
           "cta": msg["cta"], "sender_name": msg["sender_name"]}
    ctx["value_prop"] = render(vps[primary], ctx).strip()            # value props may use placeholders too
    ctx["value_prop_secondary"] = render(vps[secondary], ctx).strip()
    tpl = pack.template(kind)
    used = sorted({l.lesson_id for l in (lead, line_lesson) if l})
    return {"subject": render(tpl["subject"], ctx).strip(), "body": render(tpl["body"], ctx),
            "lessons_used": used, "hook_basis": hook_basis, "value_prop": primary, "kind": kind}
