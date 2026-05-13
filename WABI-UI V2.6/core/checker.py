"""
checker.py — Visual self-check + repair for rendered UI.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

from ..render.renderer import render_to_image_sync

try:
    from llm_gateway import GatewayClient
except ImportError:  # pragma: no cover
    GatewayClient = None

logger = logging.getLogger(__name__)

_CHECK_ENABLED = str(os.getenv("WABI_UI_VISUAL_CHECK", "0")).strip().lower() not in ("0", "false", "no", "off")
_CHECK_MODEL = "google/gemini-3.1-flash-lite-preview"
_CHECK_MAX_TOKENS = int(os.getenv("WABI_UI_VISUAL_CHECK_MAX_TOKENS", "1200"))

def _emit(msg: str) -> None:
    s = f"[ui_render.checker] {msg}"
    try:
        logger.info(s)
    except Exception:
        pass


def _strip_fences(text: str) -> str:
    s = (text or "").strip()
    if not s.startswith("```"):
        return s
    s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()
    return s


def _extract_html(text: str) -> Optional[str]:
    s = _strip_fences(text)
    if not s:
        return None
    idx = s.lower().find("<!doctype html")
    if idx < 0:
        idx = s.lower().find("<html")
    if idx >= 0:
        s = s[idx:]
    if "<html" not in s.lower():
        return None
    return s.strip()


def _gateway_complete(*, prompt: str, model: str, max_tokens: int, image_url: str | None) -> Optional[str]:
    if GatewayClient is None:
        return None
    try:
        with GatewayClient.from_env() as client:
            if image_url:
                try:
                    resp = client.chat.complete(
                        prompt=prompt,
                        model=model,
                        max_tokens=max_tokens,
                        images=[{"url": image_url}],
                    )
                    return getattr(resp, "text", None) or ""
                except TypeError:
                    pass
                except Exception:
                    pass
                try:
                    resp = client.chat.complete(
                        prompt=prompt,
                        model=model,
                        max_tokens=max_tokens,
                        image_url=image_url,
                    )
                    return getattr(resp, "text", None) or ""
                except TypeError:
                    pass
                except Exception:
                    pass
            resp = client.chat.complete(prompt=prompt, model=model, max_tokens=max_tokens)
            return getattr(resp, "text", None) or ""
    except Exception as exc:
        logger.exception("[ui_render.checker] gateway_complete failed: %s", exc)
        return None


def visual_self_check_and_fix_html(
    *,
    html: str,
    ui_image_url: str | None,
    intent: str | None,
    user_input_str: str,
    upstream_str: str,
    model: str | None = None,
) -> str:
    if not _CHECK_ENABLED:
        return html
    it = (intent or "").strip().lower()
    if it in ("guardrails", "tutorial"):
        return html
    if not isinstance(html, str) or not html.strip():
        return html

    m = (model or _CHECK_MODEL).strip() or _CHECK_MODEL
    prompt = (
        "You are a UI rendering QA and repair model.\n"
        "You will receive:\n"
        "1) UPSTREAM: the source facts (JSON/text) that the UI must reflect.\n"
        "2) HTML: the current self-contained HTML document used for rendering.\n"
        "3) SCREENSHOT: an optional image input of the rendered result.\n\n"
        "Task:\n"
        "- Visually audit the UI (if screenshot is provided) for layout issues: clipped/overlapping text, overflow, unreadable font sizes, low contrast, poor spacing, excessive empty space, misalignment.\n"
        "- Audit faithfulness: do not introduce any facts/numbers not present in UPSTREAM.\n"
        "- Repair the HTML to fix issues while preserving content. You may: adjust typography, spacing, truncation, grid layout, and component ordering.\n\n"
        "Output:\n"
        "- Return ONE complete HTML document only (no markdown fences, no explanations).\n\n"
        f"INTENT: {intent}\n"
        f"USER_INPUT: {user_input_str}\n"
        f"UPSTREAM:\n{upstream_str}\n\n"
        f"HTML:\n{html}\n"
    )

    raw = _gateway_complete(prompt=prompt, model=m, max_tokens=_CHECK_MAX_TOKENS, image_url=ui_image_url)
    fixed = _extract_html(raw or "")
    if fixed is None:
        return html
    return fixed


def render_html_with_visual_self_check(
    *,
    html: str,
    intent: str | None,
    user_input_str: str,
    upstream_str: str,
    model: str | None = None,
    max_rounds: int = 1,
) -> Tuple[str, str, Dict[str, int]]:
    t0 = time.perf_counter()
    it = (intent or "").strip().lower()
    enabled = bool(_CHECK_ENABLED) and it not in ("guardrails", "tutorial")
    m = (model or _CHECK_MODEL).strip() or _CHECK_MODEL
    _emit(f"start enabled={int(enabled)} intent={it or 'na'} rounds={int(max_rounds)} model={m}")

    vc_render_ms = 0
    vc_llm_ms = 0
    vc_rerender_ms = 0
    vc_rounds = 0
    vc_changed = 0

    try:
        t_r0 = time.perf_counter()
        img_url = render_to_image_sync(html)
        vc_render_ms = int((time.perf_counter() - t_r0) * 1000)
        _emit(f"render ok ms={vc_render_ms}")
    except Exception as exc:
        _emit(f"render error={exc}")
        raise

    if not enabled or max_rounds <= 0:
        vc_total_ms = int((time.perf_counter() - t0) * 1000)
        _emit(f"skip reason={'disabled' if not enabled else 'max_rounds'} total_ms={vc_total_ms}")
        return html, img_url, {
            "vc_enabled": int(enabled),
            "vc_rounds": 0,
            "vc_changed": 0,
            "vc_render_ms": vc_render_ms,
            "vc_llm_ms": 0,
            "vc_rerender_ms": 0,
            "vc_total_ms": vc_total_ms,
        }

    current_html = html
    current_img = img_url
    for _ in range(int(max_rounds)):
        t_llm0 = time.perf_counter()
        _emit(f"llm_check start has_image={int(bool(current_img))}")
        fixed_html = visual_self_check_and_fix_html(
            html=current_html,
            ui_image_url=current_img,
            intent=intent,
            user_input_str=user_input_str,
            upstream_str=upstream_str,
            model=model,
        )
        llm_ms = int((time.perf_counter() - t_llm0) * 1000)
        vc_llm_ms += llm_ms
        vc_rounds += 1
        _emit(f"llm_check done ms={llm_ms}")
        if fixed_html.strip() == current_html.strip():
            _emit("llm_check unchanged")
            break
        current_html = fixed_html
        vc_changed = 1
        t_r1 = time.perf_counter()
        current_img = render_to_image_sync(current_html)
        r_ms = int((time.perf_counter() - t_r1) * 1000)
        vc_rerender_ms += r_ms
        _emit(f"rerender ok ms={r_ms}")
    vc_total_ms = int((time.perf_counter() - t0) * 1000)
    _emit(f"done total_ms={vc_total_ms}")
    return current_html, current_img, {
        "vc_enabled": int(enabled),
        "vc_rounds": int(vc_rounds),
        "vc_changed": int(vc_changed),
        "vc_render_ms": int(vc_render_ms),
        "vc_llm_ms": int(vc_llm_ms),
        "vc_rerender_ms": int(vc_rerender_ms),
        "vc_total_ms": int(vc_total_ms),
    }
