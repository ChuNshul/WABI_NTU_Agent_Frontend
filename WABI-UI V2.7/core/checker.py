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

def _emit_problem(msg: str) -> None:
    s = f"[ui_render.checker] {msg}"
    try:
        print(s, flush=True)
    except Exception:
        pass
    try:
        logger.warning(s)
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

def _extract_css(text: str) -> Optional[str]:
    s = _strip_fences(text)
    s = (s or "").strip()
    if not s:
        return None
    if "<style" in s.lower():
        s = re.sub(r"(?is).*?<style[^>]*>", "", s)
        s = re.sub(r"(?is)</style>.*", "", s)
    if "{" not in s or "}" not in s:
        return None
    return s.strip()

def _find_forbidden_css_props(css: str) -> list[str]:
    s = (css or "").lower()
    forbidden = (
        "background", "background-color", "color", "fill", "stroke",
        "box-shadow", "text-shadow", "filter", "backdrop-filter",
        "border", "border-color", "border-radius", "outline",
        "animation", "transition",
    )
    hits: list[str] = []
    for prop in forbidden:
        if re.search(rf"(?i)\b{re.escape(prop)}\b\s*:", s):
            hits.append(prop)
    return hits

def _is_safe_layout_css(css: str) -> bool:
    s = (css or "").strip()
    if not s:
        return False
    return len(_find_forbidden_css_props(s)) == 0

def _trim_css(css: str, *, max_lines: int = 40, max_chars: int = 2500) -> tuple[str, bool]:
    s = (css or "").strip()
    if not s:
        return s, False
    changed = False
    lines = [ln.rstrip() for ln in s.splitlines() if ln.strip()]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        changed = True
    s2 = "\n".join(lines).strip()
    if len(s2) > max_chars:
        s2 = s2[:max_chars].rstrip()
        changed = True
    return s2, changed

def _inject_css_override(html: str, css: str) -> str:
    if not html or not css:
        return html
    tag_open = '<style id="vc-overrides">'
    tag_close = "</style>"
    if tag_open in html:
        start = html.find(tag_open) + len(tag_open)
        end = html.find(tag_close, start)
        if end > start:
            return html[:start] + "\n" + css + "\n" + html[end:]
    idx = html.lower().rfind("</head>")
    if idx >= 0:
        return html[:idx] + f'{tag_open}\n{css}\n{tag_close}\n' + html[idx:]
    return html + f"\n{tag_open}\n{css}\n{tag_close}\n"

def _extract_selectors(html: str, *, max_classes: int = 180, max_ids: int = 60) -> tuple[list[str], list[str]]:
    s = html or ""
    classes: set[str] = set()
    ids: set[str] = set()
    for m in re.finditer(r'(?i)\bclass\s*=\s*["\']([^"\']+)["\']', s):
        raw = m.group(1)
        for part in re.split(r"\s+", raw.strip()):
            if part and len(part) <= 64:
                classes.add(part)
    for m in re.finditer(r'(?i)\bid\s*=\s*["\']([^"\']+)["\']', s):
        v = (m.group(1) or "").strip()
        if v and len(v) <= 64:
            ids.add(v)
    cls = sorted(classes)[:max_classes]
    idv = sorted(ids)[:max_ids]
    return cls, idv

def _dom_outline(html: str, *, max_lines: int = 90) -> str:
    s = html or ""
    body_idx = s.lower().find("<body")
    if body_idx >= 0:
        s = s[body_idx:]
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", "", s)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", "", s)
    lines: list[str] = []
    for m in re.finditer(r"(?is)<\s*(/)?\s*([a-z0-9:-]+)([^>]*)>", s):
        closing = bool(m.group(1))
        tag = (m.group(2) or "").lower()
        if tag in ("meta", "link", "path", "circle", "rect", "stop", "defs"):
            continue
        attrs = m.group(3) or ""
        cls_m = re.search(r'(?i)\bclass\s*=\s*["\']([^"\']+)["\']', attrs)
        id_m = re.search(r'(?i)\bid\s*=\s*["\']([^"\']+)["\']', attrs)
        cls = ""
        if cls_m:
            parts = re.split(r"\s+", (cls_m.group(1) or "").strip())
            parts = [p for p in parts if p][:3]
            if parts:
                cls = " ." + " .".join(parts)
        idv = f"#{(id_m.group(1) or '').strip()}" if id_m and (id_m.group(1) or "").strip() else ""
        if closing:
            lines.append(f"</{tag}>")
        else:
            lines.append(f"<{tag}{idv}{cls}>")
        if len(lines) >= max_lines:
            break
    return "\n".join(lines)

