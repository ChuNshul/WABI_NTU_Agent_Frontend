# -*- coding: utf-8 -*-
"""对 ui_plan 做校验与必要的安全处理，输出 checked_output。"""

from __future__ import annotations

import copy
import os
import re
import time
from typing import Dict

from UI.state import GraphState
from UI.nodes.logger import log_state, preview_json, summarize_state

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

def _validate_html(html: str) -> bool:
    if not isinstance(html, str) or not html.strip():
        return False
    if "<html" not in html or "</html>" not in html:
        return False
    return True

def _validate_image(url: str) -> bool:
    if not isinstance(url, str) or not url.startswith("/static/"):
        return False
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assets_dir = os.path.join(base_dir, "assets")
        filename = url.split("/static/")[-1]
        path = os.path.join(assets_dir, filename)
        return os.path.exists(path)
    except Exception:
        return False

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
    t0 = time.perf_counter()
    state["current_node"] = "checker"
    ui_plan  = state.get("ui_plan")
    language = state.get("language", "Chinese")
    log_state(state, "info", "Checker started", node="checker", event="node_start", data=summarize_state(state))
    log_state(state, "debug", "Checker plan preview", node="checker", event="plan_preview", data={"plan": preview_json(ui_plan, limit=1500)})

    plan_ok = _validate_plan(ui_plan)
    if not plan_ok:
        ui_plan = _emergency_fallback(state)
        log_state(state, "warning", "Checker plan invalid; using fallback", node="checker", event="plan_invalid")

    html = state.get("html_content", "")
    image_url = state.get("rendered_image_url", "")
    checked_ui_plan = _post_process(ui_plan, language)
    html_ok = _validate_html(html)
    image_ok = _validate_image(image_url)
    if html_ok and image_ok:
        checked_ui_plan = {
            "mode": checked_ui_plan.get("mode", "image_render"),
            "summary": "",
            "sections": [{
                "type": "image_display",
                "url": image_url,
                "image_url": image_url,
                "caption": checked_ui_plan.get("summary", "Generated UI"),
                "rounded": True
            }],
            "suggestions": checked_ui_plan.get("suggestions", [])
        }
    log_state(
        state,
        "info",
        "Checker output ready",
        node="checker",
        event="output_ready",
        data={
            "plan_ok": plan_ok,
            "html_ok": html_ok,
            "image_ok": image_ok,
            "output_preview": preview_json(checked_ui_plan, limit=1500),
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        },
    )

    return {"checked_output": checked_ui_plan}
