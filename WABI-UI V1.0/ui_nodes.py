# -*- coding: utf-8 -*-
"""
UI Agent Nodes
Each function is a focused LangGraph node: receives UIAgentState, returns a
partial state dict. All constants live in ui_config.py; LLM infra in ui_llm.py.
"""

from __future__ import annotations

from typing import Any, Dict

from .ui_config import (
    CLARIFICATION_COPY,
    FOOD_RECOGNITION_NO_IMAGE_COPY,
    INTENT_ROUTES,
    TEXT_ONLY_PLATFORMS,
)
from .ui_llm import build_prompt, get_bedrock_client, invoke_bedrock, parse_plan_json
from .ui_state import UIAgentState


# ── Router ─────────────────────────────────────────────────────────────────────

def router_node(state: UIAgentState) -> Dict[str, Any]:
    intent = state.get("intent", "").lower()
    lang   = state.get("language", "Chinese")
    print(f"[router] intent={intent!r} | language={lang!r} | platform={state.get('platform')!r}")

    for route, intents in INTENT_ROUTES.items():
        if intent not in intents:
            continue
        if route == "food_recognition_no_image":
            result = "llm" if state.get("has_image") else route
            print(f"[router] food_recognition branch | has_image={state.get('has_image')} → {result!r}")
            return {"route": result}
        if route == "goal_planning":
            days = (state.get("user_history") or {}).get("days", [])
            result = "goal_planning_no_data" if not days else "llm"
            print(f"[router] goal_planning branch | history_days={len(days)} → {result!r}")
            return {"route": result}
        print(f"[router] matched route={route!r}")
        return {"route": route}

    print(f"[router] no match → 'llm'")
    return {"route": "llm"}


# ── Deterministic nodes ────────────────────────────────────────────────────────

def clarification_node(state: UIAgentState) -> Dict[str, Any]:
    platform = state.get("platform", "web")
    lang     = state.get("language", "Chinese")
    print(f"[clarification] lang={lang!r} | platform={platform!r}")
    key      = "web" if platform == "web" else "messaging"
    copy     = CLARIFICATION_COPY[key][lang]

    if platform == "web":
        sections = [
            {"type": "text", "content": copy["text_content"]},
            {"type": "custom_html", "description": "Clarification Options",
             "html_content": _clarification_html(copy)},
        ]
    else:
        sections = [{"type": "text", "content": copy["content"]}]

    return {"ui_plan": {
        "mode": "clarification", "language": lang,
        "summary": copy["summary"], "sections": sections, "suggestions": [],
    }}


def food_recognition_no_image_node(state: UIAgentState) -> Dict[str, Any]:
    lang = state.get("language", "Chinese")
    print(f"[food_rec_no_img] lang={lang!r}")
    c    = FOOD_RECOGNITION_NO_IMAGE_COPY[lang]
    return {"ui_plan": {
        "mode": "image_upload_request", "language": lang,
        "summary": c["summary"],
        "sections": [{"type": "text", "content": c["content"]}],
        "suggestions": [c["suggestion1"], c["suggestion2"]],
    }}


def goal_planning_no_data_node(state: UIAgentState) -> Dict[str, Any]:
    print(f"[goal_no_data] lang={state.get('language')!r} — no history days available")
    return {"ui_plan": {
        "mode": "goal_planning",
        "summary": "我还没有你的历史饮食数据，先从本周开始记录吧。",
        "sections": [{"type": "text", "content": "暂无历史数据可用于目标设定。"}],
        "suggestions": ["给我一个简单目标", "如何开始记录饮食", "今天吃什么更健康？"],
    }}


# ── LLM node ───────────────────────────────────────────────────────────────────

