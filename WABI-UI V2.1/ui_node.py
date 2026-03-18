"""
ui_node.py — LangGraph node that orchestrates UI rendering.

Pipeline:
  state → planner (LLM) → checker → builder (HTML) → renderer (PNG) → state
"""
from __future__ import annotations

import logging
from typing import Any, Dict
import time

from .planner  import _load_components, _call_llm_for_plan, fallback_plan, _call_llm_for_html, get_last_llm_error
from .prompter import build_prompt, _serialize_agent_response, build_prompt_direct_html
from .checker  import validate_plan
from .builder  import build_html
from .renderer import render_to_image_sync, warmup_renderer
import csv, os, datetime, threading, zlib, base64, queue

logger = logging.getLogger(__name__)

model_name = "google/gemini-3.1-flash-lite-preview"
# ['google/gemma-3-12b-it:free', 'google/gemma-3-27b-it:free', 'google/gemma-3-4b-it:free', 'google/gemini-2.5-flash-lite', 'google/gemini-2.5-flash', 'google/gemini-3.1-flash-lite-preview', 'meta-llama/llama-3.2-3b-instruct:free', 'meta-llama/llama-3.3-70b-instruct:free', 'nvidia/nemotron-3-nano-30b-a3b:free', 'deepseek/deepseek-chat-v3.1', 'openai/gpt-4o-mini', 'qwen/qwen3-30b-a3b', 'qwen/qwen3-4b:free', 'qwen/qwen3-next-80b-a3b-instruct:free']

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

def _get_render_mode(state: Any) -> str:
    env = os.environ.get("WABI_UI_RENDER_MODE")
    if env:
        env = env.strip().lower()
        if env.startswith("direct"):
            return "direct"
        return "planner"
    val = _get(state, "render_mode", "planner")
    return str(val).strip().lower() if val else "planner"

