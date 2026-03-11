from __future__ import annotations
from typing import Any, Dict

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: "WenQuanYi Zen Hei","Noto Sans SC","Noto Sans","DejaVu Sans",
               "Liberation Sans", sans-serif;
  background: #f0f4f8;
  padding: 14px;
}
/* ── Cards ── */
.card {
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 2px 10px rgba(0,0,0,.07);
  padding: 16px;
  margin-bottom: 10px;
}
/* ── Header ── */
.hdr-title { font-size: 16px; font-weight: 700; color: #1e293b; }
.hdr-sub   { font-size: 12.5px; color: #64748b; margin-top: 3px; }
/* ── Section title ── */
.sec-ttl {
  font-size: 12px; font-weight: 600; color: #64748b;
  text-transform: uppercase; letter-spacing: .5px; margin-bottom: 8px;
}
/* ── Text ── */
.txt { font-size: 13.5px; line-height: 1.7; color: #334155; white-space: pre-wrap; }
/* ── Highlight / Alert ── */
.hbox {
  border-radius: 10px; padding: 11px 13px;
  font-size: 13px; line-height: 1.5;
}
.hbox-info    { background:#e0f2fe; border-left:4px solid #0ea5e9; color:#0c4a6e; }
.hbox-success { background:#dcfce7; border-left:4px solid #22c55e; color:#14532d; }
.hbox-warning { background:#fef9c3; border-left:4px solid #eab308; color:#713f12; }
.hbox-error   { background:#fee2e2; border-left:4px solid #ef4444; color:#7f1d1d; }
.hbox-default { background:#f1f5f9; border-left:4px solid #94a3b8; color:#334155; }
/* ── Key-value list ── */
.kvlist { border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; }
.kvrow {
  display:flex; justify-content:space-between; align-items:center;
  padding:9px 12px; border-bottom:1px solid #f1f5f9; font-size:13px;
}
.kvrow:last-child { border-bottom:none; }
.kv-k { color:#64748b; flex:1; }
.kv-v { font-weight:500; color:#1e293b; text-align:right; max-width:55%; }
/* ── Statistic grid ── */
.sg { display:grid; gap:8px; }
.sg-cell {
  background:#f8fafc; border:1px solid #e2e8f0;
  border-radius:10px; padding:11px; text-align:center;
}
.sg-label { font-size:11px; color:#64748b; margin-bottom:3px; }
.sg-value { font-size:18px; font-weight:700; color:#1e293b; }
.sg-unit  { font-size:11px; color:#94a3b8; }
/* ── Place table ── */
table { width:100%; border-collapse:collapse; font-size:12.5px; }
th {
  background:#f8fafc; font-weight:600; color:#475569;
  padding:7px 9px; border-bottom:2px solid #e2e8f0; text-align:left;
}
td { padding:7px 9px; border-bottom:1px solid #f1f5f9; color:#334155; }
tr:last-child td { border-bottom:none; }
.veg { display:inline-block; font-size:10px; padding:1px 6px;
       border-radius:9999px; background:#dcfce7; color:#166534; }
/* ── Tag list ── */
.taglist { display:flex; flex-wrap:wrap; gap:6px; }
.tag {
  background:#e0f2fe; color:#0c4a6e;
  border:1px solid #bae6fd; padding:4px 10px;
  border-radius:9999px; font-size:12px;
}
/* ── Bar chart ── */
.bar-wrap { display:flex; flex-direction:column; gap:7px; }
.bar-row  { display:flex; align-items:center; gap:8px; }
.bar-name {
  font-size:12px; color:#475569;
  min-width:90px; max-width:120px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.bar-bg   { flex:1; background:#e2e8f0; border-radius:9999px; height:9px; overflow:hidden; }
.bar-fill { height:100%; background:#3b82f6; border-radius:9999px; min-width:3px; }
.bar-val  { font-size:12px; color:#64748b; min-width:55px; text-align:right; }
/* ── Pie chart ── */
.pie-legend { display:flex; flex-direction:column; gap:5px; flex:1; }
.pie-row  { display:flex; align-items:center; gap:7px; }
.pie-dot  { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
.pie-name { font-size:12.5px; color:#475569; flex:1; }
.pie-pct  { font-size:12.5px; color:#1e293b; font-weight:500; }
/* ── Line chart ── */
.lc-wrap { overflow-x:auto; }
.lc-table { font-size:12px; color:#475569; }
/* ── Radar chart ── */
.radar-table { font-size:12px; }
/* ── Tabs ── */
.tab-strip { display:flex; gap:5px; flex-wrap:wrap; margin-bottom:9px; }
.tab-pill {
  padding:5px 12px; border:1.5px solid #e2e8f0; border-radius:9999px;
  background:#f8fafc; font-size:12px; color:#475569;
}
.tab-label { font-size:11px; font-weight:600; color:#0ea5e9; margin-bottom:3px; }
.tab-body  { font-size:13px; line-height:1.65; color:#334155; white-space:pre-wrap; }
/* ── Steps list ── */
.steps { display:flex; flex-direction:column; gap:8px; }
.step  { display:flex; gap:10px; align-items:flex-start; font-size:13px; }
.step-n {
  width:22px; height:22px; border-radius:50%;
  background:#3b82f6; color:#fff;
  font-size:11px; font-weight:700;
  display:flex; align-items:center; justify-content:center; flex-shrink:0;
}
/* ── Progress bar ── */
.pb-row { display:flex; justify-content:space-between; margin-bottom:5px; }
.pb-label { font-size:13px; color:#334155; }
.pb-pct   { font-size:12px; color:#64748b; }
.pb-bg { background:#e2e8f0; border-radius:9999px; height:10px; overflow:hidden; }
.pb-fill { height:100%; border-radius:9999px; min-width:3px; }
/* ── Card list ── */
.cl-item { border:1px solid #f1f5f9; border-radius:10px; padding:11px; margin-bottom:7px; }
.cl-title { font-size:14px; font-weight:600; color:#1e293b; }
.cl-sub   { font-size:12.5px; color:#64748b; margin-top:2px; }
.cl-badge {
  display:inline-block; font-size:11px; padding:2px 8px;
  border-radius:9999px; background:#e0f2fe; color:#0c4a6e; margin:5px 0;
}
/* ── Comparison table ── */
.cmp th { background:#eff6ff; color:#1d4ed8; }
/* ── Image ── */
.img-wrap { text-align:center; }
.img-wrap img {
  max-width:100%; height:auto;
  border-radius:12px; display:block; margin:0 auto;
}
.img-cap { font-size:11.5px; color:#94a3b8; margin-top:4px; }
/* ── Divider / Spacer ── */
.divider { height:1px; background:#e2e8f0; margin:4px 0; }
/* ── Footer ── */
.footer { text-align:center; font-size:11px; color:#cbd5e1; padding:6px 0 2px; }
"""

_PALETTE = [
    "#3b82f6","#10b981","#f59e0b","#ef4444",
    "#8b5cf6","#06b6d4","#f97316","#84cc16",
]

_PROGRESS_COLORS = {
    "primary": "#3b82f6", "success": "#22c55e",
    "warning": "#eab308", "error": "#ef4444",
}

def _e(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )

def _fmt_num(v: Any) -> str:
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(round(f, 1))
    except Exception:
        return str(v)

def _render_section(sec: Dict[str, Any]) -> str:
    t = (sec.get("type") or "text").strip().lower()
    title = sec.get("title") or ""
    ttl_html = f'<div class="sec-ttl">{_e(title)}</div>' if title else ""
    if t in ("text", "markdown"):
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="txt">{_e(sec.get("content",""))}</div></div>'
        )
    if t in ("highlight_box", "alert"):
        variant = (sec.get("variant") or "default").lower()
        if variant not in ("info", "success", "warning", "error"):
            variant = "default"
        content = sec.get("content") or sec.get("title") or ""
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="hbox hbox-{variant}">{_e(content)}</div></div>'
        )
    if t == "key_value_list":
        items = sec.get("items") or []
        rows  = "".join(
            f'<div class="kvrow">'
            f'<span class="kv-k">{_e(i.get("label",""))}</span>'
            f'<span class="kv-v">{_e(i.get("value",""))}</span>'
            f'</div>'
            for i in items if isinstance(i, dict)
        )
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="kvlist">{rows}</div></div>'
        )
    if t == "statistic_grid":
        cols = max(1, min(int(sec.get("columns") or 2), 4))
        cells = ""
        for i in (sec.get("items") or []):
            if not isinstance(i, dict):
                continue
            unit_html = f'<div class="sg-unit">{_e(i["unit"])}</div>' if i.get("unit") else ""
            cells += (
                f'<div class="sg-cell">'
                f'<div class="sg-label">{_e(i.get("label",""))}</div>'
                f'<div class="sg-value">{_e(i.get("value",""))}</div>'
                f'{unit_html}</div>'
            )
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="sg" style="grid-template-columns:repeat({cols},1fr);">'
            f'{cells}</div></div>'
        )
    if t == "inline_stat":
        unit  = f' {_e(sec.get("unit",""))}' if sec.get("unit") else ""
        trend = sec.get("trend") or ""
        trend_html = f' <span style="color:{"#22c55e" if trend=="+" else "#ef4444"};">{_e(trend)}</span>' if trend else ""
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="txt"><b>{_e(sec.get("label",""))}</b>: '
            f'{_e(sec.get("value",""))}{unit}{trend_html}</div></div>'
        )
    if t == "place_table":
        rows_html = ""
        for it in (sec.get("items") or []):
            if not isinstance(it, dict):
                continue
            veg = '<span class="veg">🌱 Veg</span>' if it.get("is_veg") else ""
            rows_html += (
                f"<tr><td>{_e(it.get('name',''))} {veg}</td>"
                f"<td>{_e(it.get('desc',''))}</td>"
                f"<td>⭐ {_e(it.get('rating','-'))}</td>"
                f"<td>{_e(it.get('price_str','-'))}</td>"
                f"<td>{_e(it.get('dist_str','-'))}</td></tr>"
            )
        return (
            f'<div class="card">{ttl_html}'
            f'<div style="overflow-x:auto;">'
            f'<table><thead><tr>'
            f'<th>Name</th><th>Dish</th><th>Rating</th><th>Price</th><th>Dist</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table></div></div>'
        )
    if t in ("table_advanced", "comparison_table"):
        cols_def = sec.get("columns") or []
        rows_def = sec.get("rows")    or []
        cls      = "cmp" if t == "comparison_table" else ""
        hdr = "".join(f"<th>{_e(c)}</th>" for c in cols_def)
        bdy = ""
        for row in rows_def:
            bdy += "<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in (row or [])) + "</tr>"
        foot = f'<div class="txt" style="font-size:11.5px;color:#94a3b8;margin-top:6px;">{_e(sec.get("footnote",""))}</div>' if sec.get("footnote") else ""
        return (
            f'<div class="card">{ttl_html}'
            f'<div style="overflow-x:auto;">'
            f'<table class="{cls}"><thead><tr>{hdr}</tr></thead>'
            f'<tbody>{bdy}</tbody></table></div>{foot}</div>'
        )
    if t == "bar_chart":
        items  = sec.get("items") or []
        unit   = sec.get("unit") or ""
        colors = sec.get("colors") or []
        vals   = []
        for it in items:
            try:
                vals.append(float(it.get("value", 0) or 0))
            except Exception:
                vals.append(0.0)
        max_v = max(vals) if vals else 1.0
        max_v = max_v if max_v > 0 else 1.0
        bars  = ""
        for idx, (it, v) in enumerate(zip(items, vals)):
            color = (colors[idx] if idx < len(colors) else None) or _PALETTE[idx % len(_PALETTE)]
            pct   = max(2, int(round(v / max_v * 100)))
            bars += (
                f'<div class="bar-row">'
                f'<div class="bar-name" title="{_e(it.get("label",""))}">{_e(it.get("label",""))}</div>'
                f'<div class="bar-bg"><div class="bar-fill" style="width:{pct}%;background:{color};"></div></div>'
                f'<div class="bar-val">{_fmt_num(v)} {_e(unit)}</div>'
                f'</div>'
            )
        return f'<div class="card">{ttl_html}<div class="bar-wrap">{bars}</div></div>'
    if t == "pie_chart":
        items  = sec.get("items") or []
        unit   = sec.get("unit") or ""
        colors = sec.get("colors") or []
        donut  = bool(sec.get("donut"))
        vals   = []
        for it in items:
            try:
                vals.append(float(it.get("value", 0) or 0))
            except Exception:
                vals.append(0.0)
        total = sum(vals) or 1.0
        stops, cur = [], 0.0
        for idx, v in enumerate(vals):
            c = (colors[idx] if idx < len(colors) else None) or _PALETTE[idx % len(_PALETTE)]
            pf = v / total * 100
            stops.append(f"{c} {cur:.1f}% {cur+pf:.1f}%")
            cur += pf
        pie_css = ", ".join(stops)
        donut_css = (
            '; mask:radial-gradient(circle, transparent 38%, black 39%);'
            '-webkit-mask:radial-gradient(circle, transparent 38%, black 39%);'
        ) if donut else ""
        legend = ""
        for idx, (it, v) in enumerate(zip(items, vals)):
            c   = (colors[idx] if idx < len(colors) else None) or _PALETTE[idx % len(_PALETTE)]
            pct = round(v / total * 100, 1)
            legend += (
                f'<div class="pie-row">'
                f'<div class="pie-dot" style="background:{c};"></div>'
                f'<div class="pie-name">{_e(it.get("label",""))}</div>'
                f'<div class="pie-pct">{_fmt_num(v)}{" "+_e(unit) if unit else ""}  ({pct}%)</div>'
                f'</div>'
            )
        return (
            f'<div class="card">{ttl_html}'
            f'<div style="display:flex;align-items:center;gap:14px;">'
            f'<div style="width:90px;height:90px;border-radius:50%;flex-shrink:0;'
            f'background:conic-gradient({pie_css});{donut_css}"></div>'
            f'<div class="pie-legend">{legend}</div>'
            f'</div></div>'
        )
    if t == "line_chart":
        points = sec.get("points") or []
        labels = sec.get("labels") or []
        unit   = sec.get("unit") or ""
        rows   = ""
        for idx, pt in enumerate(points):
            lbl = labels[idx] if idx < len(labels) else str(idx + 1)
            rows += f"<tr><td>{_e(lbl)}</td><td>{_fmt_num(pt)} {_e(unit)}</td></tr>"
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="lc-wrap"><table class="lc-table">'
            f'<thead><tr><th>Period</th><th>Value</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></div>'
        )
    if t == "radar_chart":
        axes   = sec.get("axes")   or []
        values = sec.get("values") or []
        max_v  = sec.get("max") or 100
        rows   = ""
        for idx, ax in enumerate(axes):
            v   = values[idx] if idx < len(values) else 0
            pct = max(2, int(round(float(v) / float(max_v or 1) * 100)))
            rows += (
                f'<div class="bar-row">'
                f'<div class="bar-name">{_e(ax)}</div>'
                f'<div class="bar-bg"><div class="bar-fill" style="width:{pct}%;background:#8b5cf6;"></div></div>'
                f'<div class="bar-val">{_fmt_num(v)}</div>'
                f'</div>'
            )
        return f'<div class="card">{ttl_html}<div class="bar-wrap">{rows}</div></div>'
    if t == "tabs":
        tabs      = sec.get("tabs") or []
        tab_strip = "".join(f'<div class="tab-pill">{_e(tb.get("label",""))}</div>' for tb in tabs)
        tab_body  = ""
        for tb in tabs:
            tab_body += (
                f'<div style="margin-bottom:9px;">'
                f'<div class="tab-label">{_e(tb.get("label",""))}</div>'
                f'<div class="tab-body">{_e(tb.get("content",""))}</div>'
                f'</div>'
            )
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="tab-strip">{tab_strip}</div>'
            f'{tab_body}</div>'
        )
    if t == "tag_list":
        tags_html = "".join(
            f'<span class="tag">{_e(tg)}</span>'
            for tg in (sec.get("tags") or [])
        )
        return f'<div class="card">{ttl_html}<div class="taglist">{tags_html}</div></div>'
    if t == "button_group":
        buttons   = sec.get("buttons") or []
        btn_style = {
            "primary":   "background:#2563eb;color:#fff;border:none;",
            "secondary": "background:#e2e8f0;color:#1e293b;border:none;",
            "outline":   "background:#fff;color:#334155;border:1.5px solid #cbd5e1;",
        }
        btns = ""
        for btn in buttons:
            variant = (btn.get("variant") or "outline").lower()
            style   = btn_style.get(variant, btn_style["outline"])
            btns += (
                f'<button style="padding:9px 14px;border-radius:10px;'
                f'font-size:13px;cursor:pointer;{style}">'
                f'{_e(btn.get("label",""))}</button>'
            )
        return (
            f'<div class="card">{ttl_html}'
            f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{btns}</div></div>'
        )
    if t == "progress_bar":
        label     = sec.get("label") or ""
        value     = float(sec.get("value") or 0)
        max_v     = float(sec.get("max") or 100) or 1.0
        variant   = (sec.get("variant") or "primary").lower()
        show_pct  = sec.get("show_percent", True)
        pct_val   = round(value / max_v * 100, 1)
        pct_int   = max(2, int(pct_val))
        color     = _PROGRESS_COLORS.get(variant, "#3b82f6")
        right_lbl = f"{pct_val}%" if show_pct else f"{_fmt_num(value)}/{_fmt_num(max_v)}"
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="pb-row"><div class="pb-label">{_e(label)}</div>'
            f'<div class="pb-pct">{_e(right_lbl)}</div></div>'
            f'<div class="pb-bg"><div class="pb-fill" '
            f'style="width:{pct_int}%;background:{color};"></div></div></div>'
        )
    if t == "steps_list":
        steps    = sec.get("steps") or []
        numbered = sec.get("numbered", True)
        icons    = sec.get("icons") or []
        items_html = ""
        for idx, step in enumerate(steps):
            marker = (
                icons[idx] if idx < len(icons) else
                (f'<div class="step-n">{idx+1}</div>' if numbered else
                 '<div class="step-n" style="background:#64748b;">•</div>')
            )
            if isinstance(marker, str) and not marker.startswith("<"):
                marker = f'<div class="step-n" style="background:none;font-size:16px;">{_e(marker)}</div>'
            items_html += f'<div class="step">{marker}<div>{_e(step)}</div></div>'
        return f'<div class="card">{ttl_html}<div class="steps">{items_html}</div></div>'
    if t == "collapsible_section":
        content = sec.get("content") or ""
        return (
            f'<div class="card">{ttl_html}'
            f'<div class="txt">{_e(content)}</div></div>'
        )
    if t == "card_list":
        items_html = ""
        for it in (sec.get("items") or []):
            if not isinstance(it, dict):
                continue
            img = f'<img src="{_e(it["image_url"])}" style="max-width:100%;border-radius:8px;margin-bottom:6px;"/>' if it.get("image_url") else ""
            badge = f'<span class="cl-badge">{_e(it["badge"])}</span>' if it.get("badge") else ""
            content = f'<div class="txt" style="margin-top:4px;">{_e(it.get("content",""))}</div>' if it.get("content") else ""
            items_html += (
                f'<div class="cl-item">{img}'
                f'<div class="cl-title">{_e(it.get("title",""))}</div>'
                f'<div class="cl-sub">{_e(it.get("subtitle",""))}</div>'
                f'{badge}{content}</div>'
            )
        return f'<div class="card">{ttl_html}{items_html}</div>'
    if t == "carousel":
        items_html = ""
        for it in (sec.get("items") or []):
            if not isinstance(it, dict):
                continue
            img = f'<img src="{_e(it["image_url"])}" style="max-width:100%;border-radius:8px;margin-bottom:5px;"/>' if it.get("image_url") else ""
            sub = f'<div class="cl-sub">{_e(it.get("subtitle",""))}</div>' if it.get("subtitle") else ""
            items_html += (
                f'<div style="min-width:160px;border:1px solid #e2e8f0;border-radius:10px;padding:10px;flex-shrink:0;">'
                f'{img}<div class="cl-title">{_e(it.get("title",""))}</div>{sub}</div>'
            )
        return (
            f'<div class="card">{ttl_html}'
            f'<div style="display:flex;gap:10px;overflow-x:auto;padding-bottom:4px;">'
            f'{items_html}</div></div>'
        )
    if t == "gallery_grid":
        cols = max(1, min(int(sec.get("columns") or 3), 4))
        imgs_html = ""
        for img in (sec.get("images") or []):
            if not isinstance(img, dict) or not img.get("src"):
                continue
            cap = f'<div class="img-cap">{_e(img.get("caption",""))}</div>' if img.get("caption") else ""
            imgs_html += (
                f'<div><img src="{_e(img["src"])}" '
                f'style="width:100%;border-radius:8px;"/>{cap}</div>'
            )
        return (
            f'<div class="card">{ttl_html}'
            f'<div style="display:grid;grid-template-columns:repeat({cols},1fr);gap:8px;">'
            f'{imgs_html}</div></div>'
        )
    if t == "image_display":
        url     = sec.get("image_url") or sec.get("url") or ""
        caption = sec.get("caption") or ""
        if not url:
            return ""
        cap_html = f'<div class="img-cap">{_e(caption)}</div>' if caption else ""
        return (
            f'<div class="card"><div class="img-wrap">'
            f'<img src="{_e(url)}" alt="{_e(caption)}"/>'
            f'{cap_html}</div></div>'
        )
    if t == "divider":
        return '<div class="divider"></div>'
    if t == "spacer":
        try:
            h = int(sec.get("height") or 10)
        except Exception:
            h = 10
        return f'<div style="height:{h}px;"></div>'
    if t == "custom_html":
        raw = sec.get("html_content") or ""
        return f'<div class="card">{ttl_html}{raw}</div>'
    return ""

def build_html(plan: Dict[str, Any]) -> str:
    summary = _e(plan.get("summary") or "")
    mode    = _e((plan.get("mode") or "").replace("_", " ").title())
    body    = "\n".join(
        _render_section(s)
        for s in (plan.get("sections") or [])
        if isinstance(s, dict) and s.get("type")
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wabi – {mode}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="card" style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);color:#fff;padding:18px;">
  <div class="hdr-title" style="color:#fff;">Wabi Assistant</div>
  <div class="hdr-sub"   style="color:#94a3b8;">{summary}</div>
</div>
{body}
<div class="footer">Wabi AI · {mode}</div>
</body>
</html>"""
