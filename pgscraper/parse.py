"""Turn PropertyGuru page data into listing records.

PropertyGuru is a Next.js site: each page embeds its data as JSON in a
<script id="__NEXT_DATA__"> tag. Rather than depend on exact key paths (which
change between site releases), we walk the JSON looking for listing-shaped
objects and pull fields out by key-name heuristics. A plain-text fallback
handles listing cards scraped from the DOM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Iterator

BASE_URL = "https://www.propertyguru.com.sg"
SQM_TO_SQFT = 10.7639

# "#03-45", "# 3 - 45A", "#B1-12"
_UNIT_HASH_RE = re.compile(r"#\s*(B?\d{1,2})\s*[-–]\s*(\d{1,4}[A-Z]?)\b", re.I)
# "unit 03-45", "unit no. 3-45"
_UNIT_WORD_RE = re.compile(r"\bunit\s*(?:no\.?|number)?\s*:?\s*(B?\d{1,2})\s*[-–]\s*(\d{1,4}[A-Z]?)\b", re.I)
_FLOOR_HINT_RE = re.compile(
    r"\b(ground floor|high floor|mid floor|low floor|(?:level|lvl|floor)\s*(?:B?\d{1,2}))\b", re.I
)
_SQFT_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s?ft|sqft|square feet|sf)\b", re.I)
_SQM_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s?m|sqm|m²|square met)", re.I)
_MONEY_RE = re.compile(r"(?:S\$|\$)\s*([\d,]+(?:\.\d+)?)\s*(m|mil|million|k)?\b", re.I)


@dataclass
class Listing:
    listing_id: str
    url: str = ""
    title: str = ""
    address: str = ""
    unit_no: str = ""  # e.g. "#03-45"; several separated by ", "
    floor_hint: str = ""  # e.g. "High Floor", used when no unit number
    price: int | None = None
    size_sqft: float | None = None
    agent: str = ""
    agency: str = ""
    listed_date: str = ""
    tenure: str = ""
    text: str = field(default="", repr=False)  # searchable text blob

    @property
    def psf(self) -> float | None:
        if self.price and self.size_sqft:
            return round(self.price / self.size_sqft, 2)
        return None

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("text")
        row["psf"] = self.psf
        return row


# ---------------------------------------------------------------- text helpers

def extract_units(text: str) -> str:
    seen: list[str] = []
    for rx in (_UNIT_HASH_RE, _UNIT_WORD_RE):
        for floor, unit in rx.findall(text or ""):
            floor = floor.upper()
            if floor.isdigit():
                floor = floor.zfill(2)
            u = f"#{floor}-{unit.upper()}"
            if u not in seen:
                seen.append(u)
    return ", ".join(seen)


def extract_floor_hint(text: str) -> str:
    m = _FLOOR_HINT_RE.search(text or "")
    return m.group(1).title() if m else ""


def parse_money(value: Any) -> int | None:
    """Parse 1250000, "S$ 1,250,000", "$1.25M" -> 1250000."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    s = str(value)
    m = _MONEY_RE.search(s)
    if m:
        num = float(m.group(1).replace(",", ""))
        suffix = (m.group(2) or "").lower()
        if suffix.startswith("m"):
            num *= 1_000_000
        elif suffix == "k":
            num *= 1_000
        return int(num) if num > 0 else None
    digits = re.sub(r"[^\d.]", "", s)
    try:
        return int(float(digits)) if digits and float(digits) > 0 else None
    except ValueError:
        return None


