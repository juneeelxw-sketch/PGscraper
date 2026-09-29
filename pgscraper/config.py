"""Settings for what to search and how to recognise Ubi Techpark listings."""

PROJECT_NAME = "Ubi Techpark"

# Search result pages to crawl. Page N is fetched by inserting /N into the path
# (e.g. /property-for-sale/2?...), which is how PropertyGuru paginates.
SEARCH_URLS = [
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
