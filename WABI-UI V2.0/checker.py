"""
checker.py — Validates, normalises, and alias-expands a UI plan dict before rendering.

Changes vs original:
  - Added _expand_aliases(): recursively replaces short prop keys (output by the LLM)
    with full keys expected by builder.py.  The alias table lives in prompter.py so
    there is a single source of truth.
  - validate_plan() now calls _expand_aliases() first, so builder.py is completely
    unaware of the compact output format.
"""
from __future__ import annotations

from typing import Any, Dict

# Import alias table from prompter (single source of truth)
from .prompter import KEY_ALIASES


# ---------------------------------------------------------------------------
# Alias expansion
# ---------------------------------------------------------------------------

def _expand_aliases(obj: Any) -> Any:
    """
    Recursively walk a plan dict/list and replace any short key aliases with
    their canonical names.  Operates on the entire tree so nested structures
    (items[], gauges[], dimensions[], sections[] inside columns, etc.) are
    all normalised before reaching the builder.
    """
    if isinstance(obj, dict):
        return {KEY_ALIASES.get(k, k): _expand_aliases(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_aliases(x) for x in obj]
    return obj


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_plan(plan: Dict[str, Any], intent_default: str = "fallback") -> Dict[str, Any]:
    """
    1. Expand short key aliases produced by the LLM.
    2. Ensure the plan has all required top-level keys with sensible defaults.
    Mutates and returns the plan.
    """
    if not isinstance(plan, dict):
        plan = {}

    # ── Expand aliases first so all subsequent logic uses canonical keys ──
    plan = _expand_aliases(plan)

    plan.setdefault("mode", intent_default)
    plan.setdefault("summary", "")

    # Guarantee sections is a non-null list of dicts with a type field
    if not isinstance(plan.get("sections"), list):
        plan["sections"] = []
    plan["sections"] = [
        s for s in plan["sections"]
        if isinstance(s, dict) and isinstance(s.get("type"), str) and s["type"].strip()
    ]

    return plan