def parse_sqft(value: Any) -> float | None:
    """Parse "1,234 sqft", "115 sqm", or a bare number (assumed sqft)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    s = str(value)
    m = _SQFT_RE.search(s)
    if m:
        return float(m.group(1).replace(",", ""))
    m = _SQM_RE.search(s)
    if m:
        return round(float(m.group(1).replace(",", "")) * SQM_TO_SQFT, 1)
    if re.fullmatch(r"\s*[\d,]+(\.\d+)?\s*", s):
        return float(s.replace(",", ""))
    return None


def absolute_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return url


def listing_id_from_url(url: str) -> str:
    m = re.search(r"-(\d{6,})(?:[/?#]|$)", url or "")
    return m.group(1) if m else ""


# ---------------------------------------------------------------- JSON walking

def next_data_from_html(html: str) -> Any:
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _walk(obj: Any) -> Iterator[dict]:
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def _strings(obj: Any, depth: int = 4) -> Iterator[tuple[str, str]]:
    """Yield (key_path, string_value) for scalar values, up to `depth` levels."""
    def rec(o: Any, path: str, d: int) -> Iterator[tuple[str, str]]:
        if isinstance(o, dict):
            if d <= 0:
                return
            for k, v in o.items():
                yield from rec(v, f"{path}.{k}" if path else str(k), d - 1)
        elif isinstance(o, list):
            if d <= 0:
                return
            for v in o:
                yield from rec(v, path, d - 1)
        elif isinstance(o, (str, int, float)) and not isinstance(o, bool):
            yield path, str(o)
    yield from rec(obj, "", depth)


def _is_listing_dict(d: dict) -> bool:
    keys = {k.lower() for k in d}
    has_id = bool(keys & {"id", "listingid", "listing_id"})
    has_price = any("price" in k for k in keys)
    has_ref = any(k in keys for k in ("url", "title", "localizedtitle", "fulladdress", "address"))
    return has_id and has_price and has_ref


def _first(d: dict, *names: str) -> Any:
    lower = {k.lower(): v for k, v in d.items()}
    for n in names:
        if n.lower() in lower and lower[n.lower()] not in (None, "", [], {}):
            return lower[n.lower()]
    return None


def _price_from(d: dict) -> int | None:
    p = _first(d, "price", "askingPrice", "priceValue")
    if isinstance(p, dict):
        return parse_money(_first(p, "value", "amount", "raw", "pretty", "formatted"))
    if p is not None:
        return parse_money(p)
    for k, v in d.items():
        if "price" in k.lower() and not isinstance(v, (dict, list)):
            val = parse_money(v)
            if val:
                return val
    return None


_AREA_KEYS = ("floorarea", "floor_area", "builtuparea", "builtup", "areasqft", "sizesqft", "sqft")


def _size_from(d: dict, text: str) -> float | None:
    skip = ("psf", "psm", "price", "land")
    pairs = [(p.lower(), v) for p, v in _strings(d, depth=4) if not any(t in p.lower() for t in skip)]
    # 1) human-readable strings such as "1,238 sqft" / "115 sqm"
    for _, v in pairs:
        if _SQFT_RE.search(v) or _SQM_RE.search(v):
            return parse_sqft(v)
    # 2) bare numbers under an area-like key, e.g. floorArea: 1238 or floorArea.value
    for path, v in pairs:
        if any(k in path for k in _AREA_KEYS) and re.fullmatch(r"[\d,]+(\.\d+)?", v):
            num = float(v.replace(",", ""))
            if num <= 0:
                continue
            return round(num * SQM_TO_SQFT, 1) if "sqm" in path else num
    return parse_sqft(text)


def listing_from_dict(d: dict) -> Listing | None:
    strings = list(_strings(d))
    text = " | ".join(v for _, v in strings)

    url = ""
    raw_url = _first(d, "url", "href", "listingUrl")
    if isinstance(raw_url, str):
        url = raw_url
    else:
        for _, v in strings:
            if "/listing/" in v:
                url = v
                break
    url = absolute_url(url)

    lid = str(_first(d, "id", "listingId", "listing_id") or "") or listing_id_from_url(url)
    if not lid:
        return None

    title = _first(d, "localizedTitle", "title", "name", "headline") or ""
    address = _first(d, "fullAddress", "address", "streetName", "location") or ""
    if isinstance(address, dict):
        address = ", ".join(v for _, v in _strings(address, 2))

    agent = agency = listed = tenure = ""
    for path, v in strings:
        p = path.lower()
        if not agent and "agent" in p and p.endswith("name") and "agency" not in p:
            agent = v
        elif not agency and "agency" in p and p.endswith("name"):
            agency = v
        if not listed and any(t in p for t in ("postedon", "createdat", "listedon", "posteddate", "datelisted")):
            listed = v
        if not tenure and "tenure" in p:
            tenure = v

    return Listing(
        listing_id=lid,
        url=url,
        title=str(title),
        address=str(address),
        unit_no=extract_units(text),
        floor_hint=extract_floor_hint(text),
        price=_price_from(d),
        size_sqft=_size_from(d, text),
        agent=agent,
        agency=agency,
        listed_date=listed,
        tenure=tenure,
        text=text,
    )


def listings_from_next_data(data: Any) -> list[Listing]:
    """Find every listing-shaped object in a __NEXT_DATA__ blob."""
    best: dict[str, tuple[int, dict]] = {}
    for d in _walk(data):
        if not _is_listing_dict(d):
            continue
        lid = str(_first(d, "id", "listingId", "listing_id"))
        score = len(list(_strings(d, 2)))
        if lid not in best or score > best[lid][0]:
            best[lid] = (score, d)
    out = []
    for _, d in best.values():
        lst = listing_from_dict(d)
        if lst and lst.price:
            out.append(lst)
    return out


def listing_from_card(card: dict) -> Listing | None:
    """Fallback: a DOM card as {'id', 'href', 'text'} scraped from the page."""
    url = absolute_url(card.get("href", ""))
    text = card.get("text", "")
    lid = str(card.get("id") or "") or listing_id_from_url(url)
    if not lid:
        return None
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return Listing(
        listing_id=lid,
        url=url,
        title=first_line,
        unit_no=extract_units(text),
        floor_hint=extract_floor_hint(text),
        price=parse_money(text),
        size_sqft=parse_sqft(text),
        text=text,
    )


def matches_project(listing: Listing, terms: Iterable[str]) -> bool:
    hay = " ".join([listing.title, listing.address, listing.text, listing.url.replace("-", " ")]).lower()
    return any(t.lower() in hay for t in terms)


def enrich_from_detail(listing: Listing, html: str, page_text: str) -> None:
    """Fill gaps (esp. unit number) from the listing's own page."""
    data = next_data_from_html(html)
    detail_text = page_text or ""
    if data is not None:
        detail_text += " | " + " | ".join(v for _, v in _strings(data, depth=12))
        match = next((d for d in _walk(data) if str(_first(d, "id", "listingId") or "") == listing.listing_id
                      and _is_listing_dict(d)), None)
        if match:
            fresh = listing_from_dict(match)
            if fresh:
                listing.price = listing.price or fresh.price
                listing.size_sqft = listing.size_sqft or fresh.size_sqft
                listing.agent = listing.agent or fresh.agent
                listing.agency = listing.agency or fresh.agency
                listing.tenure = listing.tenure or fresh.tenure
                listing.listed_date = listing.listed_date or fresh.listed_date
    if not listing.unit_no:
        listing.unit_no = extract_units(detail_text)
    if not listing.floor_hint:
        listing.floor_hint = extract_floor_hint(page_text)
    if not listing.size_sqft:
        listing.size_sqft = parse_sqft(page_text)
    listing.text += " | " + page_text
