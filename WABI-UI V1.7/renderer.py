from __future__ import annotations
import base64

async def render_to_image(html: str) -> str:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        ctx     = await browser.new_context(
            viewport={"width": 440, "height": 900},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        await page.wait_for_timeout(120)
        size = await page.evaluate("""() => ({
            width:  Math.ceil(Math.max(document.body.scrollWidth,  440) + 28),
            height: Math.ceil(Math.max(document.body.scrollHeight, 200) + 28),
        })""")
        w = max(360, min(int(size.get("width",  440)), 900))
        h = max(200, min(int(size.get("height", 900)), 6000))
        await page.set_viewport_size({"width": w, "height": h})
        await page.wait_for_timeout(60)
        png_bytes = await page.screenshot(full_page=(h > 2400))
        await browser.close()
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    return data_url
