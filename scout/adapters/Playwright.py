from dataclasses import dataclass
from ..core import Document, Selector, Action
from ..scripts import load_script
from ..logger import get_logger
from playwright.async_api import async_playwright, Playwright, Browser, Page

# TODO: add functionality to use and reuse a session via storage_state in playwright
# TODO: add a way to run js code on the page

TIMEOUT = 300000
class PlaywrightAdapter:
    def __init__(self):
        self.playwright: Playwright = None
        self.browser: Browser = None
        self._logger = get_logger("Playwright")

    async def __aenter__(self):
        await self.start()
        return self

    def __aexit__(self, exc_type, exc, tb):
        pass

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()

    async def stop(self):
        await self.browser.close()
        return self

    def get_browser(self):
        pass

    async def crawl(self, url: str, selectors:list[str]=[], actions:list[Action] = []):
        page = await self.browser.new_page()
        await page.goto(url)
        # execute actions
        # execute js code
        # capture requests, responses
        try:
            await page.wait_for_selector("body", timeout=TIMEOUT)
            is_visible = await self.execute(
                    page,
                    """() => {
                        const element = document.body;
                        if (!element) return false;
                        const style = window.getComputedStyle(element);
                        const isVisible = style.display !== 'none' && 
                                        style.visibility !== 'hidden' && 
                                        style.opacity !== '0';
                        return isVisible;
                    }""",
                    timeout=30000,
                )
            if not is_visible:
                raise Exception("Body not visible")

            await self._simulate_user(page)
            self.handle_listeners(page)
            html = await page.content()
            return Document(url=url, html=html, metadata={})
        finally:
            try:
                self.handle_listeners(page)
            except StopIteration:
                pass


    def handle_listeners(self, page:Page):
        async def _handle_requests():
            pass

        async def _handle_responses():
            pass

        async def _handle_request_failures():
            pass

        page.on("request", _handle_requests)
        page.on("responses", _handle_responses)
        page.on("requestfailed", _handle_request_failures)

        yield

        page.remove_listener("request", _handle_requests)
        page.remove_listener("responses", _handle_responses)
        page.remove_listener("requestfailed", _handle_request_failures)

    async def _remove_popups(self, page:Page):
        remove_popup_js = load_script("remove_popup")
        try:
            await self.adapter.evaluate(page,
                f"""
                (async () => {{
                    try {{
                        const removeConsent = {remove_popup_js};
                        await removeConsent();
                        return {{ success: true }};
                    }} catch (error) {{
                        return {{
                            success: false,
                            error: error.toString(),
                            stack: error.stack
                        }};
                    }}
                }})()
            """
            )
            await page.wait_for_timeout(500)
        except Exception as e:
            self._logger.error(msg="Failed to remove popups", tag="SCRAPE", error=str(e))

    async def _simulate_user(self, page: Page):
        pass

    def wait(self):
        pass

    def screenshot(self):
        pass

    async def execute(self, page:Page, js_code:str):
        return await page.evaluate(js_code)