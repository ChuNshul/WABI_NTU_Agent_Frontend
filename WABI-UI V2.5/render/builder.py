"""
builder.py — HTML renderer for Wabi UI plans.

Accepts a Plan dataclass (from plan.py) or a raw dict (backward compat).

Visual redesign vs original
───────────────────────────────────────────────────────────────────────────
                      before                    after
  Theme               white cards, #f0f4f8 bg   GitHub-dark (#0d1117 base)
  Colors              hardcoded hex everywhere  CSS custom properties (:root)
  Typography          mixed sizes, no scale     4-step scale + tabular-nums
  SVG charts          flat single-colour fill   linearGradient arcs
  Header              plain linear-gradient     mesh orb + -webkit-bg-clip text
  Highlight box       pastel background         dark tinted + accent border
  Stat grid           light #f8fafc cells       dark elevated glass cells
  Bar chart           grey track               dark track + gradient fill
  Health gauge        flat grey arc            gradient arc red→green
  Calorie ring        solid blue arc           purple→cyan gradient
  Macro donut         flat per-colour arcs     gradient per-macro arcs
  Nutrient gauge      solid colour arc         same colour + glow via CSS
  Rank badges         light pastel             dark tinted gold/silver/bronze
  Tip card            pastel bg                dark tinted + accent left-border
  Restaurant chips    pastel bg                dark glass chips
───────────────────────────────────────────────────────────────────────────

Zero JavaScript — all charts are pure SVG.
Playwright/Chromium supports every CSS feature used here:
  CSS custom properties, linearGradient, -webkit-background-clip:text,
  backdrop-filter, font-variant-numeric:tabular-nums, filter:drop-shadow.
"""
from __future__ import annotations

import math
from html import escape as _esc
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.plan import Plan

# ---------------------------------------------------------------------------
# Design tokens  (the ONLY place colours live)
# ---------------------------------------------------------------------------

_TOKENS = """\
:root{
  /* surfaces */
  --bg:#0b1020;
  --card:#0f172a;
  --s1:rgba(2,6,23,.30);
  --s2:rgba(255,255,255,.03);
  --s3:rgba(255,255,255,.05);
  /* borders */
  --b0:rgba(148,163,184,.08);
  --b1:rgba(148,163,184,.15);
  --b2:rgba(148,163,184,.22);
  --b3:rgba(148,163,184,.35);
  /* text */
  --t1:#e5e7eb;
  --t2:#94a3b8;
  --t3:rgba(148,163,184,.35);
  /* semantic */
  --ok:#22c55e;    --ok-muted:rgba(34,197,94,.10);
  --warn:#f59e0b;  --warn-muted:rgba(245,158,11,.10);
  --err:#fb7185;   --err-muted:rgba(251,113,133,.10);
  --info:#38bdf8;  --info-muted:rgba(56,189,248,.10);
  /* accent */
  --accent:#fbbf24;
  --accent2:#fde047;
  --tintA:rgba(251,191,36,.14);
  --tintB:rgba(251,191,36,.06);
  --tintC:rgba(253,224,71,.05);
  --pillBg:rgba(251,191,36,.92);
  --pillBorder:rgba(251,191,36,.62);
  --pillText:#2b1700;
  --grad:linear-gradient(90deg,var(--accent),var(--accent2));
  /* radii */
  --r1:6px;--r2:10px;--r3:14px;--r4:20px;
}

body[data-mode="recommendation"]{
  --accent:#f97316;
  --accent2:#fbbf24;
  --tintA:rgba(249,115,22,.14);
  --tintB:rgba(249,115,22,.06);
  --tintC:rgba(251,191,36,.05);
  --pillBg:rgba(249,115,22,.92);
  --pillBorder:rgba(249,115,22,.62);
  --pillText:#2b1700;
}
body[data-mode="chitchat"]{
  --accent:#a78bfa;
  --accent2:#60a5fa;
  --tintA:rgba(167,139,250,.14);
  --tintB:rgba(167,139,250,.06);
  --tintC:rgba(96,165,250,.05);
  --pillBg:rgba(167,139,250,.92);
  --pillBorder:rgba(167,139,250,.62);
  --pillText:#1f1147;
}
body[data-mode="goalplanning"]{
  --accent:#3b82f6;
  --accent2:#fbbf24;
  --tintA:rgba(59,130,246,.14);
  --tintB:rgba(59,130,246,.06);
  --tintC:rgba(251,191,36,.05);
  --pillBg:rgba(59,130,246,.92);
  --pillBorder:rgba(59,130,246,.62);
  --pillText:#0b1020;
}
"""

# ---------------------------------------------------------------------------
# Utility CSS  (frozen Tailwind-compatible subset)
# ---------------------------------------------------------------------------

