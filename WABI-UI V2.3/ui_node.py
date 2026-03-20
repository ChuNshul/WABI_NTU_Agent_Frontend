"""
ui_node.py — LangGraph node that orchestrates UI rendering.

Pipeline:
  state → build_prompt() → LLM → JSON dict → Plan.from_dict() → build_html(Plan) → PNG

Changes vs original:
  - Removed _load_components() import and call (zero disk I/O at runtime)
  - build_prompt() no longer takes a `components` argument
  - validate_plan() now returns a typed Plan; build_html() accepts it directly
  - Template renders use fixed HTML (no LLM call)
"""
from __future__ import annotations

import base64
import csv
import datetime
import logging
import os
import queue
import threading
import time
import zlib
from typing import Any, Dict

from .planner  import _call_llm_for_plan, _call_llm_for_html, get_last_llm_error
from .prompter import build_prompt, build_prompt_direct_html
from .checker  import validate_plan
from .builder  import build_html
from .renderer import render_to_image_sync, warmup_renderer
from .template import render_template
from .tools import (
    extract_ui_ctx as _extract_ui_ctx,
    finalize_state as _finalize_state,
    get as _get,
    get_render_mode as _get_render_mode,
    is_empty_upstream as _is_empty_upstream,
    serialize_agent_response as _serialize_agent_response,
    should_use_template as _should_use_template,
    user_input_text as _user_input_str,
)

logger = logging.getLogger(__name__)

model_name = "google/gemini-3.1-flash-lite-preview"

def _skip_ui_node(*, state: Any, intent: str | None, user_input_str: str, upstream_str: str, render_mode: str, reason: str) -> Any:
    updates: Dict[str, Any] = {"ui_image_url": None}
    t0 = time.perf_counter()
    t1 = t2 = t3 = t4 = time.perf_counter()
    _enqueue_metrics(
        usage_info=None,
        t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
        intent=intent or "",
        user_input_str=user_input_str,
        upstream_str=upstream_str,
        ui_image_url=updates.get("ui_image_url"),
        render_mode=render_mode,
        error="" if (reason or "").strip().lower() == "exit" else (reason or "skipped"),
    )
    return _finalize_state(state, updates)

def _run_template_path(*, state: Any, updates: Dict[str, Any], intent: str | None, user_input_str: str, upstream_str: str, render_mode: str, t0: float, log_prefix: str) -> Any | None:
    tmpl_key = _should_use_template(intent or "")
    if tmpl_key is None:
        return None
    html = render_template(intent=tmpl_key, user_input=user_input_str)
    t1 = t2 = t3 = time.perf_counter()
    error_reason = ""
    try:
        img_url = render_to_image_sync(html)
        updates["ui_image_url"] = img_url
    except Exception as exc:
        logger.exception("[%s] template render_to_image failed", log_prefix)
        error_reason = f"render_to_image: {exc}"
    t4 = time.perf_counter()
    _enqueue_metrics(
        usage_info=None,
        t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
        intent=intent or "",
        user_input_str=user_input_str,
        upstream_str=upstream_str,
        ui_image_url=updates.get("ui_image_url"),
        render_mode=render_mode,
        error="" if updates.get("ui_image_url") else (error_reason or "no_image"),
    )
    return _finalize_state(state, updates)

def _render_to_image(*, html: str | None, updates: Dict[str, Any], error_reason: str, log_prefix: str) -> tuple[str, float]:
    t3 = time.perf_counter()
    try:
        if html:
            img_url = render_to_image_sync(html)
            updates["ui_image_url"] = img_url
        else:
            if not error_reason:
                error_reason = "no_html"
    except Exception as exc:
        logger.exception("[%s] render_to_image failed", log_prefix)
        if not error_reason:
            error_reason = f"render_to_image: {exc}"
    t4 = time.perf_counter()
    return error_reason, t4

def _record_metrics(*, usage_info, t0: float, t1: float, t2: float, t3: float, t4: float, intent: str | None, user_input_str: str, upstream_str: str, updates: Dict[str, Any], render_mode: str, error_reason: str) -> None:
    _enqueue_metrics(
        usage_info=usage_info if isinstance(usage_info, dict) else None,
        t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
        intent=intent or "",
        user_input_str=user_input_str,
        upstream_str=upstream_str,
        ui_image_url=updates.get("ui_image_url"),
        render_mode=render_mode,
        error="" if updates.get("ui_image_url") else (error_reason or "no_image"),
    )

# ---------------------------------------------------------------------------
# Metrics (unchanged except dark-theme fallback HTML)
# ---------------------------------------------------------------------------

