"""
planner.py — UI plan generator for Wabi assistant.

Responsibilities:
  1. Serialize agent state into a compact prompt context.
  2. Call the LLM to produce a structured UI plan (JSON).
  3. Provide a deterministic fallback plan when LLM fails.
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
# State serializers
# ---------------------------------------------------------------------------

def _get(state: Any, key: str, default=None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _serialize_nutrition(raw: Any) -> Optional[Dict]:
    """Return lean per-food nutrition dict."""
    if not isinstance(raw, dict) or not raw:
        return None
    FIELDS = (
        "calories", "energy_kcal", "calories_kcal",
        "protein_g", "carbs_g", "fat_g", "sugar_g",
        "sodium_mg", "fiber_g", "sat_fat_g",
        "is_healthy", "unhealthy_reasons",
    )
    out: Dict[str, Any] = {}
    for food, info in list(raw.items())[:15]:
        if not isinstance(info, dict):
            out[food] = info
            continue
        slim = {k: v for k, v in info.items() if k in FIELDS}
        # Normalise calorie key to "calories"
        for kcal_key in ("energy_kcal", "calories_kcal"):
            if kcal_key in slim:
                slim.setdefault("calories", slim.pop(kcal_key))
        out[food] = slim
    return out if out else None


def _serialize_restaurants(raw: Any) -> Optional[List]:
    """Return lean restaurant list."""
    if not isinstance(raw, list) or not raw:
        return None
    out: List[Dict] = []
    for r in raw[:6]:
        if not isinstance(r, dict):
            continue
        name = (
            r.get("restaurant_name") or r.get("name")
            or (r.get("restaurant") or {}).get("NAME", "Unknown")
        )
        dishes = []
        for d in (r.get("matched_dish_details") or [])[:4]:
            if isinstance(d, dict):
                dishes.append({
                    "dish_name":         d.get("dish_name"),
                    "calories":          d.get("energy_kcal") or d.get("total_calories") or d.get("calories_kcal"),
                    "sugar_g":           d.get("sugar_g") or d.get("total_sugar_g"),
                    "is_healthy":        d.get("is_healthy"),
                    "unhealthy_reasons": d.get("unhealthy_reasons"),
                })
        out.append({
            "name":       name,
            "rating":     r.get("rating"),
            "price":      r.get("price_str") or r.get("price"),
            "distance":   r.get("dist_str")  or r.get("distance"),
            "is_veg":     r.get("is_veg"),
            "cuisine":    r.get("desc") or r.get("description") or r.get("cuisine"),
            "meal_plans": (r.get("completed_meal_list_grouped") or r.get("completed_meal_list") or [])[:3],
            "dishes":     dishes,
        })
    return out if out else None


def _serialize_agent_response(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        for key in ("agent_response", "message", "response", "text"):
            if isinstance(raw.get(key), str):
                return raw[key].strip()
        return json.dumps(raw, ensure_ascii=False)
    return str(raw).strip()


# ---------------------------------------------------------------------------
# Compact component catalog
# ---------------------------------------------------------------------------

def _compact_catalog(components: Dict[str, Any]) -> str:
    lines: List[str] = []
    for name, spec in components.items():
        props_str = json.dumps(spec.get("props", {}), ensure_ascii=False, separators=(",", ":"))
        when_str  = spec.get("when", "")
        lines.append(f'  "{name}": {props_str}')
        if when_str:
            lines.append(f'    USE WHEN: {when_str}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pre-compute helpers
# ---------------------------------------------------------------------------

def _compute_macro_totals(nutrition: Optional[Dict]) -> Dict[str, float]:
    totals: Dict[str, float] = {"protein_g": 0, "carb_g": 0, "fat_g": 0, "kcal": 0,
                                 "sugar_g": 0, "sodium_mg": 0, "sat_fat_g": 0}
    if not nutrition:
        return totals
    for info in nutrition.values():
        if not isinstance(info, dict):
            continue
        totals["protein_g"] += float(info.get("protein_g") or 0)
        totals["carb_g"]    += float(info.get("carbs_g")   or 0)
        totals["fat_g"]     += float(info.get("fat_g")     or 0)
        totals["kcal"]      += float(info.get("calories")  or 0)
        totals["sugar_g"]   += float(info.get("sugar_g")   or 0)
        totals["sodium_mg"] += float(info.get("sodium_mg") or 0)
        totals["sat_fat_g"] += float(info.get("sat_fat_g") or 0)
    return totals


def _compute_health_score(nutrition: Optional[Dict]) -> Optional[float]:
    """Derive a simple 0-100 health score from the food list."""
    if not nutrition:
        return None
    foods = [v for v in nutrition.values() if isinstance(v, dict)]
    if not foods:
        return None
    healthy = sum(1 for f in foods if f.get("is_healthy") is True)
    unhealthy = sum(1 for f in foods if f.get("is_healthy") is False)
    total_rated = healthy + unhealthy
    if total_rated == 0:
        return None
    base = healthy / total_rated * 100
    # Penalise high sugar/sodium
    macros = _compute_macro_totals(nutrition)
    penalty = 0.0
    if macros["sugar_g"]   > 50:  penalty += 10
    if macros["sodium_mg"] > 1500: penalty += 10
    if macros["fat_g"]     > 40:  penalty += 5
    return max(0.0, min(100.0, base - penalty))


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(state: Any, components: Dict[str, Any]) -> str:
    intent        = _get(state, "intent")
    safety_passed = _get(state, "safety_passed")
    agent_resp    = _serialize_agent_response(_get(state, "agent_response"))
    nutrition     = _serialize_nutrition(_get(state, "nutrition_facts"))
    restaurants   = _serialize_restaurants(_get(state, "recommended_restaurants"))
    location      = _get(state, "location") or {}
    error         = _get(state, "error")

    location_str = (
        location.get("address") or location.get("formatted_address") or location.get("name") or ""
    )

    catalog = _compact_catalog(components)

    nutrition_json  = json.dumps(nutrition,   ensure_ascii=False) if nutrition   else "null"
    restaurant_json = json.dumps(restaurants, ensure_ascii=False) if restaurants else "null"

    macros      = _compute_macro_totals(nutrition)
    macro_str   = json.dumps(macros) if any(v > 0 for v in macros.values()) else "null"
    health_score = _compute_health_score(nutrition)
    score_str   = str(round(health_score, 1)) if health_score is not None else "null"

    # Derive dimension breakdown for health_score_card
    dims: List[Dict] = []
    if nutrition:
        sugar_pct  = min(100, round(macros["sugar_g"]   / 50   * 100)) if macros["sugar_g"]   else 0
        sodium_pct = min(100, round(macros["sodium_mg"] / 2300 * 100)) if macros["sodium_mg"] else 0
        fat_pct    = min(100, round(macros["fat_g"]     / 78   * 100)) if macros["fat_g"]     else 0
        prot_pct   = min(100, round(macros["protein_g"] / 50   * 100)) if macros["protein_g"] else 0
        if sugar_pct:
            dims.append({"label": "Sugar",   "value": sugar_pct,  "max": 100,
                          "variant": "error" if sugar_pct >= 80 else ("warning" if sugar_pct >= 60 else "success")})
        if sodium_pct:
            dims.append({"label": "Sodium",  "value": sodium_pct, "max": 100,
                          "variant": "error" if sodium_pct >= 80 else ("warning" if sodium_pct >= 60 else "success")})
        if fat_pct:
            dims.append({"label": "Fat",     "value": fat_pct,    "max": 100,
                          "variant": "error" if fat_pct >= 80 else ("warning" if fat_pct >= 60 else "success")})
        if prot_pct:
            dims.append({"label": "Protein", "value": prot_pct,   "max": 100, "variant": "success"})
    dims_str = json.dumps(dims) if dims else "null"

    prompt = f"""You are the UI planner for Wabi, a mobile health & nutrition assistant.
