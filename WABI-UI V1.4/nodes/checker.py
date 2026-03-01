# -*- coding: utf-8 -*-
"""对 ui_plan 做校验与必要的安全处理，输出 checked_output。"""

from __future__ import annotations

import copy
import os
import re
from typing import Dict

from UI.state import GraphState

_SCRIPT_RE   = re.compile(r"<script[\\s\\S]*?</script>", re.IGNORECASE)
_ON_EVENT_RE = re.compile(r'\\bon\\w+\\s*=\\s*"[^"]*"', re.IGNORECASE)

def _sanitise_html(html: str) -> str:
    html = _SCRIPT_RE.sub("", html)
    html = _ON_EVENT_RE.sub("", html)
    return html

def _fix_unclosed_divs(html: str) -> str:
    open_count  = html.count("<div")
    close_count = html.count("</div>")
    if open_count > close_count:
        html += "</div>" * (open_count - close_count)
    return html

_REQUIRED_KEYS   = {"mode", "summary", "sections"}
_REQUIRED_SECTION = {"type"}

def _validate_plan(plan: Dict) -> bool:
    if not isinstance(plan, dict):
        return False
    if not _REQUIRED_KEYS.issubset(plan.keys()):
        return False
    sections = plan.get("sections")
    if not isinstance(sections, list):
        return False
    for sec in sections:
        if not isinstance(sec, dict) or "type" not in sec:
            return False
    return True

def _post_process(plan: Dict, language: str) -> Dict:
    plan = copy.deepcopy(plan)

    plan.setdefault("mode",        "image_render")
    plan.setdefault("summary",     "")
    plan.setdefault("sections",    [])
    plan.setdefault("suggestions", [])
    plan["language"] = language

    for section in plan["sections"]:
        sec_type = section.get("type", "")

        if sec_type == "custom_html":
            html = section.get("html_content", "")
            html = _sanitise_html(html)
            html = _fix_unclosed_divs(html)
            section["html_content"] = html

        if sec_type in ("key_value_list", "carousel", "place_table",
                        "bar_chart", "pie_chart", "statistic_grid", "tag_list"):
            section.setdefault("items", [])

        if sec_type == "steps_list":
            section.setdefault("steps", [])

        if sec_type == "line_chart":
            section.setdefault("points", [])
            section.setdefault("labels", [])

        if sec_type == "radar_chart":
            section.setdefault("axes",   [])
            section.setdefault("values", [])

    return plan

def _emergency_fallback(state: GraphState) -> Dict:
    return {
        "mode":        "error",
        "summary":     "Sorry, something went wrong. Please try again.",
        "sections": [
            {
                "type":    "highlight_box",
                "content": "An unexpected error occurred while generating the response.",
                "variant": "error",
            }
        ],
        "suggestions": [],
    }

def check_output(state: GraphState) -> Dict:
    """
    LangGraph node function.

    Reads:  state["ui_plan"], state["language"]
    Writes: state["checked_output"]
    """
    ui_plan  = state.get("ui_plan")
    language = state.get("language", "Chinese")
    debug = os.getenv("UI_DEBUG") == "1"
    if debug:
        print(f"[Checker] Validating plan for lang={language}")

    if not _validate_plan(ui_plan):
        if debug:
            print("[Checker] Invalid or missing ui_plan — using emergency fallback")
        ui_plan = _emergency_fallback(state)

    checked_ui_plan = _post_process(ui_plan, language)
    if debug:
        print(f"[Checker] Check complete — mode={checked_ui_plan.get('mode')}, sections={len(checked_ui_plan.get('sections', []))}")

    return {"checked_output": checked_ui_plan}
