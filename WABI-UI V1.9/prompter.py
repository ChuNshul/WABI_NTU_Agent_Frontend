from typing import Any, Dict, List
import json

def _get(state: Any, key: str, default=None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)

def _serialize_agent_response(raw: Any) -> str:
    if raw is None:
        return "null"
    if isinstance(raw, str):
        return raw.strip() or "null"
    try:
        return json.dumps(raw, ensure_ascii=False)
    except Exception:
        return str(raw)

def _format_catalog(components: Dict[str, Any]) -> str:
    lines: List[str] = []
    for name, spec in components.items():
        props_str = json.dumps(spec.get("props", {}), ensure_ascii=False, separators=(",", ":"))
        when_str  = spec.get("when", "")
        lines.append(f'"{name}": {props_str}')
        if when_str:
            lines.append(f'  → USE WHEN: {when_str}')
    return "\n".join(lines)

def build_prompt(state: Any, components: Dict[str, Any]) -> str:
    mode          = "guardrail" if _get(state, "safety_passed") is False else (_get(state, "intent"))
    upstream      = _serialize_agent_response(_get(state, "agent_response"))
    user_input    = _get(state, "user_input") or "null"
    error         = _get(state, "error") or "null"
    catalog       = _format_catalog(components)

    return f"""You are the UI planner for Wabi, a health & nutrition assistant.
Your job: read the AGENT STATE, extract every piece of meaningful data from it, and
produce a JSON UI plan that visualises that data as richly as possible .
━━━ AGENT STATE ━━━
mode:             {mode}
user_input:       {user_input}
error:            {error}
upstream_response:{upstream}
━━━ INSTRUCTIONS ━━━
1. READ the upstream_response carefully. Extract ONLY facts that are explicitly present.
Never introduce new restaurants, dishes, numbers, scores, or text not found upstream.
2. FAITHFULNESS FIRST. If the upstream_response is plain text or lacks structured fields,
return a minimal plan: 1–2 text/highlight_box sections that echo the upstream text.
Do not output restaurant_list, ranking_list, charts, or gauges unless their data exists.
3. WHEN structured data exists (e.g., restaurants, foods, nutrition dicts), choose components
that best visualise it. Prefer visual components when data supports them.
4. FILL props strictly from upstream data. Do not approximate, infer, or fabricate values.
If required props are missing, skip that component entirely.
5. LIMIT to 7 sections overall. Order from most important/most visual to least.
━━━ PROP NOTES ━━━
- All number values must be JSON numbers (not strings).
- bar_chart colors[] must be the same length as items[].
- nutrient_gauge: use the "gauges" list prop, not single-gauge props.
- macro_chart: protein_g / carb_g / fat_g are grams (not percentages).
- health_score_card score: derive as 0–100 (100 × healthy_count / total_rated, then
deduct up to 25 pts for high sugar/sodium/saturated fat).
- calorie_ring target: use explicit goal if present, otherwise default to 2000.
- tip_card tone: "warning" for serious issues, "caution" for moderate, "positive" for advice.
━━━ COMPONENT CATALOG ━━━
{catalog}
━━━ OUTPUT ━━━
Return ONLY a valid JSON object — no markdown fences, no comments, no trailing commas:
{{
"mode": "{mode}",
"summary": "<Titles that match the UI content>",
"sections": [
    {{"type": "<component_type>", ...props}}
]
}}
"""