Your task: choose and fill UI components to display the agent state as a rich, data-dense mobile card layout.
Maximum 7 sections. Never invent data absent from the state.

━━━ AVAILABLE COMPONENTS ━━━
{catalog}

━━━ AGENT STATE ━━━
intent:          {intent}
safety_passed:   {safety_passed}
agent_response:  {agent_resp or "null"}
location:        {location_str or "null"}
error:           {error or "null"}
nutrition_facts: {nutrition_json}
macro_totals:    {macro_str}
health_score:    {score_str}    (pre-computed 0-100; null if no data)
score_dimensions:{dims_str}     (pre-computed dimension bars for health_score_card)
restaurants:     {restaurant_json}

━━━ LAYOUT RULES BY INTENT ━━━

■ intent = recognition  (nutrition data present)
  REQUIRED sections (skip if data null):
  1. health_score_card  score=health_score, dimensions=score_dimensions
  2. statistic_grid     headline totals from macro_totals (Calories, Protein, Carbs, Fat); 4 cells, columns=2
  3. macro_chart        protein_g/carb_g/fat_g/total_kcal from macro_totals
  4. food_health_list   one item per food: name, calories, is_healthy, reasons, macros
  5. nutrient_gauge     gauges for risky nutrients — include sodium if sodium_mg>0, sugar if sugar_g>0, sat_fat if sat_fat_g>0
                        gauge props: label, value, limit (sodium→2300mg, sugar→50g, sat_fat→20g), unit
  6. bar_chart          calorie comparison per food; color="#10b981" healthy, "#ef4444" unhealthy
  7. tip_card           1 actionable tip based on worst-scoring nutrient (tone=caution or warning)

  OPTIONAL (add if data rich enough):
  - nutrition_label     for the highest-calorie single food
  - comparison_table    if ≥3 foods: Food | Calories | Protein(g) | Fat(g) | Sugar(g)

