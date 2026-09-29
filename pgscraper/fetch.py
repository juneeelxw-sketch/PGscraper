"""Load PropertyGuru pages in a real (headless) Chromium via Playwright."""

from __future__ import annotations

import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import BrowserContext, Page, sync_playwright

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


def _challenged(page: Page) -> bool:
    title = (page.title() or "").lower()
    return any(t in title for t in ("just a moment", "attention required", "access denied"))


class Fetcher:
    """One browser session for a whole run.

    The browser profile (cookies) is kept in `profile_dir`, so once you have
    passed PropertyGuru's "Verify you are human" check in a visible browser
    (--headful), later pages and later runs usually don't ask again.
    """

    def __init__(self, headless: bool = True, delay: tuple[float, float] = (3.0, 6.0),
                 debug_dir: str | None = None, profile_dir: str = "browser-profile",
                 human_wait_seconds: int = 180):
        self.headless = headless
        self.delay = delay
        self.debug_dir = Path(debug_dir) if debug_dir else None
        self.profile_dir = profile_dir
        self.human_wait_seconds = human_wait_seconds
        self._pw = None
        self._ctx: BrowserContext | None = None
        self._page: Page | None = None
        self._last = 0.0

    def __enter__(self) -> "Fetcher":
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            self.profile_dir,
            headless=self.headless,
            locale="en-SG",
            timezone_id="Asia/Singapore",
            viewport={"width": 1366, "height": 900},
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self

    def __exit__(self, *exc) -> None:
        if self._ctx:
            self._ctx.close()
        if self._pw:
            self._pw.stop()

    def _throttle(self) -> None:
        wait = random.uniform(*self.delay) - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def _wait_for_check(self, page: Page, url: str) -> None:
        """Let an automatic check finish; in a visible browser, wait for the user to tick the box."""
        for _ in range(10):  # automatic checks usually clear within a few seconds
            if not _challenged(page):
                return
            page.wait_for_timeout(1500)
        if self.headless:
            raise BlockedError(f"PropertyGuru asked to verify you are human at {url}. "
                               "Run with --headful on your own computer and tick the box.")
        print(">>> PropertyGuru is asking you to verify you're human. Tick the box in the "
              f"browser window (waiting up to {self.human_wait_seconds}s)...", file=sys.stderr)
        deadline = time.time() + self.human_wait_seconds
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            if not _challenged(page):
                print(">>> Thanks, continuing.", file=sys.stderr)
                return
        raise BlockedError(f"Verification wasn't completed in time at {url}")

    def get(self, url: str) -> tuple[str, str, list[dict]]:
        """Return (html, visible_text, dom_cards) for a URL."""
        assert self._page is not None
        self._throttle()
        page = self._page
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        self._wait_for_check(page, url)
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

        if _challenged(page) or (resp and resp.status == 429):
            raise BlockedError(f"Blocked by PropertyGuru (title {page.title()!r}) at {url}")
        return html, text, cards
