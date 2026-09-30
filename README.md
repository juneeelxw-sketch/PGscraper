# PGscraper — Ubi Techpark sale listings

Scrapes PropertyGuru for **Ubi Techpark (10 Ubi Crescent, S408564)** units for sale and records
**unit number, asking price, floor area (sqft) and PSF**. Every run is logged, so each report shows
what's new, which prices changed, and which listings were taken down since the last run.

## Setup (on your own computer)

Needs Python 3.10+. In a terminal, from this folder:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Run

```bash
python -m pgscraper --headful
```

A browser window opens. If PropertyGuru shows **"Verify you are human"**, tick the box — the
scraper waits up to 3 minutes for you, then carries on by itself. Your pass is saved in
`browser-profile/`, so later runs usually don't ask again. Afterwards, commit
`data/observations.csv` so the next run can compare against it.

> **Why not fully automatic / in the cloud?** PropertyGuru uses Cloudflare, which shows a
> human-verification checkbox to server and headless browsers. The scraper doesn't try to get
> around that; a person ticks it once from a normal home/office connection.

Output:

| File | What |
|---|---|
| `output/ubi_techpark_<date>.xlsx` | **Listings** (current, sorted by PSF, colour-coded status), **Changes** since last run, **By Unit** (same unit listed by several agents grouped together), **Price History** (every run) |
| `output/latest.csv` | Current listings, flat |
| `data/observations.csv` | Running log of every scrape — this is the "memory" used for change tracking. Commit it. |

Useful flags: `--no-details` (don't open each listing page; faster, fewer unit numbers),
`--dry-run` (don't log this run), `--debug` (save raw HTML to `debug/`),
`--headful` (visible browser, local machine only), `--url <search url>` (custom search).
Search URLs and match terms live in `pgscraper/config.py`.

## Value 3BR EC shortlist + client deck

```bash
python -m pgscraper.ec_value --headful --contact "Your Name · 9123 4567"
```

Finds **3-bedroom Executive Condos, 1,000+ sqft, asking S$1.6M or less, in projects that TOP'd within
the last 10 years and are past their 5-year MOP**. It re-checks every listing in
`data/ec_value_3br_shortlist.csv`, searches PropertyGuru for more in each eligible project, opens each
listing for bedrooms, size and photos, and drops anything sold, withdrawn or outside the criteria.

| File | What |
|---|---|
| `output/ec_value_3br_<date>/deck.html` | Slide deck: cover, "at a glance" table, one slide per listing with photos. Open in Chrome → Print → Save as PDF to send. |
| `output/ec_value_3br_<date>/shortlist.xlsx` | Same listings with agent, notes and links, for your own follow-up |
| `output/ec_value_3br_<date>/photos/` | Downloaded listing photos |

Criteria, the project list with TOP dates, and photos per listing are in `pgscraper/config.py`
(`EC_*`). `--no-search` only re-checks the shortlist CSV.

## How it works

1. Opens the PropertyGuru search results in headless Chromium and pages through them.
2. Reads the listing data PropertyGuru embeds in each page (`__NEXT_DATA__` JSON), falling back to
   the visible listing cards.
3. Keeps only listings that mention Ubi Techpark / 10 Ubi Crescent / 408564.
4. Opens each listing to look for a unit number (`#03-45`, `unit 3-45`, …) in the description.
   Agents often don't give one; those rows show `(not stated)` plus any floor hint ("High Floor", "Level 5").
5. Compares with `data/observations.csv` to mark NEW / PRICE DOWN / PRICE UP / RELISTED / REMOVED.

If PropertyGuru blocks the browser or returns nothing, the run stops **without** touching history,
so a blocked run can't mark every listing as removed.

## Tests

```bash
python -m pytest
```