def _extract_layout_css(html: str, classes: list[str], ids: list[str], *, max_chars: int = 1800) -> str:
    s = html or ""
    styles = re.findall(r"(?is)<style[^>]*>(.*?)</style>", s)
    if not styles:
        return ""
    css_raw = "\n".join(styles)
    css_raw = re.sub(r"(?is)/\*.*?\*/", "", css_raw)

    class_tokens = [f".{c}" for c in (classes or [])]
    id_tokens = [f"#{i}" for i in (ids or [])]
    tokens = class_tokens + id_tokens

    allowed_props = (
        "display", "position", "top", "right", "bottom", "left", "inset",
        "width", "min-width", "max-width", "height", "min-height", "max-height",
        "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
        "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
        "gap", "row-gap", "column-gap",
        "grid-template-columns", "grid-template-rows", "grid-auto-flow", "grid-auto-columns", "grid-auto-rows",
        "align-items", "align-content", "justify-items", "justify-content", "place-items", "place-content",
        "flex", "flex-direction", "flex-wrap", "flex-grow", "flex-shrink", "flex-basis",
        "align-self", "justify-self", "order",
        "overflow", "overflow-x", "overflow-y",
        "white-space", "text-overflow", "word-break", "overflow-wrap",
        "line-height", "font-size", "font-weight", "letter-spacing", "text-align",
    )

    def keep_decl(decl: str) -> bool:
        d = (decl or "").strip()
        if not d or ":" not in d:
            return False
        name = d.split(":", 1)[0].strip().lower()
        if name in _find_forbidden_css_props(d):
            return False
        return name in allowed_props

    out_rules: list[str] = []
    for m in re.finditer(r"(?is)([^{}]+)\{([^{}]*)\}", css_raw):
        sel = (m.group(1) or "").strip()
        body = (m.group(2) or "").strip()
        if not sel or not body:
            continue
        sel_l = sel.lower()
        if tokens:
            if not any(tok.lower() in sel_l for tok in tokens):
                continue
        else:
            if not any(x in sel_l for x in ("body", "html", ".shell", ".card", ".hdr", ".grid", ".flex")):
                continue
        decls = [d.strip() for d in body.split(";") if d.strip()]
        kept = [d for d in decls if keep_decl(d)]
        if not kept:
            continue
        out_rules.append(f"{sel}{{" + ";".join(kept) + "}")
        if sum(len(r) for r in out_rules) >= max_chars:
            break

    joined = "\n".join(out_rules).strip()
    if len(joined) > max_chars:
        joined = joined[:max_chars].rstrip()
    return joined


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

    if GatewayClient is None:
        _emit_problem("disabled: llm_gateway not installed (cannot run visual check)")
        return html

    m = (model or _CHECK_MODEL).strip() or _CHECK_MODEL
    cls, ids = _extract_selectors(html)
    selector_hint = ", ".join([f".{c}" for c in cls] + [f"#{i}" for i in ids])
    outline = _dom_outline(html)
    layout_css = _extract_layout_css(html, cls, ids)
    prompt = (
        "UI layout QA.\n"
        "Input: a screenshot of the rendered UI (image) and a compact DOM outline + available selectors.\n"
        "Environment: viewport width≈440px, deviceScaleFactor≈2.\n"
        "Goal: fix LAYOUT issues only (clipping/overlap/overflow/spacing/misalignment/readability).\n"
        "Constraints:\n"
        "- Do NOT change HTML structure, text, classes, or existing CSS.\n"
        "- Do NOT change colors/background/shadows/borders/icons.\n"
        "- Output ONLY CSS overrides (no <style>, no markdown, no comments).\n"
        "- Keep CSS short (<=40 lines). Use existing selectors only.\n\n"
        f"AVAILABLE_SELECTORS: {selector_hint}\n\n"
        f"DOM_OUTLINE:\n{outline}\n"
        f"\nLAYOUT_CSS_SNIPPET:\n{layout_css or '[none]'}\n"
    )

    if not ui_image_url:
        _emit_problem("missing image_url: visual check will be weak (no screenshot provided)")

    raw = _gateway_complete(prompt=prompt, model=m, max_tokens=_CHECK_MAX_TOKENS, image_url=ui_image_url)
    if not raw or not str(raw).strip():
        _emit_problem("llm returned empty output (no css)")
        return html

    css = _extract_css(raw or "")
    if css is None:
        preview = str(raw).strip().replace("\n", " ")
        _emit_problem(f"llm output not css; preview={preview[:220]}")
        return html
    css, trimmed = _trim_css(css)
    if trimmed:
        _emit_problem("css trimmed to limits (<=40 lines / <=2500 chars)")
    forbidden_hits = _find_forbidden_css_props(css)
    if forbidden_hits:
        _emit_problem(f"unsafe css blocked props={','.join(forbidden_hits[:6])}")
        return html
    before = html
    after = _inject_css_override(html, css)
    if after == before:
        _emit_problem("css injection failed (html unchanged)")
        return html
    return after


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
