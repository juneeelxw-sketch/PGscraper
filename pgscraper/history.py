"""Keep every scrape in a CSV log and diff the latest run against the one before."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .parse import Listing

FIELDS = [
    "run_at", "listing_id", "unit_no", "floor_hint", "price", "size_sqft", "psf",
    "title", "address", "agent", "agency", "listed_date", "tenure", "url",
]


@dataclass
class Change:
    listing_id: str
    status: str  # NEW, RELISTED, PRICE DOWN, PRICE UP, UNCHANGED, REMOVED
    unit_no: str
    price: int | None
    prev_price: int | None
    size_sqft: float | None
    first_seen: str
    url: str
    title: str = ""
    agent: str = ""

    @property
    def price_change(self) -> int | None:
        if self.price is not None and self.prev_price is not None:
            return self.price - self.prev_price
        return None


def _num(v: str) -> float | None:
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def load(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append(path: str | Path, listings: list[Listing], run_at: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    new_file = not p.exists()
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for lst in listings:
            w.writerow({"run_at": run_at, **lst.to_row()})


def diff(current: list[Listing], rows: list[dict]) -> list[Change]:
    """Compare this run's listings with the history log (which excludes this run)."""
    runs = sorted({r["run_at"] for r in rows})
    last_run = runs[-1] if runs else None
    last_seen: dict[str, dict] = {}
    first_seen: dict[str, str] = {}
    for r in sorted(rows, key=lambda r: r["run_at"]):
        last_seen[r["listing_id"]] = r
        first_seen.setdefault(r["listing_id"], r["run_at"])
    in_last_run = {r["listing_id"] for r in rows if r["run_at"] == last_run}

    changes: list[Change] = []
    current_ids = set()
    for lst in current:
        current_ids.add(lst.listing_id)
        prev = last_seen.get(lst.listing_id)
        prev_price = int(_num(prev["price"])) if prev and _num(prev["price"]) else None
        if prev is None:
            status = "NEW"
        elif lst.listing_id not in in_last_run:
            status = "RELISTED"
        elif prev_price and lst.price and lst.price < prev_price:
            status = "PRICE DOWN"
        elif prev_price and lst.price and lst.price > prev_price:
            status = "PRICE UP"
        else:
            status = "UNCHANGED"
        changes.append(Change(
            listing_id=lst.listing_id, status=status, unit_no=lst.unit_no, price=lst.price,
            prev_price=prev_price, size_sqft=lst.size_sqft,
            first_seen=first_seen.get(lst.listing_id, "this run"), url=lst.url,
            title=lst.title, agent=lst.agent,
        ))

    for lid in sorted(in_last_run - current_ids):
        r = last_seen[lid]
        price = _num(r["price"])
        changes.append(Change(
            listing_id=lid, status="REMOVED", unit_no=r["unit_no"], price=None,
            prev_price=int(price) if price else None, size_sqft=_num(r["size_sqft"]),
            first_seen=first_seen[lid], url=r["url"], title=r["title"], agent=r["agent"],
        ))
    return changes
