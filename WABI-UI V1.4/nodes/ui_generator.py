# -*- coding: utf-8 -*-
"""根据用户输入和上游节点提供的意图与数据，由 LLM 直接生成 ui_plan，
并统一渲染为图片输出。"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

from UI.state import GraphState, Intent
from UI.ui_components import UI_COMPONENTS, SYSTEM_PROMPT_TEMPLATE
from UI.llm_config import call_llm, get_model_config, DEFAULT_MODEL
from UI.nodes.renderer import render_ui_plan_to_image
from UI.templates import clarification, food_recognition_no_image, goal_planning_no_history, error_state, guardrail

def _sanitize_sections_for_render(sections: list, uploaded_image_url: Optional[str]) -> list:
    sanitized = []
    for s in sections or []:
        if isinstance(s, dict) and (s.get("type") or "").strip() == "image_display":
            url = s.get("image_url") or s.get("url") or (s.get("props") or {}).get("image_url") or (s.get("props") or {}).get("url")
            if isinstance(url, str) and url.startswith("/static/"):
                sanitized.append(s)
            elif uploaded_image_url:
                t = dict(s)
                p = dict(t.get("props") or {})
                p["image_url"] = uploaded_image_url
                t["props"] = p
                t["url"] = uploaded_image_url
                sanitized.append(t)
        else:
            sanitized.append(s)
    return sanitized

def _build_llm_prompt(state: GraphState) -> str:
    intent = state.get("intent", "")
    language = state.get("language", "Chinese")
    user_input_raw = str(state.get("user_input", "")).strip()

    # 基础系统提示
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        components_json=json.dumps(UI_COMPONENTS, indent=2)
    )

    # 语言偏好
    prompt += f"\n\n[Language Instruction] Please reply in {language}."
    
    if user_input_raw:
        prompt += f"\n\n[User Input]\nUSER: {user_input_raw}"

    # 意图特定指令
    
    def get_recommendation_instruction():
        return (
            "\n\n[Recommendation Instruction] Use place_table for the restaurant list. "
            "Ensure all fields (id, name, desc, rating, price, dist, is_veg, price_str, dist_str) "
            "are passed into the items array."
        )
    
    def get_goal_planning_instruction():
        return (
            "\n\n[Goal Planning Instruction] Analyze the provided user_history to set specific, measurable goals "
            "and an executable weekly plan. Prefer statistic_grid, line_chart, bar_chart, "
            "pie_chart, progress_bar, steps_list. All numbers must be computable from historical data."
        )
    
    def get_food_recognition_instruction():
        return (
            "\n\n[Food Recognition Instruction] Display calories for each recognized food. "
            "Use highlight_box to emphasize unhealthy items. Show total calorie summary. "
            "Use image_display component to show the uploaded food photo."
        )
    
    def get_clarification_instruction():
        return "\n\n[Clarification Instruction] Clarify user needs, provide optional feature entries and concise explanations."
    
    def get_guardrail_instruction():
        return "\n\n[Guardrail Instruction] Identify potential risks and use highlight_box to highlight precautions and suggest alternatives."
    
    intent_instructions = {
        Intent.FOOD_RECOGNITION: get_food_recognition_instruction(),
        Intent.RECOMMENDATION: get_recommendation_instruction(),
        Intent.CLARIFICATION: get_clarification_instruction(),
        Intent.GUARDRAIL: get_guardrail_instruction(),
        Intent.GOAL_PLANNING: get_goal_planning_instruction(),
    }
    
    if intent in intent_instructions:
        prompt += intent_instructions[intent]
    return prompt

def _call_llm(prompt: str, model_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    调用LLM并解析UI计划
    
    Args:
        prompt: 提示词
        model_name: 模型名称，如果为None则使用默认模型
        
    Returns:
        解析后的UI计划字典
    """
    debug = os.getenv("UI_DEBUG") == "1"
    if debug:
        print("[UIGenerator] ===== UI LLM PROMPT (BEGIN) =====")
        print(prompt)
        print("[UIGenerator] ===== UI LLM PROMPT (END) =====")
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    
    # 调用统一的LLM接口
    if debug:
        print("[UIGenerator] Starting to generate plan")
    result = call_llm(
        model_name=model_name or DEFAULT_MODEL,
        messages=messages,
        max_tokens=4096,
        temperature=0.5,
    )
    
    if not result:
        if debug:
            print("[UIGenerator] LLM call failed")
        return None
    else:
        if debug:
            print("[UIGenerator] Plan generation completed")
    
    output_text = result["text"]
    if debug:
        print(f"[UIGenerator] Raw LLM output:\n{str(output_text)}")
    
    # 解析JSON
    match = re.search(r"\{[\s\S]*\}", output_text)
    if not match:
        return None

    try:
        plan = json.loads(match.group(0))
    except json.JSONDecodeError:
        plan = json.loads(match.group(0), strict=False)

    plan["token_usage"] = {
        "input": result["input_tokens"],
        "output": result["output_tokens"],
        "total": result["total_tokens"],
    }
    return plan

