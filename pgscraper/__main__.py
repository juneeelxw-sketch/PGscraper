"""Run with:  python -m pgscraper  [--help]"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, history, report
from .fetch import BlockedError, Fetcher, page_url
from .parse import (Listing, enrich_from_detail, listing_from_card, listings_from_next_data,
                    matches_project, next_data_from_html)


def parse_page(html: str, cards: list[dict]) -> list[Listing]:
    data = next_data_from_html(html)
    found = listings_from_next_data(data) if data is not None else []
    if not found:
        found = [l for l in (listing_from_card(c) for c in cards) if l and l.price]
    return found


def crawl(fetcher: Fetcher, search_urls: list[str], max_pages: int, log) -> list[Listing]:
    listings: dict[str, Listing] = {}
    for base in search_urls:
        for n in range(1, max_pages + 1):
            url = page_url(base, n)
            html, _, cards = fetcher.get(url)
            found = parse_page(html, cards)
            new = [l for l in found if l.listing_id not in listings]
            log(f"  page {n}: {len(found)} listings ({len(new)} new)  {url}")
            for l in new:
                listings[l.listing_id] = l
            if not new:
                break
    return list(listings.values())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pgscraper", description=f"Scrape PropertyGuru sale listings for "
                                                               f"{config.PROJECT_NAME}.")
    ap.add_argument("--url", action="append", help="search URL to crawl (repeatable; overrides config)")
    ap.add_argument("--max-pages", type=int, default=config.MAX_PAGES)
    ap.add_argument("--no-details", action="store_true", help="skip visiting each listing page "
                                                              "(faster, but finds fewer unit numbers)")
    ap.add_argument("--no-filter", action="store_true", help=f"keep listings not matching {config.PROJECT_NAME}")
    ap.add_argument("--dry-run", action="store_true", help="don't add this run to the history log")
    ap.add_argument("--headful", action="store_true", help="show the browser window (needs a display)")
    ap.add_argument("--debug", action="store_true", help="save raw HTML of every page to debug/")
    args = ap.parse_args(argv)

    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    now = datetime.now(ZoneInfo("Asia/Singapore"))
    run_at = now.strftime("%Y-%m-%d %H:%M")

    try:
        with Fetcher(headless=not args.headful, delay=config.PAGE_DELAY_SECONDS,
                     debug_dir="debug" if args.debug else None) as f:
            log("Searching PropertyGuru...")
            listings = crawl(f, args.url or config.SEARCH_URLS, args.max_pages, log)
            if not args.no_filter:
                listings = [l for l in listings if matches_project(l, config.MATCH_TERMS)]
            log(f"{len(listings)} {config.PROJECT_NAME} listings found.")

            if not args.no_details:
                for i, l in enumerate(listings, 1):
                    log(f"  details {i}/{len(listings)}: {l.url}")
                    try:
                        html, text, _ = f.get(l.url)
                        enrich_from_detail(l, html, text)
                    except BlockedError:
                        raise
                    except Exception as e:  # one bad page shouldn't sink the run
                        log(f"    skipped ({e})")
    except BlockedError as e:
        log(f"ERROR: {e}\nNothing was saved.")
        return 2

    if not listings:
        log("ERROR: no listings found. The page layout may have changed or the search returned nothing; "
            "re-run with --debug and inspect debug/*.html. History was not updated.")
        return 1

    prior = history.load(config.HISTORY_CSV)
    changes = history.diff(listings, prior)

    stamp = now.strftime("%Y-%m-%d_%H%M")
    out = Path(config.OUTPUT_DIR)
    xlsx = out / f"ubi_techpark_{stamp}.xlsx"
    report.write_xlsx(xlsx, listings, changes, prior, run_at)
    report.write_csv(out / "latest.csv", listings, changes)
    if not args.dry_run:
        history.append(config.HISTORY_CSV, listings, run_at)

    counts: dict[str, int] = {}
    for c in changes:
        counts[c.status] = counts.get(c.status, 0) + 1
    no_unit = sum(1 for l in listings if not l.unit_no)
    log(f"\nSaved {xlsx}  and  {out / 'latest.csv'}")
    log("Summary: " + ", ".join(f"{k.lower()} {v}" for k, v in sorted(counts.items())))
    if no_unit:
        log(f"{no_unit} listing(s) don't state a unit number (shown as '(not stated)').")
    return 0


if __name__ == "__main__":
    sys.exit(main())
