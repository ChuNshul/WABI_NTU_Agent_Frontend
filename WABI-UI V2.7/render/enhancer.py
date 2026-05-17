from __future__ import annotations

import re
from typing import Tuple

_STYLE_ID = "ui-render-enhancer-style"
_SCRIPT_ID = "ui-render-enhancer"

_CSS = """
.tab-pill{cursor:pointer;user-select:none;transition:transform .14s ease,border-color .14s ease,background .14s ease,color .14s ease}
.tab-pill:hover{transform:translateY(-1px)}
.tab-pill.is-active{border-color:rgba(251,191,36,.62);background:rgba(251,191,36,.10);color:#e5e7eb}
.tab-sec.is-hidden{display:none}

.ui-collapsible-trigger{cursor:pointer;user-select:none}
.ui-collapsible-trigger:focus{outline:2px solid rgba(56,189,248,.35);outline-offset:2px;border-radius:8px}
.ui-collapse-body{overflow:hidden;transition:max-height .26s ease,opacity .18s ease}
.ui-collapsed .ui-collapse-body{opacity:.0}

.card{transition:transform .16s ease,box-shadow .18s ease,border-color .18s ease}
.card:hover{transform:translateY(-1px);border-color:rgba(148,163,184,.28);box-shadow:0 16px 40px rgba(0,0,0,.35)}

.ui-copyable{cursor:copy}
.ui-copyable:hover{background:rgba(255,255,255,.04)}
.ui-copyable:active{transform:translateY(0.5px)}

.tag{cursor:pointer;transition:transform .14s ease,border-color .14s ease,background .14s ease,color .14s ease}
.tag:hover{transform:translateY(-1px);border-color:rgba(148,163,184,.28)}
.tag.is-active{border-color:rgba(56,189,248,.45);background:rgba(56,189,248,.12);color:#e5e7eb}

.overflow-x{position:relative}
.overflow-x.ui-scrollable:after{content:"";position:absolute;top:0;right:0;width:28px;height:100%;pointer-events:none;background:linear-gradient(90deg,transparent,rgba(11,16,32,.85))}

.pb-track>div,.meal-bar-fill{transition:width .75s cubic-bezier(.2,.9,.2,1)}
.bar-track svg{transition:width .75s cubic-bezier(.2,.9,.2,1)}

.ui-toast{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9999;pointer-events:none;opacity:0;transition:opacity .16s ease,transform .16s ease}
.ui-toast.show{opacity:1;transform:translateX(-50%) translateY(-2px)}
.ui-toast>div{background:rgba(15,23,42,.92);border:1px solid rgba(148,163,184,.22);color:#e5e7eb;padding:8px 10px;border-radius:9999px;font:12px/1.2 system-ui,-apple-system,sans-serif;box-shadow:0 12px 30px rgba(0,0,0,.35)}

.ui-enter{opacity:0;transform:translateY(4px);transition:opacity .38s ease,transform .38s ease}
.ui-enter.ui-in{opacity:1;transform:translateY(0)}

@media (prefers-reduced-motion: reduce){
  .tab-pill,.card,.tag,.ui-collapse-body,.pb-track>div,.meal-bar-fill,.bar-track svg,.ui-toast,.ui-enter{transition:none!important}
  .card:hover,.tab-pill:hover,.tag:hover{transform:none}
}
""".strip()

