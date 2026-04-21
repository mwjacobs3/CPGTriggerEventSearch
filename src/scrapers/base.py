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
# We want mid-market ($5M–$100M). Exclude Fortune 500 / mega-cap mentions.
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

# International exclusions — we want US-based companies
EXCLUDED_LOCATIONS = [
    "united kingdom", " uk ", "australia", " canada", "india",
    "germany", "france", "china", "japan", "mexico", "brazil",
    "europe", "european", "asia", "africa", "middle east",
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
        ICP filters (public company, non-US, not CPG-relevant).
        """
        combined = f"{title} {description}".lower()
        company = self._extract_company(title)

        if self.exclude_public and self._is_public_company(combined):
            return None

        # Mega retailers / corps are only disqualifying when they're the
        # SUBJECT of the article. A mid-market CPG brand entering Meijer /
        # Target / Whole Foods is a valid signal.
        if self._is_excluded_subject(title, company, combined):
            return None

        if self._is_excluded_location(combined):
            return None

        if event_type is None:
            event_type = self._classify(combined)

        keywords_hit = self._matched_keywords(combined, event_type)
        if not keywords_hit and not self._is_cpg_relevant(combined):
            return None

        score = self._relevance_score(combined, event_type, keywords_hit)
        industry = self._classify_industry(combined, industry_hint)

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
            description=description[:2000] if description else "",
            industry=industry,
            person_name=self._extract_person(title, event_type),
            person_title=self._extract_person_title(title, event_type),
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
        for loc in EXCLUDED_LOCATIONS:
            if loc in text:
                return True
        return False

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
        self, text: str, event_type: EventType, keywords_hit: list[str]
    ) -> float:
        score = min(len(keywords_hit) * 15, 60)  # up to 60 from keyword hits

        # Bonus for target-size signals
        if any(s in text for s in TARGET_SIZE_SIGNALS):
            score += 20

        # Bonus for key retail doors (retail expansion is highest value)
        if event_type == EventType.RETAIL_EXPANSION:
            for retailer in ["whole foods", "target", "walmart", "costco", "amazon"]:
                if retailer in text:
                    score += 10

        # Penalty for very generic / low-signal articles
        if len(keywords_hit) == 0:
            score -= 20

        return min(max(score, 0), 100)

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
