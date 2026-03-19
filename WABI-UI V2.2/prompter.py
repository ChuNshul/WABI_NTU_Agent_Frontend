"""
prompter.py — Token-optimised prompt builder for Wabi UI planner.

Changes vs original
───────────────────
- Removed _compact_prop() / _format_catalog_compact() regex machinery.
  The component catalog is now authored directly in components.py as
  structured NamedTuple data; to_prompt_catalog() is plain Python — no regex.

- build_prompt() no longer accepts a `components` argument.  The catalog
  is imported at module level from components.py (zero I/O).

- KEY_ALIASES stays here as the single source of truth.
  plan.py and checker.py both import it from here.

- _serialize_agent_response() and _get() helpers are unchanged — planner.py
  imports them directly.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from .components import to_prompt_catalog


# ---------------------------------------------------------------------------
# Prop-alias table  (short LLM output key → full builder key)
# Imported by plan.py, checker.py — do NOT move this dict.
# ---------------------------------------------------------------------------

KEY_ALIASES: Dict[str, str] = {
    # Section-level
    "ttl":  "title",
    "c":    "content",
    "var":  "variant",
    "tn":   "tone",
    "i":    "items",
    "u":    "unit",
    "sc":   "score",
    "cols": "columns",
    "clr":  "colors",
    "gs":   "gauges",
    "dims": "dimensions",
    "bkd":  "breakdown",
    "secs": "sections",
    # Inside items[] / gauges[]
    "lbl":  "label",
    "val":  "value",
    "hl":   "highlight",
    "lim":  "limit",
    "mx":   "max",
    # Macro / nutrition
    "prot": "protein_g",
    "carb": "carb_g",
    "fat":  "fat_g",
    "kcal": "total_kcal",
    # calorie_ring
    "tgt":  "target",
    "con":  "consumed",
    # nutrition_label shortcuts
    "cal":  "calories",
    "sat":  "sat_fat_g",
    "sod":  "sodium_mg",
    "sug":  "sugar_g",
    "fib":  "fiber_g",
    "srv":  "serving_size",
}


# ---------------------------------------------------------------------------
# Helpers (imported by planner.py)
# ---------------------------------------------------------------------------

def _get(state: Any, key: str, default=None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _serialize_agent_response(raw: Any) -> str:
    """Serialise upstream response; minify if it is JSON."""
    if raw is None:
        return "null"
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return "null"
        try:
            return json.dumps(json.loads(stripped), ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return stripped
    try:
        return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(raw)


def _alias_legend() -> str:
    """Compact alias reference injected once into the prompt."""
    return ", ".join(f"{v}→{k}" for k, v in KEY_ALIASES.items())


def _user_text(state: Any) -> str:
    raw = _get(state, "user_input")
    if isinstance(raw, list):
        return (raw or [{}])[0].get("text") or "null"
    return str(raw or "null")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_prompt(state: Any) -> str:
    """
    Build the LLM prompt for planner mode.
    No `components` argument needed — catalog is imported from components.py.
    """
    intent = (
        "guardrail"
        if _get(state, "safety_passed") is False
        else (_get(state, "intent") or "fallback")
    )
    upstream   = _serialize_agent_response(_get(state, "agent_response"))
    user_input = _user_text(state)
    catalog    = to_prompt_catalog()
    aliases    = _alias_legend()

    return (
        f"Wabi UI planner. Given agent state, output a JSON UI plan.\n\n"
        f"STATE: mode:{intent} | input:{user_input}\n"
        f"upstream:{upstream}\n\n"
        f"RULES:\n"
        f"1. Extract only facts present in upstream. Never fabricate data.\n"
        f"2. Decide UI language from input. Keep ALL UI labels/titles in that language; "
        f"avoid Chinese-English mixing (proper nouns may stay as-is).\n"
        f"3. summary must be concise (<=120 chars). Do NOT repeat summary verbatim in sections.\n"
        f"4. Use visual components only when their required data exists in upstream.\n"
        f"5. <=7 sections, most visual first. Omit null/empty fields.\n"
        f"6. All numbers must be JSON numbers.\n"
        f"7. Output MINIFIED JSON (no spaces/newlines outside strings).\n\n"
        f"COMPONENTS (name(props)  # when-to-use):\n"
        f"{catalog}\n\n"
        f"KEY ALIASES — use short keys in output:\n"
        f"{aliases}\n\n"
        f"OUTPUT (minified JSON, no markdown fences):\n"
        f'{{"mode":"{intent}","summary":"...","sections":[{{"type":"...",...}},...]}}'
    )


def build_prompt_direct_html(state: Any) -> str:
    intent     = (
        "guardrail"
        if _get(state, "safety_passed") is False
        else (_get(state, "intent") or "fallback")
    )
    upstream   = _serialize_agent_response(_get(state, "agent_response"))
    user_input = _user_text(state)
    return (
        "You are an expert frontend designer. Generate a COMPLETE, SELF-CONTAINED HTML document.\n"
        "Requirements:\n"
        "1) Strictly use ONLY the facts present in the upstream JSON/text below. Do not fabricate.\n"
        "2) Decide UI language from input. Keep ALL UI labels/titles in that language; "
        "avoid Chinese-English mixing (proper nouns may stay as-is).\n"
        "3) Avoid redundancy: do not repeat the same paragraph in both header and body.\n"
        "4) Dark theme (#0d1117 bg, #161b22 cards), readable typography; inline CSS in <style>.\n"
        "5) No external scripts/styles; no CDN. Minimal inline JS only if needed.\n"
        "6) Concise header (<=2 lines) with intent and summary; then sections.\n"
        "7) Keep components minimal for short answers (1-2 cards max).\n"
        "8) Width 460px container; system fonts with Noto Sans SC for CJK.\n"
        "9) Output raw HTML only. Do NOT wrap with markdown fences.\n\n"
        f"STATE: intent:{intent} | input:{user_input}\n"
        f"UPSTREAM:\n{upstream}\n\n"
        "OUTPUT: A full <!DOCTYPE html><html>... document."
    )