_JS = r"""
(() => {
  const qsa = (root, sel) => Array.from((root || document).querySelectorAll(sel));
  const isTextInput = (el) => {
    const t = (el && el.tagName || "").toLowerCase();
    return t === "input" || t === "textarea" || t === "select";
  };
  const hasSelection = () => {
    try {
      const s = window.getSelection();
      return !!(s && String(s).trim());
    } catch (_) {
      return false;
    }
  };

  let toastEl = null;
  let toastT = 0;
  const toast = (msg) => {
    if (!msg) return;
    try {
      if (!toastEl) {
        toastEl = document.createElement("div");
        toastEl.className = "ui-toast";
        toastEl.innerHTML = "<div></div>";
        document.body.appendChild(toastEl);
      }
      toastEl.firstChild.textContent = msg;
      toastEl.classList.add("show");
      clearTimeout(toastT);
      toastT = setTimeout(() => toastEl && toastEl.classList.remove("show"), 900);
    } catch (_) {}
  };

  const copyText = async (text) => {
    const v = (text || "").trim();
    if (!v) return false;
    try {
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(v);
        return true;
      }
    } catch (_) {}
    try {
      const ta = document.createElement("textarea");
      ta.value = v;
      ta.setAttribute("readonly", "true");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      ta.style.pointerEvents = "none";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand && document.execCommand("copy");
      document.body.removeChild(ta);
      return !!ok;
    } catch (_) {
      return false;
    }
  };

  const enhanceTabs = () => {
    qsa(document, ".tab-pills").forEach((pills) => {
      if (pills.dataset.uiBound === "1") return;
      const card = pills.closest(".card") || pills.parentElement;
      const pillEls = qsa(pills, ".tab-pill");
      if (!card || pillEls.length < 2) return;
      const secEls = qsa(card, ":scope > .tab-sec");
      if (secEls.length < pillEls.length) return;

      const showAll = () => {
        pillEls.forEach((p) => p.classList.remove("is-active"));
        secEls.forEach((s) => s.classList.remove("is-hidden"));
        pills.dataset.uiActive = "";
      };
      const showOne = (idx) => {
        pillEls.forEach((p, i) => p.classList.toggle("is-active", i === idx));
        secEls.forEach((s, i) => s.classList.toggle("is-hidden", i !== idx));
        pills.dataset.uiActive = String(idx);
      };
      const toggle = (idx) => {
        const cur = pills.dataset.uiActive;
        if (cur === String(idx)) showAll();
        else showOne(idx);
      };

      pillEls.forEach((pill, idx) => {
        pill.setAttribute("role", "button");
        if (!pill.hasAttribute("tabindex")) pill.tabIndex = 0;
        pill.addEventListener("click", (e) => {
          if (isTextInput(e.target) || hasSelection()) return;
          toggle(idx);
        });
        pill.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle(idx);
            return;
          }
          if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            e.preventDefault();
            const cur = Number(pills.dataset.uiActive || 0);
            const next = e.key === "ArrowRight" ? (cur + 1) : (cur - 1 + pillEls.length);
            const idx2 = next % pillEls.length;
            toggle(idx2);
            pillEls[idx2].focus();
          }
        });
      });

      pills.dataset.uiBound = "1";
    });
  };

  const enhanceCollapsibles = () => {
    const candidates = qsa(document, ".card, section");
    candidates.forEach((card) => {
      if (card.dataset.uiCollapsibleBound === "1") return;
      if (card.closest(".hdr")) return;

      let trigger =
        card.querySelector(":scope > .sec-ttl") ||
        card.querySelector(":scope > h2, :scope > h3, :scope > h4") ||
        card.querySelector(":scope > .title, :scope > .card-title");
      if (!trigger) return;

      const children = Array.from(card.children || []);
      if (children.length < 2) return;
      if (children.some((c) => c.classList && c.classList.contains("ui-collapse-body"))) return;

      const bodyWrap = document.createElement("div");
      bodyWrap.className = "ui-collapse-body";
      const rest = children.filter((c) => c !== trigger);
      rest.forEach((el) => bodyWrap.appendChild(el));
      card.appendChild(bodyWrap);

      trigger.classList.add("ui-collapsible-trigger");
      trigger.setAttribute("role", "button");
      if (!trigger.hasAttribute("tabindex")) trigger.tabIndex = 0;

      const setCollapsed = (collapsed) => {
        if (collapsed) {
          bodyWrap.style.maxHeight = "0px";
          card.classList.add("ui-collapsed");
          card.dataset.uiCollapsed = "1";
        } else {
          const h = Math.max(0, bodyWrap.scrollHeight || 0);
          bodyWrap.style.maxHeight = h ? (h + "px") : "";
          card.classList.remove("ui-collapsed");
          card.dataset.uiCollapsed = "0";
        }
      };

      const syncHeight = () => {
        if (card.dataset.uiCollapsed === "1") return;
        const h = Math.max(0, bodyWrap.scrollHeight || 0);
        if (h) bodyWrap.style.maxHeight = h + "px";
      };

      setCollapsed(false);
      window.addEventListener("resize", syncHeight, { passive: true });

      const toggle = () => setCollapsed(card.dataset.uiCollapsed !== "1");
      trigger.addEventListener("click", (e) => {
        if (isTextInput(e.target) || hasSelection()) return;
        toggle();
      });
      trigger.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        e.preventDefault();
        toggle();
      });

      card.dataset.uiCollapsibleBound = "1";
    });
  };

  const enhanceCopyables = () => {
    const sels = [
      ".kv-v", ".kv-v-s",
      ".bar-val", ".meal-cal", ".rank-val",
      ".sg-cell .txt-2xl",
      "td", "th",
    ];
    const els = qsa(document, sels.join(","));
    els.forEach((el) => {
      if (!el || el.dataset.uiCopyBound === "1") return;
      const txt = (el.innerText || "").trim();
      if (!txt || txt.length > 160) return;
      el.classList.add("ui-copyable");
      el.addEventListener("click", async (e) => {
        if (isTextInput(e.target) || hasSelection()) return;
        if (e.altKey || e.metaKey || e.ctrlKey) return;
        const t = (el.innerText || "").trim();
        const ok = await copyText(t);
        if (ok) toast("已复制");
      });
      el.dataset.uiCopyBound = "1";
    });
  };

  const enhanceTags = () => {
    qsa(document, ".tag").forEach((tag) => {
      if (!tag || tag.dataset.uiTagBound === "1") return;
      tag.setAttribute("role", "button");
      if (!tag.hasAttribute("tabindex")) tag.tabIndex = 0;
      const toggle = () => tag.classList.toggle("is-active");
      tag.addEventListener("click", (e) => {
        if (isTextInput(e.target) || hasSelection()) return;
        toggle();
      });
      tag.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        e.preventDefault();
        toggle();
      });
      tag.dataset.uiTagBound = "1";
    });
  };

  const enhanceScrollHints = () => {
    qsa(document, ".overflow-x").forEach((wrap) => {
      if (!wrap || wrap.dataset.uiScrollBound === "1") return;
      const check = () => {
        try {
          const scrollable = wrap.scrollWidth > wrap.clientWidth + 2;
          wrap.classList.toggle("ui-scrollable", scrollable);
        } catch (_) {}
      };
      check();
      wrap.addEventListener("scroll", check, { passive: true });
      window.addEventListener("resize", check, { passive: true });
      wrap.addEventListener("click", () => {
        try {
          if (!wrap.classList.contains("ui-scrollable")) return;
          const max = Math.max(0, wrap.scrollWidth - wrap.clientWidth);
          const cur = wrap.scrollLeft || 0;
          const next = cur >= max - 4 ? 0 : Math.min(max, cur + Math.floor(wrap.clientWidth * 0.85));
          wrap.scrollTo({ left: next, behavior: "smooth" });
        } catch (_) {}
      });
      wrap.dataset.uiScrollBound = "1";
    });
  };

  const animateWidths = () => {
    const items = [];
    qsa(document, ".pb-track > div, .meal-bar-fill").forEach((el) => items.push(el));
    qsa(document, ".bar-track svg").forEach((el) => items.push(el));
    items.forEach((el) => {
      if (!el || el.dataset.uiAnimBound === "1") return;
      const style = el.getAttribute("style") || "";
      const m = style.match(/width\s*:\s*([0-9.]+)%/i);
      if (!m) return;
      const w = m[1] + "%";
      try {
        el.style.width = "0%";
        requestAnimationFrame(() => { el.style.width = w; });
      } catch (_) {}
      el.dataset.uiAnimBound = "1";
    });
  };

  const animateEnter = () => {
    const cards = qsa(document, ".card");
    cards.forEach((c, i) => {
      if (!c || c.dataset.uiEnterBound === "1") return;
      c.classList.add("ui-enter");
      c.style.transitionDelay = Math.min(i * 40, 240) + "ms";
      c.dataset.uiEnterBound = "1";
    });
    requestAnimationFrame(() => {
      cards.forEach((c) => c && c.classList.add("ui-in"));
    });
  };

  const boot = () => {
    try { enhanceTabs(); } catch (_) {}
    try { enhanceCollapsibles(); } catch (_) {}
    try { enhanceCopyables(); } catch (_) {}
    try { enhanceTags(); } catch (_) {}
    try { enhanceScrollHints(); } catch (_) {}
    try { animateWidths(); } catch (_) {}
    try { animateEnter(); } catch (_) {}
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
""".strip()