_UTIL = """\
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:auto}
body{
  font-family:"Noto Sans SC","Noto Sans",system-ui,sans-serif;
  background:var(--bg);color:var(--t1);
  display:flex;justify-content:center;
  padding:10px 4px 12px;
  font-size:13.5px;line-height:1.65;
  -webkit-font-smoothing:antialiased;
}
.shell{
  width:100%;
  max-width:440px;
  position:relative;
  padding:12px 12px 10px;
  border:1px solid var(--b1);
  border-radius:var(--r4);
  background-color:var(--card);
  background-image:
    radial-gradient(circle at 50% 0%, var(--tintA) 0%, transparent 75%),
    radial-gradient(circle at 0% 100%, var(--tintB) 0%, transparent 52%),
    radial-gradient(circle at 100% 0%, var(--tintC) 0%, transparent 40%);
  box-shadow:0 20px 50px rgba(0,0,0,.6), inset 0 0 0 1px rgba(255,255,255,.05);
}
.hdr{
  margin-bottom:12px;
  position:relative;
  overflow:hidden;
  border-radius:var(--r4);
  border:1px solid var(--b1);
  background:
    radial-gradient(circle at 90% 10%, var(--tintC), transparent 60%),
    radial-gradient(circle at 15% 0%, var(--tintA), transparent 70%),
    rgba(2,6,23,.22);
  padding:16px 16px 14px;
}
.brand{
  font-weight:700;
  color:var(--accent);
  font-size:12px;
  opacity:.85;
  text-transform:uppercase;
  letter-spacing:.05em;
  margin-bottom:6px;
}
.hdr-title{
  font-size:22px;
  font-weight:900;
  letter-spacing:-0.02em;
  display:flex;
  align-items:center;
  gap:10px;
  color:#fff;
}
.pill{
  font-size:10px;
  color:var(--pillText);
  border:1px solid var(--pillBorder);
  background:var(--pillBg);
  padding:2px 8px;
  border-radius:6px;
  font-weight:900;
}
.sub{
  color:var(--t2);
  font-size:13px;
  margin-top:6px;
  line-height:1.4;
}
/* flex / grid */
.flex{display:flex}.flex-col{flex-direction:column}
.flex-1{flex:1 1 0%}.flex-shrink-0{flex-shrink:0}.min-w-0{min-width:0}
.items-center{align-items:center}.items-start{align-items:flex-start}
.items-baseline{align-items:baseline}.items-end{align-items:flex-end}
.justify-between{justify-content:space-between}.justify-center{justify-content:center}
.gap-1{gap:4px}.gap-2{gap:8px}.gap-3{gap:12px}.gap-4{gap:16px}.gap-5{gap:20px}
.grid{display:grid}
.grid2{grid-template-columns:repeat(2,minmax(0,1fr))}
.grid3{grid-template-columns:repeat(3,minmax(0,1fr))}
.grid4{grid-template-columns:repeat(4,minmax(0,1fr))}
/* spacing */
.p3{padding:12px}.p4{padding:16px}.px3{padding-left:12px;padding-right:12px}
.py2{padding-top:8px;padding-bottom:8px}
.mb1{margin-bottom:4px}.mb2{margin-bottom:8px}.mb3{margin-bottom:12px}
.mt1{margin-top:4px}.mt2{margin-top:8px}.ml-auto{margin-left:auto}
/* text sizes */
.txt-2xs{font-size:10px;line-height:1.4}
.txt-xs{font-size:11.5px;line-height:1.5}
.txt-sm{font-size:12.5px;line-height:1.6}
.txt-base{font-size:14px;line-height:1.7}
.txt-lg{font-size:16px}.txt-xl{font-size:20px}
.txt-2xl{font-size:24px;line-height:1.3}.txt-3xl{font-size:30px;line-height:1.2}
/* weights & misc */
.fw5{font-weight:500}.fw6{font-weight:600}.fw7{font-weight:700}.fw9{font-weight:900}
.upper{text-transform:uppercase}.track{letter-spacing:.12em}
.tabnum{font-variant-numeric:tabular-nums}
.truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.clamp2{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pre{white-space:pre-wrap}.break{word-break:break-word;overflow-wrap:break-word}
.text-right{text-align:right}.text-center{text-align:center}
/* colours */
.c1{color:var(--t1)}.c2{color:var(--t2)}.c3{color:var(--t3)}
.ok{color:var(--ok)}.warn{color:var(--warn)}.err{color:var(--err)}.info{color:var(--info)}
.grad-text{
  background:var(--grad);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.hdr .grad-text{
  background:none;
  -webkit-text-fill-color:#ffffff;
  color:#ffffff;
}
/* layout helpers */
.col-row{display:flex;gap:10px;margin-bottom:10px;align-items:flex-start}
.col-row>.card{flex:1;margin-bottom:0}
.overflow-x{overflow-x:auto}
.relative{position:relative}.absolute{position:absolute}.overflow-h{overflow:hidden}
.inset-0{inset:0}.pointer-none{pointer-events:none}
"""

# ---------------------------------------------------------------------------
# Component CSS
# ---------------------------------------------------------------------------

