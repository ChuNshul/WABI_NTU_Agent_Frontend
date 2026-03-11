"""
ui_node.py — LangGraph node that orchestrates UI rendering.

Pipeline:
  state → planner (LLM) → checker → builder (HTML) → renderer (PNG) → state
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from .planner  import _load_components, build_prompt, _call_llm_for_plan, fallback_plan
from .checker  import validate_plan
from .builder  import build_html
from .renderer import render_to_image

logger = logging.getLogger(__name__)

# Model used for UI planning (separate from main agent model)
_UI_PLAN_MODEL = "claude-3.5-sonnet"


# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def _get(state: Any, key: str, default=None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _set(state: Any, key: str, value: Any) -> None:
    if isinstance(state, dict):
        state[key] = value
        return
    try:
        object.__setattr__(state, key, value)
    except Exception:
        setattr(state, key, value)


def _apply(state: Any, updates: Dict[str, Any]) -> None:
    for k, v in updates.items():
        _set(state, k, v)


# ---------------------------------------------------------------------------
# Node entrypoint
# ---------------------------------------------------------------------------

def ui_node(state: Any) -> Dict[str, Any]:
    """
    Render the current agent state as a mobile UI card image.

    Returns a dict of state updates containing:
      - ui_image_url:   data-URI PNG of the rendered UI
    """
    updates: Dict[str, Any] = {"ui_image_url": None}

    intent = _get(state, "intent")
    logger.info(
        "[ui_node] start | intent=%s | model=%s | safety=%s",
        intent, _UI_PLAN_MODEL, _get(state, "safety_passed"),
    )

    # ── 1. Load component schema ──────────────────────────────────────────
    components = _load_components()
    if not components:
        logger.warning("[ui_node] ui_components.json is empty; continuing with empty schema")

    # ── 2. Build LLM prompt ───────────────────────────────────────────────
    try:
        prompt = build_prompt(state, components)
        logger.debug("[ui_node] prompt length=%d chars", len(prompt))
        print(prompt)
    except Exception:
        logger.exception("[ui_node] build_prompt failed")
        return updates

    # ── 3. Generate UI plan via LLM ───────────────────────────────────────
    plan = _call_llm_for_plan(prompt, _UI_PLAN_MODEL)
    print(plan)
    if plan is None:
        logger.warning("[ui_node] LLM plan failed; using fallback")
        plan = fallback_plan(state)
    else:
        plan = validate_plan(plan, intent_default=intent or "fallback")

    logger.info(
        "[ui_node] plan ready | mode=%s | sections=%d",
        plan.get("mode"), len(plan.get("sections", [])),
    )

    # ── 4. Render plan to HTML ─────────────────────────────────────────────
    try:
        html = build_html(plan)
        logger.debug("[ui_node] HTML length=%d chars", len(html))
    except Exception:
        logger.exception("[ui_node] build_html failed")
        return updates

    # ── 5. Screenshot HTML → PNG data-URI ─────────────────────────────────
    try:
        img_url = asyncio.run(render_to_image(html))
        updates["ui_image_url"]   = img_url
        logger.info("[ui_node] screenshot complete | url=%.64s%s",
                    img_url, "..." if len(img_url) > 64 else "")
    except Exception:
        logger.exception("[ui_node] render_to_image failed")

    _apply(state, updates)
    return updates
