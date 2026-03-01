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

def _sanitize_sections_for_render(sections: list, uploaded_image_url: Optional[str]) -> list:
    sanitized = []
    replaced = 0
    dropped = 0
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
                replaced += 1
            else:
                dropped += 1
        else:
            sanitized.append(s)
    return sanitized

def _plan_clarification(state: GraphState) -> Dict:
    """澄清意图的确定性UI计划 (统一为图片输出)"""
    lang = state.get("language", "Chinese")
    
    if lang == "English":
        summary = "I can help you with restaurant recommendations or food recognition"
        intro_text = "I can assist you with the following functions:"
        option1 = "🍽️ Restaurant Recommendations - Find restaurants based on your preferences"
        option2 = "🔍 Food Recognition - Analyze nutritional content from food photos"
        instruction = "Please tell me what you need help with, and I'll provide the appropriate service."
    else:
        summary = "我可以帮您提供餐厅推荐或食物识别服务"
        intro_text = "我可以为您提供以下功能："
        option1 = "🍽️ 餐厅推荐 - 根据您的偏好查找餐厅"
        option2 = "🔍 食物识别 - 分析食物照片的营养成分"
        instruction = "请告诉我您需要什么帮助，我将为您提供相应的服务。"

    plan = {
        "mode": "clarification",
        "language": lang,
        "summary": summary,
        "sections": [
            {"type": "text", "content": intro_text},
            {"type": "highlight_box", "content": option1, "variant": "info"},
            {"type": "highlight_box", "content": option2, "variant": "info"},
            {"type": "text", "content": instruction},
        ],
        "suggestions": [],
    }
    # 立即转为图片
    return _enforce_platform_compliance(plan, state)

def _plan_food_recognition_no_image(state: GraphState, agent_response: str = None) -> Dict:
    """无图片时的食物识别UI计划 (统一为图片输出)"""
    lang = state.get("language", "Chinese")

    if agent_response is None:
        if lang == "English":
            agent_response = (
                "Please upload a food photo, and I'll analyze the nutritional content for you.\n\n"
                "You can take a photo directly or select one from your album."
            )
        else:
            agent_response = (
                "请上传一张食物照片，我来帮您分析营养成分。\n\n"
                "您可以直接拍照或从相册选择。"
            )

    raw_text = str(agent_response or "").strip()
    parts = [p.strip() for p in re.split(r"\n\s*\n", raw_text) if p.strip()]

    if parts:
        summary = parts[0]
        body = "\n\n".join(parts[1:]) if len(parts) > 1 else ""
    else:
        summary = ""
        body = ""

    sections = []
    if body:
        sections.append({"type": "text", "content": body})
    elif summary:
        sections.append({"type": "text", "content": summary})

    plan = {
        "mode": "image_upload_request",
        "language": lang,
        "summary": summary,
        "sections": sections,
        "suggestions": ["How to use this?", "Go back"] if lang == "English" else ["这个功能怎么用？", "返回"],
        "awaiting_image": True,
    }
    return _enforce_platform_compliance(plan, state)

def _plan_goal_planning_no_history(state: GraphState) -> Dict:
    """无历史数据时的目标规划UI计划"""
    lang = state.get("language", "Chinese")
    if lang == "English":
        summary = "I don't have your diet history yet. Let's start tracking this week."
        content = "No historical data available for goal setting."
        suggestions = ["Give me a simple goal", "How to start tracking", "What to eat today?"]
    else:
        summary = "我还没有你的历史饮食数据，先从本周开始记录吧。"
        content = "暂无历史数据可用于目标设定。"
        suggestions = ["给我一个简单目标", "如何开始记录饮食", "今天吃什么更健康？"]
    
    return {
        "mode": "goal_planning",
        "summary": summary,
        "sections": [{"type": "text", "content": content}],
        "suggestions": suggestions,
    }

