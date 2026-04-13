from __future__ import annotations
import asyncio
import base64
import threading
from typing import Optional, Tuple


class _RenderRuntime:
    def __init__(self) -> None:
        self._ready = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._init_lock: Optional[asyncio.Lock] = None
        self._thread = threading.Thread(target=self._run_loop, name="ui_render_playwright", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._init_lock = asyncio.Lock()
        self._ready.set()
        loop.run_forever()

    async def _ensure(self) -> Tuple[object, object, object, asyncio.Lock]:
        init_lock = self._init_lock
        if init_lock is None:
            raise RuntimeError("Playwright loop not initialized")
        async with init_lock:
            if hasattr(self, "_lock") and getattr(self, "_lock", None) is not None:
                try:
                    browser = getattr(self, "_browser", None)
                    if browser is not None and hasattr(browser, "is_connected") and not browser.is_connected():
                        await self._recreate()
                except Exception:
                    await self._recreate()
                return self._playwright, self._browser, self._context, self._lock

            from playwright.async_api import async_playwright

            self._lock = asyncio.Lock()
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
            self._context = await self._browser.new_context(
                viewport={"width": 440, "height": 900},
                device_scale_factor=2,
            )
            self._pages_since_context = 0
            self._page = None
            return self._playwright, self._browser, self._context, self._lock

    async def _recreate(self) -> None:
        page = getattr(self, "_page", None)
        try:
            if page is not None:
                await page.close()
        except Exception:
            pass
        self._page = None

        ctx = getattr(self, "_context", None)
        try:
            if ctx is not None:
                await ctx.close()
        except Exception:
            pass
        self._context = None

        browser = getattr(self, "_browser", None)
        try:
            if browser is not None:
                await browser.close()
        except Exception:
            pass
        self._browser = None

        p = getattr(self, "_playwright", None)
        try:
            if p is not None:
                await p.stop()
        except Exception:
            pass
        self._playwright = None

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        self._context = await self._browser.new_context(
            viewport={"width": 440, "height": 900},
            device_scale_factor=2,
        )
        self._pages_since_context = 0
        self._page = None

    async def _maybe_refresh_context(self) -> None:
        try:
            pages = int(getattr(self, "_pages_since_context", 0))
        except Exception:
            pages = 0
        if pages < 50:
            return
        try:
            ctx = getattr(self, "_context", None)
            if ctx is not None:
                await ctx.close()
        except Exception:
            pass
        try:
            browser = getattr(self, "_browser", None)
            if browser is None:
                return
            self._context = await browser.new_context(
                viewport={"width": 440, "height": 900},
                device_scale_factor=2,
            )
            self._pages_since_context = 0
            self._page = None
        except Exception:
            pass

    async def _render(self, html: str) -> str:
        _, _, ctx, lock = await self._ensure()
        async with lock:
            for attempt in range(2):
                try:
                    await self._maybe_refresh_context()
                    ctx = getattr(self, "_context", None) or ctx
                    page = getattr(self, "_page", None)
                    if page is None:
                        page = await ctx.new_page()
                        self._page = page
                    page.set_default_timeout(3000)
                    await page.set_content(html, wait_until="domcontentloaded")
                    size = await page.evaluate("""() => ({
                        width:  Math.ceil(Math.max(document.body.scrollWidth,  440) + 16),
                        height: Math.ceil(Math.max(document.body.scrollHeight, 200) + 16),
                    })""")
                    w = max(360, min(int(size.get("width", 440)), 900))
                    h = max(200, min(int(size.get("height", 900)), 6000))
                    await page.set_viewport_size({"width": w, "height": h})
                    png_bytes = await page.screenshot(full_page=(h > 2400))
                    try:
                        self._pages_since_context = int(getattr(self, "_pages_since_context", 0)) + 1
                    except Exception:
                        self._pages_since_context = 1
                    break
                except Exception:
                    try:
                        page = getattr(self, "_page", None)
                        if page is not None:
                            await page.close()
                    except Exception:
                        pass
                    self._page = None
                    await self._recreate()
                    if attempt >= 1:
                        raise
        return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    def render_sync(self, html: str) -> str:
        loop = self._loop
        if loop is None:
            raise RuntimeError("Playwright loop not initialized")
        fut = asyncio.run_coroutine_threadsafe(self._render(html), loop)
        return fut.result(timeout=15)

    async def render_async(self, html: str) -> str:
        loop = self._loop
        if loop is None:
            raise RuntimeError("Playwright loop not initialized")
        fut = asyncio.run_coroutine_threadsafe(self._render(html), loop)
        return await asyncio.wrap_future(fut)


_RUNTIME: Optional[_RenderRuntime] = None


def _get_runtime() -> _RenderRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = _RenderRuntime()
    return _RUNTIME


def render_to_image_sync(html: str) -> str:
    return _get_runtime().render_sync(html)

async def render_to_image(html: str) -> str:
    return await _get_runtime().render_async(html)


_WARMUP_LOCK = threading.Lock()
_WARMUP_DONE = threading.Event()


def warmup_renderer() -> None:
    if _WARMUP_DONE.is_set():
        return
    with _WARMUP_LOCK:
        if _WARMUP_DONE.is_set():
            return

        def run() -> None:
            try:
                render_to_image_sync("<html><body></body></html>")
            except Exception:
                pass
            finally:
                _WARMUP_DONE.set()

        threading.Thread(target=run, name="ui_render_warmup", daemon=True).start()
