# -*- coding: utf-8 -*-
"""根据意图与数据生成 ui_plan，并统一渲染为图片。"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

from UI.state import GraphState, Intent
from UI.ui_components import UI_COMPONENTS, SYSTEM_PROMPT_TEMPLATE
from UI.llm_config import call_llm, get_model_config, DEFAULT_MODEL
from UI.nodes.image_renderer import render_ui_plan_to_image

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
    print(f"[UIGenerator][DEBUG] sanitize_sections replaced={replaced} dropped={dropped} in={len(sections or [])} out={len(sanitized)}")
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
    """构建LLM提示，包含完整的上下文和数据"""
    intent = state.get("intent", "")
    language = state.get("language", "Chinese")
    context_input = state.get("context_input", "")
    intent_reasoning = state.get("intent_reasoning", "")
    intent_confidence = state.get("intent_confidence", 0.0)

    # 基础系统提示
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        components_json=json.dumps(UI_COMPONENTS, indent=2)
    )

    # 统一平台指令：总是请求丰富UI，后续渲染为图片
    prompt += (
        "\n\n【生成指令】"
        "我们将以图片形式展示你的回复。"
        "请生成丰富、美观的UI组件(如表格、列表、图表等)，不要受纯文本限制。"
        "不要生成'suggestions'列表。"
        "设计应自适应，内容清晰易读，适合在移动设备上查看。"
    )

    # 语言偏好
    prompt += f"\n\n【语言指令】使用{language}回复。"

    # 意图分析信息
    prompt += (
        f"\n\n【意图分析】\n"
        f"- 检测到的意图: {intent}\n"
        f"- 置信度: {intent_confidence:.2f}\n"
        f"- 推理: {intent_reasoning}\n"
    )

    # 意图特定指令
    is_inherited = state.get("inherited_intent", False)
    is_follow_up = state.get("data_source", "").startswith("existing_")
    user_input = state.get("user_input", "").lower()
    
    # 意图跟随标记
    if is_inherited:
        prompt += (
            "\n\n【意图跟随】这是用户对上一轮意图的跟进问题。"
            "使用已有数据，根据用户要求调整展示方式。"
        )
    
    def get_recommendation_instruction():
        return (
            "\n\n【推荐指令】对餐厅列表使用dynamic_place_table。"
            "确保所有字段(id, name, desc, rating, price, dist, is_veg, price_str, dist_str)"
            "都传递到items数组中。"
        )
    
    def get_goal_planning_instruction():
        return (
            "\n\n【目标规划指令】分析提供的user_history，制定具体、可衡量的目标"
            "和可执行的周计划。优先使用statistic_grid、line_chart、bar_chart、"
            "pie_chart、progress_bar、steps_list。所有数字必须可从历史数据计算得出。"
        )
    
    def get_food_recognition_instruction():
        return (
            "\n\n【食物识别指令】展示每种识别食物的热量。"
            "使用highlight_box突出显示不健康项目。显示总热量摘要。"
        )
    
    intent_instructions = {
        Intent.GOAL_PLANNING: get_goal_planning_instruction(),
        Intent.GUARDRAIL: (
            "\n\n【安全护栏指令】使用温暖、支持的语气。"
            "使用highlight_box和key_value_list突出显示求助热线号码。"
            "不要提供替代专业心理健康支持的建议。"
        ),
        Intent.FOOD_RECOGNITION: get_food_recognition_instruction(),
        Intent.RECOMMENDATION: get_recommendation_instruction(),
        Intent.CORRECTION: (
            "\n\n【纠错指令】礼貌地承认错误，简短道歉，"
            "并邀请用户指出哪里不对。使用纯文本格式。"
        ),
        Intent.GENERIC: (
            "\n\n【通用聊天指令】用户的消息不匹配任何特定功能（食物识别、餐厅推荐、"
            "目标规划等）。用温暖、有帮助的对话语气回复。"
            "请使用丰富UI组件，我们会将其转换为图片。" 
            "保持回复简洁（2-4句话）。在suggestions数组中建议2-3个用户可以用Wabi做的事情。"
        ),
    }
    
    if intent in intent_instructions:
        prompt += intent_instructions[intent]
    
    # 跟进问题特殊处理：用户要求特定图表展示已有数据
    if (is_inherited or is_follow_up):
        # 食物识别跟进
        if intent == Intent.FOOD_RECOGNITION:
            if any(kw in user_input for kw in ["雷达图", "radar"]):
                prompt += (
                    "\n\n【跟进问题-雷达图】用户使用雷达图展示已有食物数据。"
                    "使用radar_chart组件展示各食物的营养成分对比（热量、蛋白质、脂肪、碳水等）。"
                    "确保数据来自nutrition_facts。"
                )
            elif any(kw in user_input for kw in ["饼图", "pie"]):
                prompt += (
                    "\n\n【跟进问题-饼图】用户使用饼图展示已有食物数据。"
                    "使用pie_chart组件展示各食物的热量占比。"
                )
            elif any(kw in user_input for kw in ["柱状图", "bar", "柱"]):
                prompt += (
                    "\n\n【跟进问题-柱状图】用户使用柱状图展示已有食物数据。"
                    "使用bar_chart组件对比各食物的营养成分。"
                )
            else:
                prompt += (
                    "\n\n【跟进问题】这是关于已有食物数据的跟进问题。"
                    "根据用户的要求选择合适的图表展示营养数据。"
                )
        
        # 推荐跟进
        elif intent == Intent.RECOMMENDATION:
            if any(kw in user_input for kw in ["列表", "list"]):
                prompt += (
                    "\n\n【跟进问题-列表】用户要求以列表形式展示推荐餐厅。"
                    "使用key_value_list或statistic_grid组件展示。"
                )
            elif any(kw in user_input for kw in ["排序", "排名", "sort", "rank"]):
                prompt += (
                    "\n\n【跟进问题-排序】用户要求排序展示餐厅。"
                    "按评分或距离排序，使用dynamic_place_table展示。"
                )
            elif any(kw in user_input for kw in ["地图", "位置", "map"]):
                prompt += (
                    "\n\n【跟进问题-地图】用户要求查看餐厅位置。"
                    "突出显示地图信息或位置详情。"
                )
        
        # 目标规划跟进
        elif intent == Intent.GOAL_PLANNING:
            if any(kw in user_input for kw in ["图表", "折线图", "趋势", "chart", "trend"]):
                prompt += (
                    "\n\n【跟进问题-趋势图】用户要求查看饮食趋势。"
                    "使用line_chart展示历史趋势，bar_chart对比各天数据。"
                )
            elif any(kw in user_input for kw in ["统计", "数据", "statistics", "data"]):
                prompt += (
                    "\n\n【跟进问题-统计】用户要求查看详细统计。"
                    "使用statistic_grid展示关键指标，pie_chart展示营养分布。"
                )

    # 上下文信息
    prompt += f"\n\n【完整上下文】\n{context_input}"

    # 状态数据
    context = {
        "intent": intent,
        "user_input": str(state.get("user_input", ""))[:1000],
        "agent_response": str(state.get("agent_response", ""))[:1000],
        "nutrition_facts": state.get("nutrition_facts"),
        "recommended_restaurants": state.get("recommended_restaurants"),
        "has_image": state.get("has_image", False),
        "user_history": state.get("user_history"),
        "data_source": state.get("data_source"),
    }

    prompt += f"\n\n【当前状态数据】\n{json.dumps(context, indent=2, default=str)}"
    
    # 输出格式要求
    prompt += (
        "\n\n【输出要求】\n"
        "1. 生成一个完整的UI计划JSON对象\n"
        "2. 必须包含: mode, summary, sections, suggestions\n"
        "3. sections数组中的每个对象必须有type字段\n"
        "4. 根据数据和意图选择最合适的UI组件\n"
        "5. 确保UI计划对用户友好且信息丰富\n"
    )

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
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    
    # 调用统一的LLM接口
    result = call_llm(
        model_name=model_name or DEFAULT_MODEL,
        messages=messages,
        max_tokens=4096,
        temperature=0.5,
    )
    
    if not result:
        print("[UIGenerator] LLM call failed")
        return None
    
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
    print("[UIGenerator] Rendering UI plan to image")
    
    try:
        base_url = state.get("base_url", "")
        print(f"[UIGenerator][DEBUG] base_url={base_url}")
        try:
            sec_cnt = len(plan.get("sections", []) or [])
            img_urls = []
            for s in plan.get("sections", []) or []:
                if isinstance(s, dict):
                    u = s.get("image_url") or s.get("url") or (s.get("props") or {}).get("url")
                    if u:
                        img_urls.append(str(u))
            print(f"[UIGenerator][DEBUG] sections={sec_cnt} image_urls_in_plan={img_urls}")
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
        print(f"[UIGenerator] Generated image URL: {image_url}")

        # 只返回最终渲染的图片
        result_sections = [{
            "type": "image_display",
            "url": image_url,
            "alt": plan.get("summary", "Generated UI")
        }]

        result = {
            "mode": plan.get("mode", "image_render"),
            "summary": "",
            "sections": result_sections,
            "suggestions": [] # 图片模式下不提供建议
        }
        return result
    except Exception as e:
        print(f"[UIGenerator] Error rendering image: {e}")
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
    """根据意图生成UI计划"""
    intent = state.get("intent", Intent.CLARIFICATION)
    language = state.get("language", "Chinese")

    # ── 确定性路径 ─────────────────────────────────────────────
    if intent == Intent.CLARIFICATION:
        return _plan_clarification(state)
    
    # 纠错意图：使用专门的反馈收集界面
    if intent == Intent.CORRECTION:
        agent_response = state.get("agent_response", "")
        # 从 data_source 中提取额外数据
        data = {
            "feedback_recorded": state.get("feedback_recorded"),
            "awaiting_feedback": state.get("awaiting_feedback"),
            "data_source": state.get("data_source", ""),
            "suggestions": ["指出具体错误", "重新解释您的问题", "查看相关信息"] if language != "English" else ["Point out specific errors", "Rephrase your question", "View related information"],
        }
        
        return _plan_correction_ui(state, agent_response, data)

    # 食物识别：没有图片且没有已有数据时，提示上传图片
    # 如果有数据（意图跟随）或上传了新图片，走LLM路径生成展示
    if intent == Intent.FOOD_RECOGNITION:
        has_image = state.get("has_image", False)
        has_existing_data = state.get("nutrition_facts") is not None
        is_follow_up = state.get("data_source", "").startswith("existing_")
        
        if not has_image and not has_existing_data and not is_follow_up:
            # 使用 data_provider 提供的响应文本
            agent_response = state.get("agent_response", "")
            return _plan_food_recognition_no_image(state, agent_response)

    if intent == Intent.GOAL_PLANNING:
        history = state.get("user_history")
        if not history or not history.get("days"):
            return _plan_goal_planning_no_history(state)

    # ── LLM自适应路径 ──────────────────────────────────────────
    # 获取模型配置（从state中读取或使用默认）
    llm_model = state.get("llm_model", DEFAULT_MODEL)
    print(f"[UIGenerator] 调用LLM生成UI计划，意图: {intent}, 模型: {llm_model}")
    
    prompt = _build_llm_prompt(state)
    plan = _call_llm(prompt, model_name=llm_model)

    if plan:
        plan["language"] = language
        # 如果有用户上传图片的静态URL，注入到plan中以便强制展示
        uploaded_image_url = state.get("uploaded_image_url")
        if uploaded_image_url:
            plan["uploaded_image_url"] = uploaded_image_url
        # 强制所有计划转为图片
        plan = _enforce_platform_compliance(plan, state)
        return plan

    # LLM失败 — 回退
    return _enforce_platform_compliance(_fallback_plan(state), state)


def generate_ui_plan(state: GraphState) -> Dict:
    """
    LangGraph node function.

    Reads:  intent, agent_response, nutrition_facts, recommended_restaurants,
            user_history, has_image, language, chat_history,
            context_input, intent_reasoning, intent_confidence
    Writes: ui_plan
    
    Args:
        state: 当前图状态
        
    Returns:
        包含ui_plan的字典
    """
    intent = state.get("intent", Intent.GENERIC)
    print(f"[UIGenerator] 生成UI计划 — 意图={intent}")
    
    plan = _generate_for_intent(state)
    print(f"[UIGenerator] 计划模式: {plan.get('mode')}, 部分数: {len(plan.get('sections', []))}")
    
    return {"ui_plan": plan}
