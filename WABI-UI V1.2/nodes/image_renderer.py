# -*- coding: utf-8 -*-
import os
import uuid
import json
from typing import Dict, Any
from playwright.sync_api import sync_playwright

# 简单的 HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: "WenQuanYi Zen Hei", "DejaVu Sans", "Liberation Sans", sans-serif;
            background-color: #f5f5f5;
            padding: 20px;
            margin: 0;
            width: auto;
        }}
        .container {{
            background-color: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            overflow: hidden;
            padding: 20px;
        }}
        /* ... 其他样式 ... */
        .chart-container {{
            position: relative;
            height: 250px;
            width: 100%;
        }}
        .header {{
            margin-bottom: 16px;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }}
        .title {{
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }}
        .summary {{
            font-size: 14px;
            color: #666;
            margin-top: 4px;
        }}
        .section {{
            margin-bottom: 20px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 600;
            color: #444;
            margin-bottom: 8px;
        }}
        .text-content {{
            font-size: 14px;
            line-height: 1.6;
            color: #333;
            white-space: pre-wrap;
        }}
        .highlight-box {{
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 12px;
            border-radius: 4px;
            font-size: 14px;
            color: #0d47a1;
        }}
        .key-value-list {{
            border: 1px solid #eee;
            border-radius: 8px;
        }}
        .key-value-item {{
            display: flex;
            justify-content: space-between;
            padding: 10px;
            border-bottom: 1px solid #eee;
            font-size: 14px;
        }}
        .key-value-item:last-child {{
            border-bottom: none;
        }}
        .key {{
            color: #666;
        }}
        .value {{
            font-weight: 500;
            color: #333;
        }}
        .chart-placeholder {{
            background-color: #f0f0f0;
            height: 200px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #888;
            border-radius: 8px;
            font-size: 14px;
        }}
        .tag-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .tag {{
            background: #f1f5f9;
            color: #334155;
            border: 1px solid #e2e8f0;
            padding: 6px 10px;
            border-radius: 9999px;
            font-size: 12px;
            line-height: 1;
        }}
        .button-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .button {{
            border: 1px solid #cbd5e1;
            background: #ffffff;
            color: #0f172a;
            padding: 10px 12px;
            border-radius: 10px;
            font-size: 14px;
        }}
        .button.primary {{
            background: #2563eb;
            border-color: #2563eb;
            color: #ffffff;
        }}
        .button.secondary {{
            background: #e2e8f0;
            border-color: #e2e8f0;
            color: #0f172a;
        }}
        .button.outline {{
            background: #ffffff;
        }}
        .progress-row {{
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 8px;
        }}
        .progress-label {{
            font-size: 14px;
            color: #0f172a;
            font-weight: 500;
        }}
        .progress-value {{
            font-size: 12px;
            color: #64748b;
        }}
        .progress {{
            background: #e2e8f0;
            border-radius: 9999px;
            height: 10px;
            overflow: hidden;
        }}
        .progress > div {{
            background: #2563eb;
            height: 100%;
            width: 0%;
        }}
        .form-textarea {{
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 10px;
            font-size: 14px;
            color: #334155;
            min-height: 90px;
            background: #ffffff;
            white-space: pre-wrap;
        }}
        .form-hint {{
            font-size: 12px;
            color: #64748b;
            margin-top: 6px;
        }}
        /* 简单的表格样式 */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f9f9f9;
            font-weight: 600;
        }}
    </style>
    <!-- 引入 Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">Wabi Assistant</div>
            <div class="summary">{summary}</div>
        </div>
        
        {content_html}
        
        <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #999;">
            Generated by Wabi AI
        </div>
    </div>
