"""
ui_node.py — LangGraph node that orchestrates UI rendering.

Pipeline:
  state → planner (LLM) → checker → builder (HTML) → renderer (PNG) → state
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict
import time

from .planner  import _load_components, _call_llm_for_plan, fallback_plan
from .prompter import build_prompt
from .checker  import validate_plan
from .builder  import build_html
from .renderer import render_to_image
import csv, os, datetime, threading

logger = logging.getLogger(__name__)

model_name = "google/gemma-3-12b-it:free"
# google/gemma-3-12b-it:free
# google/gemma-3-27b-it:free
# google/gemma-3-4b-it:free
# meta-llama/llama-3.2-3b-instruct:free
# meta-llama/llama-3.3-70b-instruct:free
# nvidia/nemotron-3-nano-30b-a3b:free
# qwen/qwen3-4b:free
# qwen/qwen3-next-80b-a3b-instruct:free

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

def ui_node(state: Any) -> Any:
    """
    Render the current agent state as a mobile UI card image.

    This node modifies the state in-place by setting `ui_image_url`
    and returns the entire state object.
    """
    updates: Dict[str, Any] = {"ui_image_url": None}

    intent = _get(state, "intent")
    logger.info(
        "[ui_node] start | model=%s | intent=%s | safety=%s",
        model_name, intent, _get(state, "safety_passed"),
    )

    t0 = time.perf_counter()
    # ── 1. Load component schema ──────────────────────────────────────────
    components = _load_components()
    if not components:
        logger.warning("[ui_node] ui_components.json is empty; continuing with empty schema")

    # ── 2. Build LLM prompt ───────────────────────────────────────
    try:
        prompt = build_prompt(state, components)
        logger.debug("[ui_node] prompt length=%d chars", len(prompt))
        print(prompt)
    except Exception:
        logger.exception("[ui_node] build_prompt failed")
        _apply(state, updates)
        return state
    t1 = time.perf_counter()

    # ── 3. Generate UI plan via LLM ───────────────────────────────────────
    plan_info = _call_llm_for_plan(prompt, model=model_name)
    print(plan_info)
    if plan_info is None:
        logger.warning("[ui_node] LLM plan failed; using fallback")
        plan = fallback_plan(state)
        usage_info = None
    else:
        if isinstance(plan_info, tuple):
            plan, usage_info = plan_info
        else:
            plan = plan_info
            usage_info = None
        plan = validate_plan(plan, intent_default=intent or "fallback")
    t2 = time.perf_counter()

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
        _apply(state, updates)
        return state
    t3 = time.perf_counter()

    # ── 5. Screenshot HTML → PNG data-URI ─────────────────────────────────
    try:
        img_url = asyncio.run(render_to_image(html))
        updates["ui_image_url"]   = img_url
        logger.info("[ui_node] screenshot complete | url=%.64s%s",
                    img_url, "..." if len(img_url) > 64 else "")
    except Exception:
        logger.exception("[ui_node] render_to_image failed")
    t4 = time.perf_counter()

    _csv_lock = threading.Lock()
    _csv_path = os.path.join(os.path.dirname(__file__), "ui_node_metrics.csv")
    _csv_header = [
        "timestamp",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "prompt_ms",
        "llm_ms",
        "html_ms",
        "render_ms",
        "total_ms"
    ]
    # 初始化 CSV 文件（仅首次）
    with _csv_lock:
        if not os.path.exists(_csv_path):
            with open(_csv_path, "w", newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(_csv_header)

    # 只有在 usage_info 存在时才记录
    if usage_info:
        # 组装一行数据
        row = [
            datetime.datetime.utcnow().isoformat(timespec='milliseconds') + 'Z',
            usage_info.get("model") if usage_info else "",
            usage_info.get("prompt_tokens") if usage_info else "",
            usage_info.get("completion_tokens") if usage_info else "",
            usage_info.get("total_tokens") if usage_info else "",
            usage_info.get("cost_usd") if usage_info else "",
            int((t1 - t0) * 1000),
            int((t2 - t1) * 1000),
            int((t3 - t2) * 1000),
            int((t4 - t3) * 1000),
            int((t4 - t0) * 1000),
        ]
        # 追加写入并立即刷盘，保证多线程安全
        with _csv_lock:
            with open(_csv_path, "a", newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
                f.flush()
    # 保持原有日志输出
    if usage_info:
        logger.info(
            "[ui_node] usage | model=%s | prompt=%s | completion=%s | total=%s | cost_usd=%s",
            usage_info.get("model"),
            usage_info.get("prompt_tokens"),
            usage_info.get("completion_tokens"),
            usage_info.get("total_tokens"),
            usage_info.get("cost_usd"),
        )
    logger.info(
        "[ui_node] runtime | prompt=%dms | llm=%dms | html=%dms | render=%dms | total=%dms",
        int((t1 - t0) * 1000),
        int((t2 - t1) * 1000),
        int((t3 - t2) * 1000),
        int((t4 - t3) * 1000),
        int((t4 - t0) * 1000),
    )

    _apply(state, updates)
    state.ui_image_url = updates["ui_image_url"]  # Ensure URL is set even if rendering failed
    return state
