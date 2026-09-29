"""Load PropertyGuru pages in a real (headless) Chromium via Playwright."""

from __future__ import annotations

import random
import re
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import Browser, Page, sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

# Collects listing cards from the rendered DOM, used when __NEXT_DATA__ is absent.
_CARDS_JS = """
() => {
  const seen = new Map();
  const cards = document.querySelectorAll('[data-listing-id], [da-listing-id]');
  for (const el of cards) {
    const id = el.getAttribute('data-listing-id') || el.getAttribute('da-listing-id');
    const a = el.querySelector('a[href*="/listing/"]');
    if (id && !seen.has(id)) seen.set(id, {id, href: a ? a.href : '', text: el.innerText});
  }
  if (seen.size === 0) {
    for (const a of document.querySelectorAll('a[href*="/listing/"]')) {
      let el = a;
      for (let i = 0; i < 6 && el.parentElement; i++) {
        el = el.parentElement;
        if (/\\$\\s?[\\d,]+/.test(el.innerText) && /sq/i.test(el.innerText)) break;
      }
      const href = a.href.split('?')[0];
      if (!seen.has(href)) seen.set(href, {id: '', href, text: el.innerText});
    }
  }
  return [...seen.values()];
}
"""


class BlockedError(RuntimeError):
    """PropertyGuru served a bot challenge / access-denied page."""


def page_url(search_url: str, page_no: int) -> str:
    """/property-for-sale?x=y -> /property-for-sale/2?x=y"""
    if page_no <= 1:
        return search_url
    parts = urlsplit(search_url)
    path = re.sub(r"/\d+$", "", parts.path.rstrip("/")) + f"/{page_no}"
    return urlunsplit(parts._replace(path=path))


class Fetcher:
    def __init__(self, headless: bool = True, delay: tuple[float, float] = (3.0, 6.0),
                 debug_dir: str | None = None):
        self.headless = headless
        self.delay = delay
        self.debug_dir = Path(debug_dir) if debug_dir else None
        self._pw = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._last = 0.0

    def __enter__(self) -> "Fetcher":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = self._browser.new_context(
            user_agent=USER_AGENT,
            locale="en-SG",
            timezone_id="Asia/Singapore",
            viewport={"width": 1366, "height": 900},
        )
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self._page = ctx.new_page()
        return self

    def __exit__(self, *exc) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _throttle(self) -> None:
        wait = random.uniform(*self.delay) - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def get(self, url: str) -> tuple[str, str, list[dict]]:
        """Return (html, visible_text, dom_cards) for a URL."""
        assert self._page is not None
        self._throttle()
        page = self._page
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        # Give a Cloudflare-style interstitial a chance to clear itself.
        for _ in range(20):
            title = (page.title() or "").lower()
            if "just a moment" not in title and "attention required" not in title:
                break
            page.wait_for_timeout(1500)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass

        html = page.content()
        text = page.inner_text("body") if page.query_selector("body") else ""
        cards = page.evaluate(_CARDS_JS)

        if self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", url)[-120:]
            (self.debug_dir / f"{slug}.html").write_text(html, encoding="utf-8")

        title = (page.title() or "").lower()
        status = resp.status if resp else 0
        if status in (403, 429) or "just a moment" in title or "access denied" in title:
            raise BlockedError(f"Blocked by PropertyGuru (HTTP {status}, title {page.title()!r}) at {url}")
        return html, text, cards