def _plan_error_state(state: GraphState, error_msg: str = None) -> Dict:
    """错误状态的UI计划"""
    lang = state.get("language", "Chinese")
    if error_msg is None:
        error_msg = "An error occurred" if lang == "English" else "出现错误"
    
    return {
        "mode": "error",
        "summary": error_msg,
        "sections": [
            {
                "type": "highlight_box",
                "content": "Please try again later." if lang == "English" else "请稍后重试。",
                "variant": "error",
            }
        ],
        "suggestions": [],
    }

def _plan_correction_ui(state: GraphState, agent_response: str, data: Dict) -> Dict:
    """
    纠错意图的UI计划 - 一步完成版本 (统一为图片输出)
    
    当用户触发纠错意图时，直接记录反馈并显示感谢信息，
    不再要求用户输入详细反馈。
    """
    lang = state.get("language", "Chinese")
    patient_id = state.get("patient_id", "unknown")
    
    # 一步完成：直接显示感谢信息
    if lang == "English":
        title = "Thank You for Your Feedback!"
        message = "We have received your feedback and will use it to improve our service. Please try asking your question again with more details."
    else:
        title = "感谢您的反馈！"
        message = "我们已收到您的反馈，将用于改进我们的服务。请用更详细的方式重新描述您的问题，我会尽力提供更准确的回答。"

    plan = {
        "mode": "correction_ack",  # 简化模式名称
        "language": lang,
        "summary": "",  # 清空summary，只显示图片内容
        "sections": [
            {
                "type": "highlight_box",
                "content": title,
                "variant": "success",
            },
            {
                "type": "text",
                "content": message,
            }
        ],
        "suggestions": [],
        "feedback_recorded": True,
        "awaiting_feedback": False,  # 不再等待用户反馈
    }
    return _enforce_platform_compliance(plan, state)

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
            "\n\n[Recommendation Instruction] Use dynamic_place_table for the restaurant list. "
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
    print("[UIGenerator] ===== UI LLM PROMPT (BEGIN) =====")
    print(prompt)
    print("[UIGenerator] ===== UI LLM PROMPT (END) =====")
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    
    # 调用统一的LLM接口
    print("[UIGenerator] Starting to generate plan")
    result = call_llm(
        model_name=model_name or DEFAULT_MODEL,
        messages=messages,
        max_tokens=4096,
        temperature=0.5,
    )
    
    if not result:
        print("[UIGenerator] LLM call failed")
        return None
    else:
        print("[UIGenerator] Plan generation completed")
    
    output_text = result["text"]
    print(f"[UIGenerator] Raw LLM output:\n{str(output_text)[:500]}...")
    
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
    """当所有其他方法失败时的回退UI计划"""
    lang = state.get("language", "Chinese")
    agent_response = state.get("agent_response", "")
    
    return {
        "mode": "error",
        "summary": "Sorry, I encountered an issue generating the display." if lang == "English" else "抱歉，生成显示时遇到问题。",
        "sections": [
            {"type": "text", "content": agent_response or "Please try again later."}
        ],
        "suggestions": [],
    }

def _generate_for_intent(state: GraphState) -> Dict:
    """根据当前 GraphState 调用 LLM 生成 UI 计划并转为图片。"""
    intent = state.get("intent", Intent.CLARIFICATION)
    language = state.get("language", "Chinese")

    llm_model = state.get("llm_model", DEFAULT_MODEL)
    print(f"[UIGenerator] Calling LLM to generate UI plan, intent: {intent}, model: {llm_model}")
    
    prompt = _build_llm_prompt(state)
    plan = _call_llm(prompt, model_name=llm_model)

    if plan:
        plan["language"] = language
        uploaded_image_url = state.get("uploaded_image_url")
        if uploaded_image_url:
            plan["uploaded_image_url"] = uploaded_image_url
        plan = _enforce_platform_compliance(plan, state)
        return plan

    return _enforce_platform_compliance(_fallback_plan(state), state)

def generate_ui_plan(state: GraphState) -> Dict:
    intent = state.get("intent", Intent.CLARIFICATION)
    
    plan = _generate_for_intent(state)
    
    return {"ui_plan": plan}
