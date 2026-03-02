# -*- coding: utf-8 -*-
import os
import time
import uuid
from typing import Dict, Any
from playwright.sync_api import sync_playwright
from UI.nodes.logger import log_state, preview_text

def render_html_to_image(full_html: str, output_dir: str, base_url: str = "") -> str:
    if base_url:
        full_html = full_html.replace('src="/static/', f'src="{base_url}/static/')
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(base_dir, output_dir)
    os.makedirs(output_dir, exist_ok=True)
    filename = f"ui_render_{uuid.uuid4().hex[:8]}.png"
    output_path = os.path.join(output_dir, filename)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={"width": 420, "height": 800}, device_scale_factor=2)
        page = context.new_page()
        page.set_content(full_html)
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(100)
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
    return filename

def renderer(state: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    state["current_node"] = "renderer"
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(base_dir, "assets")
    base_url = state.get("base_url", "")
    html = state.get("html_content", "") or ""
    log_state(
        state,
        "info",
        "Renderer started",
        node="renderer",
        event="node_start",
        data={"html_len": len(html), "base_url": base_url},
    )
    log_state(state, "debug", "Renderer HTML preview", node="renderer", event="html_preview", data={"html": preview_text(html)})
    filename = render_html_to_image(html, output_dir, base_url=base_url)
    image_url = f"/static/{filename}"
    log_state(
        state,
        "info",
        "Renderer image rendered",
        node="renderer",
        event="image_rendered",
        data={"image_url": image_url, "duration_ms": int((time.perf_counter() - t0) * 1000)},
    )
    return {"rendered_image_url": image_url}
