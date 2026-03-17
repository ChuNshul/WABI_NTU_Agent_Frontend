"""
builder.py — HTML renderer for Wabi UI plans.

Converts a structured plan dict produced by planner.py into a self-contained
HTML document suitable for Playwright screenshot capture.

Design principles:
  - Zero JavaScript — all charts are pure SVG or CSS.
  - Mobile-first card layout (max-width 440 px).
  - Escape all user content through _e() before insertion.
  - Each _render_* function is self-contained and returns an HTML string.
  - New components register themselves in _RENDERERS; no other file changes needed.

Component catalogue (type → renderer):
  text, highlight_box, statistic_grid, key_value_list,
  bar_chart, macro_chart, food_health_list, restaurant_list,
  progress_bar, comparison_table, tabs, tag_list,
  nutrition_label, health_score_card, calorie_ring,
  nutrient_gauge, ranking_list, tip_card, meal_summary_row,
  divider, spacer
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------

_PALETTE: List[str] = [
    "#3b82f6", "#10b981", "#f59e0b", "#ef4444",
    "#8b5cf6", "#06b6d4", "#f97316", "#84cc16",
]

_VARIANT_COLORS: Dict[str, str] = {
    "primary": "#3b82f6",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error":   "#ef4444",
    "default": "#94a3b8",
}

_HBOX_STYLES: Dict[str, Tuple[str, str]] = {
    "info":    ("background:#e0f2fe;border-left:4px solid #0ea5e9;color:#0c4a6e;", "ℹ️"),
    "success": ("background:#dcfce7;border-left:4px solid #22c55e;color:#14532d;", "✅"),
    "warning": ("background:#fef9c3;border-left:4px solid #f59e0b;color:#713f12;", "⚠️"),
    "error":   ("background:#fee2e2;border-left:4px solid #ef4444;color:#7f1d1d;", "🚫"),
    "default": ("background:#f1f5f9;border-left:4px solid #94a3b8;color:#334155;", ""),
}

_MACRO_COLORS: Dict[str, str] = {
    "protein": "#3b82f6",
    "carb":    "#f59e0b",
    "fat":     "#10b981",
}

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{
  font-family:"Noto Sans SC","WenQuanYi Zen Hei","Noto Sans","DejaVu Sans",sans-serif;
  background:#f0f4f8;padding:20px 24px;width:680px;
}
.card{
  background:#fff;border-radius:16px;
  box-shadow:0 1px 4px rgba(0,0,0,.06),0 4px 20px rgba(0,0,0,.06);
  padding:20px;margin-bottom:12px;overflow:hidden;
}
/* columns: side-by-side card row */
.col-row{display:flex;gap:12px;margin-bottom:12px;align-items:flex-start;}
.col-row>.card{flex:1;margin-bottom:0;}
.hdr-card{
  background:linear-gradient(135deg,#0f172a 0%,#1a3a5c 60%,#1e4976 100%);
  border-radius:16px;padding:22px 24px 18px;margin-bottom:12px;
  box-shadow:0 4px 20px rgba(15,23,42,.3);
}
.hdr-logo{font-size:11px;font-weight:600;letter-spacing:2px;color:#64748b;
  text-transform:uppercase;margin-bottom:8px;}
.hdr-title{font-size:20px;font-weight:700;color:#f8fafc;line-height:1.3;}
.hdr-sub{font-size:12px;color:#94a3b8;margin-top:5px;}
.sec-ttl{font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.8px;margin-bottom:12px;}
.txt{font-size:13.5px;line-height:1.75;color:#334155;white-space:pre-wrap;word-break:break-word;overflow-wrap:break-word;}
.txt-positive{color:#166534;} .txt-warning{color:#713f12;} .txt-error{color:#7f1d1d;}
.hbox{border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.6;word-break:break-word;}
/* stat grid */
.sg{display:grid;gap:10px;}
.sg-cell{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
  padding:14px 12px;text-align:center;}
.sg-cell-success{border-color:#bbf7d0;background:#f0fdf4;}
.sg-cell-warning{border-color:#fde68a;background:#fffbeb;}
.sg-cell-error{border-color:#fecaca;background:#fef2f2;}
.sg-label{font-size:11.5px;color:#64748b;margin-bottom:4px;font-weight:500;}
.sg-value{font-size:24px;font-weight:800;color:#0f172a;line-height:1.1;}
.sg-unit{font-size:11px;color:#94a3b8;margin-top:3px;}
/* kv list */
.kvlist{border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;}
/* horizontal layout — short label + short value */
.kvrow{display:flex;justify-content:space-between;align-items:baseline;
  padding:9px 13px;border-bottom:1px solid #f8fafc;font-size:13px;gap:8px;}
.kvrow:last-child{border-bottom:none;}
.kvrow-hl{background:#eff6ff;}
.kv-k{color:#64748b;flex-shrink:0;max-width:48%;word-break:break-word;}
.kv-v{font-weight:600;color:#1e293b;text-align:right;word-break:break-word;min-width:0;}
/* stacked layout — auto-used when content is long */
.kvrow-s{display:flex;flex-direction:column;
  padding:10px 13px;border-bottom:1px solid #f8fafc;font-size:13px;}
.kvrow-s:last-child{border-bottom:none;}
.kvrow-s.kvrow-hl{background:#eff6ff;}
.kv-k-s{color:#64748b;font-size:11.5px;font-weight:500;
  margin-bottom:3px;text-transform:none;}
.kv-v-s{font-weight:600;color:#1e293b;line-height:1.5;word-break:break-word;}
/* bar chart */
.bar-wrap{display:flex;flex-direction:column;gap:9px;}
.bar-row{display:flex;align-items:center;gap:10px;}
.bar-name{font-size:12.5px;color:#475569;min-width:100px;max-width:180px;flex-shrink:0;
  overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  line-height:1.3;word-break:break-word;}
.bar-bg{flex:1;background:#f1f5f9;border-radius:9999px;height:11px;overflow:hidden;}
.bar-fill{height:100%;border-radius:9999px;min-width:4px;}
.bar-val{font-size:12px;color:#64748b;min-width:60px;text-align:right;white-space:nowrap;}
/* progress */
.pb-wrap{display:flex;flex-direction:column;gap:5px;}
.pb-header{display:flex;justify-content:space-between;align-items:baseline;}
.pb-label{font-size:13px;color:#334155;font-weight:500;}
.pb-pct{font-size:12px;color:#64748b;}
.pb-bg{background:#f1f5f9;border-radius:9999px;height:12px;overflow:hidden;}
.pb-fill{height:100%;border-radius:9999px;min-width:4px;}
/* tags */
.taglist{display:flex;flex-wrap:wrap;gap:6px;}
.tag{background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;
  padding:4px 10px;border-radius:9999px;font-size:12px;}
/* tabs */
.tab-pills{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px;}
.tab-pill{padding:4px 12px;border:1.5px solid #e2e8f0;border-radius:9999px;
  background:#f8fafc;font-size:11.5px;color:#475569;font-weight:500;}
.tab-section{margin-bottom:10px;} .tab-section:last-child{margin-bottom:0;}
.tab-lbl{font-size:11.5px;font-weight:700;color:#0ea5e9;margin-bottom:4px;}
.tab-body{font-size:13px;line-height:1.65;color:#334155;white-space:pre-wrap;}
/* table */
table{width:100%;border-collapse:collapse;font-size:13px;}
th{background:#f8fafc;font-weight:600;color:#475569;padding:9px 12px;
  border-bottom:2px solid #e2e8f0;text-align:left;}
td{padding:9px 12px;border-bottom:1px solid #f8fafc;color:#334155;word-break:break-word;}
tr:last-child td{border-bottom:none;}
.tbl-num{text-align:right;font-weight:500;}
/* nutrition label */
.nl-wrap{border:2px solid #0f172a;border-radius:8px;padding:10px 12px;font-size:12px;}
.nl-title{font-size:20px;font-weight:900;color:#0f172a;line-height:1;}
.nl-serving{font-size:11px;color:#475569;margin:3px 0 6px;}
.nl-cal-row{display:flex;justify-content:space-between;align-items:baseline;
  border-top:8px solid #0f172a;border-bottom:4px solid #0f172a;padding:4px 0;margin:2px 0;}
.nl-cal-lbl{font-size:13px;font-weight:700;}
.nl-cal-val{font-size:26px;font-weight:900;color:#0f172a;}
.nl-dv-hdr{font-size:10px;text-align:right;color:#475569;
  border-bottom:1px solid #64748b;padding-bottom:3px;margin-bottom:2px;}
.nl-row{display:flex;justify-content:space-between;align-items:center;
  border-bottom:1px solid #e2e8f0;padding:3px 0;}
.nl-row:last-child{border-bottom:none;}
.nl-bold{font-weight:700;}
.nl-indent{padding-left:12px;color:#475569;}
.nl-thick{border-bottom:4px solid #0f172a;}
.nl-dv{font-weight:600;color:#0f172a;}
.nl-dv-warn{font-weight:600;color:#dc2626;}
/* ranking list */
.rank-item{display:flex;align-items:center;gap:10px;
  padding:10px 0;border-bottom:1px solid #f8fafc;}
.rank-item:last-child{border-bottom:none;}
.rank-badge{width:28px;height:28px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;}
.rank-1{background:#fef9c3;color:#a16207;border:2px solid #fde047;}
.rank-2{background:#f1f5f9;color:#475569;border:2px solid #cbd5e1;}
.rank-3{background:#fff7ed;color:#9a3412;border:2px solid #fdba74;}
.rank-n{background:#f8fafc;color:#64748b;border:2px solid #e2e8f0;}
.rank-name{flex:1;font-size:13px;font-weight:600;color:#0f172a;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.rank-sub{font-size:11.5px;color:#64748b;margin-top:1px;}
.rank-val{font-size:13px;font-weight:700;color:#0f172a;text-align:right;white-space:nowrap;}
/* tip card */
.tip-card{display:flex;gap:13px;align-items:flex-start;border-radius:12px;padding:13px;}
.tip-icon{font-size:28px;flex-shrink:0;line-height:1;}
.tip-title{font-size:13.5px;font-weight:700;margin-bottom:4px;}
.tip-body{font-size:12.5px;line-height:1.65;}
/* meal row */
.meal-row{display:grid;gap:6px;}
.meal-slot{display:flex;align-items:center;gap:9px;background:#f8fafc;
  border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;}
.meal-icon{font-size:20px;flex-shrink:0;}
.meal-name{font-size:12px;font-weight:600;color:#475569;margin-bottom:1px;}
.meal-cal{font-size:14px;font-weight:800;color:#0f172a;}
.meal-cal-unit{font-size:10px;color:#94a3b8;font-weight:400;}
.meal-bar-wrap{flex:1;}
.meal-bar-bg{background:#e2e8f0;border-radius:9999px;height:5px;margin-top:4px;overflow:hidden;}
.meal-bar-fill{height:100%;border-radius:9999px;min-width:3px;}
/* footer / divider */
.footer{text-align:center;font-size:11px;color:#cbd5e1;padding:8px 0 4px;}
.divider{height:1px;background:#e2e8f0;margin:2px 0;}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _e(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

def _fmt_num(v: Any) -> str:
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(round(f, 1))
    except Exception:
        return str(v)

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or 0)
    except Exception:
        return default

def _ttl(title: Optional[str]) -> str:
    return f'<div class="sec-ttl">{_e(title)}</div>' if title else ""

def _health_badge(is_healthy: Any) -> str:
    if is_healthy is True:
        return ('<span style="font-size:10.5px;padding:2px 8px;border-radius:9999px;'
                'background:#dcfce7;color:#166534;font-weight:600;white-space:nowrap;">&#10003; Healthy</span>')
    if is_healthy is False:
        return ('<span style="font-size:10.5px;padding:2px 8px;border-radius:9999px;'
                'background:#fee2e2;color:#991b1b;font-weight:600;white-space:nowrap;">&#10007; Caution</span>')
    return ('<span style="font-size:10.5px;padding:2px 8px;border-radius:9999px;'
            'background:#f1f5f9;color:#64748b;white-space:nowrap;">&mdash; Unknown</span>')

def _score_color(score: float) -> str:
    if score >= 70: return "#22c55e"
    if score >= 45: return "#f59e0b"
    return "#ef4444"

def _score_grade(score: float) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 55: return "C"
    if score >= 40: return "D"
    return "F"

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_donut_macro(protein_g: float, carb_g: float, fat_g: float, total_kcal: float) -> str:
    R, CX, CY = 56, 70, 70
    C = 2 * math.pi * R
    total_g = protein_g + carb_g + fat_g
    if total_g <= 0:
        return ""
    slices = [
        (protein_g, _MACRO_COLORS["protein"]),
        (carb_g,    _MACRO_COLORS["carb"]),
        (fat_g,     _MACRO_COLORS["fat"]),
    ]
    arcs, cumulative = "", 0.0
    for val, color in slices:
        if val <= 0:
            continue
        dash = val / total_g * C
        arcs += (
            f'<circle r="{R}" cx="{CX}" cy="{CY}" fill="none" stroke="{color}" stroke-width="19"'
            f' stroke-dasharray="{dash:.3f} {C:.3f}" stroke-dashoffset="{-cumulative:.3f}"'
            f' transform="rotate(-90,{CX},{CY})" stroke-linecap="butt"/>'
        )
        cumulative += dash
    ct = f"{int(total_kcal)}" if total_kcal > 0 else f"{int(total_g)}g"
    cb = "kcal" if total_kcal > 0 else "total"
    return (
        f'<svg width="140" height="140" viewBox="0 0 140 140" style="flex-shrink:0;">'
        f'<circle r="{R}" cx="{CX}" cy="{CY}" fill="none" stroke="#f1f5f9" stroke-width="19"/>'
        f'{arcs}'
        f'<text x="{CX}" y="{CY-4}" text-anchor="middle" font-size="17" font-weight="800"'
        f' fill="#0f172a" font-family="sans-serif">{_e(ct)}</text>'
        f'<text x="{CX}" y="{CY+13}" text-anchor="middle" font-size="11" fill="#94a3b8"'
        f' font-family="sans-serif">{_e(cb)}</text></svg>'
    )


def _svg_calorie_ring(consumed: float, target: float, color: str) -> str:
    R, CX, CY = 54, 70, 70
    C = 2 * math.pi * R
    ratio     = min(consumed / target, 1.0) if target > 0 else 0.0
    fill_dash = ratio * C
    remaining = max(0.0, target - consumed)
    pct       = int(round(ratio * 100))
    return (
        f'<svg width="140" height="140" viewBox="0 0 140 140">'
        f'<circle r="{R}" cx="{CX}" cy="{CY}" fill="none" stroke="#f1f5f9" stroke-width="16"/>'
        f'<circle r="{R}" cx="{CX}" cy="{CY}" fill="none" stroke="{color}" stroke-width="16"'
        f' stroke-dasharray="{fill_dash:.3f} {C:.3f}" stroke-dashoffset="0"'
        f' stroke-linecap="round" transform="rotate(-90,{CX},{CY})"/>'
        f'<text x="{CX}" y="{CY-6}" text-anchor="middle" font-size="18" font-weight="800"'
        f' fill="#0f172a" font-family="sans-serif">{_e(_fmt_num(remaining))}</text>'
        f'<text x="{CX}" y="{CY+10}" text-anchor="middle" font-size="10" fill="#94a3b8"'
        f' font-family="sans-serif">kcal left</text>'
        f'<text x="{CX}" y="{CY+24}" text-anchor="middle" font-size="11" fill="{color}"'
        f' font-family="sans-serif" font-weight="700">{pct}%</text></svg>'
    )


def _svg_health_gauge(score: float, color: str) -> str:
    R, CX, CY = 105, 130, 135
    C      = 2 * math.pi * R
    half_c = C / 2
    fill_len = (score / 100.0) * half_c

    def zone(s_pct: float, e_pct: float, zc: str) -> str:
        s = s_pct / 100 * half_c
        ln = (e_pct - s_pct) / 100 * half_c
        return (
            f'<circle r="{R}" cx="{CX}" cy="{CY}" fill="none" stroke="{zc}"'
            f' stroke-width="18" opacity="0.18"'
            f' stroke-dasharray="{ln:.3f} {C:.3f}" stroke-dashoffset="{-s:.3f}"'
            f' transform="rotate(-180,{CX},{CY})"/>'
        )

    grade = _score_grade(score)
    return (
        f'<svg width="260" height="150" viewBox="0 0 260 150" style="display:block;margin:0 auto;">'
        + zone(0, 40, "#ef4444") + zone(40, 70, "#f59e0b") + zone(70, 100, "#22c55e")
        + f'<circle r="{R}" cx="{CX}" cy="{CY}" fill="none" stroke="{color}" stroke-width="18"'
        f' stroke-dasharray="{fill_len:.3f} {C:.3f}" stroke-dashoffset="0"'
        f' stroke-linecap="round" transform="rotate(-180,{CX},{CY})"/>'
        f'<text x="18" y="{CY+16}" text-anchor="middle" font-size="10" fill="#94a3b8" font-family="sans-serif">0</text>'
        f'<text x="{CX}" y="22" text-anchor="middle" font-size="10" fill="#94a3b8" font-family="sans-serif">50</text>'
        f'<text x="242" y="{CY+16}" text-anchor="middle" font-size="10" fill="#94a3b8" font-family="sans-serif">100</text>'
        f'<text x="{CX}" y="{CY-10}" text-anchor="middle" font-size="36" font-weight="900"'
        f' fill="{color}" font-family="sans-serif">{int(score)}</text>'
        f'<text x="{CX}" y="{CY+12}" text-anchor="middle" font-size="14" fill="#94a3b8"'
        f' font-family="sans-serif">Grade {_e(grade)}</text></svg>'
    )


def _svg_nutrient_gauge_single(value: float, limit: float, color: str, unit: str) -> str:
    R, CX, CY = 62, 80, 86
    C      = 2 * math.pi * R
    half_c = C / 2
    ratio    = min(value / limit, 1.0) if limit > 0 else 0.0
    fill_len = ratio * half_c
    pct      = int(round(ratio * 100))
    return (
        f'<svg width="160" height="92" viewBox="0 0 160 92">'
        f'<circle r="{R}" cx="{CX}" cy="{CY}" fill="none" stroke="#f1f5f9" stroke-width="13"'
        f' stroke-dasharray="{half_c:.3f} {C:.3f}" transform="rotate(-180,{CX},{CY})"/>'
        f'<circle r="{R}" cx="{CX}" cy="{CY}" fill="none" stroke="{color}" stroke-width="13"'
        f' stroke-dasharray="{fill_len:.3f} {C:.3f}" stroke-dashoffset="0"'
        f' stroke-linecap="round" transform="rotate(-180,{CX},{CY})"/>'
        f'<text x="{CX}" y="{CY-4}" text-anchor="middle" font-size="18" font-weight="800"'
        f' fill="{color}" font-family="sans-serif">{_fmt_num(value)}</text>'
        f'<text x="{CX}" y="{CY+11}" text-anchor="middle" font-size="10" fill="#94a3b8"'
        f' font-family="sans-serif">{_e(unit)} &middot; {pct}% DV</text></svg>'
    )

# ---------------------------------------------------------------------------
# Component renderers
# ---------------------------------------------------------------------------

def _render_text(sec: Dict) -> str:
    tone     = (sec.get("tone") or "neutral").lower()
    tone_cls = {"positive": "txt-positive", "warning": "txt-warning", "error": "txt-error"}.get(tone, "")
    return (
        f'<div class="card">{_ttl(sec.get("title"))}'
        f'<div class="txt {tone_cls}">{_e(sec.get("content", ""))}</div></div>'
    )


def _render_highlight_box(sec: Dict) -> str:
    variant     = (sec.get("variant") or "default").lower()
    style, icon = _HBOX_STYLES.get(variant, _HBOX_STYLES["default"])
    content     = sec.get("content") or sec.get("title") or ""
    icon_html   = f'<span style="margin-right:6px;">{icon}</span>' if icon else ""
    return (
        f'<div class="card">'
        f'<div class="hbox" style="{style}">{icon_html}{_e(content)}</div></div>'
    )


def _render_statistic_grid(sec: Dict) -> str:
    cols  = max(2, min(int(sec.get("columns") or 2), 5))
    cells = ""
    for item in (sec.get("items") or []):
        if not isinstance(item, dict):
            continue
        variant   = (item.get("variant") or "default").lower()
        extra_cls = {"success": "sg-cell-success", "warning": "sg-cell-warning",
                     "error": "sg-cell-error"}.get(variant, "")
        unit_html = f'<div class="sg-unit">{_e(item["unit"])}</div>' if item.get("unit") else ""
        cells += (
            f'<div class="sg-cell {extra_cls}">'
            f'<div class="sg-label">{_e(item.get("label",""))}</div>'
            f'<div class="sg-value">{_e(item.get("value",""))}</div>'
            f'{unit_html}</div>'
        )
    return (
        f'<div class="card">{_ttl(sec.get("title"))}'
        f'<div class="sg" style="grid-template-columns:repeat({cols},1fr);">{cells}</div></div>'
    )


def _render_key_value_list(sec: Dict) -> str:
    items = [i for i in (sec.get("items") or []) if isinstance(i, dict)]
    if not items:
        return f'<div class="card">{_ttl(sec.get("title"))}</div>'

    # Auto-detect: if any row has combined content > 55 chars → stacked layout for all
    use_stacked = any(
        len(str(i.get("label", ""))) + len(str(i.get("value", ""))) > 75
        for i in items
    )

    rows = ""
    for item in items:
        key = item.get("label", "")
        val = item.get("value", "")
        hl  = "kvrow-hl" if item.get("highlight") else ""

        if use_stacked:
            rows += (
                f'<div class="kvrow-s {hl}">'
                f'<div class="kv-k-s">{_e(key)}</div>'
                f'<div class="kv-v-s">{_e(val)}</div>'
                f'</div>'
            )
        else:
            rows += (
                f'<div class="kvrow {hl}">'
                f'<span class="kv-k">{_e(key)}</span>'
                f'<span class="kv-v">{_e(val)}</span>'
                f'</div>'
            )
    return f'<div class="card">{_ttl(sec.get("title"))}<div class="kvlist">{rows}</div></div>'


def _render_bar_chart(sec: Dict) -> str:
    items  = [i for i in (sec.get("items") or []) if isinstance(i, dict)]
    unit   = sec.get("unit") or ""
    colors = list(sec.get("colors") or [])
    vals   = [_safe_float(i.get("value")) for i in items]
    max_v  = max(vals, default=1.0) or 1.0
    bars   = ""
    for idx, (item, val) in enumerate(zip(items, vals)):
        color = (colors[idx] if idx < len(colors) else None) or _PALETTE[idx % len(_PALETTE)]
        pct   = max(2, int(round(val / max_v * 100)))
        lbl   = item.get("label") or ""
        bars += (
            f'<div class="bar-row">'
            f'<div class="bar-name" title="{_e(lbl)}">{_e(lbl)}</div>'
            f'<div class="bar-bg"><div class="bar-fill" style="width:{pct}%;background:{color};"></div></div>'
            f'<div class="bar-val">{_fmt_num(val)}{" " + _e(unit) if unit else ""}</div>'
            f'</div>'
        )
    return f'<div class="card">{_ttl(sec.get("title"))}<div class="bar-wrap">{bars}</div></div>'


def _render_macro_chart(sec: Dict) -> str:
    p_g   = _safe_float(sec.get("protein_g"))
    c_g   = _safe_float(sec.get("carb_g"))
    f_g   = _safe_float(sec.get("fat_g"))
    kcal  = _safe_float(sec.get("total_kcal"))
    total = p_g + c_g + f_g
    if total <= 0:
        return ""
    svg = _svg_donut_macro(p_g, c_g, f_g, kcal)

    def _bar(lbl: str, val: float, color: str) -> str:
        pct = max(1, int(round(val / total * 100)))
        return (
            f'<div style="margin-bottom:9px;">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:3px;">'
            f'<span style="font-size:12px;color:#475569;font-weight:500;">{_e(lbl)}</span>'
            f'<span style="font-size:12px;font-weight:700;color:#0f172a;">'
            f'{_fmt_num(val)}g <span style="color:#94a3b8;font-weight:400;">({pct}%)</span></span>'
            f'</div>'
            f'<div style="background:#f1f5f9;border-radius:9999px;height:7px;">'
            f'<div style="width:{pct}%;height:100%;background:{color};border-radius:9999px;min-width:4px;"></div>'
            f'</div></div>'
        )

    legend = (
        _bar("Protein", p_g, _MACRO_COLORS["protein"])
        + _bar("Carbs",   c_g, _MACRO_COLORS["carb"])
        + _bar("Fat",     f_g, _MACRO_COLORS["fat"])
    )
    return (
        f'<div class="card">{_ttl(sec.get("title"))}'
        f'<div style="display:flex;gap:14px;align-items:center;">{svg}'
        f'<div style="flex:1;min-width:0;">{legend}</div></div></div>'
    )


def _render_food_health_list(sec: Dict) -> str:
    items = [i for i in (sec.get("items") or []) if isinstance(i, dict)]
    rows  = ""
    for idx, item in enumerate(items):
        name       = item.get("name") or "Unknown"
        calories   = item.get("calories") or 0
        is_healthy = item.get("is_healthy")
        reasons    = item.get("reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        p_g = _safe_float(item.get("protein_g"))
        c_g = _safe_float(item.get("carb_g"))
        f_g = _safe_float(item.get("fat_g"))

        parts = []
        if p_g: parts.append(f"P {_fmt_num(p_g)}g")
        if c_g: parts.append(f"C {_fmt_num(c_g)}g")
        if f_g: parts.append(f"F {_fmt_num(f_g)}g")

        macro_html   = ('<div style="font-size:11.5px;color:#94a3b8;margin-top:2px;">'
                        + _e(" \u00b7 ".join(parts)) + "</div>") if parts else ""
        reasons_html = ('<div style="font-size:11px;color:#dc2626;margin-top:3px;line-height:1.4;">'
                        + _e(", ".join(str(r) for r in reasons[:3])) + "</div>") if (reasons and is_healthy is False) else ""
        border = "" if idx == len(items) - 1 else "border-bottom:1px solid #f8fafc;"
        cal_color = "#dc2626" if _safe_float(calories) > 500 else "#0f172a"

        rows += (
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;padding:11px 0;{border}">'
            f'<div style="flex:1;min-width:0;margin-right:10px;">'
            f'<div style="font-size:13.5px;font-weight:600;color:#0f172a;'
            f'overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;'
            f'-webkit-box-orient:vertical;word-break:break-word;">{_e(name)}</div>'
            + macro_html + reasons_html
            + '</div>'
            f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px;flex-shrink:0;">'
            f'<span style="font-size:14px;font-weight:800;color:{cal_color};">'
            f'{_fmt_num(calories)}<span style="font-size:10px;font-weight:400;color:#94a3b8;"> kcal</span></span>'
            + _health_badge(is_healthy)
            + '</div></div>'
        )
    return f'<div class="card">{_ttl(sec.get("title"))}<div>{rows}</div></div>'


def _render_restaurant_list(sec: Dict) -> str:
    items = [i for i in (sec.get("items") or []) if isinstance(i, dict)]
    cards = ""
    for rest in items:
        name     = rest.get("name") or "Restaurant"
        rating   = rest.get("rating")
        price    = rest.get("price")
        distance = rest.get("distance")
        is_veg   = rest.get("is_veg")
        cuisine  = rest.get("cuisine") or ""
        dishes   = [d for d in (rest.get("dishes") or []) if isinstance(d, dict)]

        def chip(bg: str, fg: str, bd: str, text: str) -> str:
            return (f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
                    f'padding:2px 7px;border-radius:9999px;font-size:11px;">{text}</span>')

        chips = []
        if rating:   chips.append(chip("#fffbeb","#92400e","#fde68a", f"&#11088; {_e(str(rating))}"))
        if price:    chips.append(chip("#f0fdf4","#166534","#bbf7d0", f"&#128176; {_e(str(price))}"))
        if distance: chips.append(chip("#eff6ff","#1d4ed8","#bfdbfe", f"&#128205; {_e(str(distance))}"))
        if is_veg:   chips.append(chip("#dcfce7","#166534","#bbf7d0", "&#127807; Veg"))

        meta_html    = ('<div style="display:flex;flex-wrap:wrap;gap:5px;margin:6px 0 8px;">'
                        + "".join(chips) + "</div>") if chips else ""
        cuisine_html = (f'<div style="font-size:12px;color:#64748b;margin-top:2px;">{_e(cuisine)}</div>') if cuisine else ""

        dish_rows = ""
        for d in dishes[:4]:
            d_name    = d.get("name") or d.get("dish_name") or ""
            d_cal     = d.get("calories") or 0
            d_healthy = d.get("is_healthy")
            dot       = "#22c55e" if d_healthy is True else ("#ef4444" if d_healthy is False else "#94a3b8")
            cal_str   = f"{_fmt_num(d_cal)} kcal" if d_cal else ""
            dish_rows += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:12px;">'
                f'<div style="display:flex;align-items:center;gap:6px;flex:1;min-width:0;">'
                f'<div style="width:7px;height:7px;border-radius:50%;background:{dot};flex-shrink:0;"></div>'
                f'<span style="color:#475569;overflow:hidden;word-break:break-word;'
                f'display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;">{_e(d_name)}</span>'
                f'</div><span style="color:#64748b;margin-left:8px;flex-shrink:0;">{_e(cal_str)}</span></div>'
            )
        dishes_html = (
            '<div style="border-top:1px solid #f8fafc;padding-top:8px;margin-top:4px;">'
            '<div style="font-size:10.5px;font-weight:600;color:#94a3b8;text-transform:uppercase;'
            'letter-spacing:.6px;margin-bottom:5px;">Dishes</div>'
            + dish_rows + '</div>'
        ) if dish_rows else ""

        cards += (
            f'<div style="border:1px solid #e2e8f0;border-radius:12px;padding:13px;margin-bottom:9px;">'
            f'<div style="font-size:15px;font-weight:700;color:#0f172a;">{_e(name)}</div>'
            f'{cuisine_html}{meta_html}{dishes_html}</div>'
        )
    return f'<div class="card">{_ttl(sec.get("title"))}{cards}</div>'


def _render_progress_bar(sec: Dict) -> str:
    label   = sec.get("label") or ""
    value   = _safe_float(sec.get("value"))
    max_v   = _safe_float(sec.get("max")) or 1.0
    unit    = sec.get("unit") or ""
    variant = (sec.get("variant") or "primary").lower()
    color   = _VARIANT_COLORS.get(variant, _VARIANT_COLORS["primary"])
    pct     = max(2, int(value / max_v * 100))
    lbl_r   = f'{_fmt_num(value)}{" " + unit if unit else ""} / {_fmt_num(max_v)}{" " + unit if unit else ""}'
    return (
        f'<div class="card"><div class="pb-wrap">'
        f'<div class="pb-header"><div class="pb-label">{_e(label)}</div>'
        f'<div class="pb-pct">{_e(lbl_r)}</div></div>'
        f'<div class="pb-bg"><div class="pb-fill" style="width:{pct}%;background:{color};"></div></div>'
        f'</div></div>'
    )


def _render_comparison_table(sec: Dict) -> str:
    cols_def = sec.get("columns") or []
    rows_def = sec.get("rows")    or []
    hdr  = "".join(f"<th>{_e(c)}</th>" for c in cols_def)
    body = ""
    for row in rows_def:
        cells = ""
        for idx, cell in enumerate(row or []):
            cls = 'class="tbl-num"' if idx > 0 else ""
            cells += f"<td {cls}>{_e(cell)}</td>"
        body += f"<tr>{cells}</tr>"
    note = (f'<div style="font-size:11px;color:#94a3b8;margin-top:6px;">{_e(sec["footnote"])}</div>'
            if sec.get("footnote") else "")
    return (
        f'<div class="card">{_ttl(sec.get("title"))}'
        f'<div style="overflow-x:auto;"><table><thead><tr>{hdr}</tr></thead>'
        f'<tbody>{body}</tbody></table></div>{note}</div>'
    )


def _render_tabs(sec: Dict) -> str:
    tabs  = sec.get("tabs") or []
    pills = "".join(f'<div class="tab-pill">{_e(t.get("label",""))}</div>' for t in tabs)
    secs  = "".join(
        f'<div class="tab-section"><div class="tab-lbl">{_e(t.get("label",""))}</div>'
        f'<div class="tab-body">{_e(t.get("content",""))}</div></div>'
        for t in tabs
    )
    return (
        f'<div class="card">{_ttl(sec.get("title"))}'
        f'<div class="tab-pills">{pills}</div>{secs}</div>'
    )


def _render_tag_list(sec: Dict) -> str:
    tags = "".join(f'<span class="tag">{_e(t)}</span>' for t in (sec.get("tags") or []))
    return f'<div class="card">{_ttl(sec.get("title"))}<div class="taglist">{tags}</div></div>'


# ---------------------------------------------------------------------------
# New components
# ---------------------------------------------------------------------------

def _render_nutrition_label(sec: Dict) -> str:
    """FDA/HPB-style Nutrition Facts panel for a single food item."""
    name      = sec.get("name") or "Food Item"
    serving   = sec.get("serving_size") or "1 serving"
    calories  = _safe_float(sec.get("calories"))
    fat_g     = _safe_float(sec.get("fat_g"))
    sat_fat_g = _safe_float(sec.get("sat_fat_g"))
    sodium_mg = _safe_float(sec.get("sodium_mg"))
    carb_g    = _safe_float(sec.get("carb_g"))
    sugar_g   = _safe_float(sec.get("sugar_g"))
    fiber_g   = _safe_float(sec.get("fiber_g"))
    protein_g = _safe_float(sec.get("protein_g"))

    dv_overrides = sec.get("daily_values") or {}

    def _dv_pct(key: str, val: float, ref: float) -> str:
        pct = int(dv_overrides.get(key) or (round(val / ref * 100) if ref else 0))
        cls = "nl-dv-warn" if pct >= 20 else "nl-dv"
        return f'<span class="{cls}">{pct}%</span>'

    def _row(label: str, val_str: str, dv_html: str,
             bold: bool = False, indent: bool = False, thick: bool = False) -> str:
        cls = ("nl-bold " if bold else "") + ("nl-indent " if indent else "") + ("nl-thick" if thick else "")
        return (
            f'<div class="nl-row {cls.strip()}">'
            f'<span>{_e(label)} <span style="font-weight:400;color:#475569;">{_e(val_str)}</span></span>'
            f'{dv_html}</div>'
        )

    return (
        f'<div class="card">{_ttl(sec.get("title"))}'
        f'<div class="nl-wrap">'
        f'<div class="nl-title">Nutrition Facts</div>'
        f'<div class="nl-serving">Serving: {_e(serving)} &mdash; {_e(name)}</div>'
        f'<div class="nl-cal-row">'
        f'<span class="nl-cal-lbl">Calories</span>'
        f'<span class="nl-cal-val">{_fmt_num(calories)}</span></div>'
        f'<div class="nl-dv-hdr">% Daily Value*</div>'
        + _row("Total Fat",          f"{_fmt_num(fat_g)}g",     _dv_pct("fat",     fat_g,     78),   bold=True)
        + _row("Saturated Fat",      f"{_fmt_num(sat_fat_g)}g", _dv_pct("sat_fat", sat_fat_g, 20),   indent=True)
        + _row("Sodium",             f"{_fmt_num(sodium_mg)}mg",_dv_pct("sodium",  sodium_mg, 2300), bold=True)
        + _row("Total Carbohydrate", f"{_fmt_num(carb_g)}g",    _dv_pct("carb",    carb_g,    275),  bold=True)
        + _row("Dietary Fiber",      f"{_fmt_num(fiber_g)}g",   _dv_pct("fiber",   fiber_g,   28),   indent=True)
        + _row("Total Sugars",       f"{_fmt_num(sugar_g)}g",   "",                                   indent=True)
        + _row("Protein",            f"{_fmt_num(protein_g)}g", "",                                   bold=True, thick=True)
        + '<div style="font-size:9.5px;color:#94a3b8;margin-top:5px;">'
        + '*Percent Daily Values based on a 2,000 kcal diet.'
        + '</div></div></div>'
    )


def _render_health_score_card(sec: Dict) -> str:
    """Semicircle gauge health score + dimension breakdown bars, side by side."""
    score  = min(100.0, max(0.0, _safe_float(sec.get("score"))))
    color  = _score_color(score)
    svg    = _svg_health_gauge(score, color)
    dims   = [d for d in (sec.get("dimensions") or []) if isinstance(d, dict)]
    dim_html = ""
    for dim in dims[:5]:
        lbl     = dim.get("label") or ""
        val     = _safe_float(dim.get("value"))
        max_v   = _safe_float(dim.get("max")) or 100.0
        variant = (dim.get("variant") or "default").lower()
        dcolor  = _VARIANT_COLORS.get(variant, "#94a3b8")
        pct     = max(3, int(val / max_v * 100))
        dim_html += (
            f'<div style="margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
            f'<span style="font-size:13px;color:#475569;">{_e(lbl)}</span>'
            f'<span style="font-size:13px;font-weight:700;color:{dcolor};">{_fmt_num(val)}</span>'
            f'</div>'
            f'<div style="background:#f1f5f9;border-radius:9999px;height:8px;">'
            f'<div style="width:{pct}%;height:100%;background:{dcolor};border-radius:9999px;min-width:3px;"></div>'
            f'</div></div>'
        )
    if dim_html:
        # Gauge left (~260px), dims right (flex:1)
        inner = (
            f'<div style="display:flex;gap:24px;align-items:center;">'
            f'<div style="flex-shrink:0;">{svg}</div>'
            f'<div style="flex:1;min-width:0;padding-top:8px;">{dim_html}</div>'
            f'</div>'
        )
    else:
        inner = svg
    return f'<div class="card">{_ttl(sec.get("title"))}{inner}</div>'


def _render_calorie_ring(sec: Dict) -> str:
    """Full-circle calorie goal ring with optional meal breakdown."""
    consumed = _safe_float(sec.get("consumed"))
    target   = _safe_float(sec.get("target")) or 2000.0
    label    = sec.get("label") or "Daily Calories"
    ratio    = min(consumed / target, 1.0) if target > 0 else 0.0
    color    = "#22c55e" if ratio <= 0.7 else ("#f59e0b" if ratio <= 0.9 else "#ef4444")
    svg      = _svg_calorie_ring(consumed, target, color)

    breakdown = [b for b in (sec.get("breakdown") or []) if isinstance(b, dict)]
    bk_html   = ""
    for i, bk in enumerate(breakdown[:4]):
        bk_val   = _safe_float(bk.get("value"))
        bk_pct   = int(bk_val / target * 100) if target else 0
        bk_color = bk.get("color") or _PALETTE[i % len(_PALETTE)]
        bk_html += (
            f'<div style="margin-bottom:7px;">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:2px;">'
            f'<span style="font-size:11.5px;color:#475569;">{_e(bk.get("label",""))}</span>'
            f'<span style="font-size:11.5px;font-weight:600;color:#0f172a;">{_fmt_num(bk_val)} kcal</span>'
            f'</div>'
            f'<div style="background:#f1f5f9;border-radius:9999px;height:6px;">'
            f'<div style="width:{max(2,bk_pct)}%;height:100%;background:{bk_color};border-radius:9999px;"></div>'
            f'</div></div>'
        )
    consumed_note = (
        f'<div style="font-size:11px;color:#64748b;margin-bottom:4px;">'
        f'Consumed: <b style="color:#0f172a;">{_fmt_num(consumed)}</b> / {_fmt_num(target)} kcal</div>'
    )
    return (
        f'<div class="card">{_ttl(sec.get("title") or label)}'
        f'<div style="display:flex;gap:14px;align-items:center;">{svg}'
        f'<div style="flex:1;min-width:0;">{consumed_note}{bk_html}</div>'
        f'</div></div>'
    )


def _render_nutrient_gauge(sec: Dict) -> str:
    """Mini semi-circle gauges for nutrients vs daily limits. Supports single or multi-gauge."""
    gauges_raw = sec.get("gauges")
    gauges = (
        [g for g in gauges_raw if isinstance(g, dict)]
        if isinstance(gauges_raw, list)
        else ([sec] if sec.get("value") is not None else [])
    )
    if not gauges:
        return ""

    gauge_svgs = ""
    for g in gauges[:4]:
        lbl     = g.get("label") or ""
        val     = _safe_float(g.get("value"))
        limit   = _safe_float(g.get("limit")) or 100.0
        unit    = g.get("unit") or ""
        variant = (g.get("variant") or "").lower()
        if not variant:
            ratio   = val / limit if limit else 0
            variant = "error" if ratio >= 0.8 else ("warning" if ratio >= 0.6 else "success")
        color = _VARIANT_COLORS.get(variant, "#94a3b8")

        gauge_svgs += (
            f'<div style="text-align:center;flex:1;min-width:140px;">'
            f'{_svg_nutrient_gauge_single(val, limit, color, unit)}'
            f'<div style="font-size:12px;font-weight:600;color:#475569;margin-top:3px;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_e(lbl)}</div>'
            f'<div style="font-size:10.5px;color:#94a3b8;">Limit: {_fmt_num(limit)} {_e(unit)}</div>'
            f'</div>'
        )
    return (
        f'<div class="card">{_ttl(sec.get("title"))}'
        f'<div style="display:flex;gap:10px;justify-content:space-around;align-items:flex-start;">'
        f'{gauge_svgs}</div></div>'
    )


def _render_ranking_list(sec: Dict) -> str:
    """Ranked list with gold/silver/bronze badges for top 3."""
    items = [i for i in (sec.get("items") or []) if isinstance(i, dict)]
    rows  = ""
    for idx, item in enumerate(items):
        rank = idx + 1
        if rank == 1:
            badge_cls, badge_lbl = "rank-1", "&#129351;"   # 🥇
        elif rank == 2:
            badge_cls, badge_lbl = "rank-2", "&#129352;"   # 🥈
        elif rank == 3:
            badge_cls, badge_lbl = "rank-3", "&#129353;"   # 🥉
        else:
            badge_cls, badge_lbl = "rank-n", str(rank)

        name      = item.get("name") or ""
        value     = item.get("value")
        unit      = item.get("unit") or ""
        sub       = item.get("sub") or ""
        badge_txt = item.get("badge_text") or ""

        val_html = (
            f'<div class="rank-val">{_e(_fmt_num(value))}{" " + _e(unit) if unit else ""}</div>'
        ) if value is not None else ""

        badge_extra = (
            f'<span style="font-size:10.5px;padding:1px 7px;border-radius:9999px;'
            f'background:#e0f2fe;color:#0c4a6e;margin-left:5px;">{_e(badge_txt)}</span>'
        ) if badge_txt else ""

        sub_html = f'<div class="rank-sub">{_e(sub)}</div>' if sub else ""

        rows += (
            f'<div class="rank-item">'
            f'<div class="rank-badge {badge_cls}">{badge_lbl}</div>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="display:flex;align-items:center;">'
            f'<div class="rank-name">{_e(name)}</div>{badge_extra}</div>'
            f'{sub_html}</div>'
            f'{val_html}</div>'
        )
    return f'<div class="card">{_ttl(sec.get("title"))}<div>{rows}</div></div>'


def _render_tip_card(sec: Dict) -> str:
    """Styled actionable nutrition tip with emoji icon and tone-aware colours."""
    icon    = sec.get("icon") or "&#128161;"   # 💡
    title   = sec.get("title") or ""
    content = sec.get("content") or ""
    tone    = (sec.get("tone") or "positive").lower()
    bg, border, title_color = {
        "positive": ("#f0fdf4", "#bbf7d0", "#166534"),
        "caution":  ("#fffbeb", "#fde68a", "#92400e"),
        "warning":  ("#fef2f2", "#fecaca", "#991b1b"),
    }.get(tone, ("#f0fdf4", "#bbf7d0", "#166534"))
    return (
        f'<div class="card">'
        f'<div class="tip-card" style="background:{bg};border:1px solid {border};">'
        f'<div class="tip-icon">{icon}</div>'
        f'<div style="flex:1;min-width:0;">'
        f'<div class="tip-title" style="color:{title_color};">{_e(title)}</div>'
        f'<div class="tip-body" style="color:#374151;">{_e(content)}</div>'
        f'</div></div></div>'
    )


def _render_meal_summary_row(sec: Dict) -> str:
    """Grid of meal slots (Breakfast/Lunch/Dinner/Snack) with mini calorie bars."""
    meals        = [m for m in (sec.get("meals") or []) if isinstance(m, dict)]
    daily_target = _safe_float(sec.get("daily_target")) or 2000.0
    cols         = min(len(meals), 4) if meals else 1
    slots        = ""
    for m in meals[:4]:
        name     = m.get("name") or "Meal"
        icon     = m.get("icon") or "&#127869;"   # 🍽️
        calories = _safe_float(m.get("calories"))
        color    = m.get("color") or "#3b82f6"
        pct      = max(2, int(calories / daily_target * 100)) if daily_target else 2
        slots += (
            f'<div class="meal-slot">'
            f'<div class="meal-icon">{icon}</div>'
            f'<div class="meal-bar-wrap">'
            f'<div class="meal-name">{_e(name)}</div>'
            f'<div class="meal-cal">{_fmt_num(calories)}'
            f'<span class="meal-cal-unit"> kcal</span></div>'
            f'<div class="meal-bar-bg">'
            f'<div class="meal-bar-fill" style="width:{pct}%;background:{color};"></div>'
            f'</div></div></div>'
        )
    return (
        f'<div class="card">{_ttl(sec.get("title"))}'
        f'<div class="meal-row" style="grid-template-columns:repeat({cols},1fr);">'
        f'{slots}</div></div>'
    )

def _render_columns(sec: Dict) -> str:
    """
    Side-by-side card layout. Renders each child section as its own card in a flex row.
    Props: sections ([section dicts]), gap (optional px, default 12).
    The LLM can use this to place e.g. calorie_ring and macro_chart next to each other.
    """
    children = [s for s in (sec.get("sections") or []) if isinstance(s, dict) and s.get("type")]
    if not children:
        return ""
    gap = max(6, min(int(sec.get("gap") or 12), 32))
    inner = "".join(_render_section(c) for c in children)
    return f'<div class="col-row" style="gap:{gap}px;">{inner}</div>'


# ---------------------------------------------------------------------------
# Section dispatch table — add new renderers here only
# ---------------------------------------------------------------------------

_RENDERERS: Dict[str, Callable] = {
    # Text / alerts
    "text":                _render_text,
    "markdown":            _render_text,
    "highlight_box":       _render_highlight_box,
    "alert":               _render_highlight_box,
    # Data grids
    "statistic_grid":      _render_statistic_grid,
    "key_value_list":      _render_key_value_list,
    "comparison_table":    _render_comparison_table,
    "table_advanced":      _render_comparison_table,
    # Charts (SVG / CSS)
    "bar_chart":           _render_bar_chart,
    "macro_chart":         _render_macro_chart,
    "calorie_ring":        _render_calorie_ring,
    "health_score_card":   _render_health_score_card,
    "nutrient_gauge":      _render_nutrient_gauge,
    # Food & nutrition
    "food_health_list":    _render_food_health_list,
    "nutrition_label":     _render_nutrition_label,
    # Restaurant
    "restaurant_list":     _render_restaurant_list,
    "ranking_list":        _render_ranking_list,
    # Layout helpers
    "progress_bar":        _render_progress_bar,
    "tabs":                _render_tabs,
    "tag_list":            _render_tag_list,
    "tip_card":            _render_tip_card,
    "meal_summary_row":    _render_meal_summary_row,
    "divider":             lambda _: '<div class="divider"></div>',
    "spacer":              lambda s: f'<div style="height:{max(4, min(int(s.get("height") or 10), 60))}px;"></div>',
    "columns":             _render_columns,
}


def _render_section(sec: Dict[str, Any]) -> str:
    renderer = _RENDERERS.get((sec.get("type") or "").strip().lower())
    if renderer is None:
        return ""
    try:
        return renderer(sec)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("[builder] render error in '%s': %s", sec.get("type"), exc)
        return ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_html(plan: Dict[str, Any]) -> str:
    summary = _e(plan.get("summary") or "")
    mode    = _e((plan.get("mode") or "").replace("_", " ").title())
    body    = "\n".join(
        _render_section(s)
        for s in (plan.get("sections") or [])
        if isinstance(s, dict) and s.get("type")
    )
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>Wabi \u2013 {mode}</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n<body>\n'
        '<div class="hdr-card">\n'
        '  <div class="hdr-logo">Wabi Assistant</div>\n'
        f'  <div class="hdr-title">{summary}</div>\n'
        f'  <div class="hdr-sub" style="color:#64748b;font-size:11px;">{mode}</div>\n'
        '</div>\n'
        f'{body}\n'
        f'<div class="footer">Wabi AI \u00b7 {mode}</div>\n'
        '</body>\n</html>'
    )