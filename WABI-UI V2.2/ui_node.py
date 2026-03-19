"""
ui_node.py — LangGraph node that orchestrates UI rendering.

Pipeline:
  state → build_prompt() → LLM → JSON dict → Plan.from_dict() → build_html(Plan) → PNG

Changes vs original:
  - Removed _load_components() import and call (zero disk I/O at runtime)
  - build_prompt() no longer takes a `components` argument
  - validate_plan() now returns a typed Plan; build_html() accepts it directly
  - Fallback HTML uses dark theme to match the redesigned builder
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

from .planner  import _call_llm_for_plan, fallback_plan, _call_llm_for_html, get_last_llm_error
from .prompter import build_prompt, _serialize_agent_response, build_prompt_direct_html
from .checker  import validate_plan
from .builder  import build_html
from .renderer import render_to_image_sync, warmup_renderer

logger = logging.getLogger(__name__)

model_name = "google/gemini-3.1-flash-lite-preview"

# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def _get(state: Any, key: str, default=None) -> Any:
    if isinstance(state, dict): return state.get(key, default)
    return getattr(state, key, default)

def _set(state: Any, key: str, value: Any) -> None:
    if isinstance(state, dict):
        state[key] = value; return
    try:   object.__setattr__(state, key, value)
    except Exception: setattr(state, key, value)

def _apply(state: Any, updates: Dict[str, Any]) -> None:
    for k, v in updates.items(): _set(state, k, v)

def _get_render_mode(state: Any) -> str:
    env = os.environ.get("WABI_UI_RENDER_MODE")
    if env:
        env = env.strip().lower()
        return "direct" if env.startswith("direct") else "planner"
    val = _get(state, "render_mode", "planner")
    return str(val).strip().lower() if val else "planner"

def _user_input_str(state: Any) -> str:
    raw = _get(state, "user_input")
    if isinstance(raw, list): return str((raw or [{}])[0].get("text") or "")
    return str(raw or "")

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

def ui_node(state: Any) -> Any:
    warmup_renderer()
    if _get_render_mode(state) == "direct":
        return ui_node_direct_html(state)

    updates: Dict[str, Any] = {"ui_image_url": None}
    intent = (
        "guardrail" if _get(state, "safety_passed") is False
        else (_get(state, "intent") or "fallback")
    )
    logger.info("[ui_node] start | model=%s | intent=%s", model_name, intent)

    t0 = time.perf_counter()

    # 1. Build prompt  (no components argument — loaded inside build_prompt)
    error_reason = ""
    try:
        prompt = build_prompt(state)
        logger.debug("[ui_node] prompt length=%d", len(prompt))
    except Exception as exc:
        logger.exception("[ui_node] build_prompt failed")
        error_reason = f"build_prompt: {exc}"; prompt = ""
    t1 = time.perf_counter()

    # 2. LLM → raw dict
    plan_info = _call_llm_for_plan(prompt, model=model_name)
    if plan_info is None:
        logger.warning("[ui_node] LLM failed; using fallback")
        raw_plan   = fallback_plan(state)
        usage_info = None
        if not error_reason: error_reason = get_last_llm_error() or "llm_plan_failed"
    else:
        raw_plan, usage_info = plan_info if isinstance(plan_info, tuple) else (plan_info, None)

    # 3. Raw dict → typed Plan  (alias expansion + validation)
    plan = validate_plan(raw_plan, intent_default=intent or "fallback")
    t2 = time.perf_counter()
    logger.info("[ui_node] plan | mode=%s | sections=%d", plan.mode, len(plan.sections))

    # 4. Plan → HTML
    html = None
    try:
        html = build_html(plan)
        logger.debug("[ui_node] HTML length=%d", len(html))
    except Exception as exc:
        logger.exception("[ui_node] build_html failed")
        if not error_reason: error_reason = f"build_html: {exc}"
    t3 = time.perf_counter()

    # 5. HTML → PNG
    try:
        if html:
            img_url = render_to_image_sync(html)
            updates["ui_image_url"] = img_url
        else:
            if not error_reason: error_reason = "no_html"
    except Exception as exc:
        logger.exception("[ui_node] render_to_image failed")
        if not error_reason: error_reason = f"render_to_image: {exc}"
    t4 = time.perf_counter()

    upstream_str = _serialize_agent_response(_get(state, "agent_response"))
    _enqueue_metrics(
        usage_info=usage_info if isinstance(usage_info, dict) else None,
        t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
        intent=intent or "",
        user_input_str=_user_input_str(state),
        upstream_str=upstream_str,
        ui_image_url=updates.get("ui_image_url"),
        render_mode=_get_render_mode(state),
        error="" if updates.get("ui_image_url") else (error_reason or "no_image"),
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

    _apply(state, updates)
    try: state.ui_image_url = updates.get("ui_image_url")
    except Exception: pass
    return state


# ---------------------------------------------------------------------------
# Direct-HTML path
# ---------------------------------------------------------------------------

_FALLBACK_HTML_TMPL = """\
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{{background:#0d1117;color:#e6edf3;font:13.5px/1.65 system-ui,sans-serif;
  padding:18px;width:468px}}
