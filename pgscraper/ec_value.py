"""Value 3BR EC shortlist: 3-bedroom Executive Condos completed 2016 or later, under a price cap.

Run with:  python -m pgscraper.ec_value --headful

Re-checks every listing in data/ec_value_3br_shortlist.csv, searches PropertyGuru for more in each
eligible EC project, opens each listing for its bedrooms, size and photos, and writes:

  output/ec_value_3br_<date>/deck.html   one slide per listing, photos embedded; print to PDF to send
  output/ec_value_3br_<date>/shortlist.xlsx
  output/ec_value_3br_<date>/photos/      the downloaded photos
"""

from __future__ import annotations

import argparse
import base64
import csv
import html as htmllib
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font

from . import config
from .__main__ import crawl
from .fetch import BlockedError, Fetcher
from .parse import Listing, enrich_from_detail, extract_bedrooms, extract_photos, listing_id_from_url


@dataclass
class ECListing:
    listing: Listing
    project: str
    bedrooms: int | None = None
    photo_urls: list[str] = field(default_factory=list)
    photo_files: list[Path] = field(default_factory=list)
    note: str = ""
    live: bool = True

    @property
    def top(self) -> date:
        return date.fromisoformat(config.EC_PROJECTS[self.project][0])

    @property
    def street(self) -> str:
        return config.EC_PROJECTS[self.project][1]

    @property
    def area(self) -> str:
        return config.EC_PROJECTS[self.project][2]


def years_since(d: date, today: date) -> float:
    return (today - d).days / 365.25


def eligible_projects(today: date) -> list[str]:
    """Projects TOP'd in EC_MIN_TOP_YEAR or later that are past MOP (so can be resold)."""
    out = []
    for name, (top, *_rest) in config.EC_PROJECTS.items():
        top_date = date.fromisoformat(top)
        if top_date.year >= config.EC_MIN_TOP_YEAR and years_since(top_date, today) >= config.EC_MOP_YEARS:
            out.append(name)
    return out


def project_of(listing: Listing, projects: list[str]) -> str | None:
    hay = " ".join([listing.title, listing.address, listing.url.replace("-", " ")]).lower()
    for p in sorted(projects, key=len, reverse=True):  # "The Vales" before "Vales"
        if p.lower() in hay:
            return p
    return None


def fits(ec: ECListing) -> bool:
    l = ec.listing
    if not l.price or l.price > config.EC_MAX_PRICE:
        return False
    if l.size_sqft is not None and l.size_sqft < config.EC_MIN_SQFT:
        return False
    if ec.bedrooms is not None and ec.bedrooms != config.EC_BEDROOMS:
        return False
    return True


def load_shortlist(path: str, projects: list[str]) -> list[ECListing]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with p.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["project"] not in projects:
                continue
            l = Listing(listing_id=r["listing_id"] or listing_id_from_url(r["url"]), url=r["url"],
                        title=r["project"], address=r.get("block_address", ""),
                        price=int(r["price"]) if r.get("price") else None,
                        size_sqft=float(r["size_sqft"]) if r.get("size_sqft") else None)
            out.append(ECListing(l, r["project"], note=r.get("check", "")))
    return out


def gone(html: str, listing_id: str) -> bool:
    """True if a listing page no longer shows that listing (sold/withdrawn -> redirect or 404 page)."""
    low = html.lower()
    if any(t in low for t in ("listing is no longer available", "page not found", "no longer active")):
        return True
    return listing_id not in html


# ---------------------------------------------------------------- output

def _fmt_money(v: int | None) -> str:
    return f"S${v:,.0f}" if v else "-"


def _img_tag(path: Path, cls: str) -> str:
    mime = {"png": "image/png", "webp": "image/webp"}.get(path.suffix.lstrip(".").lower(), "image/jpeg")
    data = base64.b64encode(path.read_bytes()).decode()
    return f'<img class="{cls}" src="data:{mime};base64,{data}" alt="">'