def llm_ui_generator_node(state: UIAgentState) -> Dict[str, Any]:
    print(f"[llm_generator] intent={state.get('intent')!r} | lang={state.get('language')!r} | platform={state.get('platform')!r}")
    client = get_bedrock_client()
    if client is None:
        return {"error": "Bedrock client unavailable.", "input_tokens": 0, "output_tokens": 0}

    try:
        raw_text, in_tok, out_tok = invoke_bedrock(client, build_prompt(state))
        plan = parse_plan_json(raw_text)
        if plan is None or "sections" not in plan:
            return {"error": f"Invalid LLM JSON: {raw_text[:200]}", "input_tokens": in_tok, "output_tokens": out_tok}
        return {"ui_plan": plan, "input_tokens": in_tok, "output_tokens": out_tok, "error": None}
    except Exception as exc:
        print(f"[UIAgent] LLM error: {exc}")
        return {"error": str(exc), "input_tokens": 0, "output_tokens": 0}


# ── Platform enforcer ──────────────────────────────────────────────────────────

def platform_enforcer_node(state: UIAgentState) -> Dict[str, Any]:
    platform = state.get("platform", "web")
    language = state.get("language", "Chinese")
    plan     = dict(state.get("ui_plan") or {})
    sections = plan.get("sections")
    print(f"[platform_enforcer] platform={platform!r} | language={language!r} | sections={len(sections) if isinstance(sections, list) else 0}")
    if isinstance(sections, list):
        if platform in TEXT_ONLY_PLATFORMS:
            sections = _downgrade_to_text(sections, platform)
        for s in sections:
            if s.get("type") == "custom_html":
                _sanitize_html(s)
        plan["sections"] = sections

    plan["token_usage"] = {
        "input":  state.get("input_tokens", 0),
        "output": state.get("output_tokens", 0),
        "total":  state.get("input_tokens", 0) + state.get("output_tokens", 0),
    }
    plan["language"] = state.get("language", "Chinese")
    return {"ui_plan": plan}


# ── Fallback ───────────────────────────────────────────────────────────────────

def fallback_node(state: UIAgentState) -> Dict[str, Any]:
    print(f"[UIAgent] Fallback: {state.get('error')}")
    return {"ui_plan": {
        "mode": "error", "language": state.get("language", "Chinese"),
        "summary": "Sorry, I encountered an issue generating the display.",
        "sections": [{"type": "text", "content": state.get("agent_response") or "Please try again later."}],
        "suggestions": [],
        "token_usage": {"input": 0, "output": 0, "total": 0},
    }}


# ── Private helpers ────────────────────────────────────────────────────────────

def _clarification_html(copy: dict) -> str:
    btn = (
        'class="px-3 py-2 rounded-full border text-sm" '
        'style="background:var(--bg-color);color:var(--text-color);border-color:var(--border-color);"'
    )
    buttons = "".join(
        f'<button {btn} onclick="document.getElementById(\'userInput\').value=\'{b["value"]}\';sendMessage()">{b["text"]}</button>'
        for b in copy["buttons"]
    )
    return (
        f'<div class="p-4" style="background:var(--card-bg);">'
        f'<div class="text-sm mb-3" style="color:var(--text-color);">{copy["title"]}</div>'
        f'<div class="flex gap-2 flex-wrap">{buttons}</div>'
        f'</div>'
    )


def _downgrade_to_text(sections: list, platform: str) -> list:
    """Convert non-text components to plain text for messaging platforms."""
    allowed = {"text", "image_display"}
    for s in sections:
        if s.get("type") in allowed:
            continue
        print(f"[UIAgent] Converting '{s.get('type')}' → text for {platform}")
        lines = []
        if s.get("title"):
            lines.append(f"*{s['title']}*")
        items = s.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                label = item.get("label") or item.get("title") or ""
                value = item.get("value") or item.get("subtitle") or item.get("description") or ""
                lines.append(f"{label}: {value}" if label and value else str(label or value))
        elif s.get("content"):
            lines.append(str(s["content"]))
        s["type"] = "text"
        s["content"] = "\n".join(lines)
    return sections


def _sanitize_html(section: dict) -> None:
    """Strip script tags and fix unclosed divs in custom_html sections."""
    html = section.get("html_content", "")
    if "<script>" in html:
        html = html.replace("<script>", "").replace("</script>", "")
    missing = html.count("<div") - html.count("</div>")
    if missing > 0:
        html += "</div>" * missing
    section["html_content"] = html