_COMP = """\
/* ── Card ── */
.card{
  background:var(--s1);border:1px solid var(--b1);
  border-radius:16px;padding:14px;margin-bottom:12px;overflow:hidden;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.03);
}
/* ── Section title ── */
.sec-ttl{
  font-size:10px;font-weight:700;color:var(--t3);
  text-transform:uppercase;letter-spacing:.14em;margin-bottom:12px;
}
/* ── Badge ── */
.badge{
  display:inline-flex;align-items:center;gap:4px;
  padding:2px 9px;border-radius:9999px;
  font-size:10.5px;font-weight:600;white-space:nowrap;
}
.b-ok{background:var(--ok-muted);color:var(--ok)}
.b-warn{background:var(--warn-muted);color:var(--warn)}
.b-err{background:var(--err-muted);color:var(--err)}
.b-info{background:var(--info-muted);color:var(--info)}
.b-def{background:rgba(240,246,252,.07);color:var(--t2)}
/* ── Highlight box ── */
.hbox{
  display:flex;gap:10px;align-items:flex-start;
  border-left:3px solid;border-radius:0 var(--r2) var(--r2) 0;
  padding:12px 14px 12px 15px;font-size:13px;line-height:1.7;
  word-break:break-word;
}
.hbox-info{background:var(--info-muted);border-color:var(--info)}
.hbox-ok{background:var(--ok-muted);border-color:var(--ok)}
.hbox-warn{background:var(--warn-muted);border-color:var(--warn)}
.hbox-err{background:var(--err-muted);border-color:var(--err)}
/* ── Stat grid ── */
.sg-cell{
  background:var(--s2);border:1px solid var(--b1);
  border-radius:14px;padding:12px 10px;text-align:center;
}
.sg-ok{border-color:rgba(63,185,80,.25);background:rgba(63,185,80,.06)}
.sg-warn{border-color:rgba(210,153,34,.25);background:rgba(210,153,34,.06)}
.sg-err{border-color:rgba(248,81,73,.25);background:rgba(248,81,73,.06)}
/* ── KV list ── */
.kvlist{border:1px solid var(--b1);border-radius:var(--r2);overflow:hidden}
.kvrow,.kvrow-s{border-bottom:1px solid var(--b0);font-size:13px}
.kvrow{display:flex;justify-content:space-between;align-items:baseline;padding:9px 13px;gap:8px}
.kvrow:last-child,.kvrow-s:last-child{border-bottom:none}
.kvrow-hl{background:rgba(124,58,237,.08)}
.kv-k{color:var(--t2);flex-shrink:0;max-width:50%;word-break:break-word}
.kv-v{font-weight:600;color:var(--t1);text-align:right;word-break:break-word;min-width:0}
.kvrow-s{display:flex;flex-direction:column;padding:10px 13px}
.kv-k-s{color:var(--t3);font-size:11px;font-weight:500;margin-bottom:3px}
.kv-v-s{font-weight:600;color:var(--t1);line-height:1.5;word-break:break-word}
/* ── Bar chart ── */
.bar-wrap{display:flex;flex-direction:column;gap:10px}
.bar-row{display:flex;align-items:center;gap:10px}
.bar-name{font-size:12px;color:var(--t2);min-width:88px;max-width:160px;flex-shrink:0;line-height:1.3}
.bar-track{flex:1;background:var(--s2);border-radius:9999px;height:8px;overflow:hidden;border:1px solid var(--b0)}
.bar-val{font-size:11.5px;color:var(--t2);min-width:50px;text-align:right;white-space:nowrap}
/* ── Progress bar ── */
.pb-track{background:var(--s2);border-radius:9999px;height:10px;overflow:hidden;border:1px solid var(--b0)}
/* ── Tags ── */
.taglist{display:flex;flex-wrap:wrap;gap:6px}
.tag{background:var(--s2);color:var(--t2);border:1px solid var(--b1);padding:3px 10px;border-radius:9999px;font-size:11.5px}
/* ── Tabs ── */
.tab-pills{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
.tab-pill{padding:3px 12px;border:1px solid var(--b2);border-radius:9999px;background:var(--s2);font-size:11.5px;color:var(--t2);font-weight:500}
.tab-sec{margin-bottom:8px}.tab-sec:last-child{margin-bottom:0}
.tab-lbl{font-size:11.5px;font-weight:700;color:var(--info);margin-bottom:3px}
.tab-body{font-size:13px;line-height:1.65;color:var(--t2);white-space:pre-wrap}
/* ── Table ── */
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{background:var(--s2);font-weight:600;color:var(--t2);padding:9px 12px;border-bottom:1px solid var(--b2);text-align:left}
td{padding:8px 12px;border-bottom:1px solid var(--b0);color:var(--t1);word-break:break-word}
tr:last-child td{border-bottom:none}
.tbl-num{text-align:right;font-weight:500;font-variant-numeric:tabular-nums}
/* ── Nutrition label ── */
.nl-wrap{border:2px solid var(--b2);border-radius:var(--r2);padding:12px 14px;background:var(--s2)}
.nl-title{font-size:22px;font-weight:900;color:var(--t1);line-height:1}
.nl-srv{font-size:11px;color:var(--t2);margin:4px 0 8px}
.nl-cal{display:flex;justify-content:space-between;align-items:baseline;border-top:7px solid var(--b2);border-bottom:3px solid var(--b2);padding:5px 0}
.nl-cal-lbl{font-size:13px;font-weight:700;color:var(--t1)}
.nl-cal-val{font-size:28px;font-weight:900;color:var(--t1)}
.nl-dvhdr{font-size:10px;text-align:right;color:var(--t2);border-bottom:1px solid var(--b1);padding-bottom:3px;margin-bottom:2px}
.nl-row{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--b0);padding:4px 0}
.nl-row:last-child{border-bottom:none}
.nl-bold{font-weight:700;color:var(--t1)}.nl-indent{padding-left:14px;color:var(--t2)}
.nl-thick{border-bottom:3px solid var(--b2)}
.nl-dv{font-weight:700;color:var(--t1)}.nl-dv-warn{font-weight:700;color:var(--warn)}
/* ── Ranking ── */
.rank-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--b0)}
.rank-item:last-child{border-bottom:none}
.rank-badge{width:28px;height:28px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800}
.rk1{background:rgba(212,172,13,.15);color:#d4ac0d;border:1px solid rgba(212,172,13,.3)}
.rk2{background:rgba(140,148,156,.12);color:#8b949e;border:1px solid rgba(140,148,156,.25)}
.rk3{background:rgba(204,120,50,.15);color:#d4854a;border:1px solid rgba(204,120,50,.3)}
.rkn{background:var(--s2);color:var(--t3);border:1px solid var(--b1)}
.rank-name{flex:1;font-size:13px;font-weight:600;color:var(--t1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rank-sub{font-size:11.5px;color:var(--t2);margin-top:1px}
.rank-val{font-size:13px;font-weight:700;color:var(--t1);text-align:right;white-space:nowrap}
/* ── Tip card ── */
.tip-card{display:flex;gap:12px;align-items:flex-start;border-radius:var(--r2);padding:14px;border-left:3px solid}
.tip-title{font-size:13px;font-weight:700;margin-bottom:4px}
.tip-body{font-size:12.5px;line-height:1.6;color:var(--t2)}
/* ── Meal row ── */
.meal-row{display:grid;gap:8px}
.meal-slot{display:flex;align-items:center;gap:10px;background:var(--s2);border:1px solid var(--b1);border-radius:var(--r2);padding:10px 12px}
.meal-icon{font-size:18px;flex-shrink:0}
.meal-name{font-size:12px;font-weight:600;color:var(--t2);margin-bottom:2px}
.meal-cal{font-size:15px;font-weight:800;color:var(--t1)}
.meal-cal-u{font-size:10px;color:var(--t3);font-weight:400}
.meal-bar-bg{background:var(--s3);border-radius:9999px;height:5px;margin-top:4px;overflow:hidden}
.meal-bar-fill{height:100%;border-radius:9999px;min-width:3px}
/* ── Food health list ── */
.fhl-item{padding:12px;background:var(--s2);border:1px solid var(--b1);border-radius:var(--r2);margin-bottom:8px}
.fhl-item:last-child{margin-bottom:0}
.fhl-name{font-size:13.5px;font-weight:700;color:var(--t1);margin-bottom:4px}
/* ── Restaurant ── */
.rst-item{padding:14px;background:var(--s2);border:1px solid var(--b1);border-radius:var(--r2);margin-bottom:8px}
.rst-item:last-child{margin-bottom:0}
.rst-name{font-size:14px;font-weight:700;color:var(--t1);margin-bottom:6px}
.rst-chips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px}
.rst-chip{display:inline-flex;align-items:center;padding:2px 8px;border:1px solid var(--b1);border-radius:9999px;font-size:11px;color:var(--t2);background:var(--s3)}
.rst-dish{font-size:12px;color:var(--t2);padding:3px 0;border-bottom:1px solid var(--b0)}
.rst-dish:last-child{border-bottom:none}
/* ── Misc ── */
.divider{height:1px;background:var(--b1);margin:4px 0}
.footer{text-align:center;font-size:10px;color:var(--t3);padding:10px 0 4px;letter-spacing:.08em}
"""

_CSS = _TOKENS + _UTIL + _COMP

# ---------------------------------------------------------------------------
# Gradient palette for bar/chart fills
# ---------------------------------------------------------------------------

_GRAD_PAIRS: List[Tuple[str, str]] = [
    ("#7c3aed", "#0891b2"),  # purple → cyan   (primary)
    ("#2563eb", "#06b6d4"),  # blue   → sky
    ("#d97706", "#f97316"),  # amber  → orange
    ("#059669", "#10b981"),  # emerald gradient
    ("#9333ea", "#ec4899"),  # purple → pink
    ("#0891b2", "#10b981"),  # cyan   → green
    ("#f59e0b", "#ef4444"),  # amber  → red (risky)
]

def _pair(i: int) -> Tuple[str, str]:
    return _GRAD_PAIRS[i % len(_GRAD_PAIRS)]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _e(v: Any) -> str:
    return _esc(str(v) if v is not None else "", quote=True)

def _n(v: Any) -> str:
    """Format a number removing unnecessary decimals."""
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(round(f, 1))
    except Exception:
        return str(v) if v is not None else ""

def _f(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or 0)
    except Exception:
        return d

def _ttl(t: Optional[str]) -> str:
    return f'<div class="sec-ttl">{_e(t)}</div>' if t else ""

def _badge(text: str, cls: str = "b-def") -> str:
    return f'<span class="badge {cls}">{_e(text)}</span>'

def _health_badge(ok: Any) -> str:
    if ok is True:  return _badge("✓ Healthy", "b-ok")
    if ok is False: return _badge("✗ Caution", "b-err")
    return _badge("— Unknown", "b-def")

def _score_grade(s: float) -> str:
    return "A" if s>=85 else "B" if s>=70 else "C" if s>=55 else "D" if s>=40 else "F"

