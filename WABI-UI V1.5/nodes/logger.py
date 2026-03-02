from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

_UI_LOGGER_NAME = "wabi.ui"
_UI_DEBUG_ENV = "UI_DEBUG"
_STATE_LOG_LIMIT = 500
_RUN_LOG_LIMIT = 500

_RUNS: Dict[str, Dict[str, Any]] = {}
_RUNS_LOCK = threading.Lock()


def _get_logger() -> logging.Logger:
    logger = logging.getLogger(_UI_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s][%(levelname)s][%(name)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger


def is_debug_enabled() -> bool:
    return os.getenv(_UI_DEBUG_ENV) == "1"


def set_debug_enabled(enable: bool) -> None:
    os.environ[_UI_DEBUG_ENV] = "1" if enable else "0"


def _normalize_level(level: str) -> str:
    lvl = (level or "").strip().lower()
    if lvl in {"warn", "warning"}:
        return "warning"
    if lvl in {"err"}:
        return "error"
    if lvl in {"critical", "fatal"}:
        return "critical"
    if lvl in {"debug", "info", "error"}:
        return lvl
    return "info"


def _should_console_log(normalized_level: str) -> bool:
    if normalized_level in {"error", "critical"}:
        return True
    return is_debug_enabled()


def _emit_console(normalized_level: str, message: str) -> None:
    logger = _get_logger()
    if normalized_level == "critical":
        logger.critical(message)
    elif normalized_level == "error":
        logger.error(message)
    elif normalized_level == "warning":
        logger.warning(message)
    elif normalized_level == "debug":
        logger.debug(message)
    else:
        logger.info(message)


def _truncate_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    keep = max(0, limit - 3)
    return text[:keep] + "..."


def preview_text(value: Any, head: int = 600, tail: int = 200) -> Dict[str, Any]:
    s = "" if value is None else str(value)
    head = max(0, int(head))
    tail = max(0, int(tail))
    if len(s) <= head + tail:
        return {"len": len(s), "text": s}
    return {"len": len(s), "head": _truncate_text(s, head), "tail": s[-tail:] if tail else ""}


def preview_json(value: Any, limit: int = 2000) -> Dict[str, Any]:
    try:
        s = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        s = str(value)
    return {"len": len(s), "text": _truncate_text(s, int(limit))}


def summarize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    keys = sorted([str(k) for k in (state or {}).keys()])
    ui_plan = state.get("ui_plan") if isinstance(state, dict) else None
    sections_count = None
    if isinstance(ui_plan, dict):
        sections = ui_plan.get("sections")
        if isinstance(sections, list):
            sections_count = len(sections)
    html = state.get("html_content") if isinstance(state, dict) else None
    return {
        "run_id": state.get("run_id"),
        "intent": state.get("intent"),
        "llm_model": state.get("llm_model"),
        "has_image": state.get("has_image"),
        "user_input_len": len(str(state.get("user_input", "") or "")),
        "ui_plan_mode": ui_plan.get("mode") if isinstance(ui_plan, dict) else None,
        "ui_plan_sections": sections_count,
        "html_len": len(str(html or "")) if html is not None else None,
        "keys": keys,
    }


def start_run(run_id: str) -> None:
    if not run_id:
        return
    now = time.time()
    with _RUNS_LOCK:
        _RUNS[run_id] = {"start_time": now, "status": "running", "logs": []}


def finish_run(run_id: str, status: str) -> None:
    if not run_id:
        return
    now = time.time()
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if not run:
            return
        run["status"] = status
        run["end_time"] = now


def get_run_snapshot(run_id: str, tail: int = 50) -> Dict[str, Any]:
    now = time.time()
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if not run:
            return {"status": "not_found"}
        start_time = float(run.get("start_time", now) or now)
        elapsed = max(0.0, now - start_time)
        logs = list(run.get("logs", []))
        if tail and len(logs) > tail:
            logs = logs[-tail:]
        status = run.get("status") or "running"
    return {"status": status, "elapsed_ms": int(elapsed * 1000), "logs": logs}


def _append_run_log(run_id: Optional[str], entry: Dict[str, Any]) -> None:
    if not run_id:
        return
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if not run:
            run = {"start_time": time.time(), "status": "running", "logs": []}
            _RUNS[run_id] = run
        logs = run.setdefault("logs", [])
        logs.append(entry)
        if len(logs) > _RUN_LOG_LIMIT:
            run["logs"] = logs[-_RUN_LOG_LIMIT:]


def _format_console(entry: Dict[str, Any]) -> str:
    parts = []
    run_id = entry.get("run_id")
    node = entry.get("node")
    event = entry.get("event")
    if run_id:
        parts.append(f"run_id={run_id}")
    if node:
        parts.append(f"node={node}")
    if event:
        parts.append(f"event={event}")
    prefix = f"[{' '.join(parts)}] " if parts else ""
    return prefix + str(entry.get("message", ""))


def log(
    level: str,
    message: str,
    *,
    run_id: Optional[str] = None,
    node: Optional[str] = None,
    event: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    normalized = _normalize_level(level)
    entry: Dict[str, Any] = {"t": time.time(), "level": normalized, "message": str(message)}
    if run_id:
        entry["run_id"] = run_id
    if node:
        entry["node"] = node
    if event:
        entry["event"] = event
    if data is not None:
        entry["data"] = data
    _append_run_log(run_id, entry)
    if _should_console_log(normalized):
        _emit_console(normalized, _format_console(entry))


def log_state(
    state: Dict[str, Any],
    level: str,
    message: str,
    *,
    node: Optional[str] = None,
    event: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    normalized = _normalize_level(level)
    run_id = state.get("run_id") if isinstance(state, dict) else None
    entry: Dict[str, Any] = {"t": time.time(), "level": normalized, "message": str(message)}
    if run_id:
        entry["run_id"] = run_id
    if node:
        entry["node"] = node
    if event:
        entry["event"] = event
    if data is not None:
        entry["data"] = data
    logs = state.get("logs") or []
    logs.append(entry)
    if len(logs) > _STATE_LOG_LIMIT:
        logs = logs[-_STATE_LOG_LIMIT:]
    state["logs"] = logs
    _append_run_log(run_id, entry)
    if _should_console_log(normalized):
        _emit_console(normalized, _format_console(entry))
