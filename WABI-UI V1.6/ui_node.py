from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict
from .planner import _load_components, build_prompt, _call_llm_for_plan, fallback_plan
from .checker import validate_plan
from .builder import build_html
from .renderer import render_to_image

logger = logging.getLogger(__name__)

def _g(state: Any, key: str, default=None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)

def _set(state: Any, key: str, value: Any) -> None:
    if isinstance(state, dict):
        state[key] = value
    else:
        try:
            object.__setattr__(state, key, value)
        except Exception:
            setattr(state, key, value)

def _apply(state: Any, updates: Dict[str, Any]) -> None:
    for k, v in updates.items():
        _set(state, k, v)

def ui_node(state: Any) -> Dict[str, Any]:
    updates: Dict[str, Any] = {
        "ui_image_url":   None,
    }
    intent     = _g(state, "intent")
    model_name = "claude-3.5-sonnet"
    logger.info(
        "[ui_node] start | intent=%s | model=%s | safety=%s",
        intent, model_name, _g(state, "safety_passed"),
    )
    components = _load_components()
    if not components:
        logger.warning("[ui_node] ui_components.json 为空，使用空组件表继续")
    try:
        prompt = build_prompt(state, components)
        print("prompt:", prompt)
        logger.debug("[ui_node] prompt 长度=%d chars", len(prompt))
    except Exception as exc:
        logger.exception("[ui_node] build_prompt 失败: %s", exc)
        return updates
    plan = _call_llm_for_plan(prompt, model_name)
    print("UI plan:", plan)
    if plan is None:
        logger.warning("[ui_node] UI plan 失败，使用 fallback plan")
        plan = fallback_plan(state)
    else:
        plan = validate_plan(plan, intent_default=_g(state, "intent") or "fallback")
    logger.info(
        "[ui_node] plan ready | mode=%s | sections=%d",
        plan.get("mode"), len(plan.get("sections", [])),
    )
    try:
        html = build_html(plan)
        logger.debug("[ui_node] HTML 长度=%d chars", len(html))
    except Exception as exc:
        logger.exception("[ui_node] build_html 失败: %s", exc)
        return updates
    try:
        img_url = asyncio.run(render_to_image(html))
        updates["ui_image_url"]  = img_url
        updates["agent_response"] = [
            {"type": "image_url", "image_url": {"url": img_url}}
        ]
        logger.info("[ui_node] 截图完成 | url=%.64s%s", img_url, "..." if len(img_url) > 64 else "")
    except Exception as exc:
        logger.exception("[ui_node] render_to_image 失败: %s", exc)
    _apply(state, updates)
    return updates
