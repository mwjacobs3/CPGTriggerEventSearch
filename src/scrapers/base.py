"""Base scraper with DOSS ICP filtering — mid-market US CPG companies only."""

from __future__ import annotations

import hashlib
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import requests

from ..models import EventType, TriggerEvent


# ── Company-size & public-company exclusions ─────────────────────────────────
# We want mid-market ($5M–$500M). Exclude Fortune 500 / mega-cap mentions.
PUBLIC_COMPANY_INDICATORS = [
    "nasdaq:", "(nasdaq", "nyse:", "(nyse", "otcbb:", "(otcbb",
    "otc markets", "(otcqx", "(otcqb", "amex:", "(amex",
    "s&p 500", "fortune 500", "fortune 100", "fortune 1000",
    "russell 2000", "russell 1000", "dow jones industrial",
    "publicly traded", "publicly-traded", "publicly held",
    "market capitalization of", "market cap of $",
    "q1 earnings", "q2 earnings", "q3 earnings", "q4 earnings",
    "quarterly earnings", "annual report",
    "10-k filing", "10-q filing", "8-k filing",
    "sec filing", "proxy statement", "investor relations",
    "shareholder meeting", "dividend declaration",
]

# Ticker patterns: (NYSE: ABC), (NASDAQ: XYZ), NYSE:ABC, etc.
PUBLIC_TICKER_REGEX = re.compile(
    r"\((?:nyse|nasdaq|otcbb|otcqx|otcqb|amex|lse|tsx|asx)\s*[:.]\s*[a-z0-9.\-]{1,6}\)"
    r"|\b(?:nyse|nasdaq|otcbb|amex|lse|tsx|asx)\s*:\s*[a-z0-9.\-]{1,6}\b",
    re.IGNORECASE,
)

# Mega CPG manufacturers — if they appear anywhere in the text, drop the
# article (it's either about them or an acquisition involving them).
EXCLUDED_MEGA_CPG = [
    "nestle", "nestlé", "unilever", "procter & gamble", " p&g ",
    "colgate", "l'oreal", "loreal", "l’oreal",
    "johnson & johnson", " j&j ", "kimberly-clark",
    "general mills", "kraft heinz", "campbell soup", "conagra", "hershey",
    "mondelez", "pepsico", "coca-cola", "coca cola", "mars inc",
    "mars wrigley", "mars petcare",
    "kellogg", "kellanova", "post holdings", "treehouse foods",
    "sysco", "us foods", "performance food group",
    "reckitt", "church & dwight", "clorox",
    "anheuser-busch", "anheuser busch", "ab inbev", "molson coors",
    "constellation brands", "diageo", "heineken", "keurig dr pepper",
    "tyson foods", " tyson ", "hormel", "smithfield foods",
    "archer daniels midland", " adm ", "bunge",
    "estee lauder", "estée lauder", "coty inc", "revlon inc",
    "haleon", "kenvue",
]

# Major retailers / large corporations — filter ONLY when they are the
# subject of the article. A mid-market CPG brand *entering* Meijer / Target /
# Whole Foods / Container Store is a HIGH-value signal for DOSS, so we can't
# blanket-exclude these names.
EXCLUDED_MEGA_SUBJECTS = [
    # Grocery / mass
    "walmart", "amazon", "target", "target corporation",
    "kroger", "costco", "costco wholesale",
    "albertsons", "safeway", "dollar general", "dollar tree",
    "family dollar", "five below", "ollie's",
    "meijer", "publix", "wegmans", "h-e-b", "heb grocery",
    "giant eagle", "ahold delhaize", "ahold", "stop & shop",
    "food lion", "harris teeter", "whole foods", "whole foods market",
    "trader joe's", "trader joes", "sprouts farmers market",
    "aldi", "lidl",
    # Drug / convenience
    "cvs", "cvs health", "cvs pharmacy", "walgreens", "rite aid",
    "7-eleven", "circle k",
    # Big-box / specialty
    "home depot", "the home depot", "lowe's", "lowes",
    "best buy", "macy's", "macys", "nordstrom", "jcpenney",
    "kohl's", "kohls", "tjx", "tj maxx", "marshalls", "homegoods",
    "dick's sporting goods", "academy sports", "tractor supply",
    "bed bath", "container store", "the container store",
    "ikea", "williams-sonoma", "pottery barn",
    "ulta", "ulta beauty", "sephora",
    "petsmart", "petco", "pet supplies plus",
    "sam's club", "sams club", "bj's wholesale", "bjs wholesale",
    "five below", "burlington", "ross stores", "dollar tree",
    # Beauty / apparel department stores
    "saks fifth avenue", "bloomingdale's", "bloomingdales", "neiman marcus",
    # QSR / foodservice (not CPG)
    "starbucks", "mcdonald's", "mcdonalds", "chipotle", "dunkin",
    "burger king", "wendy's", "wendys", "taco bell", "kfc",
    "domino's", "dominos", "pizza hut", "subway restaurants",
    "chick-fil-a", "chick fil a", "panera bread", "shake shack",
    # Media / tech / entertainment
    "espn", "the walt disney", "walt disney", "disney company", "disney+",
    "warner bros", "warner media", "warnermedia",
    "nbcuniversal", "nbc universal", "paramount global", "paramount+",
    "fox corporation", "fox news", "comcast", "netflix", "spotify",
    "meta platforms", "alphabet inc", "apple inc", "microsoft",
    "abc news", "cbs news", "nbc news",
    # Airlines / hospitality / telecom (not DOSS ICP)
    "united airlines", "delta air lines", "american airlines", "southwest airlines",
    "marriott", "hilton worldwide", "hyatt hotels",
    "verizon", "at&t", "t-mobile",
    "exxon", "chevron", "shell plc",
]

