from __future__ import annotations
import json
import os
import re
import time
from typing import Any, Dict, Optional

from UI.state import GraphState, Intent
from UI.llm_config import call_llm, DEFAULT_MODEL
from UI.nodes.logger import log, log_state, preview_json, preview_text, summarize_state
from UI.templates import clarification, food_recognition_no_image, goal_planning_no_history, error_state, guardrail

UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_COMPONENTS_PATH = os.path.join(UI_DIR, "ui_components.json")
with open(UI_COMPONENTS_PATH, "r", encoding="utf-8") as f:
    UI_COMPONENTS = json.load(f)

SYSTEM_PROMPT = """You are an expert UI planner for Wabi health assistant.
Select appropriate components and produce a JSON UI plan based on intent, user input, and upstream data.

Available Components:
{components}

Rules:
1. Prefer structured components for facts and lists. Use place_table for restaurant lists; include id,name,desc,rating,price_str,dist_str,is_veg.
2. For nutrition facts, use key_value_list and highlight_box for warnings.
3. If needed, use custom_html with valid, safe HTML. Avoid scripts and inline event handlers.
4. Provide 3-5 suggestions that are conversational and answerable by the assistant.
5. Keep layout mobile-friendly and concise.
6. Charts: bar_chart for comparisons, pie_chart for proportions, line_chart for trends.

Output only JSON:
{{
  "mode": "<intent>",
  "summary": "<short summary>",
  "sections": [{{"type":"<component>", ...props}}],
  "suggestions": ["..."]
}}
"""

def _sanitize_sections(sections: list, uploaded_image_url: Optional[str]) -> list:
    s2 = []
    for s in sections or []:
        if isinstance(s, dict) and (s.get("type") or "").strip() == "image_display":
            url = s.get("image_url") or s.get("url") or (s.get("props") or {}).get("image_url") or (s.get("props") or {}).get("url")
            if isinstance(url, str) and url.startswith("/static/"):
                s2.append(s)
            elif uploaded_image_url:
                t = dict(s)
                p = dict(t.get("props") or {})
                p["image_url"] = uploaded_image_url
                t["props"] = p
                t["url"] = uploaded_image_url
                s2.append(t)
        else:
            s2.append(s)
    return s2

def _build_prompt(state: GraphState) -> str:
    language = state.get("language", "Chinese")
    user_input_raw = str(state.get("user_input", "")).strip()
    intent = state.get("intent", "")
    prompt = SYSTEM_PROMPT.format(components=json.dumps(UI_COMPONENTS, indent=2))
    prompt += f"\n\nReply in {language}."
    if user_input_raw:
        prompt += f"\n\n[User]\n{user_input_raw}"
    data_fields = []
    for key in ["nutrition_facts", "recommended_restaurants", "food_detection_json", "user_history"]:
        val = state.get(key)
        if val is not None:
            try:
                data_fields.append(f"{key}={json.dumps(val)[:2000]}")
            except Exception:
                data_fields.append(f"{key}={str(val)[:2000]}")
    if data_fields:
        prompt += "\n\n[Current State Data]\n" + "\n".join(data_fields)
    if intent:
        prompt += f"\n\n[Intent]\n{intent}"
    return prompt

def _call_llm_parse(
    prompt: str, model_name: Optional[str] = None, trace: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    result = call_llm(
        model_name=model_name or DEFAULT_MODEL,
        messages=messages,
        max_tokens=4096,
        temperature=0.5,
        trace=trace,
    )
    if not result:
        return None
    output_text = result["text"]
    m = re.search(r"\{[\s\S]*\}", output_text)
    if not m:
        if trace:
            log(
                "warning",
                "Planner LLM returned no JSON object",
                run_id=trace.get("run_id"),
                node=trace.get("node"),
                event="plan_parse_failed",
                data={"output_preview": preview_text(output_text)},
            )
        return None
    try:
        plan = json.loads(m.group(0))
    except json.JSONDecodeError:
        try:
            plan = json.loads(m.group(0), strict=False)
        except Exception:
            if trace:
                log(
                    "warning",
                    "Planner failed to parse JSON plan",
                    run_id=trace.get("run_id"),
                    node=trace.get("node"),
                    event="plan_parse_failed",
                    data={"json_preview": preview_text(m.group(0))},
                )
            return None
    plan["token_usage"] = {
        "input": result["input_tokens"],
        "output": result["output_tokens"],
        "total": result["total_tokens"],
    }
    return plan

def planner(state: GraphState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    state["current_node"] = "planner"
    intent = state.get("intent", Intent.CLARIFICATION)
    model_name = state.get("llm_model", DEFAULT_MODEL)
    uploaded_image_url = state.get("uploaded_image_url")
    
    log_state(
        state,
        "info",
        "Planner started",
        node="planner",
        event="node_start",
        data=summarize_state(state),
    )
    log_state(
        state,
        "info",
        "Planner checking fixed templates",
        node="planner",
        event="fixed_template_check",
        data={"intent": intent},
    )
    fixed_plan = None
    if intent == Intent.FOOD_RECOGNITION and not state.get("has_image") and not uploaded_image_url:
        fixed_plan = food_recognition_no_image(state, state.get("agent_response"))
    elif intent == Intent.GOAL_PLANNING and ("MOCK_USER_HISTORY" not in str(state.get("user_input", ""))):
        fixed_plan = goal_planning_no_history(state)
    elif intent == Intent.GUARDRAIL:
        fixed_plan = guardrail(state)
    elif intent == Intent.CLARIFICATION:
        fixed_plan = clarification(state)
    if fixed_plan:
        log_state(
            state,
            "info",
            "Planner using fixed template",
            node="planner",
            event="fixed_template_used",
            data={"intent": intent, "plan_preview": preview_json(fixed_plan, limit=1500)},
        )
        plan = fixed_plan
    else:
        log_state(state, "info", "Planner building prompt", node="planner", event="prompt_build_start")
        prompt = _build_prompt(state)
        log_state(
            state,
            "debug",
            "Planner prompt built",
            node="planner",
            event="prompt_built",
            data={"model": model_name, "prompt": preview_text(prompt)},
        )
        trace = {"run_id": state.get("run_id"), "node": "planner"}
        plan = _call_llm_parse(prompt, model_name=model_name, trace=trace)
    if not plan:
        log_state(
            state,
            "error",
            "Planner failed to generate plan; using error fallback",
            node="planner",
            event="plan_fallback",
        )
        agent_response = state.get("agent_response", "")
        plan = error_state(state, agent_response if agent_response else None)
    sections = _sanitize_sections(plan.get("sections", []) or [], uploaded_image_url)
    plan["sections"] = sections
    plan["language"] = state.get("language", "Chinese")
    
    if uploaded_image_url:
        plan["uploaded_image_url"] = uploaded_image_url
        
    token_usage = plan.get("token_usage") if isinstance(plan, dict) else None
    log_state(
        state,
        "info",
        "Planner plan generated",
        node="planner",
        event="plan_ready",
        data={
            "mode": plan.get("mode") if isinstance(plan, dict) else None,
            "sections": len(plan.get("sections", []) or []) if isinstance(plan, dict) else None,
            "token_usage": token_usage,
        },
    )
    log_state(
        state,
        "debug",
        "Planner plan preview",
        node="planner",
        event="plan_preview",
        data={"plan": preview_json(plan, limit=2000)},
    )
    log_state(
        state,
        "info",
        "Planner finished",
        node="planner",
        event="node_end",
        data={"duration_ms": int((time.perf_counter() - t0) * 1000)},
    )
    return {"ui_plan": plan}
