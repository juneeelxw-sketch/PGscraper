"""Settings for what to search and how to recognise Ubi Techpark listings."""

PROJECT_NAME = "Ubi Techpark"

# Search result pages to crawl. Page N is fetched by inserting /N into the path
# (e.g. /property-for-sale/2?...), which is how PropertyGuru paginates.
SEARCH_URLS = [
    # Project-specific pages (PropertyGuru project id 20401); found via search engines.
    "https://www.commercialguru.com.sg/find-commercial-properties/property-for-sale/at-ubi-techpark-20401",
    "https://www.propertyguru.com.sg/search-property/10-ubi-crescent-ubi-techpark/sale",
    "https://www.propertyguru.com.sg/property-for-sale?market=commercial&freetext=Ubi%20Techpark",
    "https://www.propertyguru.com.sg/property-for-sale?freetext=Ubi%20Techpark",
]

# A listing counts as Ubi Techpark if its title/address/text contains any of these
# (case-insensitive). 10 Ubi Crescent, S(408564) is the development's address.
MATCH_TERMS = [
    "ubi techpark",
    "ubi tech park",
    "10 ubi crescent",
    "408564",
]

MAX_PAGES = 10
PAGE_DELAY_SECONDS = (3.0, 6.0)  # random pause between page loads

HISTORY_CSV = "data/observations.csv"
OUTPUT_DIR = "output"


# ------------------------------------------------------------------ rental search
# Used by `python -m pgscraper --rental`: whole-unit 3-bedroom rentals near the
# stations a family client can use (wife works in Sengkang, older son's school in
# Punggol, younger son likely at Pathlight in Ang Mo Kio, business at Circuit Road).

RENTAL_NAME = "3BR rentals near NEL / CCL / TEL"

_PG = "https://www.propertyguru.com.sg"

# PropertyGuru "near MRT station" pages: slug-<PropertyGuru station id>.
RENTAL_STATIONS = [
    "ne13-kovan-mrt-station-182",
    "ne14-hougang-mrt-station-185",
    "ne15-buangkok-mrt-station-188",
    "ne12-serangoon-mrt-station-179",
    "ne11-woodleigh-mrt-station-176",  # id inferred from the NE numbering; others were seen on PG
    "ne10-potong-pasir-mrt-station-173",
    "cc12-bartley-mrt-station-1634",
    "cc11-tai-seng-mrt-station-1631",
    "cc10-macpherson-mrt-station-1628",
    "ne16-sengkang-mrt-station-191",  # lower priority, but it's where the wife works
]
# Stations whose PropertyGuru id we don't know: searched by name instead.
RENTAL_FREETEXT = [
    "Lorong Chuan MRT",
    "Mayflower MRT",
    "Upper Thomson MRT",
    "Bright Hill MRT",
]
RENTAL_SEARCH_URLS = (
    [f"{_PG}/apartment-condo-for-rent/near-{s}/with-3-bedrooms" for s in RENTAL_STATIONS]
    + [f"{_PG}/property-for-rent?listingType=rent&isCommercial=false&propertyTypeGroup=N&bedrooms=3"
       f"&freetext={t.replace(' ', '%20')}" for t in RENTAL_FREETEXT]
)

# Listings outside these limits are dropped; the rest are graded in the report.
RENTAL_MAX_RENT = 5500      # show near misses up to this
RENTAL_IDEAL_RENT = 5000    # client's target
RENTAL_MIN_SQFT = 900       # show slightly smaller units down to this
RENTAL_IDEAL_SQFT = 1100    # client's target size
RENTAL_MIN_BEDS = 3
RENTAL_MIN_BATHS = 2
# Whole units in condos, ECs or landed only.
RENTAL_EXCLUDE_TERMS = ["hdb", "room rental", "common room", "master room", "master bedroom for rent",
                        "room for rent"]

RENTAL_HISTORY_CSV = "data/rental_observations.csv"
