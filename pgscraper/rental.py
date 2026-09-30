"""Keep whole-unit rentals that fit the client's brief and grade how well they fit."""

from __future__ import annotations

from . import config
from .parse import Listing

IDEAL, CLOSE = "IDEAL", "CLOSE"


def excluded(l: Listing) -> str:
    """Why a listing is out of scope, or "" if it should be kept."""
    hay = " ".join([l.property_type, l.title, l.url.replace("-", " ")]).lower()
    for term in config.RENTAL_EXCLUDE_TERMS:
        if term in hay:
            return f"excluded ({term})"
    if not l.price:
        return "no rent shown"
    if l.price > config.RENTAL_MAX_RENT:
        return f"rent over S${config.RENTAL_MAX_RENT:,}"
    if l.size_sqft and l.size_sqft < config.RENTAL_MIN_SQFT:
        return f"smaller than {config.RENTAL_MIN_SQFT} sqft"
    if l.bedrooms and l.bedrooms < config.RENTAL_MIN_BEDS:
        return f"fewer than {config.RENTAL_MIN_BEDS} bedrooms"
    return ""


def grade(l: Listing) -> tuple[str, str]:
    """(IDEAL | CLOSE, note). IDEAL = within the target rent and size, with enough bathrooms."""
    misses = []
    if l.price and l.price > config.RENTAL_IDEAL_RENT:
        misses.append(f"S${l.price - config.RENTAL_IDEAL_RENT:,} over target")
    if l.size_sqft and l.size_sqft < config.RENTAL_IDEAL_SQFT:
        misses.append(f"{config.RENTAL_IDEAL_SQFT - l.size_sqft:,.0f} sqft under target")
    if l.bathrooms and l.bathrooms < config.RENTAL_MIN_BATHS:
        misses.append(f"only {l.bathrooms} bath")
    unknown = [n for n, v in (("size", l.size_sqft), ("beds", l.bedrooms), ("baths", l.bathrooms)) if not v]
    if unknown:
        misses.append("check " + "/".join(unknown))
    return (CLOSE if misses else IDEAL), "; ".join(misses)


def select(listings: list[Listing], log=lambda m: None) -> list[Listing]:
    kept, dropped = [], {}
    for l in listings:
        why = excluded(l)
        if why:
            dropped[why] = dropped.get(why, 0) + 1
        else:
            kept.append(l)
    for why, n in sorted(dropped.items()):
        log(f"  dropped {n}: {why}")
    return kept