# Legacy alias — preserved so older configs that reference this still load.
EXCLUDED_COMPANIES = EXCLUDED_MEGA_CPG

# Positive signals that a company is in the right size band
TARGET_SIZE_SIGNALS = [
    "series a", "series b", "seed round", "bootstrap", "emerging brand",
    "startup", "dtc", "direct-to-consumer", "d2c", "challenger brand",
    "growing brand", "independent brand", "family-owned", "founder-led",
]

# Location signals — we FLAG rather than exclude. US companies are the
# priority DOSS ICP (US-based supply chain / 3PL footprint), but an
# international brand entering US retail or raising from US funds is still
# a valid lead — it gets tagged "International" and scored lower.
INTERNATIONAL_SIGNALS = [
    "united kingdom", " uk ", " u.k.", "britain", "british", "london",
    "australia", "australian", "sydney", "melbourne",
    " canada", "canadian", "toronto", "vancouver", "montreal",
    "india", "indian", "mumbai", "bangalore", "delhi",
    "germany", "german", "berlin", "munich",
    "france", "french", "paris",
    "china", "chinese", "shanghai", "beijing",
    "japan", "japanese", "tokyo",
    "mexico", "mexican",
    "brazil", "brazilian",
    "europe", "european union", " eu ",
    "asia-pacific", "apac", "asia pacific",
    "africa", "african",
    "middle east", "uae", "dubai", "saudi arabia",
    "singapore", "hong kong", "south korea", "korean",
    "ireland", "irish", "dublin",
    "netherlands", "dutch", "amsterdam",
    "spain", "spanish", "madrid", "barcelona",
    "italy", "italian", "milan", "rome",
    "sweden", "swedish", "stockholm",
    "new zealand",
]

# Explicit US signals: we look for these FIRST — if present, it's a US company
# even if the article also mentions international markets (e.g. "US-based X
# expands to Europe").
US_SIGNALS = [
    " u.s.", " u.s ", "u.s.-based", "us-based", "usa",
    "united states", " american ", "america",
    "stateside", "domestic market",
]

# US state names + abbreviations — presence strongly implies a US HQ or plant.
US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "washington, d.c.",
    "district of columbia",
}

# City, ST patterns like "Austin, TX" / "New York, NY"
US_CITY_STATE_REGEX = re.compile(
    r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?,\s*"
    r"(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
    r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|"
    r"UT|VT|VA|WA|WV|WI|WY|DC)\b"
)

# ── Founder extraction patterns ──────────────────────────────────────────────
# Applied to original-case text so the captured name is properly capitalized.
# Run in order; first match wins.
_FOUNDER_REGEXES = [
    # "founded by Jane Doe" / "was founded by Jane Doe"
    re.compile(r"[Ff]ounded\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z'’\-]+){1,2})"),
    # "Founder & CEO Jane Doe" / "Co-Founder and CEO Jane Doe"
    re.compile(
        r"(?:[Cc]o-)?[Ff]ounder\s*(?:and|&|,)\s*(?:[Cc]o-)?(?:CEO|COO|CMO|CFO|President)\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z'’\-]+){1,2})"
    ),
    # "Jane Doe, founder" / "Jane Doe, co-founder and CEO"
    re.compile(
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z'’\-]+){1,2}),\s+(?:the\s+)?(?:[Cc]o-)?[Ff]ounder"
    ),
    # "founder Jane Doe" / "co-founder Jane Doe" at clause start
    re.compile(
        r"(?:^|[.\s])(?:[Cc]o-)?[Ff]ounder\s+([A-Z][a-z]+(?:\s+[A-Z][a-z'’\-]+){1,2})"
    ),
]

# Tokens that look like capitalized names but are not people — avoid false
# positives like "Founder CEO" or "Founder LLC".
_FOUNDER_NAME_BLOCKLIST = {
    "Ceo", "Coo", "Cmo", "Cfo", "Llc", "Inc", "Corp", "Company",
    "President", "Partners", "Ventures", "Capital", "Holdings",
}

