from typing import Any, Awaitable, Callable, Optional, Union
from ..core import Document, Action, Selector, NetworkRule, RequestModel, ResponseModel
from ..scripts import load_script
from ..logger import get_logger
from playwright.async_api import (
    Playwright,
    Browser,
    Page,
    Request,
    Response,
    async_playwright,
)
import inspect
import random

# TODO: add functionality to use and reuse a session via storage_state in playwright
# TODO: add a way to run js code on the page

# make it dynamic
TIMEOUT = 30000


class PlaywrightAdapter:
    def __init__(
        self,
        browser_cdp_endpoint: str | None = None,
    ):
        self._browser_cdp_endpoint = browser_cdp_endpoint
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self._logger = get_logger("Playwright")
        self.screenshots: list[Union[bytes, str]] = []
        self._timeout = TIMEOUT
        self._url_timeout = TIMEOUT

        # rules
        self._network_rule = NetworkRule()

        self._requests = []
        self._responses = []

    def set_timeout(self, timeout: int = TIMEOUT) -> None:
        self._timeout = timeout

    @property
    def playwright(self) -> Playwright:
        if self._playwright is None:
            raise RuntimeError("PlaywrightAdapter is not started")
        return self._playwright

    def _action_timeout(self, action: Action) -> int:
        return action.timeout if action.timeout is not None else self._timeout

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
        # Do not suppress exceptions from inside `async with`.
        # Returning a truthy value would swallow errors and make `scrape()` look like it returned None.
        return False

    # rules
    def set_network_rule(self, rule: NetworkRule):
        self._network_rule = rule

    def set_cdp_endpoint(self, browser_cdp_endpoint: str):
        self._browser_cdp_endpoint = browser_cdp_endpoint

    # interaction methods
    async def start(self):
        self._playwright = await async_playwright().start()
        if not self._browser_cdp_endpoint:
            raise ValueError("browser_cdp_endpoint is required")
        self.browser = await self._playwright.chromium.connect_over_cdp(
            self._browser_cdp_endpoint
        )

    async def stop(self):
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self.browser = None
        return self

    async def _new_page(self) -> Page:
        assert self.browser is not None
        if self.browser.contexts:
            context = self.browser.contexts[0]
        else:
            context = await self.browser.new_context()
        return await context.new_page()

    async def scrape(self, url: str, actions: list[Action] = []):
        self.screenshots = []
        page = await self._new_page()
        page.set_default_timeout(self._timeout)
        page.set_default_navigation_timeout(self._timeout)
        listener = self._handle_listeners(page)
        try:
            nav_response = await page.goto(
                url, wait_until="domcontentloaded", timeout=self._url_timeout
            )
            await page.wait_for_selector("body", timeout=self._timeout)
            next(listener)
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
                self._timeout,
            )
            if not is_visible:
                raise Exception("Body not visible")

            await page.wait_for_timeout(500)
            await self._remove_popups(page)
            await self._simulate_user(page)

            for action in actions:
                try:
                    await self.execute(page, action)
                except Exception as e:
                    self._logger.error(msg=action.kind, error=str(e), tag=f"ACTION")

            await page.wait_for_timeout(self._timeout)
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
                requests=self._requests,
                response=self._responses,
            )
        finally:
            # Ensure generator cleanup even if it was never started.
            # `next(listener)` may raise StopIteration when the generator ends.
            try:
                next(listener)
            except StopIteration:
                pass
            # Not closing the page as it might be interfered through the cdp by other processes
            # actions are already performed on this page
            # other way would would be storing all the actions in a cache with session-id
            # then repeat/replay those actions via session id on the separate process to get the same state
            # await page.close()

    def _handle_listeners(self, page: Page):
        def _handle_requests(request: Request):
            if not self._network_rule.is_matching(request.url):
                return
            # Avoid await request.response() here: it races with navigation/teardown and
            # can raise TargetClosedError. URL is enough for debug logging.
            if self._network_rule.log_request:
                self._logger.info("%s %s", request.method, request.url, tag="REQUEST")
            self._requests.append(
                RequestModel(
                    url=request.url, method=request.method, headers=request.headers
                )
            )

        async def _handle_responses(response: Response):
            if not self._network_rule.is_matching(response.url):
                return
            if self._network_rule.log_response:
                self._logger.info(
                    "%s %s", response.url, response.status, tag="RESPONSE"
                )
            try:
                body = None
                if self._network_rule.on_response:
                    result = self._network_rule.on_response(response)
                    if inspect.isawaitable(result):
                        body = await result
                    else:
                        body = result
                else:
                    body = await response.body()
            except Exception as e:
                # Some responses don't have a retrievable body (e.g. race with teardown, caching, redirects).
                # If this bubbles out of the event callback it can abort the scrape.
                if self._network_rule.log_response:
                    self._logger.error(
                        msg="Response body unavailable for " + response.url,
                        tag="RESPONSE_BODY",
                        error=str(e),
                    )
                body = None

            self._responses.append(
                ResponseModel(
                    url=response.url,
                    headers=response.headers,
                    status=response.status,
                    method=response.request.method,
                    body=body,
                )
            )

        page.on("request", _handle_requests)
        page.on("response", _handle_responses)

        yield

        page.remove_listener("request", _handle_requests)
        page.remove_listener("response", _handle_responses)

    async def _remove_popups(self, page: Page):
        remove_popup_js = load_script("remove_popup")
        try:
            await page.evaluate(
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
                msg="Failed to remove popups", tag="CONSENT_MANAGEMENT", error=str(e)
            )

    async def _simulate_user(self, page: Page, interactions: int = 3) -> None:
        async def _sim_mouse_move() -> None:
            vp = page.viewport_size
            if vp:
                w, h = int(vp["width"]), int(vp["height"])
            else:
                size = await page.evaluate(
                    "() => ({ w: window.innerWidth, h: window.innerHeight })"
                )
                w, h = int(size["w"]), int(size["h"])
            await page.mouse.move(
                random.randint(0, max(1, w - 1)),
                random.randint(0, max(1, h - 1)),
            )

        async def _sim_wheel() -> None:
            await page.mouse.wheel(0, random.randint(120, 480))

        async def _sim_js_scroll() -> None:
            await self.execute(
                page,
                "() => window.scrollBy(0, Math.floor(120 + Math.random() * 420))",
            )

        actions: list[Callable[[], Awaitable[None]]] = [
            _sim_mouse_move,
            _sim_wheel,
            _sim_js_scroll,
        ]

        hi = min(2800, max(200, self._timeout // 5))
        lo = max(100, min(500, hi // 2))
        for _ in range(interactions):
            await random.choice(actions)()
            await page.wait_for_timeout(random.randint(lo, hi))

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
                    action.selector.value, timeout=self._action_timeout(action)
                )
                return
            if action.selector.kind == "url":
                await page.wait_for_url(
                    action.selector.value, timeout=self._action_timeout(action)
                )
                return

        t = self._action_timeout(action)
        if action.kind == "goto":
            await page.goto(action.value, timeout=t)
        elif action.kind == "back":
            await page.go_back(timeout=t)
        elif action.kind == "forward":
            await page.go_forward(timeout=t)
        elif action.kind == "reload":
            await page.reload(timeout=t)
        elif action.kind == "click":
            await page.click(self._element_target(action), timeout=t)
        elif action.kind == "type":
            text = action.value
            if text is None:
                raise ValueError("type action requires value (text to type)")
            await page.type(self._element_target(action), text, timeout=t)
        elif action.kind == "press":
            key = action.value
            if key is None:
                raise ValueError("press action requires value (key name, e.g. Enter)")
            await page.press(self._element_target(action), key, timeout=t)
        elif action.kind == "hover":
            await page.hover(self._element_target(action), timeout=t)
        elif action.kind == "scroll":
            if action.value is None:
                raise ValueError(
                    "scroll action requires value (vertical wheel delta as a number, e.g. '800')"
                )
            await page.mouse.wheel(0, float(action.value.strip()))
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

    # helpers
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
