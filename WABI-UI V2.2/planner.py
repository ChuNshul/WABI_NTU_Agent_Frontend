"""
planner.py — UI plan generator for Wabi assistant.

Changes vs original
───────────────────
- Removed _load_components() / @lru_cache / disk I/O entirely.
  Component registry now lives in components.py (import-time constant).

- build_prompt() no longer receives a `components` argument — the catalog
  is pulled inside build_prompt() from components.py directly.

- _extract_usage() extracted as a helper to avoid duplicate code between
  _call_llm_for_plan() and _call_llm_for_html().

- All other logic (fallback_plan, _parse_json, error propagation) unchanged.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from .prompter import _get, _serialize_agent_response

# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------
_last_llm_error: str = ""


def _set_last_llm_error(msg: str) -> None:
    global _last_llm_error
    _last_llm_error = str(msg or "").strip()


def get_last_llm_error() -> str:
    return _last_llm_error


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def _extract_usage(usage: Any, cost: Any, model: Any) -> Optional[Dict[str, Any]]:
    if usage is None:
        return None
    try:
        return {
            "prompt_tokens":     int(getattr(usage, "prompt_tokens",     0)),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0)),
            "total_tokens":      int(getattr(usage, "total_tokens",      0)),
            "cost_usd":          float(cost) if cost is not None else None,
            "model":             model,
        }
    except Exception:
        return None


def _call_llm_for_plan(prompt: str, model: Optional[str] = None):
    try:
        from llm_gateway import GatewayClient
    except Exception as exc:
        _set_last_llm_error(f"[planner] Cannot import GatewayClient: {exc}")
        return None

    try:
        with GatewayClient.from_env() as client:
            if model is None:
                models = client.models.list()
                model  = models[0] if models else None
            response = client.chat.complete(prompt=prompt, model=model, max_tokens=1000)
            raw_text: str = response.text or ""
            usage_info = _extract_usage(
                getattr(response, "usage", None),
                getattr(response, "cost_usd", None),
                getattr(response, "model", None),
            )
    except Exception as exc:
        _set_last_llm_error(f"[planner] Gateway chat.complete failed: {exc}")
        return None

    if not raw_text:
        _set_last_llm_error("[planner] Gateway returned empty response")
        return None

    logger.debug("[planner] raw response (%.200s…)", raw_text)
    plan = _parse_json(raw_text)
    if plan is None:
        if not get_last_llm_error():
            _set_last_llm_error("[planner] Failed to parse plan JSON")
        return None

    return (plan, usage_info)


def _call_llm_for_html(prompt: str, model: Optional[str] = None):
    try:
        from llm_gateway import GatewayClient
    except Exception as exc:
        _set_last_llm_error(f"[planner] Cannot import GatewayClient: {exc}")
        return None

    try:
        with GatewayClient.from_env() as client:
            if model is None:
                models = client.models.list()
                model  = models[0] if models else None
            response = client.chat.complete(prompt=prompt, model=model, max_tokens=1500)
            raw_text: str = response.text or ""
            usage_info = _extract_usage(
                getattr(response, "usage", None),
                getattr(response, "cost_usd", None),
                getattr(response, "model", None),
            )
    except Exception as exc:
        _set_last_llm_error(f"[planner] Gateway chat.complete failed: {exc}")
        return None

    if not raw_text:
        _set_last_llm_error("[planner] Gateway returned empty response")
        return None

    return (raw_text, usage_info)


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        _set_last_llm_error("[planner] No JSON object in LLM output")
        return None
    json_str = match.group(0)
    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError:
        try:
            plan = json.loads(json_str, strict=False)
        except Exception as exc:
            _set_last_llm_error(f"[planner] JSON parse failed: {exc}")
            logger.error("[planner] JSON parse failed | raw: %.300s", json_str)
            return None
    return plan if isinstance(plan, dict) else None


# ---------------------------------------------------------------------------
# Fallback plan (when LLM call fails)
# ---------------------------------------------------------------------------

def fallback_plan(state: Any) -> Dict[str, Any]:
    raw   = _get(state, "upstream_response") or _get(state, "agent_response")
    text  = raw if isinstance(raw, str) else _serialize_agent_response(raw)
    error = _get(state, "error")

    sections: List[Dict] = []
    if text and text != "null":
        sections.append({"type": "text", "content": text, "tone": "neutral"})
    if error:
        sections.append({"type": "highlight_box", "content": f"Error: {error}", "variant": "error"})
    if not sections:
        sections.append({"type": "text", "content": "Wabi Assistant is ready.", "tone": "neutral"})

    return {
        "mode":     "fallback",
        "summary":  text[:100] if (text and text != "null") else "Wabi Assistant",
        "sections": sections,
    }