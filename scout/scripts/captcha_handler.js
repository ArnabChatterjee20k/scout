/**
 * Captcha handler — detection and light UX helpers (similar layout to remove_popup.js).
 *
 * What this does:
 * - Finds common CAPTCHA / bot-check widgets (reCAPTCHA, hCaptcha, Turnstile, etc.)
 * - Scrolls the primary widget into view and exposes a small summary on window.__scout_captcha
 * - Returns a structured object for your Python/Playwright layer to act on (wait, pause, delegate)
 *
 * What this does NOT do:
 * - No automated “solving” of image/audio challenges, no token harvesting, no bypass of protections.
 *   Wire a compliant flow in Playwright (manual solve, official APIs, or your own backend) if needed.
 */
async () => {
    const isVisible = (el) => {
        if (!el) return false;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return false;
        const s = window.getComputedStyle(el);
        return s.display !== "none" && s.visibility !== "hidden" && Number(s.opacity) > 0;
    };

    const providers = [];
    const seenEls = new Set();

    const push = (id, el, extra = {}) => {
        if (!el || seenEls.has(el) || !isVisible(el)) return;
        seenEls.add(el);
        providers.push({ id, tag: el.tagName, ...extra });
    };

    // --- Phase 1: iframes (src patterns) ---
    const iframeSrcPatterns = [
        { id: "recaptcha", test: (u) => /google\.com\/recaptcha|recaptcha\/api2\//i.test(u) },
        { id: "hcaptcha", test: (u) => /hcaptcha\.com\/captcha/i.test(u) },
        { id: "turnstile", test: (u) => /challenges\.cloudflare\.com\/turnstile/i.test(u) },
        { id: "friendly_captcha", test: (u) => /friendlycaptcha\.com|api\.friendlycaptcha/i.test(u) },
        { id: "mtcaptcha", test: (u) => /mtcaptcha/i.test(u) },
        { id: "arkose", test: (u) => /arkoselabs|funcaptcha/i.test(u) },
    ];

    document.querySelectorAll("iframe").forEach((iframe) => {
        try {
            const src = iframe.src || "";
            for (const { id, test } of iframeSrcPatterns) {
                if (test(src)) {
                    push(id, iframe, { src: src.slice(0, 200) });
                    break;
                }
            }
        } catch (_) { /* ignore */ }
    });

    // --- Phase 2: known DOM hooks (widget roots) ---
    const rootSelectors = [
        { id: "recaptcha_v2", sel: ".g-recaptcha, [class*='g-recaptcha']" },
        { id: "recaptcha_badge", sel: ".grecaptcha-badge" },
        { id: "hcaptcha", sel: ".h-captcha, [data-hcaptcha-sitekey]" },
        { id: "turnstile", sel: ".cf-turnstile, [class*='cf-turnstile']" },
    ];

    for (const { id, sel } of rootSelectors) {
        document.querySelectorAll(sel).forEach((el) => push(id, el));
    }

    // --- Phase 3: Turnstile / Cloudflare input tokens (presence only) ---
    const cfResponse = document.querySelector(
        'input[name="cf-turnstile-response"], input[name="cf_captcha_kind"]'
    );
    if (cfResponse && isVisible(cfResponse.closest("form") || cfResponse)) {
        push("turnstile_input", cfResponse, { name: cfResponse.name });
    }

    // --- Phase 4: de-dupe by element identity ---
    const seen = new Set();
    const unique = [];
    for (const p of providers) {
        // approximate dedupe: same id + first matching element ref not stored; use JSON for simple cases
        const key = `${p.id}:${p.src || p.tag || ""}`;
        if (seen.has(key)) continue;
        seen.add(key);
        unique.push(p);
    }

    // --- Phase 5: scroll primary widget into view ---
    let scrolled = false;
    const primary =
        document.querySelector("iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='turnstile']") ||
        document.querySelector(".g-recaptcha, .h-captcha, [data-sitekey]");

    if (primary && isVisible(primary)) {
        try {
            primary.scrollIntoView({ block: "center", behavior: "instant" });
            scrolled = true;
        } catch (_) { /* ignore */ }
    }

    const summary = {
        detected: unique.length > 0,
        count: unique.length,
        providers: unique,
        scrolledIntoView: scrolled,
        href: typeof location !== "undefined" ? location.href : "",
    };

    try {
        window.__scout_captcha = summary;
    } catch (_) { /* ignore */ }

    return summary;
};
