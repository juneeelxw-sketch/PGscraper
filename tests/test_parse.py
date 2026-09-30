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


def test_rental_card_fields():
    l = listing_from_card({"id": "500111222", "href": "/listing/for-rent-rio-vista-500111222",
                           "text": "Rio Vista\nS$ 4,500 /mo\n3 Beds 2 Baths 1,238 sqft\nCondominium\n"
                                   "8 min (650 m) from NE15 Buangkok MRT Station"})
    assert (l.price, l.size_sqft, l.bedrooms, l.bathrooms) == (4500, 1238, 3, 2)
    assert l.property_type == "Condominium"
    assert l.mrt == "8 min (650 m) from NE15 Buangkok MRT Station"


def test_rental_json_fields():
    data = {"listings": [{"id": 1, "url": "/listing/for-rent-x-1", "title": "X", "price": {"value": 4800},
                          "floorArea": {"value": 1100}, "bedrooms": 3, "bathrooms": {"value": 2},
                          "propertyType": {"text": "Executive Condominium"}}]}
    l = listings_from_next_data(data)[0]
    assert (l.bedrooms, l.bathrooms, l.property_type) == (3, 2, "Executive Condominium")


def test_rental_select_and_grade():
    from pgscraper.rental import CLOSE, IDEAL, grade, select
    ideal = Listing("1", title="Jewel @ Buangkok", price=4800, size_sqft=1130, bedrooms=3, bathrooms=2,
                    property_type="Condominium")
    pricey = Listing("2", title="Kovan Melody", price=5500, size_sqft=1270, bedrooms=3, bathrooms=2)
    kept = select([ideal, pricey,
                   Listing("3", title="Blk 123", price=3500, size_sqft=1100, bedrooms=3, property_type="HDB"),
                   Listing("4", title="Quartz", price=1200, url="/listing/for-rent-room-rental-4",
                           property_type="Room Rental"),
                   Listing("5", title="Big", price=7000, size_sqft=1500, bedrooms=3),
                   Listing("6", title="Tiny", price=3000, size_sqft=700, bedrooms=3)])
    assert [l.listing_id for l in kept] == ["1", "2"]
    assert grade(ideal) == (IDEAL, "")
    assert grade(pricey) == (CLOSE, "S$500 over target")