def _ensure_csv_header(path: str, header: list) -> None:
    if not os.path.exists(path):
        with open(path, "w", newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(header)

_CSV_LOCK = threading.Lock()
_CSV_PATH = os.path.join(os.path.dirname(__file__), "ui_node_metrics.csv")
_CSV_HEADER = [
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
    "total_ms",
    "intent",
    "user_input",
    "upstream",
    "ui_image_compressed",
    "render_mode",
    "error",
]
_METRICS_Q: "queue.Queue[dict]" = queue.Queue(maxsize=256)
_METRICS_THREAD: threading.Thread | None = None


def _start_metrics_writer() -> None:
    global _METRICS_THREAD
    if _METRICS_THREAD is not None and _METRICS_THREAD.is_alive():
        return

    def worker() -> None:
        while True:
            item = _METRICS_Q.get()
            if item is None:
                return
            try:
                with _CSV_LOCK:
                    _ensure_csv_header(_CSV_PATH, _CSV_HEADER)

                img_url = item.get("ui_image_url") or ""
                try:
                    ui_image_compressed = (
                        base64.b64encode(zlib.compress(img_url.encode("utf-8"))).decode("ascii")
                        if img_url
                        else ""
                    )
                except Exception:
                    ui_image_compressed = ""

                usage_info = item.get("usage_info")
                row = [
                    item.get("timestamp") or "",
                    (usage_info.get("model") if usage_info else "") if isinstance(usage_info, dict) else "",
                    (usage_info.get("prompt_tokens") if usage_info else "") if isinstance(usage_info, dict) else "",
                    (usage_info.get("completion_tokens") if usage_info else "") if isinstance(usage_info, dict) else "",
                    (usage_info.get("total_tokens") if usage_info else "") if isinstance(usage_info, dict) else "",
                    (usage_info.get("cost_usd") if usage_info else "") if isinstance(usage_info, dict) else "",
                    item.get("prompt_ms") or 0,
                    item.get("llm_ms") or 0,
                    item.get("html_ms") or 0,
                    item.get("render_ms") or 0,
                    item.get("total_ms") or 0,
                    item.get("intent") or "",
                    item.get("user_input") or "",
                    item.get("upstream") or "",
                    ui_image_compressed,
                    item.get("render_mode") or "",
                    item.get("error") or "",
                ]
                with _CSV_LOCK:
                    with open(_CSV_PATH, "a", newline="", encoding="utf-8") as f:
                        csv.writer(f).writerow(row)
                        f.flush()
            except Exception:
                pass

    _METRICS_THREAD = threading.Thread(target=worker, name="ui_node_metrics_writer", daemon=True)
    _METRICS_THREAD.start()


def _enqueue_metrics(
    *,
    usage_info: dict | None,
    t0: float,
    t1: float,
    t2: float,
    t3: float,
    t4: float,
    intent: str,
    user_input_str: str,
    upstream_str: str,
    ui_image_url: str | None,
    render_mode: str,
    error: str,
) -> None:
    _start_metrics_writer()
    item = {
        "timestamp": datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "usage_info": usage_info if isinstance(usage_info, dict) else None,
        "prompt_ms": int(max((t1 - t0), 0) * 1000),
        "llm_ms": int(max((t2 - t1), 0) * 1000),
        "html_ms": int(max((t3 - t2), 0) * 1000),
        "render_ms": int(max((t4 - t3), 0) * 1000),
        "total_ms": int(max((t4 - t0), 0) * 1000),
        "intent": intent or "",
        "user_input": user_input_str,
        "upstream": upstream_str,
        "ui_image_url": ui_image_url or "",
        "render_mode": render_mode,
        "error": error,
    }
    try:
        _METRICS_Q.put_nowait(item)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Node entrypoint
# ---------------------------------------------------------------------------

def ui_node(state: Any) -> Any:
    """
    Render the current agent state as a mobile UI card image.

    This node modifies the state in-place by setting `ui_image_url`
    and returns the entire state object.
    """
    warmup_renderer()
    # Route to direct-HTML mode if requested
    if _get_render_mode(state) == "direct":
        return ui_node_direct_html(state)

    updates: Dict[str, Any] = {"ui_image_url": None}

    intent     = (
        "guardrail"
        if _get(state, "safety_passed") is False
        else (_get(state, "intent") or "fallback")
    )
    logger.info(
        "[ui_node] start | model=%s | intent=%s",
        model_name, intent
    )

    t0 = time.perf_counter()
    # ── 1. Load component schema ──────────────────────────────────────────
    components = _load_components()
    if not components:
        logger.warning("[ui_node] ui_components.json is empty; continuing with empty schema")

    # ── 2. Build LLM prompt ───────────────────────────────────────
    error_reason = ""
    try:
        prompt = build_prompt(state, components)
        logger.debug("[ui_node] prompt length=%d chars", len(prompt))
    except Exception as exc:
        logger.exception("[ui_node] build_prompt failed")
        error_reason = f"build_prompt: {exc}"
        prompt = ""
    t1 = time.perf_counter()

    # ── 3. Generate UI plan via LLM ───────────────────────────────────────
    plan_info = _call_llm_for_plan(prompt, model=model_name)
    if plan_info is None:
        logger.warning("[ui_node] LLM plan failed; using fallback")
        plan = fallback_plan(state)
        usage_info = None
        if not error_reason:
            error_reason = get_last_llm_error() or "llm_plan_failed"
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
    html = None
    try:
        html = build_html(plan)
        logger.debug("[ui_node] HTML length=%d chars", len(html))
    except Exception as exc:
        logger.exception("[ui_node] build_html failed")
        if not error_reason:
            error_reason = f"build_html: {exc}"
    t3 = time.perf_counter()

    # ── 5. Screenshot HTML → PNG data-URI ─────────────────────────────────
    try:
        if html:
            img_url = render_to_image_sync(html)
            updates["ui_image_url"]   = img_url
            logger.info("[ui_node] screenshot complete | url=%.64s%s",
                        img_url, "..." if len(img_url) > 64 else "")
        else:
            if not error_reason:
                error_reason = "no_html"
    except Exception as exc:
        logger.exception("[ui_node] render_to_image failed")
        if not error_reason:
            error_reason = f"render_to_image: {exc}"
    t4 = time.perf_counter()

    user_input_raw = _get(state, "user_input")
    if isinstance(user_input_raw, list):
        user_input_val = (user_input_raw or [{}])[0].get("text")
    else:
        user_input_val = user_input_raw
    user_input_str = str(user_input_val or "")

    upstream_str = _serialize_agent_response(_get(state, "agent_response"))
    _enqueue_metrics(
        usage_info=usage_info if isinstance(usage_info, dict) else None,
        t0=t0,
        t1=t1,
        t2=t2,
        t3=t3,
        t4=t4,
        intent=intent or "",
        user_input_str=user_input_str,
        upstream_str=upstream_str,
        ui_image_url=updates.get("ui_image_url"),
        render_mode=_get_render_mode(state),
        error="" if updates.get("ui_image_url") else (error_reason or "no_image"),
    )
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
    _set(state, "ui_image_url", updates["ui_image_url"])
    return state

# ---------------------------------------------------------------------------
# Alternative path: direct-HTML via LLM
# ---------------------------------------------------------------------------
def ui_node_direct_html(state: Any) -> Any:
    """
    Alternative renderer: directly ask LLM to produce the complete HTML,
    then screenshot and log with the SAME CSV schema.
    """
    warmup_renderer()
    updates: Dict[str, Any] = {"ui_image_url": None}
    intent = (
        "guardrail"
        if _get(state, "safety_passed") is False
        else (_get(state, "intent") or "fallback")
    )
    logger.info("[ui_node_direct_html] start | model=%s | intent=%s", model_name, intent)

    t0 = time.perf_counter()
    error_reason = ""
    try:
        prompt = build_prompt_direct_html(state)
        logger.debug("[ui_node_direct_html] prompt length=%d chars", len(prompt))
    except Exception as exc:
        logger.exception("[ui_node_direct_html] build_prompt_direct_html failed")
        error_reason = f"build_prompt_direct_html: {exc}"
        # continue with minimal HTML to allow CSV logging
        prompt = ""
    t1 = time.perf_counter()

    html_info = _call_llm_for_html(prompt, model=model_name)
    if html_info is None:
        logger.warning("[ui_node_direct_html] LLM returned empty; fallback to plain HTML")
        text = _serialize_agent_response(_get(state, "agent_response"))
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{{background:#0b1221;color:#cbd5f5;font:14px/1.5 system-ui,Segoe UI,Roboto;}}.card{{width:420px;margin:8px auto;padding:16px;border:1px solid #1f2a44;border-radius:8px;background:#0f172a;}}</style></head><body><div class='card'><h3>{intent}</h3><pre style='white-space:pre-wrap'>{text}</pre></div></body></html>"
        usage_info = None
        if not error_reason:
            error_reason = get_last_llm_error() or "llm_html_failed"
    else:
        html, usage_info = html_info
    t2 = time.perf_counter()
    t3 = t2  # no builder stage

    try:
        img_url = render_to_image_sync(html)
        updates["ui_image_url"] = img_url
    except Exception as exc:
        logger.exception("[ui_node_direct_html] render_to_image failed")
        if not error_reason:
            error_reason = f"render_to_image: {exc}"
    t4 = time.perf_counter()

    user_input_raw = _get(state, "user_input")
    if isinstance(user_input_raw, list):
        user_input_val = (user_input_raw or [{}])[0].get("text")
    else:
        user_input_val = user_input_raw
    user_input_str = str(user_input_val or "")
    upstream_str = _serialize_agent_response(_get(state, "agent_response"))
    _enqueue_metrics(
        usage_info=usage_info if isinstance(usage_info, dict) else None,
        t0=t0,
        t1=t1,
        t2=t2,
        t3=t3,
        t4=t4,
        intent=intent or "",
        user_input_str=user_input_str,
        upstream_str=upstream_str,
        ui_image_url=updates.get("ui_image_url"),
        render_mode="direct",
        error="" if updates.get("ui_image_url") else (error_reason or "no_image"),
    )

    _apply(state, updates)
    _set(state, "ui_image_url", updates["ui_image_url"])
    return state
