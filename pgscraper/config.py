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


# ------------------------------------------------ "Value 3BR" EC shortlist (python -m pgscraper.ec_value)

EC_MAX_PRICE = 1_600_000
EC_MIN_SQFT = 1000
EC_BEDROOMS = 3
EC_MIN_TOP_YEAR = 2016  # oldest TOP year to include (The Topiary's year)
EC_MOP_YEARS = 5  # ECs can't be resold on the open market before this

# ECs with TOP in 2016 or later, with their TOP date (source: executive-condominium.com/ecs-top-date).
# The age/MOP rules above decide which are in play on a given day; add new projects here as they TOP.
EC_PROJECTS = {
    "Waterbay": ("2016-01-27", "Edgefield Plains", "Punggol"),
    "CityLife @ Tampines": ("2016-02-03", "Tampines Central 7", "Tampines"),
    "Twin Fountains": ("2016-03-14", "Woodlands Avenue 6", "Woodlands"),
    "The Topiary": ("2016-03-22", "Fernvale Lane", "Sengkang"),
    "Forestville": ("2016-04-01", "Woodlands Drive 16", "Woodlands"),
    "Lush Acres": ("2016-07-30", "Sengkang West Way", "Sengkang"),
    "SkyPark Residences": ("2016-08-10", "Sembawang Crescent", "Sembawang"),
    "Ecopolitan": ("2016-08-29", "Punggol Walk", "Punggol"),
    "Sea Horizon": ("2016-10-07", "Pasir Ris Rise", "Pasir Ris"),
    "The Amore": ("2016-11-28", "Edgedale Plains", "Punggol"),
    "Lake Life": ("2016-12-30", "Tao Ching Road / Yuan Ching Road", "Jurong West"),
    "Bellewoods": ("2017-03-16", "Woodlands Avenue 5", "Woodlands"),
    "The Vales": ("2017-05-02", "Anchorvale Crescent", "Sengkang"),
    "Bellewaters": ("2017-05-03", "Anchorvale Crescent", "Sengkang"),
    "The Terrace": ("2017-05-25", "Edgedale Plains", "Punggol"),
    "Signature at Yishun": ("2017-07-14", "Yishun Street 51", "Yishun"),
    "Westwood Residences": ("2017-10-24", "Westwood Avenue", "Jurong West"),
    "The Brownstone": ("2017-10-30", "Canberra Drive", "Sembawang"),
    "The Criterion": ("2018-02-26", "Yishun Street 51", "Yishun"),
    "Wandervale": ("2018-03-14", "Choa Chu Kang Avenue 3", "Choa Chu Kang"),
    "Sol Acres": ("2018-03-12", "Choa Chu Kang Grove", "Choa Chu Kang"),
    "Parc Life": ("2018-03-29", "Sembawang Crescent", "Sembawang"),
    "The Visionaire": ("2018-06-14", "Canberra Drive", "Sembawang"),
    "Treasure Crest": ("2018-09-14", "Anchorvale Crescent", "Sengkang"),
    "Northwave": ("2019-02-11", "Woodlands Avenue 12", "Woodlands"),
    "iNz Residence": ("2019-04-30", "Choa Chu Kang Avenue 5", "Choa Chu Kang"),
    "Hundred Palms Residences": ("2019-12-18", "Yio Chu Kang Road", "Hougang"),
    "Rivercove Residences": ("2020-10-02", "Anchorvale Lane", "Sengkang"),
    "Piermont Grand": ("2023-01-03", "Sumang Walk", "Punggol"),
    "Parc Canberra": ("2023-09-21", "Canberra Link", "Sembawang"),
}

# Hand-researched listings that are always re-checked, even if the searches miss them.
EC_SHORTLIST_CSV = "data/ec_value_3br_shortlist.csv"
EC_SEARCH_URL = "https://www.propertyguru.com.sg/property-for-sale?freetext={q}"
EC_MAX_PAGES = 3
EC_PHOTOS_PER_LISTING = 4
