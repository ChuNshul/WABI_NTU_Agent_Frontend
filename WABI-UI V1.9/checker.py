"""
checker.py — Validates and normalises a UI plan dict before rendering.
"""
from __future__ import annotations

from typing import Any, Dict


def validate_plan(plan: Dict[str, Any], intent_default: str = "fallback") -> Dict[str, Any]:
    """
    Ensure the plan has all required top-level keys with sensible defaults.
    Mutates and returns the plan.
    """
    if not isinstance(plan, dict):
        plan = {}

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