def _score_color(s: float) -> str:
    return "var(--ok)" if s>=70 else "var(--warn)" if s>=45 else "var(--err)"

def _variant_color(v: str) -> str:
    return {"success":"var(--ok)","ok":"var(--ok)",
            "warning":"var(--warn)","caution":"var(--warn)",
            "error":"var(--err)","danger":"var(--err)",
            "info":"var(--info)"}.get((v or "").lower(), "var(--t2)")

def _traffic_color(ratio: float) -> str:
    return "var(--err)" if ratio>=0.80 else "var(--warn)" if ratio>=0.60 else "var(--ok)"

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_lgrad(gid: str, c1: str, c2: str, x1=0, y1=0, x2=1, y2=0) -> str:
    return (
        f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'gradientUnits="objectBoundingBox">'
        f'<stop offset="0%" stop-color="{c1}"/>'
        f'<stop offset="100%" stop-color="{c2}"/>'
        f'</linearGradient>'
    )

# ---------------------------------------------------------------------------
# Component renderers
# ---------------------------------------------------------------------------

def _render_text(s: Dict) -> str:
    tone = (s.get("tone") or "neutral").lower()
    cls  = {"positive":"ok","warning":"warn","error":"err"}.get(tone, "c2")
    return (
        f'<div class="card">{_ttl(s.get("title"))}'
        f'<div class="txt-sm {cls} pre break">{_e(s.get("content",""))}</div></div>'
    )


def _render_highlight_box(s: Dict) -> str:
    v   = (s.get("variant") or "info").lower()
    cls = {"info":"hbox-info","success":"hbox-ok","warning":"hbox-warn","error":"hbox-err"}.get(v,"hbox-info")
    icon= {"info":"ℹ","success":"✓","warning":"⚠","error":"✕"}.get(v,"ℹ")
    ic  = {"info":"var(--info)","success":"var(--ok)","warning":"var(--warn)","error":"var(--err)"}.get(v,"var(--info)")
    return (
        f'<div class="card"><div class="hbox {cls}">'
        f'<span style="color:{ic};flex-shrink:0;font-size:14px;line-height:1.4">{icon}</span>'
        f'<div class="flex-1 min-w-0">{_e(s.get("content") or s.get("title",""))}</div>'
        f'</div></div>'
    )


def _render_statistic_grid(s: Dict) -> str:
    cols = max(2, min(int(s.get("columns") or 2), 4))
    cells = ""
    for it in (s.get("items") or []):
        if not isinstance(it, dict): continue
        v   = (it.get("variant") or "default").lower()
        xc  = {"success":"sg-ok","ok":"sg-ok","warning":"sg-warn","caution":"sg-warn",
               "error":"sg-err","danger":"sg-err"}.get(v, "")
        vc  = _variant_color(v) if v not in ("default","") else "var(--t1)"
        u   = f'<div class="txt-2xs c3 mt1 tabnum">{_e(it["unit"])}</div>' if it.get("unit") else ""
        cells += (
            f'<div class="sg-cell {xc}">'
            f'<div class="txt-xs c2 upper track mb1">{_e(it.get("label",""))}</div>'
            f'<div class="txt-2xl fw9 tabnum" style="color:{vc}">{_e(it.get("value",""))}</div>'
            f'{u}</div>'
        )
    return f'<div class="card">{_ttl(s.get("title"))}<div class="grid gap-2 grid{cols}">{cells}</div></div>'


def _render_key_value_list(s: Dict) -> str:
    items = [i for i in (s.get("items") or []) if isinstance(i, dict)]
    if not items: return f'<div class="card">{_ttl(s.get("title"))}</div>'
    stacked = any(len(str(i.get("label","")))+len(str(i.get("value","")))>65 for i in items)
    rows = ""
    for it in items:
        hl = "kvrow-hl" if it.get("highlight") else ""
        if stacked:
            rows += (f'<div class="kvrow-s {hl}">'
                     f'<div class="kv-k-s">{_e(it.get("label",""))}</div>'
                     f'<div class="kv-v-s">{_e(it.get("value",""))}</div></div>')
        else:
            rows += (f'<div class="kvrow {hl}">'
                     f'<span class="kv-k">{_e(it.get("label",""))}</span>'
                     f'<span class="kv-v">{_e(it.get("value",""))}</span></div>')
    return f'<div class="card">{_ttl(s.get("title"))}<div class="kvlist">{rows}</div></div>'


def _render_bar_chart(s: Dict) -> str:
    items  = [i for i in (s.get("items") or []) if isinstance(i, dict)]
    if not items: return ""
    unit   = s.get("unit") or ""
    colors = list(s.get("colors") or [])
    vals   = [_f(i.get("value")) for i in items]
    mx     = max(vals, default=1.0) or 1.0
    bars   = ""
    for idx, (it, val) in enumerate(zip(items, vals)):
        c1, c2  = _pair(idx)
        custom  = colors[idx] if idx < len(colors) else None
        pct     = max(3, round(val / mx * 100))
        gid     = f"bg{idx}"
        fill    = custom if custom else f"url(#{gid})"
        defs    = (f'<defs>{_svg_lgrad(gid,c1,c2)}</defs>' if not custom else "")
        bars += (
            f'<div class="bar-row">'
            f'<div class="bar-name clamp2" title="{_e(it.get("label",""))}">'
            f'{_e(it.get("label",""))}</div>'
            f'<div class="bar-track">'
            f'<svg style="width:{pct}%;height:8px;display:block">'
            f'{defs}<rect width="100%" height="8" fill="{fill}" rx="4"/></svg>'
            f'</div>'
            f'<div class="bar-val tabnum">{_n(val)}{"&nbsp;"+_e(unit) if unit else ""}</div>'
            f'</div>'
        )
    return f'<div class="card">{_ttl(s.get("title"))}<div class="bar-wrap">{bars}</div></div>'


