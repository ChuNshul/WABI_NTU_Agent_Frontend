"""
prompter.py — Token-optimised prompt builder for UI Render planner.
"""
from __future__ import annotations

from typing import Any, Dict

from ..core.components import to_prompt_catalog
from ..core.tools import extract_ui_ctx as _extract_ui_ctx


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


def _alias_legend() -> str:
    """Compact alias reference injected once into the prompt."""
    return ", ".join(f"{v}→{k}" for k, v in KEY_ALIASES.items())


def _prompt_ctx(state: Any) -> tuple[str | None, str, str]:
    intent, _, user_input_str, upstream_str = _extract_ui_ctx(state, user_input_default="null")
    return intent, upstream_str, user_input_str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_prompt(state: Any) -> str:
    """
    Build the LLM prompt for planner mode.
    No `components` argument needed — catalog is imported from components.py.
    """
    intent, upstream, user_input = _prompt_ctx(state)
    catalog    = to_prompt_catalog()
    aliases    = _alias_legend()

    return (
        f"UI Render planner. Given agent state, output a JSON UI plan.\n\n"
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
        f"7. For any icon fields, output ONLY an emoji/symbol (no letters/numbers). "
        f"Examples: water→💧, calories→🔥, protein→�. Never output icon names like 'water'.\n"
        f"8. Output MINIFIED JSON (no spaces/newlines outside strings).\n\n"
        f"COMPONENTS (name(props)  # when-to-use):\n"
        f"{catalog}\n\n"
        f"KEY ALIASES — use short keys in output:\n"
        f"{aliases}\n\n"
        f"OUTPUT (minified JSON, no markdown fences):\n"
        f'{{"mode":"{intent}","summary":"...","sections":[{{"type":"...",...}},...]}}'
    )


def build_prompt_direct_html(state: Any) -> str:
    intent, upstream, user_input = _prompt_ctx(state)
    return (
        "You are an expert frontend designer. Generate a COMPLETE, SELF-CONTAINED HTML document.\n"
        "Requirements:\n"
        "1) Strictly use ONLY the facts present in the upstream JSON/text below. Do not fabricate.\n"
        "2) Decide UI language from input. Keep ALL UI labels/titles in that language; "
        "avoid Chinese-English mixing (proper nouns may stay as-is).\n"
        "3) Avoid redundancy: do not repeat the same paragraph in both header and body.\n"
        "4) Dark theme (#0d1117 bg, #161b22 cards), readable typography; inline CSS in <style>.\n"
        "5) No external scripts/styles/fonts; no CDN. Do not use icon fonts. "
        "If you need an icon, use emoji (e.g., 💧🔥🥗) or inline SVG — never icon names like 'water'.\n"
        "6) Concise header (<=2 lines) with intent and summary; then sections.\n"
        "7) Keep components minimal for short answers (1-2 cards max).\n"
        "8) Width 460px container; system fonts with Noto Sans SC for CJK.\n"
        "9) Output raw HTML only. Do NOT wrap with markdown fences.\n\n"
        f"STATE: intent:{intent} | input:{user_input}\n"
        f"UPSTREAM:\n{upstream}\n\n"
        "OUTPUT: A full <!DOCTYPE html><html>... document."
    )


def build_prompt_direct_image(state: Any) -> str:
    intent, upstream, user_input = _prompt_ctx(state)
    return (
        "You are an expert data visualization designer. Generate ONE portrait infographic image that visualizes the data.\n"
        "Requirements:\n"
        "1) Strictly use ONLY the facts present in the upstream JSON/text below. Do not fabricate.\n"
        "2) Decide UI language from input. Keep ALL UI labels/titles in that language; "
        "avoid Chinese-English mixing (proper nouns may stay as-is).\n"
        "3) Visualize ALL important data. Do not omit items. If the data is long, compress using tables, grids, small multiples, or grouped cards.\n"
        "4) No generic app chrome: do NOT include navigation bars, tab bars, headers with avatars, notification icons, search bars, or settings icons unless they appear in the upstream data.\n"
        "5) Prioritize clarity and density: clear hierarchy, consistent alignment, concise labels, and meaningful visual encodings (tables, progress bars, sparklines, simple charts).\n"
        "6) Dark theme, high contrast, readable typography. No watermarks.\n"
        "7) Portrait layout, width ~460px; keep margins tight but readable; align content in sections.\n"
        "8) Make text crisp and correctly spelled; prefer short labels over long paragraphs.\n\n"
        f"STATE: intent:{intent} | input:{user_input}\n"
        f"UPSTREAM:\n{upstream}\n"
    )
