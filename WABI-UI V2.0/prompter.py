"""
prompter.py — Token-optimised prompt builder for Wabi UI planner.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Prop-alias table (short output key → full builder key)
# Kept here as the single source of truth; checker.py imports this.
# ---------------------------------------------------------------------------

KEY_ALIASES: Dict[str, str] = {
    # Common section-level props
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
    "secs": "sections",     # nested sections inside `columns` component
    # Inside items[] / gauges[] dicts
    "lbl":  "label",
    "val":  "value",
    "hl":   "highlight",
    "lim":  "limit",
    "mx":   "max",
    # Macro / nutrition fields
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
# Helpers
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
        # Minify JSON strings to cut input tokens
        try:
            return json.dumps(json.loads(stripped), ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return stripped
    try:
        return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(raw)


# ---------------------------------------------------------------------------
# Compact catalog formatter
# ---------------------------------------------------------------------------

def _compact_prop(pname: str, pdesc: str) -> str:
    """
    Convert a verbose prop description to a compact token-efficient one-liner.
    Applies the alias table so the catalog already shows the short key the LLM
    should output.
    """
    # Look up alias (reverse mapping: full name → short name)
    _reverse = {v: k for k, v in KEY_ALIASES.items()}
    short = _reverse.get(pname, pname)

    optional = "optional" in pdesc or pname.endswith("?")
    suffix   = "?" if optional else ""

    # Array / list type — extract inner field names
    if pdesc.lstrip().startswith("[") or re.match(r"list", pdesc[:10], re.I):
        inner = re.search(r"\{([^}]+)\}", pdesc)
        if inner:
            raw_fields = [f.strip().split()[0].rstrip(",:") for f in inner.group(1).split(",")]
            # Apply reverse alias to inner field names too
            fields = [_reverse.get(f, f) for f in raw_fields[:6]]
            return f"{short}{suffix}:[{{{','.join(fields)}}}]"
        return f"{short}{suffix}:[]"

    # Enum type
    enum_m = re.search(r"([\w]+(?:\s*\|\s*[\w]+){1,})", pdesc)
    if enum_m:
        opts = re.sub(r"\s*\|\s*", "|", enum_m.group(1))
        return f"{short}{suffix}:[{opts}]"

    return f"{short}{suffix}"


def _format_catalog_compact(components: Dict[str, Any]) -> str:
    """Return a compact, one-line-per-component catalog for the prompt (all components)."""
    lines: List[str] = []
    for name, spec in components.items():
        props   = spec.get("props", {})
        when    = spec.get("when", "")

        prop_parts = [_compact_prop(k, str(v)) for k, v in props.items()]
        line = f"{name}({', '.join(prop_parts)})"

        if when:
            brief = when.split(".")[0].split(";")[0].strip()[:80]
            line += f"  # {brief}"
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Alias legend for the prompt (auto-generated from KEY_ALIASES)
# ---------------------------------------------------------------------------

def _alias_legend() -> str:
    """Compact alias reference injected once into the prompt."""
    pairs = [f"{v}→{k}" for k, v in KEY_ALIASES.items()]
    return ", ".join(pairs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_prompt(state: Any, components: Dict[str, Any]) -> str:
    intent     = (
        "guardrail"
        if _get(state, "safety_passed") is False
        else (_get(state, "intent") or "fallback")
    )
    upstream   = _serialize_agent_response(_get(state, "agent_response"))
    user_input = (_get(state, "user_input") or [{}])[0].get("text") if isinstance(_get(state, "user_input"), list) else (_get(state, "user_input") or "null")
    catalog    = _format_catalog_compact(components)
    aliases    = _alias_legend()

    return (
        f"Wabi UI planner. Given agent state, output a JSON UI plan.\n\n"
        f"STATE: mode:{intent} | input:{user_input}\n"
        f"upstream:{upstream}\n\n"
        f"RULES:\n"
        f"1. Extract only facts present in upstream. Never fabricate data.\n"
        f"2. Plain/unstructured upstream → 1-2 text/highlight_box sections only.\n"
        f"3. Use visual components only when their required data exists in upstream.\n"
        f"4. ≤7 sections, most visual first. Omit null/empty fields.\n"
        f"5. All numbers must be JSON numbers. colors[]=same length as items[].\n"
        f"6. nutrient_gauge: use gs[] list. macro_chart: grams not %.\n"
        f"7. health_score_card sc 0-100. calorie_ring tgt default 2000.\n"
        f"8. Output MINIFIED JSON (no spaces/newlines outside strings).\n\n"
        f"COMPONENTS (name(props) # when-to-use):\n"
        f"{catalog}\n\n"
        f"KEY ALIASES — use short keys in output:\n"
        f"{aliases}\n\n"
        f'OUTPUT (minified JSON, no markdown fences):\n'
        f'{{"mode":"{intent}","summary":"...","sections":[{{"type":"...",...}},...]}}'
    )

def build_prompt_direct_html(state: Any) -> str:
    intent     = (
        "guardrail"
        if _get(state, "safety_passed") is False
        else (_get(state, "intent") or "fallback")
    )
    upstream   = _serialize_agent_response(_get(state, "agent_response"))
    user_input = (_get(state, "user_input") or [{}])[0].get("text") if isinstance(_get(state, "user_input"), list) else (_get(state, "user_input") or "null")
    return (
        "You are an expert frontend designer. Generate a COMPLETE, SELF-CONTAINED HTML document.\n"
        "Requirements:\n"
        "1) Strictly use ONLY the facts present in the upstream JSON/text below. Do not fabricate.\n"
        "2) Mobile-first layout, dark theme, readable typography; include minimal inline CSS in <style>.\n"
        "3) No external scripts/styles; no CDN; avoid heavy JS. If interactivity is needed, use small inline JS only.\n"
        "4) Present a concise header with intent and summary; then sections (text, lists, simple tables, small badges/chips).\n"
        "5) Keep width within 420px container; use system fonts.\n"
        "6) Output raw HTML only. Do NOT wrap with markdown fences.\n\n"
        f"STATE: intent:{intent} | input:{user_input}\n"
        f"UPSTREAM:\n{upstream}\n\n"
        "OUTPUT: A full <!DOCTYPE html><html>... document with <head><meta charset=\"utf-8\"> and inline <style>."
    )
