"""
planner.py — UI plan generator for UI Render assistant.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

try:
    from llm_gateway import GatewayClient
except ImportError:  # pragma: no cover
    GatewayClient = None

logger = logging.getLogger(__name__)

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


def _extract_image_data_url(raw_text: str) -> Optional[str]:
    s = str(raw_text or "").strip()
    if not s:
        return None
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    if s.startswith("data:image/"):
        return s
    idx = s.find("data:image/")
    if idx >= 0:
        cand = s[idx:].strip().strip('"').strip("'")
        return cand if cand.startswith("data:image/") else None
    if "{" in s and "}" in s:
        match = re.search(r"\{[\s\S]*\}", s)
        if match:
            try:
                obj = json.loads(match.group(0))
            except Exception:
                obj = None
            if isinstance(obj, dict):
                for k in ("data_url", "image_data_url", "image", "image_url", "url"):
                    v = obj.get(k)
                    if isinstance(v, str) and v.strip().startswith("data:image/"):
                        return v.strip()
    b64 = re.sub(r"\s+", "", s)
    if len(b64) >= 1024 and re.fullmatch(r"[A-Za-z0-9+/=]+", b64):
        return f"data:image/png;base64,{b64}"
    return None


def _call_llm_for_image(
    prompt: str,
    model: Optional[str] = None,
    *,
    response_image: Optional[Dict[str, Any]] = None,
):
    try:
        from llm_gateway import GatewayClient
    except Exception as exc:
        _set_last_llm_error(f"[planner] Cannot import GatewayClient: {exc}")
        return None

    try:
        with GatewayClient.from_env() as client:
            if model is None:
                models = client.models.list()
                model = models[0] if models else None
            response = client.chat.complete(
                prompt=prompt,
                model=model,
                max_tokens=512,
                response_image=response_image or {"include_text": False, "aspect_ratio": "9:16"},
            )
            usage_info = _extract_usage(
                getattr(response, "usage", None),
                getattr(response, "cost_usd", None),
                getattr(response, "model", None),
            )
    except Exception as exc:
        _set_last_llm_error(f"[planner] Gateway chat.complete failed: {exc}")
        return None

    images = getattr(response, "images", None)
    if images:
        try:
            url = getattr(images[0], "url", None)
        except Exception:
            url = None
        if isinstance(url, str) and url.strip():
            return (url.strip(), usage_info)

    raw_text: str = getattr(response, "text", "") or ""
    data_url = _extract_image_data_url(raw_text)
    if data_url:
        return (data_url, usage_info)

    if not raw_text:
        _set_last_llm_error("[planner] Gateway returned empty response")
        return None
    _set_last_llm_error("[planner] Failed to extract image data URL from model output")
    return None


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