def _render_macro_chart(s: Dict) -> str:
    P, C, F = _f(s.get("protein_g")), _f(s.get("carb_g")), _f(s.get("fat_g"))
    kcal    = _f(s.get("total_kcal")) or (P*4+C*4+F*9)
    total   = P+C+F
    if total <= 0: return ""

    CX, CY, R, SW = 70, 70, 52, 16
    circ = 2*math.pi*R
    segs = [
        ("mp", P, "#58a6ff", "#7c3aed"),
        ("mc", C, "#f59e0b", "#f97316"),
        ("mf", F, "#3fb950", "#06b6d4"),
    ]
    defs_html, arcs_html, offset = "", "", 0.0
    for gid, val, c1, c2 in segs:
        if val <= 0: continue
        dash = val/total*circ
        defs_html += _svg_lgrad(gid, c1, c2)
        arcs_html += (
            f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="url(#{gid})" '
            f'stroke-width="{SW}" stroke-linecap="round" '
            f'stroke-dasharray="{dash:.2f} {circ:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {CX} {CY})"/>'
        )
        offset += dash

    ct = _n(kcal) if kcal > 0 else _n(total)
    cb = "kcal" if kcal > 0 else "g"
    donut = (
        f'<svg width="140" height="140" viewBox="0 0 140 140" style="flex-shrink:0">'
        f'<defs>{defs_html}</defs>'
        f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="var(--s2)" stroke-width="{SW+2}"/>'
        f'{arcs_html}'
        f'<text x="{CX}" y="{CY-5}" text-anchor="middle" dominant-baseline="central" '
        f'fill="var(--t1)" font-size="19" font-weight="900" font-family="inherit">{_e(ct)}</text>'
        f'<text x="{CX}" y="{CY+14}" text-anchor="middle" '
        f'fill="var(--t3)" font-size="10" font-family="inherit">{_e(cb)}</text>'
        f'</svg>'
    )
    legend = ""
    for (_, lbl_short), val, col in zip(
        [("mp","Protein"),("mc","Carbs"),("mf","Fat")],
        [P, C, F],
        ["#58a6ff","#f59e0b","#3fb950"]
    ):
        pct = max(1, round(val/total*100))
        legend += (
            f'<div class="flex items-center gap-2 mb2">'
            f'<div style="width:9px;height:9px;border-radius:50%;background:{col};flex-shrink:0"></div>'
            f'<div class="txt-sm c2 flex-1">{lbl_short}</div>'
            f'<div class="txt-sm fw6 c1 tabnum">{_n(val)}'
            f'<span class="txt-2xs c3"> g ({pct}%)</span></div>'
            f'</div>'
        )
    # correct variable name
    labels = [("Protein", P, "#58a6ff"), ("Carbs", C, "#f59e0b"), ("Fat", F, "#3fb950")]
    legend = ""
    for lbl_name, val, col in labels:
        pct = max(1, round(val/total*100))
        legend += (
            f'<div class="flex items-center gap-2 mb2">'
            f'<div style="width:9px;height:9px;border-radius:50%;background:{col};flex-shrink:0"></div>'
            f'<div class="txt-sm c2 flex-1">{lbl_name}</div>'
            f'<div class="txt-sm fw6 c1 tabnum">{_n(val)}'
            f'<span class="txt-2xs c3"> g ({pct}%)</span></div>'
            f'</div>'
        )
    return (
        f'<div class="card">{_ttl(s.get("title") or "Macronutrients")}'
        f'<div class="flex items-center gap-4">{donut}'
        f'<div class="flex-1 min-w-0">{legend}</div></div></div>'
    )


def _render_calorie_ring(s: Dict) -> str:
    consumed = _f(s.get("consumed"))
    target   = _f(s.get("target")) or 2000.0
    ratio    = min(consumed/target, 1.1) if target else 0
    remaining = max(0.0, target-consumed)
    ring_col = "var(--ok)" if ratio<=0.75 else "var(--warn)" if ratio<=0.95 else "var(--err)"

    CX, CY, R, SW = 80, 80, 64, 13
    circ = 2*math.pi*R
    fill = min(ratio, 1.0)*circ

    svg = (
        f'<svg width="160" height="160" viewBox="0 0 160 160" style="flex-shrink:0">'
        f'<defs>{_svg_lgrad("crg","#7c3aed","#0891b2")}</defs>'
        f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="var(--s2)" stroke-width="{SW+2}"/>'
        f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="url(#crg)" '
        f'stroke-width="{SW}" stroke-dasharray="{fill:.2f} {circ:.2f}" '
        f'stroke-linecap="round" transform="rotate(-90 {CX} {CY})"/>'
        f'<text x="{CX}" y="{CY-8}" text-anchor="middle" dominant-baseline="central" '
        f'fill="var(--t1)" font-size="22" font-weight="900" font-family="inherit">{_e(_n(remaining))}</text>'
        f'<text x="{CX}" y="{CY+12}" text-anchor="middle" '
        f'fill="var(--t3)" font-size="10" font-family="inherit">kcal left</text>'
        f'<text x="{CX}" y="{CY+27}" text-anchor="middle" '
        f'fill="{ring_col}" font-size="11" font-weight="700" font-family="inherit">'
        f'{int(ratio*100)}%</text>'
        f'</svg>'
    )
    breakdown = [b for b in (s.get("breakdown") or []) if isinstance(b, dict)]
    bkd = ""
    for b in breakdown[:4]:
        bv   = _f(b.get("value"))
        bp   = max(2, int(bv/target*100)) if target else 2
        bcol = b.get("color") or "#7c3aed"
        bkd += (
            f'<div class="flex items-center gap-2 mb1">'
            f'<div class="txt-xs c2" style="min-width:64px">{_e(b.get("label",""))}</div>'
            f'<div style="flex:1;height:5px;background:var(--s3);border-radius:9999px;overflow:hidden">'
            f'<div style="width:{bp}%;height:100%;background:{bcol};border-radius:9999px"></div></div>'
            f'<div class="txt-xs c2 tabnum" style="min-width:38px;text-align:right">{_n(bv)}</div>'
            f'</div>'
        )
    side = (
        f'<div class="flex-1 min-w-0">'
        f'<div class="mb3">'
        f'<div class="txt-2xs c3 upper track mb1">Consumed</div>'
        f'<div class="txt-2xl fw9 tabnum c1">{_n(consumed)}'
        f'<span class="txt-xs c3 fw5"> kcal</span></div></div>'
        f'{bkd}</div>'
    )
    return (
        f'<div class="card">{_ttl(s.get("title") or "Calorie Intake")}'
        f'<div class="flex items-center gap-4">{svg}{side}</div></div>'
    )


