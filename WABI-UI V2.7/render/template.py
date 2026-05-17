from __future__ import annotations

import html

from .enhancer import ensure_enhanced_html


def _e(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _is_cjk(text: str) -> bool:
    for ch in text:
        o = ord(ch)
        if (
            0x4E00 <= o <= 0x9FFF
            or 0x3400 <= o <= 0x4DBF
            or 0x3040 <= o <= 0x30FF
            or 0xAC00 <= o <= 0xD7AF
        ):
            return True
    return False


def _template_guardrails(*, ui_lang: str = "zh") -> str:
    i18n = {
        "en": {
            "title": "Immediate Support",
            "subtitle": "If you’re thinking about self-harm or suicide, please get help now.",
            "p1": "I’m really glad you told me. It sounds like you may be expressing thoughts of self-harm or suicide. This is serious, and it’s important to get immediate help.",
            "p2": "I want to be sensitive to how you’re feeling. I’m not equipped to assess or provide emergency support, but a trained professional can help you right now.",
            "p3": "Please contact one of these resources immediately:",
            "p4": "If you can, please reach out to one of these numbers now. If you’d like, I can stay with you here while you do.",
            "res_title": "Singapore resources",
            "res_tag": "24/7 services"
        },
        "zh": {
            "title": "寻求即刻帮助",
            "subtitle": "如果您有自残或自杀的想法，请立即寻求帮助。",
            "p1": "我很感谢您能告诉我这些。听起来您可能正在经历自残或自杀的想法。这非常严肃，寻求即刻帮助至关重要。",
            "p2": "我非常关心您的感受。虽然我无法提供专业的评估或紧急支援，但专业的心理健康人员现在就能为您提供帮助。",
            "p3": "请立即联系以下资源：",
            "p4": "如果可以，请现在拨打这些电话。如果您愿意，我可以一直在这里陪着您。",
            "res_title": "新加坡援助资源",
            "res_tag": "24/7服务"
        }
    }

    t = i18n.get(ui_lang, i18n["en"])

    if ui_lang == "zh":
        resources = [
            ("995", "新加坡紧急服务（消防 / 救护车）"),
            ("1-767", "新加坡援人协会 SOS 24 小时热线"),
            ("1771", "National Mindline 24 小时情绪支持热线"),
            ("1800 283 7019", "SAMH 热线（心理健康与咨询）"),
        ]
    else:
        resources = [
            ("995", "Singapore Emergency Services (Fire / Ambulance)"),
            ("1-767", "Samaritans of Singapore (SOS) 24-hour hotline"),
            ("1771", "National Mindline (24-hour emotional support)"),
            ("1800 283 7019", "SAMH Helpline (Mental health & counseling)"),
        ]
    resources_items = "".join(
        f'<li class="item"><div class="num kv-v">{_e(num)}</div><div class="desc">{_e(desc)}</div></li>'
        for num, desc in resources
    )
    
    return f'''<!DOCTYPE html>
<html lang="{ui_lang}">
<head>
<meta charset="UTF-8">
<style>
:root {{
    --bg: #0b1020;
    --card-base: #0f172a;
    --muted: #94a3b8;
    --text: #e5e7eb;
    --border: rgba(148, 163, 184, 0.15);
    --accent: #ef4444;
    --accent2: #f97316;
}}
* {{ box-sizing: border-box; }}

html, body {{
    margin: 0;
    padding: 0;
    background: var(--bg);
    overflow: hidden;
}}

body {{
    display: flex;
    justify-content: center;
    padding: 10px 0 12px;
}}

.card {{
    width: 420px;
    position: relative;
    padding: 14px 18px;
    border: 1px solid var(--border);
    border-radius: 20px;
    color: var(--text);
    font: 14px/1.6 system-ui, -apple-system, sans-serif;
    background-color: #0f172a;
    background-image: 
        radial-gradient(circle at 50% 0%, rgba(239, 68, 68, 0.15) 0%, transparent 75%),
        radial-gradient(circle at 0% 100%, rgba(249, 115, 22, 0.08) 0%, transparent 50%),
        radial-gradient(circle at 100% 0%, rgba(239, 68, 68, 0.05) 0%, transparent 40%);
    box-shadow: 
        0 20px 50px rgba(0, 0, 0, 0.6),
        inset 0 0 0 1px rgba(255, 255, 255, 0.05);
}}

.hdr {{ margin-bottom: 12px; }}
.logo {{ font-weight: 700; color: #fecaca; font-size: 12px; margin-bottom: 4px; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.05em; }}
.title {{ font-size: 24px; font-weight: 800; letter-spacing: -0.02em; display: flex; align-items: center; gap: 10px; color: #fff; }}
.pill {{ font-size: 10px; color: #fff; border: 1px solid var(--accent); background: var(--accent); padding: 2px 8px; border-radius: 6px; font-weight: 900; }}
.sub {{ color: var(--muted); font-size: 13px; margin-top: 6px; line-height: 1.4; }}

.alert {{ margin-top: 12px; border-left: 4px solid var(--accent); padding: 11px 14px; background: rgba(239, 68, 68, 0.06); border-radius: 0 12px 12px 0; }}
.p {{ margin: 0 0 6px 0; font-size: 13px; line-height: 1.55; color: #d1d5db; }}
.p:last-child {{ margin-bottom: 0; }}

.resources {{ margin-top: 16px; background: rgba(2, 6, 23, 0.3); border: 1px solid var(--border); border-radius: 16px; padding: 14px; }}
.rt {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }}
.rk {{ color: #fecaca; font-weight: 700; font-size: 14px; }}
.tag {{ font-size: 10px; color: var(--muted); border: 1px solid var(--border); padding: 1px 8px; border-radius: 999px; background: rgba(255,255,255,0.03); }}

.list {{ margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 7px; }}
.item {{ 
    display: flex; 
    align-items: center; 
    background: rgba(255, 255, 255, 0.03); 
    border: 1px solid rgba(255, 255, 255, 0.05); 
    border-radius: 12px; 
    padding: 11px;
    transition: background 0.2s;
}}
.num {{ min-width: 132px; font-weight: 800; font-size: 16px; color: #fff; border-right: 1px solid rgba(255,255,255,0.1); margin-right: 12px; }}
.desc {{ color: #94a3b8; font-size: 12px; line-height: 1.4; flex: 1; }}

.footer {{ margin-top: 20px; color: rgba(148, 163, 184, 0.3); font-size: 11px; text-align: center; font-weight: 500; }}
</style>
</head>
<body>
<div class="card">
    <div class="hdr">
        <div class="logo">UI Render Assistant</div>
        <div class="title">{t['title']}<span class="pill">GUARDRAILS</span></div>
        <div class="sub">{t['subtitle']}</div>
    </div>
    <div class="alert">
        <p class="p">{t['p1']}</p>
        <p class="p">{t['p2']}</p>
        <p class="p">{t['p3']}</p>
    </div>
    <section class="resources">
        <div class="rt sec-ttl"><div class="rk">{t['res_title']}</div><div class="tag">{t['res_tag']}</div></div>
        <ul class="list">
            {resources_items}
        </ul>
    </section>
    <div class="alert" style="border-left-color:var(--accent2); background:rgba(249,115,22,0.06)">
        <p class="p">{t['p4']}</p>
    </div>
</div>
</body>
</html>'''


def _template_tutorial(*, ui_lang: str = "zh") -> str:
    i18n = {
        "en": {
            "title": "Upload a Photo",
            "pill": "TUTORIAL",
            "subtitle": "Send food photos via WeChat or WhatsApp to get help.",
            "hint": "Best results: clear photos + 2–3 angles + include packaging/labels if any.",
            "prep_title": "Before You Send",
            "prep": [
                "Take 2–3 photos: top view + side view; add a close-up if needed.",
                "Use good lighting; avoid heavy shadows; keep text readable.",
                "If it’s packaged food, include nutrition facts + ingredient list.",
            ],
            "wechat_title": "WeChat",
            "wechat_steps": [
                "Open this chat.",
                "Tap “+” in the input bar.",
                "Choose Photos or Camera.",
                "Select or take photos, then Send.",
            ],
            "wa_title": "WhatsApp",
            "wa_steps": [
                "Open this chat.",
                "Tap the paperclip or camera icon.",
                "Choose Gallery or Camera.",
                "Select or take photos, then Send.",
            ],
            "add_title": "Add a Short Note",
            "add": [
                "What is it? (dish name / brand)",
                "Portion size? (small/medium/large, or grams if known)",
                "Any special requests? (calories, macros, healthy tips)",
            ],
            "examples_title": "Message Examples",
            "examples": [
                "“Estimate calories and macros from these photos.”",
                "“Is this meal healthy? Give 3 improvements.”",
                "“Read the nutrition label and summarize key numbers.”",
            ],
        },
        "zh": {
            "title": "上传图片指引",
            "pill": "指引",
            "subtitle": "请通过微信或 WhatsApp 发送食物图片以获得帮助。",
            "hint": "效果更好：清晰照片 + 2–3 个角度 + 有包装就拍标签。",
            "prep_title": "发送前准备",
            "prep": [
                "拍 2–3 张：俯拍 + 侧拍；必要时再拍一张特写。",
                "光线充足，避免强阴影；保证文字清晰可见。",
                "如果是包装食品，请拍营养成分表 + 配料表。",
            ],
            "wechat_title": "微信",
            "wechat_steps": [
                "进入本聊天。",
                "点击输入框旁的“+”。",
                "选择“相册”或“拍摄”。",
                "选图或拍照后点击“发送”。",
            ],
            "wa_title": "WhatsApp",
            "wa_steps": [
                "进入本聊天。",
                "点击回形针或相机图标。",
                "选择“相册/图库”或“相机”。",
                "选图或拍照后点击“发送”。",
            ],
            "add_title": "建议补充一句话",
            "add": [
                "这是什么？（菜名/品牌）",
                "份量大概多少？（小/中/大，或克数）",
                "你希望我重点做什么？（估热量、三大营养素、健康建议等）",
            ],
            "examples_title": "你可以这样发",
            "examples": [
                "“请根据这些照片估算热量和三大营养素。”",
                "“这顿饭健康吗？给我 3 条改进建议。”",
                "“请读取营养标签并总结关键数值。”",
            ],
        },
    }
    t = i18n.get(ui_lang, i18n["en"])
    def _items(lines) -> str:
        return "".join(
            f'<li class="item"><div class="num kv-v">{idx}</div><div class="desc">{_e(s)}</div></li>'
            for idx, s in enumerate(lines, start=1)
        )
    prep_items = _items(t["prep"])
    wechat_items = _items(t["wechat_steps"])
    wa_items = _items(t["wa_steps"])
    add_items = _items(t["add"])
    examples_items = "".join(
        f'<li class="item"><div class="num kv-v">{idx}</div><div class="desc">{_e(s)}</div></li>'
        for idx, s in enumerate(t["examples"], start=1)
    )
    return f'''<!DOCTYPE html>
<html lang="{ui_lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(t["title"])}</title>
<style>
:root {{
    --bg: #0b1020;
    --muted: #94a3b8;
    --text: #e5e7eb;
    --border: rgba(148, 163, 184, 0.15);
    --accent: #22c55e;
    --wx: #22c55e;
    --wa: #14b8a6;
}}
* {{ box-sizing: border-box; }}
html, body {{
    margin: 0;
    padding: 0;
    background: var(--bg);
    overflow: hidden;
}}
body {{
    display: flex;
    justify-content: center;
    padding: 10px 0 12px;
}}
.card {{
    width: 420px;
    position: relative;
    padding: 14px 18px;
    border: 1px solid var(--border);
    border-radius: 20px;
    color: var(--text);
    font: 14px/1.6 system-ui, -apple-system, sans-serif;
    background-color: #0f172a;
    background-image:
        radial-gradient(circle at 50% 0%, rgba(34, 197, 94, 0.14) 0%, transparent 75%),
        radial-gradient(circle at 0% 100%, rgba(34, 197, 94, 0.06) 0%, transparent 52%),
        radial-gradient(circle at 100% 0%, rgba(34, 197, 94, 0.04) 0%, transparent 40%);
    box-shadow:
        0 20px 50px rgba(0, 0, 0, 0.6),
        inset 0 0 0 1px rgba(255, 255, 255, 0.05);
}}
.hdr {{ margin-bottom: 12px; }}
.logo {{ font-weight: 700; color: rgba(187, 247, 208, 0.95); font-size: 12px; margin-bottom: 4px; opacity: 0.85; text-transform: uppercase; letter-spacing: 0.05em; }}
.title {{ font-size: 22px; font-weight: 800; letter-spacing: -0.02em; display: flex; align-items: center; gap: 10px; color: #fff; }}
.pill {{ font-size: 10px; color: #052e16; border: 1px solid rgba(34,197,94,0.6); background: rgba(34,197,94,0.9); padding: 2px 8px; border-radius: 6px; font-weight: 900; }}
.sub {{ color: var(--muted); font-size: 13px; margin-top: 6px; line-height: 1.4; }}
.alert {{ margin-top: 12px; border-left: 4px solid var(--accent); padding: 11px 14px; background: rgba(34, 197, 94, 0.07); border-radius: 0 12px 12px 0; }}
.p {{ margin: 0; font-size: 13px; line-height: 1.55; color: #d1d5db; }}
.resources {{ margin-top: 14px; background: rgba(2, 6, 23, 0.3); border: 1px solid var(--border); border-radius: 16px; padding: 14px; }}
.rt {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }}
.rk {{ color: rgba(187, 247, 208, 0.95); font-weight: 700; font-size: 14px; }}
.list {{ margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 7px; }}
.item {{
    display: flex;
    align-items: center;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 11px;
}}
.num {{ min-width: 56px; font-weight: 900; font-size: 15px; color: #fff; border-right: 1px solid rgba(255,255,255,0.1); margin-right: 12px; text-align: center; }}
.desc {{ color: #94a3b8; font-size: 12px; line-height: 1.4; flex: 1; }}
.grid {{ display: grid; grid-template-columns: 1fr; gap: 12px; }}
.app {{
    border: 1px solid rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.02);
    border-radius: 14px;
    padding: 12px;
}}
.apphdr {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }}
.badge {{
    font-size: 10px;
    font-weight: 900;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,0.12);
    background: rgba(255,255,255,0.04);
    color: #d1fae5;
}}
.badge.wx {{ border-color: rgba(34,197,94,0.55); background: rgba(34,197,94,0.14); color: #bbf7d0; }}
.badge.wa {{ border-color: rgba(20,184,166,0.55); background: rgba(20,184,166,0.14); color: #99f6e4; }}
.rk.wx {{ color: #bbf7d0; }}
.rk.wa {{ color: #99f6e4; }}
</style>
</head>
<body>
<div class="card">
    <div class="hdr">
        <div class="logo">UI Render Assistant</div>
        <div class="title">{_e(t["title"])}<span class="pill">{_e(t["pill"])}</span></div>
        <div class="sub">{_e(t["subtitle"])}</div>
    </div>
    <div class="alert"><p class="p">{_e(t["hint"])}</p></div>
    <section class="resources">
        <div class="rt sec-ttl"><div class="rk">📷 {_e(t["prep_title"])}</div></div>
        <ul class="list">{prep_items}</ul>
    </section>
    <section class="resources">
        <div class="rt sec-ttl"><div class="rk">⬆️ {_e("Upload Steps" if ui_lang == "en" else "上传步骤")}</div></div>
        <div class="grid">
            <section class="app">
                <div class="apphdr sec-ttl"><div class="rk wx">WeChat</div><div class="badge wx">WECHAT</div></div>
                <ul class="list">{wechat_items}</ul>
            </section>
            <section class="app">
                <div class="apphdr sec-ttl"><div class="rk wa">WhatsApp</div><div class="badge wa">WHATSAPP</div></div>
                <ul class="list">{wa_items}</ul>
            </section>
        </div>
    </section>
    <section class="resources">
        <div class="rt sec-ttl"><div class="rk">📝 {_e(t["add_title"])}</div></div>
        <ul class="list">{add_items}</ul>
    </section>
    <section class="resources">
        <div class="rt sec-ttl"><div class="rk">💬 {_e(t["examples_title"])}</div></div>
        <ul class="list">{examples_items}</ul>
    </section>
</div>
</body>
</html>'''


def render_template(*, intent: str, user_input: str) -> str:
    it = (intent or "").strip().lower()
    ui_lang = "zh" if _is_cjk(user_input or "") else "en"
    if it == "guardrails":
        return ensure_enhanced_html(_template_guardrails(ui_lang=ui_lang))
    if it == "tutorial":
        return ensure_enhanced_html(_template_tutorial(ui_lang=ui_lang))
    return ensure_enhanced_html(_template_tutorial(ui_lang=ui_lang))