# ── Outreach enrichment ──────────────────────────────────────────────────────
# Extract company website (apex domain) — skip press-wire/aggregator domains
# since those are article hosts, not the company's own site.
_URL_REGEX = re.compile(r"https?://(?:www\.)?([a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z0-9\-.]+)")
_NON_COMPANY_DOMAINS = {
    "businesswire.com", "prnewswire.com", "globenewswire.com",
    "einpresswire.com", "accesswire.com", "finsmes.com",
    "techcrunch.com", "crunchbase.com", "venturebeat.com",
    "fortune.com", "inc.com", "axios.com", "beveragedaily.com",
    "fooddive.com", "foodnavigator-usa.com", "foodbusinessnews.net",
    "preparedfoods.com", "bevnet.com", "candyindustry.com",
    "snackandbakery.com", "petfoodindustry.com", "grocerydive.com",
    "progressivegrocer.com", "supermarketnews.com", "retaildive.com",
    "winsightgrocerybusiness.com", "csnews.com", "chainstoreage.com",
    "beautyindependent.com", "drugstorenews.com", "cosmeticsdesign.com",
    "happi.com", "glossy.co", "wwd.com", "naturalproductsinsider.com",
    "nutraceuticalsworld.com", "nutritionaloutlook.com",
    "modernretail.co", "retailbrew.com", "digiday.com",
    "google.com", "news.google.com", "yahoo.com",
    "linkedin.com", "twitter.com", "facebook.com", "instagram.com",
    "youtube.com", "medium.com", "substack.com",
}
_LINKEDIN_COMPANY_REGEX = re.compile(
    r"linkedin\.com/company/([a-zA-Z0-9\-_]+)", re.IGNORECASE
)
_LINKEDIN_PROFILE_REGEX = re.compile(
    r"linkedin\.com/in/([a-zA-Z0-9\-_]+)", re.IGNORECASE
)

# City, ST capture (reuses US_CITY_STATE_REGEX intent, but with named groups so
# we can pull them apart for hq_city / hq_state).
_CITY_STATE_CAPTURE_REGEX = re.compile(
    r"\b(?P<city>[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?),\s*"
    r"(?P<state>AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|"
    r"MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|"
    r"TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b"
)

# ── Viability signals ────────────────────────────────────────────────────────
# Two phrasings we see in press copy:
#   "Founded in 2018, ..."                 → pattern 1
#   "Founded by Ben Goodwin in 2018"       → pattern 2 (year after the founder name)
_FOUNDING_YEAR_REGEXES = [
    re.compile(r"[Ff]ounded\s+in\s+((?:19|20)\d{2})"),
    re.compile(
        r"[Ff]ounded\s+by\s+[A-Z][A-Za-z'’\-]+(?:\s+[A-Z][A-Za-z'’\-]+){1,4}"
        r"\s+in\s+((?:19|20)\d{2})"
    ),
]
_EMPLOYEE_COUNT_REGEXES = [
    re.compile(
        r"(?:team\s+of|workforce\s+of|employs|with)\s+"
        r"([\d,]+)\s+(?:employees|people|staff|team\s+members)",
        re.IGNORECASE,
    ),
    re.compile(r"\b([\d,]+)[-\s]+(?:person|employee)\s+(?:team|company|staff)", re.IGNORECASE),
    re.compile(r"\b([\d,]+)\s+employees\b", re.IGNORECASE),
]
_TOTAL_FUNDING_REGEX = re.compile(
    r"(?:raised|secured|bringing\s+total\s+to|total\s+of)\s+"
    r"\$\s*([\d,.]+)\s*(million|billion|M|B)\b"
    r"(?:[^.]{0,40}(?:to\s+date|in\s+total|total\s+raised|overall|across|cumulative))",
    re.IGNORECASE,
)
_SKU_COUNT_REGEX = re.compile(
    r"\b([\d,]+)\s+(?:new\s+|total\s+|additional\s+|more\s+|unique\s+)?SKUs?\b",
    re.IGNORECASE,
)

# Retailers we consider "major doors" for distribution footprint counting.
# Reuses the spirit of EXCLUDED_MEGA_SUBJECTS but narrowed to retail channels.
RETAIL_DOOR_KEYWORDS = [
    "whole foods", "target", "walmart", "costco", "kroger", "publix",
    "sprouts", "trader joe's", "trader joes", "wegmans", "meijer",
    "h-e-b", "heb", "safeway", "albertsons", "giant eagle", "food lion",
    "harris teeter", "ulta", "sephora", "cvs", "walgreens", "rite aid",
    "petsmart", "petco", "sam's club", "sams club", "bj's wholesale",
    "amazon", "7-eleven", "dollar general", "aldi", "lidl",
    "container store", "home depot", "lowe's",
]

# ── DOSS fit signals ─────────────────────────────────────────────────────────
OPS_PAIN_KEYWORDS = [
    "scaling fulfillment", "fulfillment challenges", "fulfillment partner",
    "fulfillment operations", "order fulfillment",
    "inventory management", "inventory challenges", "inventory visibility",
    "supply chain challenges", "supply chain bottleneck",
    "supply chain complexity", "supply chain transformation",
    "distribution challenges", "distribution bottleneck",
    "operational complexity", "ops challenges", "ops transformation",
    "warehouse transition", "wms migration",
    "demand planning", "forecast accuracy", "stockouts", "overstock",
    "outgrew", "outgrowing", "couldn't keep up", "can't keep up",
    "scaling operations", "scale operations", "operational headwinds",
]

