from typing import Any, Literal, Optional, Union

from ..core import Document, Action, Selector
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
        self.screenshots: list[Union[bytes, str]] = []

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
        return self

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()

    async def stop(self):
        await self.browser.close()
        return self

    def get_browser(self):
        pass

    async def scrape(self, url: str, actions: list[Action] = []):
        self.screenshots = []
        page = await self.browser.new_page()
        nav_response = await page.goto(url)
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
                30000,
            )
            if not is_visible:
                raise Exception("Body not visible")

            await self._simulate_user(page)
            self.handle_listeners(page)

            for action in actions:
                await self.execute(page, action)

            html = await page.content()
            metadata = {
                "title": await page.title(),
                "url": url,
                "status": nav_response.status if nav_response else None,
                "headers": dict(nav_response.headers) if nav_response else {},
                "cookies": await page.context.cookies(),
                "storage": await page.context.storage_state(),
                "screenshots": self.screenshots,
            }
            shot_bytes = [s for s in self.screenshots if isinstance(s, bytes)]
            return Document(
                url=url,
                html=html,
                metadata=metadata,
                markdown=None,
                screenshots=shot_bytes,
            )
        finally:
            try:
                self.handle_listeners(page)
            except StopIteration:
                pass

    # need to implement custom filters as well
    # best to use a user defined callaback which takes the request and response and returns a value
    def handle_listeners(self, page: Page):
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

    async def _remove_popups(self, page: Page):
        remove_popup_js = load_script("remove_popup")
        try:
            await self.adapter.evaluate(
                page,
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
            """,
            )
            await page.wait_for_timeout(500)
        except Exception as e:
            self._logger.error(
                msg="Failed to remove popups", tag="SCRAPE", error=str(e)
            )

    async def _simulate_user(self, page: Page):
        pass

    def wait(self):
        pass

    def screenshot(self):
        pass

    async def execute(
        self, page: Page, action: Union[Action, str], timeout: Optional[int] = None
    ) -> Any:
        if isinstance(action, str):
            _ = timeout  # reserved for future per-call timeout wiring
            return await page.evaluate(action)

        if action.selector is not None:
            if action.selector.kind == "load_state":
                await page.wait_for_load_state(
                    action.selector.value, timeout=action.timeout
                )
                return
            if action.selector.kind == "url":
                await page.wait_for_url(action.selector.value, timeout=action.timeout)
                return

        if action.kind == "goto":
            await page.goto(action.value)
        elif action.kind == "back":
            await page.back()
        elif action.kind == "forward":
            await page.forward()
        elif action.kind == "reload":
            await page.reload()
        elif action.kind == "click":
            await page.click(self._element_target(action))
        elif action.kind == "type":
            text = action.value
            if text is None:
                raise ValueError("type action requires value (text to type)")
            await page.type(self._element_target(action), text)
        elif action.kind == "press":
            key = action.value
            if key is None:
                raise ValueError("press action requires value (key name, e.g. Enter)")
            await page.press(self._element_target(action), key)
        elif action.kind == "hover":
            await page.hover(self._element_target(action))
        elif action.kind == "scroll":
            await page.scroll(action.value)
        elif action.kind == "screenshot":
            if action.value:
                await page.screenshot(path=action.value)
                self.screenshots.append(action.value)
            else:
                self.screenshots.append(await page.screenshot())
        elif action.kind == "run_js_code":
            await page.evaluate(action.value)
        else:
            raise ValueError(f"Invalid action: {action.kind}")

    def _playwright_selector_string(self, sel: Selector) -> str:
        """
        Map a Scout Selector to a Playwright selector string for DOM actions
        (click, type, hover, press).

        Only kinds that resolve to a locator string are supported here.
        ``url``, ``load_state``, and ``state`` describe navigation / readiness /
        custom conditions, not elements — use them via dedicated wait APIs, not
        as the target of an interaction.
        """
        if sel.kind == "css":
            return sel.value
        if sel.kind == "tag":
            return sel.value
        if sel.kind == "xpath":
            return f"xpath={sel.value}"
        if sel.kind == "text":
            return f"text={sel.value}"
        if sel.kind == "url":
            raise ValueError(
                "Selector kind 'url' matches request URL patterns (e.g. **/api/x); "
                "it is not a DOM selector. For clicks, use css, tag, xpath, or text; "
                "for network waits, use page.wait_for_response(...) with this pattern."
            )
        if sel.kind == "load_state":
            raise ValueError(
                "Selector kind 'load_state' is for page.wait_for_load_state(...) "
                f"(e.g. {sel.value!r}), not for click/type. Pass load state waits outside "
                "of _element_target, or use a DOM selector kind for the element."
            )
        raise ValueError(f"Unknown selector kind: {sel.kind!r}")

    def _element_target(self, action: Action) -> str:
        """Prefer `action.selector` for element actions; fall back to `action.value` (raw CSS string)."""
        if action.selector is not None:
            return self._playwright_selector_string(action.selector)
        if action.value is not None:
            return action.value
        raise ValueError(f"Action {action.kind!r} requires a selector or value")