def write_deck(path: Path, items: list[ECListing], today: date, contact: str) -> None:
    e = htmllib.escape
    slides = []
    cheapest = min(items, key=lambda x: x.listing.price or 0)
    biggest = max(items, key=lambda x: x.listing.size_sqft or 0)
    slides.append(f"""
<section class="slide cover">
  <div class="kicker">Value 3BR · Executive Condos</div>
  <h1>3-bedroom ECs under {_fmt_money(config.EC_MAX_PRICE)}</h1>
  <p class="sub">{config.EC_MIN_SQFT:,}+ sqft · completed {config.EC_MIN_TOP_YEAR} or later ·
     past MOP, open to all buyers</p>
  <div class="stats">
    <div><b>{len(items)}</b><span>listings</span></div>
    <div><b>{len({i.project for i in items})}</b><span>projects</span></div>
    <div><b>{_fmt_money(cheapest.listing.price)}</b><span>from</span></div>
    <div><b>{biggest.listing.size_sqft or 0:,.0f} sqft</b><span>largest</span></div>
  </div>
  <p class="foot">Prepared {today:%d %b %Y}{' · ' + e(contact) if contact else ''}</p>
</section>""")

    rows = [f"<tr><td>{e(i.project)}</td><td>{e(i.area)}</td><td>{i.top.year}</td>"
            f"<td class=n>{i.listing.size_sqft or 0:,.0f}</td><td class=n>{_fmt_money(i.listing.price)}</td>"
            f"<td class=n>{_fmt_money(round(i.listing.psf)) if i.listing.psf else '-'}</td></tr>"
            for i in items]
    per = 14
    for start in range(0, len(rows), per):
        more = f" ({start // per + 1}/{-(-len(rows) // per)})" if len(rows) > per else ""
        slides.append(f"""
<section class="slide">
  <h2>At a glance{more}</h2>
  <table><thead><tr><th>Project</th><th>Area</th><th>TOP</th><th class=n>Sqft</th><th class=n>Asking</th>
  <th class=n>PSF</th></tr></thead><tbody>{''.join(rows[start:start + per])}</tbody></table>
</section>""")

    for i in items:
        l = i.listing
        photos = [p for p in i.photo_files if p.exists()]
        hero = _img_tag(photos[0], "hero") if photos else '<div class="hero empty">Photos on request</div>'
        thumbs = "".join(_img_tag(p, "thumb") for p in photos[1:4])
        age = years_since(i.top, today)
        facts = [("Asking", _fmt_money(l.price)), ("Size", f"{l.size_sqft or 0:,.0f} sqft"),
                 ("PSF", _fmt_money(round(l.psf)) if l.psf else "-"),
                 ("Bedrooms", str(i.bedrooms or config.EC_BEDROOMS)),
                 ("TOP", f"{i.top:%b %Y} ({age:.0f} yrs)"), ("Tenure", "99-yr lease")]
        if l.floor_hint:
            facts.append(("Floor", l.floor_hint))
        fact_html = "".join(f"<div><span>{k}</span><b>{e(v)}</b></div>" for k, v in facts)
        slides.append(f"""
<section class="slide listing">
  <div class="photos">{hero}<div class="thumbs">{thumbs}</div></div>
  <div class="info">
    <div class="kicker">{e(i.area)}</div>
    <h2>{e(i.project)}</h2>
    <p class="addr">{e(l.address or i.street)}</p>
    <div class="facts">{fact_html}</div>
    <p class="ref">Ref {e(l.listing_id)}</p>
  </div>
</section>""")

    slides.append(f"""
<section class="slide cover end">
  <h1>Keen to view any of these?</h1>
  <p class="sub">Tell me which ones stand out and I'll arrange viewings and check the latest prices.</p>
  <p class="foot">{e(contact) or '&nbsp;'}</p>
  <p class="fine">Asking prices and availability as listed on {today:%d %b %Y}; they can change without notice.</p>
</section>""")

    path.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Value 3BR ECs</title>
