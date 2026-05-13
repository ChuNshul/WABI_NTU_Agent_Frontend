from __future__ import annotations

import base64
import datetime
import json
import os
import uuid
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
    def normalize_mode(v: Any) -> str:
        s = str(v or "").strip().lower()
        if not s:
            return "plan"
        if s in ("plan", "html", "image"):
            return s
        return s

    env = os.environ.get("UI_RENDER_MODE")
    if env:
        return normalize_mode(env)
    val = get(state, "render_mode", "plan")
    return normalize_mode(val)


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


_OUTPUT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "output"))

def _slug(s: str, *, max_len: int = 48) -> str:
    s = (s or "").strip().lower()
    if not s:
        return "na"
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in ("-", "_"):
            out.append(ch)
        else:
            out.append("_")
    slug = "".join(out).strip("_")
    if not slug:
        slug = "na"
    return slug[:max_len]

def _decode_data_url_png(data_url: str) -> bytes | None:
    s = (data_url or "").strip()
    if not s.startswith("data:image/"):
        return None
    comma = s.find(",")
    if comma < 0:
        return None
    header = s[:comma].lower()
    payload = s[comma + 1 :].strip()
    if ";base64" not in header:
        return None
    try:
        return base64.b64decode(payload, validate=False)
    except Exception:
        return None

def save_render_artifacts(*, html: str | None, ui_image_url: str | None, intent: str | None, render_mode: str) -> None:
    try:
        os.makedirs(_OUTPUT_DIR, exist_ok=True)
    except Exception:
        return

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    name = f"{ts}_{_slug(render_mode)}_{_slug(intent or '')}_{uuid.uuid4().hex[:10]}"
    if isinstance(html, str) and html.strip():
        try:
            with open(os.path.join(_OUTPUT_DIR, f"{name}.html"), "w", encoding="utf-8", newline="\n") as f:
                f.write(html)
        except Exception:
            pass

    if isinstance(ui_image_url, str) and ui_image_url.strip():
        png = _decode_data_url_png(ui_image_url)
        if png is not None:
            try:
                with open(os.path.join(_OUTPUT_DIR, f"{name}.png"), "wb") as f:
                    f.write(png)
            except Exception:
                pass
        else:
            try:
                with open(os.path.join(_OUTPUT_DIR, f"{name}.image_url.txt"), "w", encoding="utf-8", newline="\n") as f:
                    f.write(ui_image_url.strip())
            except Exception:
                pass
