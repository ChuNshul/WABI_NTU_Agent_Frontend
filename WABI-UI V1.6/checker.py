from __future__ import annotations
from typing import Any, Dict

def validate_plan(plan: Dict[str, Any], intent_default: str = "fallback") -> Dict[str, Any]:
    plan = plan or {}
    if not isinstance(plan, dict):
        plan = {}
    plan.setdefault("mode", intent_default)
    plan.setdefault("summary", "")
    plan.setdefault("sections", [])
    if not isinstance(plan["sections"], list):
        plan["sections"] = []
    return plan