def _render_health_score_card(s: Dict) -> str:
    score = max(0.0, min(_f(s.get("score")), 100.0))
    grade = _score_grade(score)
    color = _score_color(score)

    CX, CY, R, SW = 110, 100, 84, 15
    circ  = 2*math.pi*R
    half  = circ/2
    fill  = (score/100)*half

    def zone(sp: float, ep: float, col: str) -> str:
        sl = sp/100*half
        ln = (ep-sp)/100*half
        return (
            f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="{col}" '
            f'stroke-width="{SW+4}" opacity=".15" '
            f'stroke-dasharray="{ln:.2f} {circ:.2f}" stroke-dashoffset="{-sl:.2f}" '
            f'transform="rotate(-180 {CX} {CY})"/>'
        )

    gid = "hsg"
    svg = (
        f'<svg width="220" height="118" viewBox="0 0 220 118" style="display:block;margin:0 auto">'
        f'<defs>{_svg_lgrad(gid,"#f85149","#3fb950",0,0,1,0)}</defs>'
        + zone(0,40,"var(--err)") + zone(40,70,"var(--warn)") + zone(70,100,"var(--ok)")
        + f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="var(--s2)" '
        f'stroke-width="{SW+2}" stroke-dasharray="{half:.2f} {circ:.2f}" '
        f'transform="rotate(-180 {CX} {CY})"/>'
        f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="url(#{gid})" '
        f'stroke-width="{SW}" stroke-dasharray="{fill:.2f} {circ:.2f}" '
        f'stroke-linecap="round" transform="rotate(-180 {CX} {CY})"/>'
        f'<text x="12" y="{CY+14}" text-anchor="middle" font-size="9" fill="var(--t3)" font-family="inherit">0</text>'
        f'<text x="{CX}" y="14" text-anchor="middle" font-size="9" fill="var(--t3)" font-family="inherit">50</text>'
        f'<text x="208" y="{CY+14}" text-anchor="middle" font-size="9" fill="var(--t3)" font-family="inherit">100</text>'
        f'<text x="{CX}" y="{CY-8}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="32" font-weight="900" fill="{color}" font-family="inherit">{int(score)}</text>'
        f'<text x="{CX}" y="{CY+13}" text-anchor="middle" font-size="12" fill="var(--t2)" font-family="inherit">'
        f'Grade {_e(grade)}</text>'
        f'</svg>'
    )
    dims_html = ""
    for dim in (s.get("dimensions") or []):
        if not isinstance(dim, dict): continue
        dv  = _f(dim.get("value"))
        dmx = _f(dim.get("max")) or 100.0
        dp  = min(int(dv/dmx*100), 100) if dmx else 0
        dc  = _variant_color(dim.get("variant") or "")
        dims_html += (
            f'<div class="flex items-center gap-2 mb2">'
            f'<div class="txt-xs c2" style="min-width:90px">{_e(dim.get("label",""))}</div>'
            f'<div style="flex:1;height:8px;background:var(--s2);border-radius:9999px;overflow:hidden;border:1px solid var(--b0)">'
            f'<div style="width:{dp}%;height:100%;background:{dc};border-radius:9999px"></div></div>'
            f'<div class="txt-xs c2 tabnum" style="min-width:42px;text-align:right">'
            f'{_n(dv)}/{_n(dmx)}</div>'
            f'</div>'
        )
    return (
        f'<div class="card">{_ttl(s.get("title") or "Health Score")}'
        f'{svg}'
        f'{"<div style=margin-top:12px></div>" + dims_html if dims_html else ""}'
        f'</div>'
    )


def _render_nutrient_gauge(s: Dict) -> str:
    gauges = [g for g in (s.get("gauges") or []) if isinstance(g, dict)]
    if not gauges and s.get("label"):
        gauges = [{"label":s.get("label"),"value":s.get("value"),
                   "limit":s.get("limit"),"unit":s.get("unit")}]
    if not gauges: return ""

    def _mini(g: Dict) -> str:
        val   = _f(g.get("value"))
        lim   = _f(g.get("limit")) or 1.0
        unit  = g.get("unit") or ""
        ratio = min(val/lim, 1.0) if lim else 0
        col   = _variant_color(g.get("variant") or "") if g.get("variant") else _traffic_color(ratio)
        pct   = int(ratio*100)
        CX, CY, R, SW = 55, 52, 40, 10
        circ = 2*math.pi*R
        half = circ/2
        fill = ratio*half
        return (
            f'<div style="text-align:center;flex:1;min-width:0">'
            f'<svg width="110" height="64" viewBox="0 0 110 64">'
            f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="var(--s2)" stroke-width="{SW+2}" '
            f'stroke-dasharray="{half:.2f} {circ:.2f}" transform="rotate(-180 {CX} {CY})"/>'
            f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="{col}" stroke-width="{SW}" '
            f'stroke-dasharray="{fill:.2f} {circ:.2f}" '
            f'stroke-linecap="round" transform="rotate(-180 {CX} {CY})"/>'
            f'<text x="{CX}" y="{CY-4}" text-anchor="middle" dominant-baseline="central" '
            f'font-size="14" font-weight="900" fill="{col}" font-family="inherit">{_n(val)}</text>'
            f'<text x="{CX}" y="{CY+9}" text-anchor="middle" '
            f'font-size="9" fill="var(--t3)" font-family="inherit">{_e(unit)} · {pct}%</text>'
            f'</svg>'
            f'<div class="txt-xs c2" style="margin-top:2px">{_e(g.get("label",""))}</div>'
            f'</div>'
        )

    gauges_html = "".join(_mini(g) for g in gauges[:4])
    return (
        f'<div class="card">{_ttl(s.get("title") or "Nutrient Gauges")}'
        f'<div class="flex gap-2">{gauges_html}</div></div>'
    )


def _render_nutrition_label(s: Dict) -> str:
    name  = s.get("name") or "Food Item"
    srv   = s.get("serving_size") or "1 serving"
    cal   = _f(s.get("calories"))
    fat   = _f(s.get("fat_g"))
    sat   = _f(s.get("sat_fat_g"))
    sod   = _f(s.get("sodium_mg"))
    carb  = _f(s.get("carb_g"))
    sug   = _f(s.get("sugar_g"))
    fib   = _f(s.get("fiber_g"))
    prot  = _f(s.get("protein_g"))

    def dv(val: float, ref: float) -> str:
        p   = round(val/ref*100) if ref else 0
        cls = "nl-dv-warn" if p>=20 else "nl-dv"
        return f'<span class="{cls}">{p}%</span>'

    def row(lbl: str, val_s: str, dv_h: str, bold=False, indent=False, thick=False) -> str:
        cls = ("nl-bold " if bold else "") + ("nl-indent " if indent else "") + ("nl-thick" if thick else "")
        return (
            f'<div class="nl-row {cls.strip()}">'
            f'<span>{_e(lbl)} <span style="font-weight:400;color:var(--t2)">{_e(val_s)}</span></span>'
            f'{dv_h}</div>'
        )

    return (
        f'<div class="card">{_ttl(s.get("title"))}'
        f'<div class="nl-wrap">'
        f'<div class="nl-title">Nutrition Facts</div>'
        f'<div class="nl-srv">{_e(name)} · {_e(srv)}</div>'
        f'<div class="nl-cal"><span class="nl-cal-lbl">Calories</span>'
        f'<span class="nl-cal-val tabnum">{int(cal)}</span></div>'
        f'<div class="nl-dvhdr">% Daily Value*</div>'
        + row("Total Fat",          f"{_n(fat)}g",  dv(fat,78),   bold=True)
        + row("Saturated Fat",      f"{_n(sat)}g",  dv(sat,20),   indent=True)
        + row("Sodium",             f"{_n(sod)}mg", dv(sod,2300), bold=True)
        + row("Total Carbohydrate", f"{_n(carb)}g", dv(carb,275), bold=True)
        + row("Dietary Fiber",      f"{_n(fib)}g",  dv(fib,28),   indent=True)
        + row("Total Sugars",       f"{_n(sug)}g",  "",           indent=True)
        + row("Protein",            f"{_n(prot)}g", "",           bold=True, thick=True)
        + '<div style="font-size:9.5px;color:var(--t3);margin-top:5px">'
        + '*Based on a 2,000 kcal diet.'
        + '</div></div></div>'
    )