.card{{background:#161b22;border:1px solid rgba(240,246,252,.1);
  border-radius:14px;padding:18px;margin-bottom:10px}}
h3{{color:#d2a8ff;margin-bottom:8px;font-size:15px}}
pre{{white-space:pre-wrap;font-size:12.5px;color:#8b949e}}
</style></head><body>
<div class="card"><h3>{intent}</h3><pre>{text}</pre></div>
</body></html>"""


def ui_node_direct_html(state: Any) -> Any:
    warmup_renderer()
    updates: Dict[str, Any] = {"ui_image_url": None}
    intent = (
        "guardrail" if _get(state, "safety_passed") is False
        else (_get(state, "intent") or "fallback")
    )
    logger.info("[ui_node_direct_html] start | model=%s | intent=%s", model_name, intent)

    t0 = time.perf_counter()
    error_reason = ""
    try:
        prompt = build_prompt_direct_html(state)
    except Exception as exc:
        logger.exception("[ui_node_direct_html] build_prompt_direct_html failed")
        error_reason = f"build_prompt_direct_html: {exc}"; prompt = ""
    t1 = time.perf_counter()

    html_info = _call_llm_for_html(prompt, model=model_name)
    if html_info is None:
        logger.warning("[ui_node_direct_html] LLM empty; using fallback")
        text = _serialize_agent_response(_get(state, "agent_response"))
        html = _FALLBACK_HTML_TMPL.format(intent=intent, text=text)
        usage_info = None
        if not error_reason: error_reason = get_last_llm_error() or "llm_html_failed"
    else:
        html, usage_info = html_info
    t2 = t3 = time.perf_counter()

    try:
        img_url = render_to_image_sync(html)
        updates["ui_image_url"] = img_url
    except Exception as exc:
        logger.exception("[ui_node_direct_html] render_to_image failed")
        if not error_reason: error_reason = f"render_to_image: {exc}"
    t4 = time.perf_counter()

    upstream_str = _serialize_agent_response(_get(state, "agent_response"))
    _enqueue_metrics(
        usage_info=usage_info if isinstance(usage_info, dict) else None,
        t0=t0, t1=t1, t2=t2, t3=t3, t4=t4,
        intent=intent or "",
        user_input_str=_user_input_str(state),
        upstream_str=upstream_str,
        ui_image_url=updates.get("ui_image_url"),
        render_mode="direct",
        error="" if updates.get("ui_image_url") else (error_reason or "no_image"),
    )

    _apply(state, updates)
    try: state.ui_image_url = updates.get("ui_image_url")
    except Exception: pass
    return state
