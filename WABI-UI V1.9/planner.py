"""
planner.py — UI plan generator for Wabi assistant.

Responsibilities:
  1. Serialize raw agent state into a prompt context.
  2. Call the LLM (via tools.llm_factory) to produce a structured UI plan.
  3. Provide a deterministic fallback plan when the LLM fails.

Design philosophy:
  - The LLM is responsible for reading upstream_response, understanding its
    structure, extracting relevant data, and choosing how to visualise it.
  - This file does NOT pre-parse, pre-compute, or impose layout rules.
  - The prompt gives the LLM full visibility of the raw state and the component
    catalog, then lets it decide what to render and how.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COMPONENTS_PATH = os.path.join(os.path.dirname(__file__), "ui_components.json")

# Import prompt-related helpers from prompter
from .prompter import _get, _serialize_agent_response

# ---------------------------------------------------------------------------
# Component schema loader
# ---------------------------------------------------------------------------

def _load_components() -> Dict[str, Any]:
    try:
        with open(_COMPONENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("[planner] Failed to load ui_components.json: %s", exc)
        return {}

# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm_for_plan(prompt: str, model: Optional[str] = None):
    try:
        from llm_gateway import GatewayClient
    except Exception as exc:
        logger.error("[planner] Cannot import GatewayClient: %s", exc)
        return None

    try:
        with GatewayClient.from_env() as client:
            # 如果未指定模型，则列出可用模型并取第一个
            if model is None:
                models = client.models.list()
                model = models[0] if models else None
            response = client.chat.complete(
                prompt=prompt,
                model=model,
                max_tokens=1000,
            )
            raw_text: str = response.text or ""
            usage = getattr(response, "usage", None)
            cost = getattr(response, "cost_usd", None)
            model = getattr(response, "model", None)
    except Exception as exc:
        logger.error("[planner] Gateway chat.complete failed: %s", exc)
        return None

    if not raw_text:
        logger.error("[planner] Gateway returned empty response")
        return None

    logger.debug("[planner] Gateway raw response (%.200s…)", raw_text)
    plan = _parse_json(raw_text)
    if plan is None:
        return None
    usage_info = None
    if usage is not None:
        try:
            usage_info = {
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0)),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0)),
                "total_tokens": int(getattr(usage, "total_tokens", 0)),
                "cost_usd": float(cost) if cost is not None else None,
                "model": model,
            }
        except Exception:
            usage_info = None
    return (plan, usage_info)


def _parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        logger.error("[planner] No JSON object in LLM output")
        return None
    json_str = match.group(0)
    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError:
        try:
            plan = json.loads(json_str, strict=False)
        except Exception as exc:
            logger.error("[planner] JSON parse failed: %s | raw: %.300s", exc, json_str)
            return None
    return plan if isinstance(plan, dict) else None


# ---------------------------------------------------------------------------
# Fallback plan
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
        "summary":  (text[:100] if text and text != "null" else "Wabi Assistant"),
        "sections": sections,
    }
