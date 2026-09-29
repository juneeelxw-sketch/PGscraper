import json

from pgscraper.history import diff
from pgscraper.parse import (Listing, extract_units, listing_from_card, listings_from_next_data,
                             matches_project, parse_money, parse_sqft)


def test_extract_units():
    assert extract_units("Rare unit #03-45 at Ubi Techpark") == "#03-45"
    assert extract_units("# 3 - 45a and unit 5-12") == "#03-45A, #05-12"
    assert extract_units("Unit no. B1-02, ramp up") == "#B1-02"
    assert extract_units("High floor, great view") == ""


def test_parse_money_and_size():
    assert parse_money("S$ 1,250,000") == 1_250_000
    assert parse_money("$1.25M") == 1_250_000
    assert parse_money(980000) == 980000
    assert parse_sqft("1,238 sqft") == 1238
    assert parse_sqft("115 sqm") == round(115 * 10.7639, 1)


NEXT_DATA = {"props": {"pageProps": {"pageData": {"data": {"listingsData": [
    {"listingData": {
        "id": 500123456, "url": "/listing/for-sale-ubi-techpark-500123456",
        "localizedTitle": "Ubi Techpark", "fullAddress": "10 Ubi Crescent",
        "price": {"value": 1500000, "pretty": "S$ 1,500,000"},
        "floorArea": {"value": 1500, "unit": "sqft"},
        "pricePerArea": {"value": 1000},
        "agent": {"name": "Jane Tan"}, "description": "Unit #04-10, ramp up",
    }},
    {"listingData": {
        "id": 500999999, "url": "/listing/for-sale-other-500999999",
        "localizedTitle": "Other Building", "fullAddress": "1 Somewhere Rd",
        "price": {"value": 2000000}, "listingFeatures": ["2,000 sqft"],
    }},
]}}}}}


def test_listings_from_next_data():
    got = {l.listing_id: l for l in listings_from_next_data(NEXT_DATA)}
    a = got["500123456"]
    assert (a.price, a.size_sqft, a.unit_no, a.agent) == (1_500_000, 1500, "#04-10", "Jane Tan")
    assert a.url == "https://www.propertyguru.com.sg/listing/for-sale-ubi-techpark-500123456"
    assert a.psf == 1000
    assert got["500999999"].size_sqft == 2000
    assert matches_project(a, ["ubi techpark"]) and not matches_project(got["500999999"], ["ubi techpark"])


def test_card_fallback():
    l = listing_from_card({"id": "", "href": "/listing/ubi-techpark-for-sale-24681357",
                           "text": "Ubi Techpark\n10 Ubi Crescent\nS$ 880,000\n1,076 sqft\n#02-33"})
    assert (l.listing_id, l.price, l.size_sqft, l.unit_no) == ("24681357", 880_000, 1076, "#02-33")


def test_history_diff():
    prior = [
        {"run_at": "2026-09-01 09:00", "listing_id": "1", "price": "1000000", "unit_no": "#01-01",
         "size_sqft": "1000", "url": "u1", "title": "", "agent": ""},
        {"run_at": "2026-09-01 09:00", "listing_id": "2", "price": "900000", "unit_no": "",
         "size_sqft": "900", "url": "u2", "title": "", "agent": ""},
        {"run_at": "2026-08-01 09:00", "listing_id": "3", "price": "800000", "unit_no": "",
         "size_sqft": "", "url": "u3", "title": "", "agent": ""},
    ]
    now = [Listing("1", price=950000), Listing("3", price=800000), Listing("4", price=1)]
    st = {c.listing_id: c.status for c in diff(now, prior)}
    assert st == {"1": "PRICE DOWN", "3": "RELISTED", "4": "NEW", "2": "REMOVED"}