def _ensure_csv_header(path: str, header: list) -> None:
    if not os.path.exists(path):
        with open(path, "w", newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(header)

_CSV_LOCK   = threading.Lock()
_CSV_PATH   = os.path.join(os.path.dirname(__file__), "ui_node_metrics.csv")
_CSV_HEADER = [
    "timestamp","model","prompt_tokens","completion_tokens",
    "total_tokens","cost_usd","prompt_ms","llm_ms","html_ms",
    "render_ms","total_ms","intent","user_input","upstream",
    "ui_image_compressed","render_mode","error",
]
_METRICS_Q: "queue.Queue[dict]" = queue.Queue(maxsize=256)
_METRICS_THREAD: threading.Thread | None = None


def _start_metrics_writer() -> None:
    global _METRICS_THREAD
    if _METRICS_THREAD is not None and _METRICS_THREAD.is_alive(): return
    def worker() -> None:
        while True:
            item = _METRICS_Q.get()
            try:
                if item is None:
                    return
                with _CSV_LOCK:
                    _ensure_csv_header(_CSV_PATH, _CSV_HEADER)
                img_url = item.get("ui_image_url") or ""
                try:
                    compressed = base64.b64encode(zlib.compress(img_url.encode())).decode("ascii") if img_url else ""
                except Exception:
                    compressed = ""
                u = item.get("usage_info")
                def _u(k): return (u.get(k) if u else "") if isinstance(u, dict) else ""
                row = [
                    item.get("timestamp") or "", _u("model"),
                    _u("prompt_tokens"), _u("completion_tokens"), _u("total_tokens"), _u("cost_usd"),
                    item.get("prompt_ms") or 0, item.get("llm_ms") or 0,
                    item.get("html_ms") or 0, item.get("render_ms") or 0, item.get("total_ms") or 0,
                    item.get("intent") or "", item.get("user_input") or "",
                    item.get("upstream") or "", compressed,
                    item.get("render_mode") or "", item.get("error") or "",
                ]
                with _CSV_LOCK:
                    with open(_CSV_PATH, "a", newline="", encoding="utf-8") as f:
                        csv.writer(f).writerow(row)
                        f.flush()
            except Exception:
                pass
            finally:
                try:
                    _METRICS_Q.task_done()
                except Exception:
                    pass
    _METRICS_THREAD = threading.Thread(target=worker, name="ui_metrics", daemon=True)
    _METRICS_THREAD.start()

def flush_metrics(timeout_s: float = 2.0) -> bool:
    _start_metrics_writer()
    deadline = time.time() + max(0.0, float(timeout_s))
    while True:
        unfinished = getattr(_METRICS_Q, "unfinished_tasks", 0)
        if unfinished == 0:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.01)


def _enqueue_metrics(*, usage_info, t0, t1, t2, t3, t4,
                     intent, user_input_str, upstream_str,
                     ui_image_url, render_mode, error) -> None:
    _start_metrics_writer()
    try:
        _METRICS_Q.put_nowait({
            "timestamp":    datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "usage_info":   usage_info if isinstance(usage_info, dict) else None,
            "prompt_ms":    int(max(t1-t0,0)*1000),
            "llm_ms":       int(max(t2-t1,0)*1000),
            "html_ms":      int(max(t3-t2,0)*1000),
            "render_ms":    int(max(t4-t3,0)*1000),
            "total_ms":     int(max(t4-t0,0)*1000),
            "intent":       intent or "",
            "user_input":   user_input_str,
            "upstream":     upstream_str,
            "ui_image_url": ui_image_url or "",
            "render_mode":  render_mode,
            "error":        error,
        })
    except Exception: pass


# ---------------------------------------------------------------------------
# Node entrypoint
# ---------------------------------------------------------------------------

