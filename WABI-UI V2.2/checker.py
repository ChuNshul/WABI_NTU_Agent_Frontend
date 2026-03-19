"""
checker.py — Plan validation shim.

What changed
────────────
Original: contained _expand_aliases() + validate_plan() — owned both the
alias expansion logic and the validation contract.

Now: all that logic has moved into Plan.from_dict() in plan.py, making
plan.py the single authoritative schema layer.  checker.py is now a
one-function shim that exists only to preserve the call-site in ui_node.py
without requiring changes there.

If you are reading this and want to add validation rules (e.g. max sections,
required fields per component type), add them to Plan.from_dict() in plan.py.
"""
from __future__ import annotations

from typing import Any, Dict

from .plan import Plan


def validate_plan(raw: Any, intent_default: str = "fallback") -> Plan:
    """
    Validate, alias-expand, and coerce a raw LLM plan dict into a typed Plan.

    Returns a Plan instance.  builder.py and ui_node.py accept Plan directly
    (build_html updated to take Plan; ui_node uses plan.to_dict() if needed).
    """
    if not isinstance(raw, dict):
        raw = {}
    return Plan.from_dict(raw, intent_default=intent_default)