</body>
</html>
"""

def _render_section(section: Dict[str, Any]) -> str:
    """渲染单个 section 为 HTML"""
    sec_type = section.get("type", "text")
    props = section.get("props") or {}

    def get(key: str, default=None):
        if key in section:
            return section.get(key, default)
        return props.get(key, default)

    html = '<div class="section">'
    
    title = get("title")
    if title:
        html += f'<div class="section-title">{title}</div>'
        
    if sec_type == "image_display":
        image_url = get("image_url") or get("url")
        caption = get("caption", "")
        rounded = bool(get("rounded", True))
        width = get("width")
        height = get("height")

        if image_url:
            style_parts = ["max-width:100%", "height:auto", "display:block", "margin:0 auto 8px", "object-fit:contain"]
            if rounded:
                style_parts.append("border-radius:12px")
            if isinstance(width, (int, float)):
                style_parts.append(f"width:{int(width)}px")
            if isinstance(height, (int, float)):
                style_parts.append(f"max-height:{int(height)}px")
            style = ";".join(style_parts)
            html += f'<img src="{image_url}" alt="{caption}" style="{style}"/>'
            if caption:
                html += f'<div class="text-content" style="font-size:12px;color:#666;margin-top:4px;">{caption}</div>'
        else:
            html += '<div class="chart-placeholder">图片加载失败</div>'
        
    elif sec_type == "text":
        content = get("content", "")
        html += f'<div class="text-content">{content}</div>'
        
    elif sec_type == "highlight_box":
        content = get("content", "")
        html += f'<div class="highlight-box">{content}</div>'
        
    elif sec_type == "key_value_list":
        html += '<div class="key-value-list">'
        for item in get("items", []) or []:
            label = item.get("label", "")
            value = item.get("value", "")
            html += f'<div class="key-value-item"><span class="key">{label}</span><span class="value">{value}</span></div>'
        html += '</div>'
        
    elif sec_type == "dynamic_place_table":
        html += '<table><thead><tr><th>Name</th><th>Rating</th><th>Price</th></tr></thead><tbody>'
        for item in get("items", []) or []:
            name = item.get("name", "")
            rating = item.get("rating", "-")
            price = item.get("price_str", "-")
            html += f'<tr><td>{name}</td><td>{rating}</td><td>{price}</td></tr>'
        html += '</tbody></table>'
        
    elif sec_type in ["bar_chart", "pie_chart", "line_chart", "radar_chart"]:
        chart_title = get("title", "")
        chart_id = f"chart_{uuid.uuid4().hex[:8]}"
        
        items = get("items")
        labels = []
        values = []

        if items:
            labels = [item.get("label", "") for item in items]
            values = [item.get("value", 0) for item in items]
        else:
            if sec_type == "line_chart":
                labels = get("labels", []) or []
                values = get("points", []) or []
            elif sec_type == "radar_chart":
                labels = get("axes", []) or []
                values = get("values", []) or []

        labels = labels or []
        values = values or []
        
        chart_config = {
            "type": "bar" if sec_type == "bar_chart" else "pie" if sec_type == "pie_chart" else "line" if sec_type == "line_chart" else "radar",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": chart_title,
                    "data": values,
                    "backgroundColor": [
                        'rgba(54, 162, 235, 0.6)',
                        'rgba(255, 99, 132, 0.6)',
                        'rgba(75, 192, 192, 0.6)',
                        'rgba(255, 206, 86, 0.6)',
                        'rgba(153, 102, 255, 0.6)',
                        'rgba(255, 159, 64, 0.6)'
                    ],
                    "borderColor": [
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(75, 192, 192, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(153, 102, 255, 1)',
                        'rgba(255, 159, 64, 1)'
                    ],
                    "borderWidth": 1
                }]
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "animation": False,  # 禁用动画，确保截图时图表已渲染完成
                "plugins": {
                    "legend": {
                        "position": 'bottom'
                    },
                    "title": {
                        "display": bool(chart_title),
                        "text": chart_title
                    }
                }
            }
        }
        
        chart_config_json = json.dumps(chart_config)
        
        html += f'''
        <div class="chart-container">
            <canvas id="{chart_id}"></canvas>
        </div>
        <script>
            (function() {{
                const ctx = document.getElementById('{chart_id}').getContext('2d');
                new Chart(ctx, {chart_config_json});
            }})();
        </script>
        '''
        
        # 如果是 statistic_grid，可以用网格布局
    elif sec_type == "statistic_grid":
        columns = get("columns", 2)
        try:
            columns = int(columns)
        except Exception:
            columns = 2
        columns = max(1, min(columns, 4))
        html += f'<div style="display: grid; grid-template-columns: repeat({columns}, 1fr); gap: 10px;">'
        for item in get("items", []) or []:
            label = item.get("label", "")
            value = item.get("value", "")
            html += f'<div style="background:#f9f9f9; padding:10px; border-radius:8px; text-align:center;"><div style="font-size:12px; color:#666;">{label}</div><div style="font-size:16px; font-weight:bold;">{value}</div></div>'
        html += '</div>'

    elif sec_type == "tag_list":
        tags = get("tags", []) or []
        html += '<div class="tag-list">'
        for tag in tags:
            html += f'<span class="tag">{tag}</span>'
        html += '</div>'

    elif sec_type == "button_group":
        buttons = get("buttons", []) or []
        html += '<div class="button-group">'
        for btn in buttons:
            label = btn.get("label", "")
            variant = (btn.get("variant") or "outline").strip().lower()
            if variant not in {"primary", "secondary", "outline"}:
                variant = "outline"
            html += f'<button class="button {variant}" type="button">{label}</button>'
        html += '</div>'

    elif sec_type == "progress_bar":
        label = get("label", "")
        value = get("value", 0) or 0
        max_value = get("max", 100) or 100
        show_percent = bool(get("show_percent", True))
        try:
            value_f = float(value)
        except Exception:
            value_f = 0.0
        try:
            max_f = float(max_value)
        except Exception:
            max_f = 100.0
        ratio = 0.0 if max_f <= 0 else max(0.0, min(1.0, value_f / max_f))
        percent = int(round(ratio * 100))
        right_text = f"{percent}%" if show_percent else f"{value}/{max_value}"
        html += f'<div class="progress-row"><div class="progress-label">{label}</div><div class="progress-value">{right_text}</div></div>'
        html += f'<div class="progress"><div style="width:{percent}%;"></div></div>'

    elif sec_type == "feedback_form":
        placeholder = get("placeholder", "")
        submit_label = get("submit_label", "")
        html += f'<div class="form-textarea">{placeholder}</div>'
        if submit_label:
            html += f'<div class="form-hint">{submit_label}</div>'
        
    else:
        # 默认回退
        content = str(section.get("content", ""))
        html += f'<div class="text-content">{content}</div>'
        
    html += '</div>'
    return html

def render_ui_plan_to_image(ui_plan: Dict[str, Any], output_dir: str, base_url: str = "") -> str:
    """
    将 UI Plan 渲染为图片 (使用 Playwright)
    
    Args:
        ui_plan: UI 计划字典
        output_dir: 图片输出目录
        base_url: Web服务的根地址, 用于拼接图片绝对路径
        
    Returns:
        生成的图片文件名
    """
    # 1. 生成 HTML
    summary = ui_plan.get("summary", "")
    content_html = ""
    imgs = []
    for section in ui_plan.get("sections", []):
        content_html += _render_section(section)
        try:
            if isinstance(section, dict):
                props = section.get("props") or {}
                u = (section.get("image_url") or section.get("url") or props.get("image_url") or props.get("url"))
                if u:
                    imgs.append(str(u))
        except Exception:
            pass
        
    full_html = HTML_TEMPLATE.format(summary=summary, content_html=content_html)

    # 关键修复：将相对路径替换为绝对路径
    if base_url:
        full_html = full_html.replace('src="/static/', f'src="{base_url}/static/')
    print(f"[ImageRenderer][DEBUG] base_url={base_url}")
    print(f"[ImageRenderer][DEBUG] section_count={len(ui_plan.get('sections', []))}")
    print(f"[ImageRenderer][DEBUG] candidate_img_srcs={imgs}")
    try:
        has_img_tag = '<img ' in full_html
        static_count = full_html.count('/static/')
        preview = full_html[:400].replace("\n", " ")
        print(f"[ImageRenderer][DEBUG] html_has_img_tag={has_img_tag} static_ref_count={static_count}")
        print(f"[ImageRenderer][DEBUG] html_preview={preview}...")
    except Exception:
        pass
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(base_dir, output_dir)

    os.makedirs(output_dir, exist_ok=True)
    filename = f"ui_render_{uuid.uuid4().hex[:8]}.png"
    output_path = os.path.join(output_dir, filename)
    
    # 3. 使用 Playwright 截图
    with sync_playwright() as p:
        try:
            # 启动浏览器 (headless=True 是默认的)
            # 添加 --no-sandbox 参数以适应服务器环境
            browser = p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
            
            context = browser.new_context(viewport={"width": 420, "height": 800}, device_scale_factor=2)
            page = context.new_page()
            try:
                page.on("console", lambda m: print(f"[ImageRenderer][PAGE][console] {m.type} {m.text}"))
                page.on("requestfailed", lambda r: print(f"[ImageRenderer][PAGE][requestfailed] {r.url} error={r.failure}"))
                page.on("response", lambda resp: (print(f"[ImageRenderer][PAGE][response] {resp.request.url} status={resp.status}") if "/static/" in resp.request.url else None))
            except Exception:
                pass
            
            # 加载 HTML 内容
            page.set_content(full_html)
            
            # 等待网络空闲，确保 Chart.js 加载完成
            page.wait_for_load_state('networkidle')
            try:
                page.wait_for_function("() => typeof Chart !== 'undefined'")
            except Exception:
                pass
            page.wait_for_timeout(100)
            try:
                img_states = page.evaluate("""
                    () => Array.from(document.images).map(img => ({
                        src: img.src,
                        complete: img.complete,
                        width: img.naturalWidth,
                        height: img.naturalHeight
                    }))
                """)
                print(f"[ImageRenderer][DEBUG] document_images={img_states}")
            except Exception as e:
                print(f"[ImageRenderer][DEBUG] inspect_images_error={e}")

            size = page.evaluate(
                """() => {
                    const body = document.body;
                    const container = document.querySelector('.container');
                    const el = container || body;
                    const rect = el.getBoundingClientRect();
                    const width = Math.ceil(Math.max(rect.width, el.scrollWidth, body.scrollWidth) + 40);
                    const height = Math.ceil(Math.max(rect.height, el.scrollHeight, body.scrollHeight) + 40);
                    return { width, height };
                }"""
            )

            width = int(size.get("width", 420) or 420)
            height = int(size.get("height", 800) or 800)
            width = max(360, min(width, 900))
            height = max(240, min(height, 5000))

            if height <= 2200:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(50)
                size2 = page.evaluate(
                    """() => {
                        const body = document.body;
                        const container = document.querySelector('.container');
                        const el = container || body;
                        const rect = el.getBoundingClientRect();
                        const height = Math.ceil(Math.max(rect.height, el.scrollHeight, body.scrollHeight) + 40);
                        return { height };
                    }"""
                )
                height2 = int(size2.get("height", height) or height)
                height2 = max(240, min(height2, 2200))
                page.set_viewport_size({"width": width, "height": height2})
                page.wait_for_timeout(50)
                page.screenshot(path=output_path, full_page=False)
            else:
                page.screenshot(path=output_path, full_page=True)
            
            browser.close()
        except Exception as e:
            print(f"[ImageRenderer] Playwright error: {e}")
            raise e
    
    return filename
