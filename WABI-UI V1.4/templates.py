from __future__ import annotations
import re
from typing import Any, Dict, Optional
from UI.state import GraphState

def clarification(state: GraphState) -> Dict[str, Any]:
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
    return {
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

def food_recognition_no_image(state: GraphState, agent_response: str = None) -> Dict[str, Any]:
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
    return {
        "mode": "image_upload_request",
        "language": lang,
        "summary": summary,
        "sections": sections,
        "suggestions": ["How to use this?", "Go back"] if lang == "English" else ["这个功能怎么用？", "返回"],
        "awaiting_image": True,
    }

def goal_planning_no_history(state: GraphState) -> Dict[str, Any]:
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

def guardrail(state: GraphState) -> Dict[str, Any]:
    lang = state.get("language", "Chinese")
    if lang == "English":
        summary = "I want to be sensitive to how you are feeling. Here are some resources that can help."
        intro = "I am not able to provide professional support, but there are people who can help you right now."
        note = "If you are in immediate danger, please contact emergency services."
        sections = [
            {
                "type": "highlight_box",
                "content": "It sounds like you may be going through a difficult time. You are not alone.",
                "variant": "warning",
            },
            {
                "type": "text",
                "content": intro,
            },
            {
                "type": "key_value_list",
                "title": "Support resources (Singapore)",
                "items": [
                    {"label": "SOS 24-hour Hotline", "value": "1-767", "highlight": True},
                    {"label": "National Mindline", "value": "1771", "highlight": True},
                    {"label": "SAMH Helpline", "value": "1800-283-7019", "highlight": True},
                    {"label": "Emergency", "value": "995", "highlight": False},
                ],
            },
            {
                "type": "text",
                "content": note,
            },
        ]
        suggestions = ["Talk to someone I trust", "Show more resources"]
    else:
        summary = "我理解你现在可能正经历一段不容易的时刻，这里有一些可以帮助你的资源。"
        intro = "我无法提供专业的心理支持，但有一些专业机构可以在你需要的时候为你提供帮助。"
        note = "如果你处在紧急危险中，请立即联系当地急救电话。"
        sections = [
            {
                "type": "highlight_box",
                "content": "听起来你可能正经历一段艰难的时期，你并不孤单。",
                "variant": "warning",
            },
            {
                "type": "text",
                "content": intro,
            },
            {
                "type": "key_value_list",
                "title": "支持资源（新加坡）",
                "items": [
                    {"label": "SOS 24 小时热线", "value": "1-767", "highlight": True},
                    {"label": "National Mindline 热线", "value": "1771", "highlight": True},
                    {"label": "SAMH 热线", "value": "1800-283-7019", "highlight": True},
                    {"label": "紧急电话", "value": "995", "highlight": False},
                ],
            },
            {
                "type": "text",
                "content": note,
            },
        ]
        suggestions = ["我想和信任的人聊聊", "显示更多帮助资源"]
    return {
        "mode": "guardrail",
        "summary": summary,
        "sections": sections,
        "suggestions": suggestions,
    }

def error_state(state: GraphState, error_msg: Optional[str] = None) -> Dict[str, Any]:
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
