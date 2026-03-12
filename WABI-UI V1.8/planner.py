"""
planner.py — UI plan generator for Wabi assistant.

Responsibilities:
  1. Serialize raw agent state into a prompt context.
  2. Call the LLM (via tools.llm_factory) to produce a structured UI plan.
  3. Provide a deterministic fallback plan when the LLM fails.

Design philosophy:
  - The LLM is responsible for reading upstream_response, understanding its
    structure, extracting relevant data, and choosing how to visualise it.
  - This file does NOT pre-parse, pre-compute, or impose layout rules.
  - The prompt gives the LLM full visibility of the raw state and the component
    catalog, then lets it decide what to render and how.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COMPONENTS_PATH = os.path.join(os.path.dirname(__file__), "ui_components.json")

# ---------------------------------------------------------------------------
# Component schema loader
# ---------------------------------------------------------------------------

def _load_components() -> Dict[str, Any]:
    try:
        with open(_COMPONENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("[planner] Failed to load ui_components.json: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# State accessor
# ---------------------------------------------------------------------------

def _get(state: Any, key: str, default=None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _serialize_agent_response(raw: Any) -> str:
    """Best-effort stringify of upstream_response for the prompt."""
    if raw is None:
        return "null"
    if isinstance(raw, str):
        return raw.strip() or "null"
    try:
        return json.dumps(raw, ensure_ascii=False)
    except Exception:
        return str(raw)


# ---------------------------------------------------------------------------
# Component catalog formatter
# ---------------------------------------------------------------------------

def _format_catalog(components: Dict[str, Any]) -> str:
    """
    Render the component catalog as a compact reference block.
    Each entry shows the component name, its props schema, and the USE WHEN hint.
    """
    lines: List[str] = []
    for name, spec in components.items():
        props_str = json.dumps(spec.get("props", {}), ensure_ascii=False, separators=(",", ":"))
        when_str  = spec.get("when", "")
        lines.append(f'"{name}": {props_str}')
        if when_str:
            lines.append(f'  → USE WHEN: {when_str}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(state: Any, components: Dict[str, Any]) -> str:
    mode          = "guardrail" if _get(state, "safety_passed") is False else (_get(state, "intent"))
    upstream      = _serialize_agent_response(_get(state, "upstream_response") or _get(state, "agent_response"))
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


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm_for_plan(prompt: str, provider: str = "bedrock_claude") -> Optional[Dict[str, Any]]:
    try:
        from tools.llm_factory import get_llm_client
    except ImportError:
        logger.error("[planner] Cannot import get_llm_client from tools.llm_factory")
        return None

    try:
        from langchain_core.messages import HumanMessage
    except ImportError:
        logger.error("[planner] langchain_core not available")
        return None

    try:
        client = get_llm_client(provider=provider)
    except Exception as exc:
        logger.error("[planner] get_llm_client failed: %s", exc)
        return None

    try:
        raw_text: str = client.generate(
            messages=[HumanMessage(content=prompt)],
        )
    except Exception as exc:
        logger.error("[planner] LLM generate() failed: %s", exc)
        return None

    if not raw_text:
        logger.error("[planner] LLM returned empty response")
        return None

    logger.debug("[planner] LLM raw response (%.200s…)", raw_text)
    return _parse_json(raw_text)


def _parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        logger.error("[planner] No JSON object in LLM output")
        return None
    json_str = match.group(0)
    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError:
        try:
            plan = json.loads(json_str, strict=False)
        except Exception as exc:
            logger.error("[planner] JSON parse failed: %s | raw: %.300s", exc, json_str)
            return None
    return plan if isinstance(plan, dict) else None


# ---------------------------------------------------------------------------
# Fallback plan
# ---------------------------------------------------------------------------

def fallback_plan(state: Any) -> Dict[str, Any]:
    raw   = _get(state, "upstream_response") or _get(state, "agent_response")
    text  = raw if isinstance(raw, str) else _serialize_agent_response(raw)
    error = _get(state, "error")

    sections: List[Dict] = []
    if text and text != "null":
        sections.append({"type": "text", "content": text, "tone": "neutral"})
    if error:
        sections.append({"type": "highlight_box", "content": f"Error: {error}", "variant": "error"})
    if not sections:
        sections.append({"type": "text", "content": "Wabi Assistant is ready.", "tone": "neutral"})

    return {
        "mode":     "fallback",
        "summary":  (text[:100] if text and text != "null" else "Wabi Assistant"),
        "sections": sections,
    }
