from __future__ import annotations
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COMPONENTS_PATH = os.path.join(os.path.dirname(__file__), "ui_components.json")

def _load_components() -> Dict[str, Any]:
    try:
        with open(_COMPONENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("[ui_node] 无法加载 ui_components.json: %s", exc)
        return {}

def _serialize_nutrition(nutrition: Any) -> str:
    if not isinstance(nutrition, dict):
        return "null"
    out = {}
    for food, info in list(nutrition.items())[:15]:
        if not isinstance(info, dict):
            out[food] = info
            continue
        out[food] = {
            k: v for k, v in info.items()
            if k in (
                "calories", "energy_kcal", "calories_kcal",
                "protein_g", "carbs_g", "fat_g", "sugar_g",
                "sodium_mg", "fiber_g",
                "is_healthy", "unhealthy_reasons",
            )
        }
    return json.dumps(out, ensure_ascii=False)

def _serialize_restaurants(restaurants: Any) -> str:
    if not isinstance(restaurants, list):
        return "null"
    slim = []
    for r in restaurants[:5]:
        if not isinstance(r, dict):
            continue
        name = (
            r.get("restaurant_name")
            or r.get("name")
            or (r.get("restaurant") or {}).get("NAME", "Unknown")
        )
        dish_details = []
        for d in (r.get("matched_dish_details") or [])[:3]:
            if isinstance(d, dict):
                dish_details.append({
                    k: v for k, v in d.items()
                    if k in (
                        "dish_name", "restaurant_name",
                        "energy_kcal", "total_calories", "calories_kcal",
                        "sugar_g", "total_sugar_g",
                        "is_healthy", "unhealthy_reasons",
                    )
                })
        slim.append({
            "restaurant_name": name,
            "rating":    r.get("rating"),
            "price_str": r.get("price_str") or r.get("price"),
            "dist_str":  r.get("dist_str")  or r.get("distance"),
            "is_veg":    r.get("is_veg"),
            "desc":      r.get("desc") or r.get("description") or r.get("cuisine"),
            "meal_plans": (
                r.get("completed_meal_list_grouped")
                or r.get("completed_meal_list")
                or []
            )[:3],
            "dish_nutrition": dish_details,
        })
    return json.dumps(slim, ensure_ascii=False)

def _serialize_agent_response(agent_resp: Any) -> str:
    if agent_resp is None:
        return ""
    if isinstance(agent_resp, str):
        return agent_resp.strip()
    if isinstance(agent_resp, dict):
        for key in ("agent_response", "message", "response", "text"):
            if agent_resp.get(key) and isinstance(agent_resp[key], str):
                return agent_resp[key].strip()
        return json.dumps(agent_resp, ensure_ascii=False)
    return str(agent_resp).strip()

def build_prompt(state: Any, components: Dict[str, Any]) -> str:
    intent        = getattr(state, "intent", None) if not isinstance(state, dict) else state.get("intent") or "clarification"
    safety_passed = getattr(state, "safety_passed", None) if not isinstance(state, dict) else state.get("safety_passed")
    agent_resp    = _serialize_agent_response(state.get("agent_response") if isinstance(state, dict) else getattr(state, "agent_response", None))
    nutrition     = _serialize_nutrition(state.get("nutrition_facts") if isinstance(state, dict) else getattr(state, "nutrition_facts", None))
    restaurants   = _serialize_restaurants(state.get("recommended_restaurants") if isinstance(state, dict) else getattr(state, "recommended_restaurants", None))
    location      = state.get("location") if isinstance(state, dict) else getattr(state, "location", {}) or {}
    food_vis_path = state.get("food_vis_path") if isinstance(state, dict) else getattr(state, "food_vis_path", None)
    food_det      = state.get("food_detection_json") if isinstance(state, dict) else getattr(state, "food_detection_json", None)
    error         = state.get("error") if isinstance(state, dict) else getattr(state, "error", None)
    patient_id    = (state.get("patient_id") if isinstance(state, dict) else getattr(state, "patient_id", None)) or "anonymous"
    has_image     = (state.get("has_image") if isinstance(state, dict) else getattr(state, "has_image", False)) or False

    location_str = (
        (location or {}).get("address")
        or (location or {}).get("formatted_address")
        or (location or {}).get("name")
        or ""
    )

    food_det_str = "null"
    if isinstance(food_det, dict):
        food_det_str = json.dumps({
            "detected_items": food_det.get("detected_items") or [],
        }, ensure_ascii=False)

    comp_schema = json.dumps(
        {k: {"description": v.get("description", ""), "props": v.get("props", {})}
         for k, v in components.items()},
        ensure_ascii=False, indent=2,
    )

    image_note = ""
    if food_vis_path:
        image_note = (
            f"\nA food photo is available at: {food_vis_path}\n"
            "Use an image_display section at the top of sections[] with this path.\n"
        )

    prompt = f"""You are a UI planner for Wabi, a health & nutrition assistant app.
Your job: read the current agent state data and select the most appropriate UI components
to build a clear, informative mobile card interface.

=== AVAILABLE COMPONENTS ===
{comp_schema}

=== CURRENT STATE ===
intent:         {intent}
safety_passed:  {safety_passed}
patient_id:     {patient_id}
has_image:      {has_image}
agent_response: {agent_resp if agent_resp else "null"}
location:       {location_str or "null"}
nutrition_facts:{nutrition}
recommended_restaurants: {restaurants}
food_detection: {food_det_str}
error:          {error or "null"}
{image_note}

=== INSTRUCTIONS ===
1. Analyse the state data above and decide which components best present the information.
2. For intent=recognition: show nutrition data with charts/key-value lists; highlight healthy vs unhealthy foods.
3. For intent=recommendation: show restaurant list (place_table), meal plans (tabs), calorie comparison (bar_chart).
4. For safety_passed=false: show a warning highlight_box only.
5. For intent=exit: show a friendly goodbye card.
6. If data fields are null/empty for a component, skip that component entirely.
7. Do NOT invent data that is not present in the state.
8. Keep the layout mobile-friendly (max 5-7 sections).
9. Use the agent_response as the main summary text if no richer data is available.

Output ONLY a valid JSON object, no markdown fences, no explanation:
{{
  "mode": "<intent string>",
  "summary": "<one-line summary shown in the header>",
  "sections": [
    {{"type": "<component_type>", ...props filled with real state data}}
  ]
}}"""
    return prompt

def _call_llm_for_plan(prompt: str, model_name: str) -> Optional[Dict[str, Any]]:
    try:
        from langgraph_app.agents.ui_render.llm_config import call_llm
    except ImportError:
        try:
            from llm_config import call_llm
        except ImportError:
            logger.error("[ui_node] 无法导入 call_llm，请检查项目路径")
            return None

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    result = call_llm(
        model_name=model_name,
        messages=messages,
        max_tokens=4096,
        temperature=0.4,
        trace={"node": "ui_render"},
    )
    if not result:
        logger.error("[ui_node] call_llm 返回空结果")
        return None

    raw_text: str = result.get("text", "")
    logger.debug(
        "[ui_node] LLM raw (tokens in=%s out=%s): %s…",
        result.get("input_tokens"),
        result.get("output_tokens"),
        raw_text[:200],
    )

    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        logger.error("[ui_node] LLM 输出中未找到 JSON 对象")
        return None

    json_str = match.group(0)
    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError:
        try:
            plan = json.loads(json_str, strict=False)
        except Exception as exc:
            logger.error("[ui_node] JSON 解析失败: %s | raw: %s", exc, json_str[:300])
            return None

    if not isinstance(plan, dict):
        return None
    return plan

def fallback_plan(state: Any) -> Dict[str, Any]:
    agent_resp = _serialize_agent_response(state.get("agent_response") if isinstance(state, dict) else getattr(state, "agent_response", None))
    error      = state.get("error") if isinstance(state, dict) else getattr(state, "error", None)
    sections: List[Dict] = []
    if agent_resp:
        sections.append({"type": "text", "content": agent_resp})
    if error:
        sections.append({
            "type": "highlight_box",
            "content": f"Error: {error}",
            "variant": "error",
        })
    if not sections:
        sections.append({"type": "text", "content": "Wabi Assistant is ready."})
    return {
        "mode":     "fallback",
        "summary":  (agent_resp[:80] if agent_resp else "Wabi Assistant"),
        "sections": sections,
    }