■ intent = recommendation  (restaurant data present)
  1. text               agent_response summary
  2. statistic_grid     restaurant count, avg rating, location (columns=3)
  3. restaurant_list    fill from restaurants array
  4. ranking_list       rank by rating; items: name=restaurant name, value=rating, unit="★", sub=cuisine
  5. bar_chart          dish calorie comparison — top 6 dishes across all restaurants
  6. tag_list           cuisine types and dietary tags
  7. tip_card           healthy eating tip relevant to the restaurant choices

■ intent = clarification | fallback
  1. text    agent_response

■ intent = exit
  1. highlight_box  variant=success, friendly goodbye

■ safety_passed = false  (overrides intent)
  1. highlight_box  variant=error, content=agent_response

━━━ PROP-FILLING RULES ━━━
- food_health_list items: map each key in nutrition_facts → {{name:<key>, calories:info.calories,
  is_healthy:info.is_healthy, reasons:info.unhealthy_reasons, protein_g:info.protein_g,
  fat_g:info.fat_g, carb_g:info.carbs_g}}
- restaurant_list items: map each restaurant directly; dishes → dishes array
- macro_chart: use macro_totals values (protein_g, carb_g, fat_g, kcal)
- health_score_card: use pre-computed health_score and score_dimensions as-is
- nutrient_gauge: always use "gauges" list prop (not single-gauge mode)
- statistic_grid variant: calories>700 or fat>40 → "warning"; ≤400 → "success"; else "default"
- bar_chart colors: is_healthy=true → "#10b981", is_healthy=false → "#ef4444", unknown → "#3b82f6"
- tip_card tone: warning if score<45, caution if score<70, positive otherwise

━━━ OUTPUT FORMAT ━━━
Return ONLY a valid JSON object (no markdown fences, no comments):
{{
  "mode": "<intent>",
  "summary": "<one concise sentence for header subtitle>",
  "sections": [
    {{"type": "<component_type>", ...props}}
  ]
}}"""
    return prompt


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm_for_plan(prompt: str, model_name: str) -> Optional[Dict[str, Any]]:
    try:
        from langgraph_app.agents.ui_render.llm_config import call_llm
    except ImportError:
        try:
            from llm_config import call_llm
        except ImportError:
            logger.error("[planner] Cannot import call_llm — check project paths")
            return None

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    result = call_llm(
        model_name=model_name,
        messages=messages,
        max_tokens=4096,
        temperature=0.15,    # Low temp → deterministic JSON output
        trace={"node": "ui_render"},
    )
    if not result:
        logger.error("[planner] call_llm returned empty result")
        return None

    raw_text: str = result.get("text", "")
    logger.debug("[planner] LLM response (in=%s out=%s): %.200s…",
                 result.get("input_tokens"), result.get("output_tokens"), raw_text)

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
    agent_resp = _serialize_agent_response(_get(state, "agent_response"))
    error      = _get(state, "error")
    sections: List[Dict] = []
    if agent_resp:
        sections.append({"type": "text", "content": agent_resp, "tone": "neutral"})
    if error:
        sections.append({"type": "highlight_box", "content": f"Error: {error}", "variant": "error"})
    if not sections:
        sections.append({"type": "text", "content": "Wabi Assistant is ready.", "tone": "neutral"})
    return {
        "mode":     "fallback",
        "summary":  agent_resp[:100] if agent_resp else "Wabi Assistant",
        "sections": sections,
    }