def _enforce_platform_compliance(plan: Dict, state: GraphState) -> Dict:
    """将 UI Plan 渲染为图片，并保留原有 sections。"""
    
    try:
        base_url = state.get("base_url", "")
        try:
            sec_cnt = len(plan.get("sections", []) or [])
            img_urls = []
            for s in plan.get("sections", []) or []:
                if isinstance(s, dict):
                    u = s.get("image_url") or s.get("url") or (s.get("props") or {}).get("url")
                    if u:
                        img_urls.append(str(u))
        except Exception:
            pass
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base_dir, "assets")
        uploaded_image_url = state.get("uploaded_image_url") or plan.get("uploaded_image_url")
        sanitized_sections = _sanitize_sections_for_render(plan.get("sections", []) or [], uploaded_image_url)
        sanitized_plan = {
            "summary": plan.get("summary", ""),
            "sections": sanitized_sections,
        }
        filename = render_ui_plan_to_image(sanitized_plan, output_dir, base_url=base_url)
        
        image_url = f"/static/{filename}"

        # 返回最终渲染的图片，使用标准 image_display 组件，确保前端可识别
        result_sections = [{
            "type": "image_display",
            "url": image_url,
            "image_url": image_url,
            "caption": plan.get("summary", "Generated UI"),
            "rounded": True
        }]

        result = {
            "mode": plan.get("mode", "image_render"),
            "summary": "",
            "sections": result_sections,
            "suggestions": plan.get("suggestions")
        }
        return result
    except Exception as e:
        text_content = plan.get("summary", "Rendering failed")
        return {
            "mode": "error",
            "summary": text_content,
            "sections": [{"type": "text", "content": text_content}],
            "suggestions": []
        }

def _fallback_plan(state: GraphState) -> Dict:
    agent_response = state.get("agent_response", "")
    msg = agent_response or ""
    return error_state(state, msg if msg else None)

def _generate_for_intent(state: GraphState) -> Dict:
    """根据当前 GraphState 调用 LLM 生成 UI 计划并转为图片。"""
    intent = state.get("intent", Intent.CLARIFICATION)
    language = state.get("language", "Chinese")

    llm_model = state.get("llm_model", DEFAULT_MODEL)
    debug = os.getenv("UI_DEBUG") == "1"
    if debug:
        print(f"[UIGenerator] Calling LLM to generate UI plan, intent={intent}, model={llm_model}")
    
    if intent == Intent.FOOD_RECOGNITION and not state.get("has_image") and not state.get("uploaded_image_url"):
        p = food_recognition_no_image(state, state.get("agent_response"))
        return _enforce_platform_compliance(p, state)
    if intent == Intent.GOAL_PLANNING and ("MOCK_USER_HISTORY" not in str(state.get("user_input", ""))):
        p = goal_planning_no_history(state)
        return _enforce_platform_compliance(p, state)
    if intent == Intent.GUARDRAIL:
        p = guardrail(state)
        return _enforce_platform_compliance(p, state)
    if intent == Intent.CLARIFICATION:
        p = clarification(state)
        return _enforce_platform_compliance(p, state)

    prompt = _build_llm_prompt(state)
    plan = _call_llm(prompt, model_name=llm_model)

    if plan:
        plan["language"] = language
        uploaded_image_url = state.get("uploaded_image_url")
        if uploaded_image_url:
            plan["uploaded_image_url"] = uploaded_image_url
        token_usage = plan.get("token_usage")
        if isinstance(token_usage, dict):
            if debug:
                print(f"[UIGenerator] Token usage (UI plan): input={token_usage.get('input')}, output={token_usage.get('output')}, total={token_usage.get('total')}")
        plan = _enforce_platform_compliance(plan, state)
        return plan

    return _enforce_platform_compliance(_fallback_plan(state), state)

def generate_ui_plan(state: GraphState) -> Dict:
    intent = state.get("intent", Intent.CLARIFICATION)
    
    plan = _generate_for_intent(state)
    
    return {"ui_plan": plan}