TECH_STACK_KEYWORDS = [
    "shopify", "netsuite", "sap", "oracle", "bigcommerce", "woocommerce",
    "magento", "cin7", "skubana", "shipbob", "shiphero", "flowspace",
    "brightpearl", "flexport", "fishbowl", "quickbooks commerce",
    "extensiv", "deposco", "manhattan associates", "blue yonder",
    "acumatica", "microsoft dynamics", "dynamics 365",
]

THREE_PL_KEYWORDS = [
    "3pl", "third-party logistics", "third party logistics",
    "fulfillment partner", "logistics partner", "co-packer", "copacker",
    "contract manufacturer", "fulfillment center", "fulfillment network",
    "distribution center", "dc network",
]

CHANNEL_DTC_KEYWORDS = [
    "dtc", "d2c", "direct-to-consumer", "direct to consumer",
    "e-commerce brand", "ecommerce brand", "online-first",
]
CHANNEL_RETAIL_KEYWORDS = [
    "retail launch", "in stores at", "on shelves at", "hits shelves",
    "retail expansion", "enters retail", "brick-and-mortar",
    "brick and mortar", "retail-first",
]

# Signals that the story is about a CPG brand *entering* a retailer rather
# than about the retailer itself (so we can keep those even if a mega-
# retailer name appears in the title).
RETAIL_ENTRY_SIGNALS = [
    "launches at", "launches in", "launches into",
    "available at", "available in", "rolls out at", "rolls out in",
    "enters", "expands to", "expands into", "debuts at", "debuts in",
    "hits shelves at", "lands at", "now at",
    "distribution deal with", "distribution agreement with",
    "partners with", "partnership with",
]

# ── Industry classification (DOSS ICP slices) ────────────────────────────────
INDUSTRY_LABELS = {
    "food_beverage":        "Food & Beverage",
    "health_beauty":        "Health & Beauty",
    "wellness_supplements": "Supplements & Wellness",
    "household_home":       "Household & Home",
    "pet":                  "Pet & Specialty",
    "other_cpg":            "Consumer Goods (Other)",
}

INDUSTRY_KEYWORDS = {
    "food_beverage": [
        "food", "beverage", "drink", "snack", "grocery", "coffee", "tea",
        "beer", "wine", "spirits", "alcohol", "bakery", "candy", "chocolate",
        "dairy", "cheese", "yogurt", "ice cream", "frozen food", "meat",
        "seafood", "plant-based", "vegan", "protein bar", "functional beverage",
        "specialty food", "artisan food", "nutrition bar", "sauce", "condiment",
        "sparkling water", "energy drink", "soda", "kombucha", "cereal",
    ],
    "health_beauty": [
        "beauty", "skincare", "haircare", "cosmetic", "makeup", "fragrance",
        "personal care", "bath", "body care", "clean beauty", "indie beauty",
        "grooming", "shaving", "sun care", "deodorant", "nail care",
        "color cosmetic", "prestige beauty", "masstige",
    ],
    "wellness_supplements": [
        "supplement", "vitamin", "nutraceutical", "wellness", "herbal",
        "nootropic", "adaptogen", "probiotic", "collagen", "electrolyte",
        "functional supplement", "sports nutrition",
    ],
    "household_home": [
        "cleaning", "household", "laundry", "dish soap", "detergent",
        "home goods", "home care", "eco-friendly home", "paper product",
        "candle", "home fragrance",
    ],
    "pet": [
        "pet food", "pet brand", "pet care", "pet wellness", "dog food",
        "cat food", "pet treat", "pet supplement", "petsmart", "petco",
    ],
}

# RSS feed "category" hint → industry key
RSS_CATEGORY_TO_INDUSTRY = {
    "food & beverage":         "food_beverage",
    "beverage":                "food_beverage",
    "retail / grocery":        "food_beverage",
    "health & beauty":         "health_beauty",
    "supplements & wellness":  "wellness_supplements",
    "pet / specialty":         "pet",
}


