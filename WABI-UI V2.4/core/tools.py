from __future__ import annotations

import json
import os
from typing import Any, Dict


def get(state: Any, key: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def set_(state: Any, key: str, value: Any) -> None:
    if isinstance(state, dict):
        state[key] = value
        return
    try:
        object.__setattr__(state, key, value)
    except Exception:
        setattr(state, key, value)


def apply_updates(state: Any, updates: Dict[str, Any]) -> None:
    for k, v in updates.items():
        set_(state, k, v)


def get_render_mode(state: Any) -> str:
    env = os.environ.get("WABI_UI_RENDER_MODE")
    if env:
        env = env.strip().lower()
        return "direct" if env.startswith("direct") else "planner"
    val = get(state, "render_mode", "planner")
    return str(val).strip().lower() if val else "planner"


def user_input_text(state: Any, default: str = "") -> str:
    raw = get(state, "user_input")
    if isinstance(raw, list):
        return str((raw or [{}])[0].get("text") or default)
    return str(raw or default)


def serialize_agent_response(raw: Any) -> str:
    if raw is None:
        return "null"
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return "null"
        try:
            return json.dumps(json.loads(stripped), ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return stripped
    try:
        return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(raw)


def is_empty_upstream(state: Any) -> bool:
    raw = get(state, "agent_response")
    if raw is None:
        return True
    if isinstance(raw, str):
        return not raw.strip()
    if isinstance(raw, (list, dict, tuple, set)):
        return len(raw) == 0
    try:
        s = str(raw).strip()
        return not s or s.lower() == "null"
    except Exception:
        return True


def should_use_template(intent: str) -> str | None:
    it = (intent or "").strip().lower()
    if it in ("guardrails", "tutorial"):
        return it
    return None


def extract_ui_ctx(state: Any, *, user_input_default: str = "") -> tuple[str | None, str, str, str]:
    intent = "guardrails" if get(state, "safety_passed") is False else get(state, "intent")
    user_input_str = user_input_text(state, default=user_input_default)
    upstream_str = serialize_agent_response(get(state, "agent_response"))
    it = (intent or "").strip().lower()
    return intent, it, user_input_str, upstream_str


def finalize_state(state: Any, updates: Dict[str, Any]) -> Any:
    apply_updates(state, updates)
    try:
        state.ui_image_url = updates.get("ui_image_url")
    except Exception:
        pass
    return state