def _render_food_health_list(s: Dict) -> str:
    items = [i for i in (s.get("items") or []) if isinstance(i, dict)]
    if not items: return ""
    cards = ""
    for it in items:
        name    = it.get("name") or "Food"
        cal     = _f(it.get("calories"))
        p,c,f   = _f(it.get("protein_g")), _f(it.get("carb_g")), _f(it.get("fat_g"))
        badge   = _health_badge(it.get("is_healthy"))
        reasons = it.get("reasons") or []
        if isinstance(reasons, str): reasons = [reasons]
        macros  = " · ".join(filter(None, [
            f"P {_n(p)}g" if p else "", f"C {_n(c)}g" if c else "", f"F {_n(f)}g" if f else ""
        ]))
        rea_h = (f'<div class="txt-2xs err mt1">{_e(", ".join(str(r) for r in reasons[:3]))}</div>'
                 if reasons and it.get("is_healthy") is False else "")
        cards += (
            f'<div class="fhl-item">'
            f'<div class="flex items-center justify-between mb1">'
            f'<div class="fhl-name">{_e(name)}</div>'
            f'<div class="flex items-center gap-2">'
            f'<span class="txt-sm fw7 c1 tabnum">{_n(cal)}'
            f'<span class="txt-2xs c3"> kcal</span></span>'
            f'{badge}</div></div>'
            f'<div class="txt-2xs c3">{_e(macros)}</div>'
            f'{rea_h}</div>'
        )
    return f'<div class="card">{_ttl(s.get("title") or "Food Analysis")}{cards}</div>'


def _render_restaurant_list(s: Dict) -> str:
    items = [i for i in (s.get("items") or []) if isinstance(i, dict)]
    if not items: return ""
    cards = ""
    for it in items:
        name    = it.get("name") or "Restaurant"
        chips   = []
        if it.get("rating"):   chips.append(f'<span class="rst-chip">★ {_e(str(it["rating"]))}</span>')
        if it.get("price"):    chips.append(f'<span class="rst-chip">{_e(str(it["price"]))}</span>')
        if it.get("distance"): chips.append(f'<span class="rst-chip">📍 {_e(str(it["distance"]))}</span>')
        if it.get("cuisine"):  chips.append(f'<span class="rst-chip">{_e(str(it["cuisine"]))}</span>')
        if it.get("is_veg"):   chips.append(f'<span class="badge b-ok">Veg</span>')
        chips_h = f'<div class="rst-chips">{"".join(chips)}</div>' if chips else ""
        dishes  = [d for d in (it.get("dishes") or []) if isinstance(d, dict)]
        dish_h  = ""
        for d in dishes[:5]:
            dot   = "🟢" if d.get("is_healthy") is True else "🔴" if d.get("is_healthy") is False else "⚪"
            dcal  = _f(d.get("calories"))
            dcal_s = f" · {_n(dcal)} kcal" if dcal else ""
            dish_h += f'<div class="rst-dish">{dot} {_e(d.get("name",""))}<span class="c3">{_e(dcal_s)}</span></div>'
        if dish_h: dish_h = f'<div style="margin-top:8px">{dish_h}</div>'
        cards += f'<div class="rst-item"><div class="rst-name">{_e(name)}</div>{chips_h}{dish_h}</div>'
    return f'<div class="card">{_ttl(s.get("title") or "Recommendations")}{cards}</div>'


def _render_ranking_list(s: Dict) -> str:
    items = [i for i in (s.get("items") or []) if isinstance(i, dict)]
    if not items: return ""
    rows = ""
    for idx, it in enumerate(items, 1):
        bcls = {1:"rk1",2:"rk2",3:"rk3"}.get(idx,"rkn")
        blbl = {1:"🥇",2:"🥈",3:"🥉"}.get(idx, str(idx))
        bxt  = (f'<span class="badge b-info ml-auto">{_e(it["badge_text"])}</span>'
                if it.get("badge_text") else "")
        val_h = (f'<div class="rank-val tabnum">{_e(str(it["value"]))}'
                 f'{"&nbsp;"+_e(str(it["unit"])) if it.get("unit") else ""}</div>'
                 if it.get("value") is not None else "")
        sub_h = f'<div class="rank-sub">{_e(it.get("sub",""))}</div>' if it.get("sub") else ""
        rows += (
            f'<div class="rank-item">'
            f'<div class="rank-badge {bcls}">{blbl}</div>'
            f'<div class="flex-1 min-w-0">'
            f'<div class="flex items-center"><div class="rank-name">{_e(it.get("name",""))}</div>{bxt}</div>'
            f'{sub_h}</div>'
            f'{val_h}</div>'
        )
    return f'<div class="card">{_ttl(s.get("title"))}<div>{rows}</div></div>'


def _render_tip_card(s: Dict) -> str:
    tone = (s.get("tone") or "positive").lower()
    bg, border, tcol = {
        "positive": ("var(--ok-muted)",   "rgba(63,185,80,.3)",   "var(--ok)"),
        "caution":  ("var(--warn-muted)",  "rgba(210,153,34,.3)",  "var(--warn)"),
        "warning":  ("var(--err-muted)",   "rgba(248,81,73,.3)",   "var(--err)"),
    }.get(tone, ("var(--ok-muted)", "rgba(63,185,80,.3)", "var(--ok)"))
    icon = s.get("icon") or "💡"
    return (
        f'<div class="card">'
        f'<div class="tip-card" style="background:{bg};border-left-color:{border}">'
        f'<div style="font-size:20px;flex-shrink:0;line-height:1">{_e(icon)}</div>'
        f'<div class="flex-1 min-w-0">'
        f'<div class="tip-title" style="color:{tcol}">{_e(s.get("title",""))}</div>'
        f'<div class="tip-body">{_e(s.get("content",""))}</div>'
        f'</div></div></div>'
    )


def _render_meal_summary_row(s: Dict) -> str:
    meals  = [m for m in (s.get("meals") or []) if isinstance(m, dict)]
    dtgt   = _f(s.get("daily_target")) or 2000.0
    cols   = min(len(meals), 4) if meals else 1
    slots  = ""
    for m in meals[:4]:
        cal  = _f(m.get("calories"))
        pct  = max(2, int(cal/dtgt*100)) if dtgt else 2
        col  = m.get("color") or "#7c3aed"
        icon = m.get("icon") or "🍽"
        slots += (
            f'<div class="meal-slot">'
            f'<div class="meal-icon">{_e(icon)}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div class="meal-name">{_e(m.get("name","Meal"))}</div>'
            f'<div class="meal-cal tabnum">{_n(cal)}'
            f'<span class="meal-cal-u"> kcal</span></div>'
            f'<div class="meal-bar-bg">'
            f'<div class="meal-bar-fill" style="width:{pct}%;background:{col}"></div>'
            f'</div></div></div>'
        )
    return (
        f'<div class="card">{_ttl(s.get("title"))}'
        f'<div class="meal-row" style="grid-template-columns:repeat({cols},1fr)">{slots}</div></div>'
    )