def _ui_node_impl(state: Any, render_mode: str, intent: str | None, it: str, user_input_str: str, upstream_str: str) -> Any:
    updates: Dict[str, Any] = {"ui_image_url": None}
    log_prefix = "ui_node_direct_html" if render_mode == "direct" else "ui_node"
    logger.info("[%s] start | model=%s | intent=%s", log_prefix, model_name, intent)

    t0 = time.perf_counter()
    handled = _run_template_path(
        state=state,
        updates=updates,
        intent=intent,
        user_input_str=user_input_str,
        upstream_str=upstream_str,
        render_mode=render_mode,
        t0=t0,
        log_prefix=log_prefix,
    )
    if handled is not None:
        return handled

    error_reason = ""
    usage_info = None

    if render_mode == "direct":
        try:
            prompt = build_prompt_direct_html(state)
        except Exception as exc:
            logger.exception("[ui_node_direct_html] build_prompt_direct_html failed")
            error_reason = f"build_prompt_direct_html: {exc}"
            prompt = ""
        t1 = time.perf_counter()

        html_info = _call_llm_for_html(prompt, model=model_name)
        t2 = time.perf_counter()
        if html_info is None:
            usage_info = None
            if not error_reason:
                error_reason = get_last_llm_error() or "llm_html_failed"
            t3 = t4 = t2
            _record_metrics(
                usage_info=usage_info,
                t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
                intent=intent,
                user_input_str=user_input_str,
                upstream_str=upstream_str,
                updates=updates,
                render_mode="direct",
                error_reason=error_reason,
            )
            return _finalize_state(state, updates)
        else:
            html, usage_info = html_info
        t3 = t2
        error_reason, t4 = _render_to_image(html=html, updates=updates, error_reason=error_reason, log_prefix=log_prefix)
        _record_metrics(
            usage_info=usage_info,
            t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
            intent=intent,
            user_input_str=user_input_str,
            upstream_str=upstream_str,
            updates=updates,
            render_mode="direct",
            error_reason=error_reason,
        )
        return _finalize_state(state, updates)

    try:
        prompt = build_prompt(state)
        logger.debug("[ui_node] prompt length=%d", len(prompt))
    except Exception as exc:
        logger.exception("[ui_node] build_prompt failed")
        error_reason = f"build_prompt: {exc}"
        prompt = ""
    t1 = time.perf_counter()

    plan_info = _call_llm_for_plan(prompt, model=model_name)
    t2 = time.perf_counter()
    if plan_info is None:
        usage_info = None
        if not error_reason:
            error_reason = get_last_llm_error() or "llm_plan_failed"
        t3 = t4 = t2
        _record_metrics(
            usage_info=usage_info,
            t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
            intent=intent,
            user_input_str=user_input_str,
            upstream_str=upstream_str,
            updates=updates,
            render_mode="planner",
            error_reason=error_reason,
        )
        return _finalize_state(state, updates)
    else:
        raw_plan, usage_info = plan_info if isinstance(plan_info, tuple) else (plan_info, None)

    plan = validate_plan(raw_plan, intent_default=intent or "fallback")
    logger.info("[ui_node] plan | mode=%s | sections=%d", plan.mode, len(plan.sections))

    html = None
    try:
        html = build_html(plan)
        logger.debug("[ui_node] HTML length=%d", len(html))
    except Exception as exc:
        logger.exception("[ui_node] build_html failed")
        if not error_reason:
            error_reason = f"build_html: {exc}"
    t3 = time.perf_counter()
    if not html:
        t4 = t3
        _record_metrics(
            usage_info=usage_info,
            t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
            intent=intent,
            user_input_str=user_input_str,
            upstream_str=upstream_str,
            updates=updates,
            render_mode="planner",
            error_reason=error_reason or "build_html_failed",
        )
        return _finalize_state(state, updates)

    error_reason, t4 = _render_to_image(html=html, updates=updates, error_reason=error_reason, log_prefix=log_prefix)
    _record_metrics(
        usage_info=usage_info,
        t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
        intent=intent,
        user_input_str=user_input_str,
        upstream_str=upstream_str,
        updates=updates,
        render_mode="planner",
        error_reason=error_reason,
    )
    if usage_info:
        logger.info(
            "[ui_node] usage | model=%s | prompt=%s | completion=%s | cost=%s",
            usage_info.get("model"), usage_info.get("prompt_tokens"),
            usage_info.get("completion_tokens"), usage_info.get("cost_usd"),
        )
    logger.info(
        "[ui_node] runtime | prompt=%dms | llm=%dms | html=%dms | render=%dms | total=%dms",
        int((t1-t0)*1000), int((t2-t1)*1000), int((t3-t2)*1000),
        int((t4-t3)*1000), int((t4-t0)*1000),
    )
    return _finalize_state(state, updates)


def ui_node(state: Any) -> Any:
    render_mode = _get_render_mode(state)
    intent, it, user_input_str, upstream_str = _extract_ui_ctx(state)
    if it == "exit":
        return _skip_ui_node(state=state, intent=intent, user_input_str=user_input_str, upstream_str=upstream_str, render_mode=render_mode, reason="exit")
    if it not in ("guardrails", "tutorial") and _is_empty_upstream(state):
        return _skip_ui_node(state=state, intent=intent, user_input_str=user_input_str, upstream_str=upstream_str, render_mode=render_mode, reason="empty_upstream")
    warmup_renderer()
    return _ui_node_impl(state, render_mode, intent, it, user_input_str, upstream_str)


# ---------------------------------------------------------------------------
# Direct-HTML path
# ---------------------------------------------------------------------------

def ui_node_direct_html(state: Any) -> Any:
    intent, it, user_input_str, upstream_str = _extract_ui_ctx(state)
    if it == "exit":
        return _skip_ui_node(state=state, intent=intent, user_input_str=user_input_str, upstream_str=upstream_str, render_mode="direct", reason="exit")
    if it not in ("guardrails", "tutorial") and _is_empty_upstream(state):
        return _skip_ui_node(state=state, intent=intent, user_input_str=user_input_str, upstream_str=upstream_str, render_mode="direct", reason="empty_upstream")
    warmup_renderer()
    return _ui_node_impl(state, "direct", intent, it, user_input_str, upstream_str)
