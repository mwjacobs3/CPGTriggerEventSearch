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
    "nasdaq:", "(nasdaq", "nyse:", "(nyse", "otcbb:", "otc markets",
    "s&p 500", "fortune 500", "fortune 100",
]

EXCLUDED_COMPANIES = [
    "nestle", "unilever", "procter & gamble", " p&g ", "colgate",
    "l'oreal", "loreal", "johnson & johnson", "j&j", "kimberly-clark",
    "general mills", "kraft heinz", "campbell soup", "conagra", "hershey",
    "mondelez", "pepsico", "coca-cola", "coca cola", "mars inc",
    "kellogg", "post holdings", "treehouse foods", "sysco", "us foods",
    "amazon ", "walmart ", "target corp", "kroger", "costco wholesale",
    "albertsons", "dollar general", "cvs health", "walgreens",
]

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
        extra_excluded = [c.lower() for c in filters.get("excluded_public_companies", [])]
        self._excluded_companies = EXCLUDED_COMPANIES + extra_excluded

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
    ) -> Optional[TriggerEvent]:
        """
        Build and validate a TriggerEvent. Returns None if the event fails
        ICP filters (public company, non-US, not CPG-relevant).
        """
        combined = f"{title} {description}".lower()

        if self.exclude_public and self._is_public_company(combined):
            return None

        if self._is_excluded_location(combined):
            return None

        if event_type is None:
            event_type = self._classify(combined)

        keywords_hit = self._matched_keywords(combined, event_type)
        if not keywords_hit and not self._is_cpg_relevant(combined):
            return None

        score = self._relevance_score(combined, event_type, keywords_hit)

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
            company_name=self._extract_company(title),
            description=description[:2000] if description else "",
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
        for indicator in PUBLIC_COMPANY_INDICATORS:
            if indicator in text:
                return True
        for company in self._excluded_companies:
            if company in f" {text} ":
                return True
        return False

    def _is_excluded_location(self, text: str) -> bool:
        for loc in EXCLUDED_LOCATIONS:
            if loc in text:
                return True
        return False

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