class BaseScraper(ABC):

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.get("scraper", {}).get(
                "user_agent",
                "Mozilla/5.0 (compatible; CPGTriggerEventSearch/2.0)",
            )
        })
        self.timeout = config.get("scraper", {}).get("timeout", 30)
        self.request_delay = config.get("scraper", {}).get("request_delay", 1.5)

        keywords = config.get("keywords", {})
        self.kw_launch    = [k.lower() for k in keywords.get("product_launch", [])]
        self.kw_retail    = [k.lower() for k in keywords.get("retail_expansion", [])]
        self.kw_funding   = [k.lower() for k in keywords.get("funding", [])]
        self.kw_exec_hire = [k.lower() for k in keywords.get("exec_hire", [])]

        filters = config.get("territory", {}).get("company_filters", {})
        self.exclude_public = filters.get("exclude_public_companies", True)
        extra_mega_cpg = [c.lower() for c in filters.get("excluded_public_companies", [])]
        extra_subjects = [c.lower() for c in filters.get("excluded_mega_subjects", [])]
        self._excluded_mega_cpg = EXCLUDED_MEGA_CPG + extra_mega_cpg
        self._excluded_subjects = EXCLUDED_MEGA_SUBJECTS + extra_subjects

        # ICP size band — DOSS targets $5M–$500M revenue. We use total
        # funding raised and employee count as the two press-derivable
        # proxies for company size.
        size_band = filters.get("size_band", {})
        self.funding_min_usd = float(size_band.get("funding_min_usd", 5_000_000))
        self.funding_max_usd = float(size_band.get("funding_max_usd", 500_000_000))
        self.employee_min    = int(size_band.get("employee_min", 10))
        self.employee_max    = int(size_band.get("employee_max", 1_000))
        self.employee_hard_max = int(size_band.get("employee_hard_max", 2_000))

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def scrape(self) -> list[TriggerEvent]:
        pass

    # ── Event construction helpers ────────────────────────────────────────────

    def _make_event(
        self,
        title: str,
        url: str,
        description: str,
        source_name: str,
        published_date: datetime,
        event_type: Optional[EventType] = None,
        query: Optional[str] = None,
        industry_hint: Optional[str] = None,
    ) -> Optional[TriggerEvent]:
        """
        Build and validate a TriggerEvent. Returns None if the event fails
        ICP filters (public company, mega-cap, not CPG-relevant). Location
        is TAGGED (US vs International) rather than filtered — international
        companies are kept but scored lower so the US pipeline stays on top.
        """
        original   = f"{title}\n{description or ''}"
        combined   = original.lower()
        company    = self._extract_company(title)

        if self.exclude_public and self._is_public_company(combined):
            return None

        # Mega retailers / corps are only disqualifying when they're the
        # SUBJECT of the article. A mid-market CPG brand entering Meijer /
        # Target / Whole Foods is a valid signal.
        if self._is_excluded_subject(title, company, combined):
            return None

        if event_type is None:
            event_type = self._classify(combined)

        keywords_hit = self._matched_keywords(combined, event_type)
        if not keywords_hit and not self._is_cpg_relevant(combined):
            return None

        is_us, country     = self._detect_country(original, combined)
        industry           = self._classify_industry(combined, industry_hint)
        founder            = self._extract_founder(original)

        # Outreach enrichment
        website            = self._extract_website(original, url)
        company_linkedin   = self._extract_linkedin_company(original)
        founder_linkedin   = self._extract_linkedin_profile(original)
        hq_city, hq_state  = self._extract_city_state(original)

        # Viability signals — founding_year regex is case-sensitive so it
        # needs original case text (second pattern matches founder names).
        founding_year      = self._extract_founding_year(original)
        employee_count     = self._extract_employee_count(original)
        total_funding      = self._extract_total_funding(original)
        retail_doors       = self._extract_retail_doors(combined)
        sku_count          = self._extract_sku_count(combined)

        # DOSS fit signals
        ops_pain           = self._has_ops_pain(combined)
        tech_stack         = self._extract_tech_stack(combined)
        three_pl           = self._has_three_pl(combined)
        channel_mix        = self._detect_channel_mix(combined)

        score = self._relevance_score(
            combined, event_type, keywords_hit, is_us,
            ops_pain=ops_pain, three_pl=three_pl,
            retail_door_count=len(retail_doors),
            total_funding=total_funding,
            employee_count=employee_count,
        )

        from ..models import EventSource
        source_enum = EventSource.OTHER

        return TriggerEvent(
            id=self._generate_id(url, title),
            title=title.strip(),
            event_type=event_type,
            source=source_enum,
            url=url,
            published_date=published_date,
            source_name=source_name,
            company_name=company,
            company_country=country,
            is_us_company=is_us,
            description=description[:2000] if description else "",
            industry=industry,
            company_website=website,
            company_linkedin=company_linkedin,
            founder_linkedin=founder_linkedin,
            hq_city=hq_city,
            hq_state=hq_state,
            founding_year=founding_year,
            employee_count=employee_count,
            total_funding=total_funding,
            retail_doors=retail_doors,
            sku_count=sku_count,
            ops_pain_signal=ops_pain,
            tech_stack=tech_stack,
            three_pl_mention=three_pl,
            channel_mix=channel_mix,
            person_name=self._extract_person(title, event_type),
            person_title=self._extract_person_title(title, event_type),
            founder_name=founder,
            funding_round=self._extract_funding_round(combined),
            funding_amount=self._extract_funding_amount(combined),
            matched_keywords=keywords_hit,
            relevance_score=score,
            query=query,
        )

    # ── Filtering ─────────────────────────────────────────────────────────────

    def _is_public_company(self, text: str) -> bool:
        """True if the article is clearly about a publicly traded company."""
        if PUBLIC_TICKER_REGEX.search(text):
            return True
        for indicator in PUBLIC_COMPANY_INDICATORS:
            if indicator in text:
                return True
        padded = f" {text} "
        for company in self._excluded_mega_cpg:
            if company in padded:
                return True
        return False

    def _is_excluded_subject(
        self, title: str, company: str, text: str
    ) -> bool:
        """
        True if the leading company / subject of the article is a mega
        retailer or major corporation. Preserves articles where a small CPG
        brand is *entering* one of these retailers (the signal we want).
        """
        title_lower = (title or "").lower()
        company_lower = (company or "").lower().strip()

        # If the article explicitly frames a retail entry ("X launches at
        # Meijer"), keep it — the subject is the entering brand, not the
        # retailer.
        has_entry_signal = any(sig in text for sig in RETAIL_ENTRY_SIGNALS)

        for subject in self._excluded_subjects:
            # Match on the extracted company name first (most precise).
            if company_lower and subject in company_lower:
                return True
            # Fall back to checking the opening 60 chars of the title, which
            # catches cases where company extraction missed. Skip this
            # fallback when the article looks like a retail-entry story.
            if has_entry_signal:
                continue
            leading = title_lower[:60]
            if subject in leading:
                return True
        return False

    def _is_excluded_location(self, text: str) -> bool:
        """Preserved for backwards compatibility — always returns False now.
        Location is tagged via `_detect_country`, not filtered."""
        return False

    def _detect_country(
        self, original_text: str, lower_text: str
    ) -> tuple[Optional[bool], Optional[str]]:
        """
        Classify a signal as US / International / Unknown.

        Returns (is_us_company, country_label) where country_label is one of
        "US", "International", or None. US signals take priority — a US-based
        brand expanding to Europe should still be tagged US.
        """
        padded = f" {lower_text} "

        # Strong US signals
        for sig in US_SIGNALS:
            if sig in padded:
                return True, "US"

        # US state names
        for state in US_STATES:
            if f" {state} " in padded or f" {state}," in padded:
                return True, "US"

        # "Austin, TX" style city/state (use original case — regex requires caps)
        if US_CITY_STATE_REGEX.search(original_text):
            return True, "US"

        # International signals
        for sig in INTERNATIONAL_SIGNALS:
            if sig in padded:
                return False, "International"

        return None, None

    def _classify_industry(
        self, text: str, hint: Optional[str] = None
    ) -> str:
        """Return an industry key (e.g. 'food_beverage'). Falls back to a
        source-provided hint (RSS feed category) and finally 'other_cpg'."""
        scores = {
            key: sum(1 for kw in kws if kw in text)
            for key, kws in INDUSTRY_KEYWORDS.items()
        }
        best_key = max(scores, key=lambda k: scores[k])
        if scores[best_key] > 0:
            return best_key
        if hint:
            mapped = RSS_CATEGORY_TO_INDUSTRY.get(hint.strip().lower())
            if mapped:
                return mapped
        return "other_cpg"

    def _is_cpg_relevant(self, text: str) -> bool:
        cpg_terms = [
            "food", "beverage", "drink", "snack", "grocery", "nutrition",
            "supplement", "vitamin", "health", "beauty", "wellness", "skincare",
            "haircare", "cosmetic", "personal care", "household", "cleaning",
            "cpg", "consumer packaged goods", "consumer goods", "fmcg",
            "brand", "retail", "dtc", "direct to consumer", "e-commerce",
            "supply chain", "operations", "logistics", "fulfillment",
            "natural", "organic", "plant-based", "clean label", "functional",
        ]
        return any(t in text for t in cpg_terms)

    # ── Classification ────────────────────────────────────────────────────────

    def _classify(self, text: str) -> EventType:
        scores = {
            EventType.EXEC_HIRE:        sum(1 for k in self.kw_exec_hire if k in text),
            EventType.RETAIL_EXPANSION: sum(1 for k in self.kw_retail    if k in text),
            EventType.FUNDING:          sum(1 for k in self.kw_funding    if k in text),
            EventType.PRODUCT_LAUNCH:   sum(1 for k in self.kw_launch     if k in text),
        }
        best = max(scores, key=lambda e: scores[e])
        return best if scores[best] > 0 else EventType.OTHER

    def _matched_keywords(self, text: str, event_type: EventType) -> list[str]:
        mapping = {
            EventType.PRODUCT_LAUNCH:   self.kw_launch,
            EventType.RETAIL_EXPANSION: self.kw_retail,
            EventType.FUNDING:          self.kw_funding,
            EventType.EXEC_HIRE:        self.kw_exec_hire,
        }
        kws = mapping.get(event_type, [])
        return [k for k in kws if k in text]

    # ── Relevance scoring ─────────────────────────────────────────────────────

    def _relevance_score(
        self,
        text: str,
        event_type: EventType,
        keywords_hit: list[str],
        is_us: Optional[bool] = None,
        ops_pain: bool = False,
        three_pl: bool = False,
        retail_door_count: int = 0,
        total_funding: Optional[str] = None,
        employee_count: Optional[str] = None,
    ) -> float:
        score = min(len(keywords_hit) * 15, 60)  # up to 60 from keyword hits

        # Bonus for target-size signals
        if any(s in text for s in TARGET_SIZE_SIGNALS):
            score += 20

        # Retail expansion — every major door mentioned adds fit signal
        if event_type == EventType.RETAIL_EXPANSION and retail_door_count > 0:
            score += min(retail_door_count * 8, 24)

        # Penalty for very generic / low-signal articles
        if len(keywords_hit) == 0:
            score -= 20

        # Territory bias: DOSS sells into US supply chains first.
        if is_us is True:
            score += 15
        elif is_us is False:
            score -= 25

        # DOSS fit: ops pain is the strongest buying signal we can derive
        # from press copy. 3PL mentions indicate the company has outgrown
        # self-fulfillment — ripe moment for a DOSS conversation.
        if ops_pain:
            score += 15
        if three_pl:
            score += 10

        # ── Size-band signals ($5M–$500M revenue proxy) ───────────────────
        funding_usd = self._parse_funding_usd(total_funding)
        if funding_usd is not None:
            if self.funding_min_usd <= funding_usd <= self.funding_max_usd:
                score += 15
            elif funding_usd > self.funding_max_usd:
                score -= 30
            elif funding_usd > 0 and funding_usd < self.funding_min_usd:
                # Pre-revenue / very early — still a possible lead but down-weight.
                score -= 5

        emp_count = self._parse_employee_count(employee_count)
        if emp_count is not None:
            if self.employee_min <= emp_count <= self.employee_max:
                score += 10
            elif emp_count > self.employee_hard_max:
                score -= 20
            elif emp_count > self.employee_max:
                score -= 5

        return min(max(score, 0), 100)

    @staticmethod
    def _parse_funding_usd(funding_str: Optional[str]) -> Optional[float]:
        """Convert "$25 Million" / "$1.2 Billion" → float dollars. None if unparseable."""
        if not funding_str:
            return None
        m = re.search(
            r"\$?\s*([\d,]+(?:\.\d+)?)\s*(million|billion|m|b)\b",
            funding_str,
            re.IGNORECASE,
        )
        if not m:
            return None
        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            return None
        unit = m.group(2).lower()
        multiplier = 1_000_000_000 if unit in ("billion", "b") else 1_000_000
        return amount * multiplier

    @staticmethod
    def _parse_employee_count(emp_str: Optional[str]) -> Optional[int]:
        """Best-effort parse of employee_count strings like "40", "100" → int."""
        if not emp_str:
            return None
        digits = re.search(r"(\d[\d,]*)", emp_str)
        if not digits:
            return None
        try:
            return int(digits.group(1).replace(",", ""))
        except ValueError:
            return None

    # ── Extraction helpers ────────────────────────────────────────────────────

    def _extract_company(self, title: str) -> str:
        if not title:
            return ""
        clean = re.sub(r"\s+-\s+[^-]+$", "", title)  # strip " - Source Name"
        clean = re.sub(r"\s+\|\s+[^|]+$", "", clean)  # strip " | Source"
        action_verbs = [
            " raises ", " announces ", " launches ", " unveils ",
            " acquires ", " hires ", " appoints ", " names ", " secures ",
            " closes ", " taps ", " expands ", " partners ", " debuts ",
            " introduces ", " nets ", " welcomes ", " promotes ",
            " invests ", " enters ", " joins ", " signs ",
        ]
        lower, cut = clean.lower(), len(clean)
        for v in action_verbs:
            idx = lower.find(v)
            if 0 < idx < cut:
                cut = idx
        company = clean[:cut].strip(" ,;:")
        return company if 2 <= len(company) <= 80 else ""

    def _extract_person(self, title: str, event_type: EventType) -> Optional[str]:
        if event_type != EventType.EXEC_HIRE:
            return None
        # Pattern: "Company Names/Appoints FIRSTNAME LASTNAME as/to TITLE"
        m = re.search(
            r"(?:names?|appoints?|hires?|welcomes?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:as|to)",
            title,
        )
        return m.group(1) if m else None

    def _extract_person_title(self, title: str, event_type: EventType) -> Optional[str]:
        if event_type != EventType.EXEC_HIRE:
            return None
        title_keywords = [
            "vp", "vice president", "director", "chief", "head of",
            "svp", "evp", "coo", "cso", "csco",
        ]
        lower = title.lower()
        for kw in title_keywords:
            idx = lower.find(kw)
            if idx >= 0:
                return title[idx : idx + 60].split(",")[0].strip()
        return None

    def _extract_website(self, text: str, article_url: str) -> Optional[str]:
        """Return the first plausible company domain found in the article.

        Skips press-wire / aggregator / social domains (which host the
        article, not the company). Also skips the article URL's own domain.
        """
        article_host = ""
        if article_url:
            m = _URL_REGEX.search(article_url)
            if m:
                article_host = m.group(1).lower()

        for m in _URL_REGEX.finditer(text or ""):
            host = m.group(1).lower().rstrip(".,);:")
            if not host or "." not in host:
                continue
            # Normalize to apex for domain comparison
            apex = ".".join(host.split(".")[-2:])
            if apex in _NON_COMPANY_DOMAINS:
                continue
            if host == article_host or apex == article_host:
                continue
            return host
        return None

    def _extract_linkedin_company(self, text: str) -> Optional[str]:
        m = _LINKEDIN_COMPANY_REGEX.search(text or "")
        return f"linkedin.com/company/{m.group(1)}" if m else None

    def _extract_linkedin_profile(self, text: str) -> Optional[str]:
        m = _LINKEDIN_PROFILE_REGEX.search(text or "")
        return f"linkedin.com/in/{m.group(1)}" if m else None

    def _extract_city_state(
        self, text: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Return (city, 2-letter state) from "City, ST" pattern, or (None, None)."""
        m = _CITY_STATE_CAPTURE_REGEX.search(text or "")
        if not m:
            return None, None
        return m.group("city"), m.group("state")

    def _extract_founding_year(self, text: str) -> Optional[int]:
        if not text:
            return None
        for rx in _FOUNDING_YEAR_REGEXES:
            m = rx.search(text)
            if not m:
                continue
            try:
                year = int(m.group(1))
            except ValueError:
                continue
            # Sanity bound — CPG brands in this pipeline aren't from 1925.
            if 1970 <= year <= datetime.utcnow().year:
                return year
        return None

    def _extract_employee_count(self, text: str) -> Optional[str]:
        if not text:
            return None
        for rx in _EMPLOYEE_COUNT_REGEXES:
            m = rx.search(text)
            if m:
                return m.group(1).replace(",", "")
        return None

    def _extract_total_funding(self, text: str) -> Optional[str]:
        if not text:
            return None
        m = _TOTAL_FUNDING_REGEX.search(text)
        if not m:
            return None
        unit = m.group(2).capitalize()
        if unit == "M":
            unit = "Million"
        elif unit == "B":
            unit = "Billion"
        return f"${m.group(1)} {unit}"

    def _extract_retail_doors(self, text: str) -> list[str]:
        """Distinct retailers mentioned in the article — a rough footprint proxy."""
        if not text:
            return []
        found = []
        for kw in RETAIL_DOOR_KEYWORDS:
            if kw in text and kw not in found:
                found.append(kw)
        return found

    def _extract_sku_count(self, text: str) -> Optional[str]:
        if not text:
            return None
        m = _SKU_COUNT_REGEX.search(text)
        return m.group(1) if m else None

    def _has_ops_pain(self, text: str) -> bool:
        return any(kw in text for kw in OPS_PAIN_KEYWORDS) if text else False

    def _extract_tech_stack(self, text: str) -> list[str]:
        if not text:
            return []
        return [kw for kw in TECH_STACK_KEYWORDS if kw in text]

    def _has_three_pl(self, text: str) -> bool:
        return any(kw in text for kw in THREE_PL_KEYWORDS) if text else False

    def _detect_channel_mix(self, text: str) -> Optional[str]:
        if not text:
            return None
        has_dtc = any(kw in text for kw in CHANNEL_DTC_KEYWORDS)
        has_retail = (
            any(kw in text for kw in CHANNEL_RETAIL_KEYWORDS)
            or any(kw in text for kw in RETAIL_DOOR_KEYWORDS)
        )
        if has_dtc and has_retail:
            return "DTC_PLUS_RETAIL"
        if has_dtc:
            return "DTC"
        if has_retail:
            return "RETAIL"
        return None

    def _extract_founder(self, text: str) -> Optional[str]:
        """Find a founder name in the article (title + description).

        Runs for ALL event types, not just exec hires — a funding or launch
        article that mentions the founder gives us a contact point.
        """
        if not text:
            return None
        for rx in _FOUNDER_REGEXES:
            m = rx.search(text)
            if not m:
                continue
            name = m.group(1).strip()
            # Guard against capturing role titles as names
            first_token = name.split()[0] if name else ""
            if first_token in _FOUNDER_NAME_BLOCKLIST:
                continue
            if 4 <= len(name) <= 60:
                return name
        return None

    def _extract_funding_round(self, text: str) -> Optional[str]:
        for label in ["series c", "series b", "series a", "seed round", "pre-seed"]:
            if label in text:
                return label.title()
        return None

    def _extract_funding_amount(self, text: str) -> Optional[str]:
        m = re.search(
            r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion|M\b|B\b)",
            text,
            re.IGNORECASE,
        )
        if m:
            return f"${m.group(1)} {m.group(2).capitalize()}"
        return None

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_id(url: str, title: str) -> str:
        key = f"{url}|{title}".lower().strip()
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        if not date_str:
            return datetime.utcnow()
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                pass
        return datetime.utcnow()

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text or "").strip()

    def _sleep(self) -> None:
        time.sleep(self.request_delay)