def _render_comparison_table(s: Dict) -> str:
    cols = [str(c) for c in (s.get("columns") or [])]
    rows = s.get("rows") or []
    if not cols and not rows: return ""
    hdr  = "".join(f"<th>{_e(c)}</th>" for c in cols)
    body = ""
    for row in rows:
        if not isinstance(row, (list, tuple)): continue
        cells = "".join(
            f'<td class="{"tbl-num" if isinstance(c,(int,float)) else ""}">'
            f'{_e(str(c) if c is not None else "")}</td>'
            for c in row
        )
        body += f"<tr>{cells}</tr>"
    fn = f'<div class="txt-2xs c3 mt1">{_e(s["footnote"])}</div>' if s.get("footnote") else ""
    return (
        f'<div class="card">{_ttl(s.get("title"))}'
        f'<div class="overflow-x"><table><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table></div>'
        f'{fn}</div>'
    )


def _render_progress_bar(s: Dict) -> str:
    val = _f(s.get("value"))
    mx  = _f(s.get("max")) or 100.0
    pct = max(2, min(int(val/mx*100), 100)) if mx else 0
    c1, c2 = {
        "primary": ("#7c3aed","#0891b2"),
        "success": ("#3fb950","#0891b2"),
        "warning": ("#d29922","#f97316"),
        "error":   ("#f85149","#ff6b6b"),
    }.get((s.get("variant") or "primary").lower(), ("#7c3aed","#0891b2"))
    unit = s.get("unit") or ""
    return (
        f'<div class="card">'
        f'<div class="flex justify-between items-baseline mb2">'
        f'<div class="txt-sm c2 fw5">{_e(s.get("label",""))}</div>'
        f'<div class="txt-sm fw7 c1 tabnum">{_n(val)}'
        f'{"&nbsp;"+_e(unit) if unit else ""} '
        f'<span class="txt-2xs c3">/ {_n(mx)}</span></div></div>'
        f'<div class="pb-track">'
        f'<div style="width:{pct}%;height:10px;border-radius:9999px;'
        f'background:linear-gradient(90deg,{c1},{c2})"></div>'
        f'</div></div>'
    )


def _render_tabs(s: Dict) -> str:
    tabs = [t for t in (s.get("tabs") or []) if isinstance(t, dict)]
    if not tabs: return ""
    pills = "".join(f'<div class="tab-pill">{_e(t.get("label",""))}</div>' for t in tabs)
    secs  = "".join(
        f'<div class="tab-sec"><div class="tab-lbl">{_e(t.get("label",""))}</div>'
        f'<div class="tab-body">{_e(t.get("content",""))}</div></div>'
        for t in tabs
    )
    return f'<div class="card">{_ttl(s.get("title"))}<div class="tab-pills">{pills}</div>{secs}</div>'


def _render_tag_list(s: Dict) -> str:
    tags = [str(t) for t in (s.get("tags") or []) if t]
    if not tags: return ""
    return (
        f'<div class="card">{_ttl(s.get("title"))}'
        f'<div class="taglist">{"".join(f"<span class=tag>{_e(t)}</span>" for t in tags)}</div></div>'
    )


def _render_columns(s: Dict) -> str:
    children = [c for c in (s.get("sections") or []) if isinstance(c,dict) and c.get("type")]
    if not children: return ""
    gap   = max(6, min(int(s.get("gap") or 12), 32))
    inner = "".join(_render_section(c) for c in children)
    return f'<div class="col-row" style="gap:{gap}px">{inner}</div>'


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_RENDERERS: Dict[str, Callable] = {
    "text":              _render_text,
    "markdown":          _render_text,
    "highlight_box":     _render_highlight_box,
    "alert":             _render_highlight_box,
    "statistic_grid":    _render_statistic_grid,
    "key_value_list":    _render_key_value_list,
    "comparison_table":  _render_comparison_table,
    "table_advanced":    _render_comparison_table,
    "bar_chart":         _render_bar_chart,
    "macro_chart":       _render_macro_chart,
    "calorie_ring":      _render_calorie_ring,
    "health_score_card": _render_health_score_card,
    "nutrient_gauge":    _render_nutrient_gauge,
    "nutrition_label":   _render_nutrition_label,
    "food_health_list":  _render_food_health_list,
    "restaurant_list":   _render_restaurant_list,
    "ranking_list":      _render_ranking_list,
    "progress_bar":      _render_progress_bar,
    "tabs":              _render_tabs,
    "tag_list":          _render_tag_list,
    "tip_card":          _render_tip_card,
    "meal_summary_row":  _render_meal_summary_row,
    "divider":           lambda _: '<hr class="divider">',
    "spacer":            lambda s: f'<div style="height:{max(4,min(int(s.get("height") or 8),48))}px"></div>',
    "columns":           _render_columns,
}


def _render_section(sec: Dict[str, Any]) -> str:
    fn = _RENDERERS.get((sec.get("type") or "").strip().lower())
    if fn is None: return ""
    try:
        return fn(sec)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("[builder] render error '%s': %s", sec.get("type"), exc)
        return ""


# ---------------------------------------------------------------------------
# Header  (glassmorphism-lite: mesh orb + gradient text)
# ---------------------------------------------------------------------------

def _build_header(summary: str, mode: str) -> str:
    title = summary or mode or "Wabi"
    sub = mode if summary else ""
    pill = (mode or "").upper()
    parts = [
        '<div class="hdr">',
        '<div class="brand">Wabi Assistant</div>',
        f'<div class="hdr-title"><span class="grad-text">{_e(title)}</span>'
        f'<span class="pill">{_e(pill)}</span></div>',
    ]
    if sub:
        parts.append(f'<div class="sub">{_e(sub)}</div>')
    parts.append("</div>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Public entry point — accepts Plan dataclass OR plain dict
# ---------------------------------------------------------------------------

def build_html(plan: Any) -> str:
    """
    Render a UI plan to a complete HTML document.

    `plan` may be a Plan dataclass (preferred) or a raw dict (backward compat).
    """
    # Support both Plan dataclass and raw dict
    if hasattr(plan, "to_dict"):
        d = plan.to_dict()
    elif isinstance(plan, dict):
        d = plan
    else:
        d = {}

    summary  = d.get("summary") or ""
    mode_raw = (d.get("mode") or "").strip().lower()
    mode     = mode_raw.replace("_", " ").title()
    sections = d.get("sections") or []

    body = "\n".join(
        _render_section(s)
        for s in sections
        if isinstance(s, dict) and s.get("type")
    )
    header = _build_header(summary, mode)

    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>Wabi – {_e(mode)}</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n'
        f'<body data-mode="{_e(mode_raw)}">\n'
        f'<div class="shell">'
        f'{header}\n{body}'
        f'</div>\n'
        '</body>\n</html>'
    )