<style>
:root{{--ink:#1d2a2a;--muted:#5d6b6b;--accent:#0f6b5c;--bg:#f4f1ea;--card:#fff}}
*{{box-sizing:border-box}} body{{margin:0;background:#ddd;font:16px/1.4 "Helvetica Neue",Arial,sans-serif;color:var(--ink)}}
.slide{{width:1280px;height:720px;margin:24px auto;background:var(--bg);padding:56px 64px;position:relative;overflow:hidden;
  page-break-after:always;break-after:page}}
.kicker{{text-transform:uppercase;letter-spacing:.12em;font-size:14px;color:var(--accent);font-weight:700}}
h1{{font-size:56px;margin:16px 0}} h2{{font-size:36px;margin:8px 0 16px}}
.sub{{font-size:22px;color:var(--muted);max-width:900px}}
.cover{{background:var(--accent);color:#fff}} .cover .kicker,.cover .sub{{color:#d7efe9}}
.stats{{display:flex;gap:48px;margin-top:56px}} .stats b{{display:block;font-size:40px}} .stats span{{color:#d7efe9}}
.foot{{position:absolute;bottom:48px;left:64px;font-size:18px}} .fine{{position:absolute;bottom:20px;left:64px;font-size:12px;color:#d7efe9}}
table{{width:100%;border-collapse:collapse;font-size:15px}} th,td{{padding:6px 10px;border-bottom:1px solid #d9d4c7;text-align:left}}
th{{color:var(--muted);font-weight:600}} .n{{text-align:right;font-variant-numeric:tabular-nums}}
.listing{{display:grid;grid-template-columns:760px 1fr;gap:40px;padding:40px}}
.photos{{display:flex;flex-direction:column;gap:10px}}
.hero{{width:760px;height:470px;object-fit:cover;border-radius:6px;background:#cfc9bb}}
.hero.empty{{display:flex;align-items:center;justify-content:center;color:var(--muted)}}
.thumbs{{display:flex;gap:10px}} .thumb{{width:246px;height:150px;object-fit:cover;border-radius:4px}}
.addr{{color:var(--muted);margin:0 0 24px}}
.facts{{display:grid;grid-template-columns:1fr 1fr;gap:18px 24px}} .facts span{{display:block;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
.facts b{{font-size:24px}} .ref{{position:absolute;bottom:32px;right:48px;color:var(--muted);font-size:12px}}
@media print{{body{{background:none}} .slide{{margin:0}} @page{{size:1280px 720px;margin:0}}}}
</style></head><body>{''.join(slides)}</body></html>""", encoding="utf-8")


def write_xlsx(path: Path, items: list[ECListing], today: date) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Shortlist"
    headers = ["Project", "Area", "TOP", "Age (yrs)", "Bedrooms", "Size (sqft)", "Asking Price", "PSF",
               "Address", "Floor", "Agent", "Photos", "Notes", "URL"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i in items:
        l = i.listing
        ws.append([i.project, i.area, i.top.isoformat(), round(years_since(i.top, today), 1), i.bedrooms,
                   l.size_sqft, l.price, l.psf, l.address, l.floor_hint, l.agent, len(i.photo_files),
                   i.note, l.url])
        ws.cell(ws.max_row, len(headers)).hyperlink = l.url
    for col, fmt in (("G", '"S$"#,##0'), ("H", '"S$"#,##0'), ("F", "#,##0")):
        for cell in ws[col][1:]:
            cell.number_format = fmt
    ws.freeze_panes = "A2"
    wb.save(path)


# ---------------------------------------------------------------- run

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pgscraper.ec_value", description=__doc__.split("\n\n")[0])
    ap.add_argument("--headful", action="store_true", help="show the browser window (needs a display)")
    ap.add_argument("--no-search", action="store_true", help="only re-check the shortlist CSV")
    ap.add_argument("--photos", type=int, default=config.EC_PHOTOS_PER_LISTING, help="photos per listing")
    ap.add_argument("--contact", default="", help='your name/number for the deck, e.g. "June Ling · 9123 4567"')
    ap.add_argument("--debug", action="store_true", help="save raw HTML of every page to debug/")
    args = ap.parse_args(argv)

    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    now = datetime.now(ZoneInfo("Asia/Singapore"))
    today = now.date()
    projects = eligible_projects(today)
    log(f"Eligible EC projects ({len(projects)}): {', '.join(projects)}")

    found: dict[str, ECListing] = {e.listing.listing_id: e for e in load_shortlist(config.EC_SHORTLIST_CSV, projects)}
    out_dir = Path(config.OUTPUT_DIR) / f"ec_value_3br_{today:%Y-%m-%d}"
    photo_dir = out_dir / "photos"

    try:
        with Fetcher(headless=not args.headful, delay=config.PAGE_DELAY_SECONDS,
                     debug_dir="debug" if args.debug else None) as f:
            if not args.no_search:
                for p in projects:
                    log(f"Searching {p}...")
                    for l in crawl(f, [config.EC_SEARCH_URL.format(q=quote_plus(p))], config.EC_MAX_PAGES, log):
                        if l.listing_id not in found and project_of(l, [p]):
                            ec = ECListing(l, p)
                            if fits(ec):
                                found[l.listing_id] = ec

            candidates = list(found.values())
            log(f"{len(candidates)} candidate listings; opening each for bedrooms, size and photos.")
            for n, ec in enumerate(candidates, 1):
                l = ec.listing
                log(f"  {n}/{len(candidates)} {ec.project} {l.url}")
                try:
                    html, text, _ = f.get(l.url)
                except BlockedError:
                    raise
                except Exception as exc:
                    log(f"    skipped ({exc})")
                    continue
                if gone(html, l.listing_id):
                    ec.live = False
                    log("    no longer listed")
                    continue
                # A fresh page beats the (possibly stale) shortlist figures.
                old_price, old_size = l.price, l.size_sqft
                l.price = l.size_sqft = None
                enrich_from_detail(l, html, text)
                l.price = l.price or old_price
                l.size_sqft = l.size_sqft or old_size
                ec.bedrooms = extract_bedrooms(text)
                ec.photo_urls = extract_photos(html, l.listing_id, limit=args.photos)
                for k, url in enumerate(ec.photo_urls, 1):
                    body = f.download(url, referer=l.url)
                    if body:
                        photo_dir.mkdir(parents=True, exist_ok=True)
                        ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
                        dest = photo_dir / f"{l.listing_id}_{k}.{ext if ext in ('jpg', 'jpeg', 'png', 'webp') else 'jpg'}"
                        dest.write_bytes(body)
                        ec.photo_files.append(dest)
                log(f"    {_fmt_money(l.price)}, {l.size_sqft or 0:,.0f} sqft, {ec.bedrooms or '?'} bed, "
                    f"{len(ec.photo_files)} photos")
    except BlockedError as e:
        log(f"ERROR: {e}\nNothing was saved.")
        return 2

    keep = [ec for ec in found.values() if ec.live and fits(ec)]
    keep.sort(key=lambda ec: (ec.listing.price or 0, -(ec.listing.size_sqft or 0)))
    dropped = len(found) - len(keep)
    if not keep:
        log("ERROR: no listings matched. Re-run with --debug and check debug/*.html.")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    write_deck(out_dir / "deck.html", keep, today, args.contact)
    write_xlsx(out_dir / "shortlist.xlsx", keep, today)
    log(f"\n{len(keep)} listings kept ({dropped} dropped: sold/withdrawn or outside the criteria).")
    log(f"Deck: {out_dir / 'deck.html'}  (open in Chrome, Print > Save as PDF to send)")
    log(f"Spreadsheet: {out_dir / 'shortlist.xlsx'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