def strip_scripts(html: str, *, keep_script_ids: Tuple[str, ...] = (_SCRIPT_ID,)) -> str:
    s = html or ""
    if not isinstance(s, str) or not s:
        return html

    keep_pat = "|".join(re.escape(i) for i in keep_script_ids if i)
    if not keep_pat:
        return re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", s)

    out: list[str] = []
    pos = 0
    for m in re.finditer(r"(?is)<script\b([^>]*)>.*?</script>", s):
        out.append(s[pos:m.start()])
        attrs = m.group(1) or ""
        if re.search(rf'(?is)\bid\s*=\s*["\'](?:{keep_pat})["\']', attrs):
            out.append(m.group(0))
        pos = m.end()
    out.append(s[pos:])
    return "".join(out)


def ensure_enhanced_html(html: str, *, strip_existing_scripts: bool = False) -> str:
    s = html or ""
    if not isinstance(s, str) or not s.strip():
        return html

    if strip_existing_scripts:
        s = strip_scripts(s, keep_script_ids=(_SCRIPT_ID,))

    has_style = (f'id="{_STYLE_ID}"' in s) or (f"id='{_STYLE_ID}'" in s)
    has_script = (f'id="{_SCRIPT_ID}"' in s) or (f"id='{_SCRIPT_ID}'" in s)

    if not has_style:
        style_tag = f'<style id="{_STYLE_ID}">{_CSS}</style>'
        idx = s.lower().rfind("</head>")
        s = (s[:idx] + style_tag + s[idx:]) if idx >= 0 else (style_tag + s)

    if not has_script:
        script_tag = f'<script id="{_SCRIPT_ID}">{_JS}</script>'
        idx = s.lower().rfind("</body>")
        s = (s[:idx] + script_tag + s[idx:]) if idx >= 0 else (s + script_tag)

    return s


def ensure_interactive_html(html: str, *, strip_existing_scripts: bool = False) -> str:
    return ensure_enhanced_html(html, strip_existing_scripts=strip_existing_scripts)

