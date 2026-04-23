"""Data models for CPG trigger events."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(Enum):
    PRODUCT_LAUNCH   = "product_launch"    # New brand/product going to market
    RETAIL_EXPANSION = "retail_expansion"  # DTC brand entering retail channels
    FUNDING          = "funding"           # PE/VC Series A/B investment
    EXEC_HIRE        = "exec_hire"         # New ops/supply chain executive
    OTHER            = "other"


class EventSource(Enum):
    RSS_FEED     = "rss_feed"
    GOOGLE_NEWS  = "google_news"
    JOB_BOARD    = "job_board"   # Press-release-based exec hire detection
    FINSMES      = "finsmes"
    OTHER        = "other"


@dataclass
class TriggerEvent:
    """A single CPG trigger event surfaced as a DOSS sales signal."""

    id: str                        # sha256(url + title)
    title: str
    event_type: EventType
    source: EventSource
    url: str
    published_date: datetime

    discovered_date: datetime = field(default_factory=datetime.utcnow)
    source_name: Optional[str] = None    # Human-readable feed/source name

    # Company intel
    company_name: Optional[str] = None
    company_location: Optional[str] = None
    company_country: Optional[str] = None   # "US" | "International" | None (unknown)
    is_us_company: Optional[bool] = None    # True=US, False=Intl, None=Unknown
    industry: Optional[str] = None     # DOSS ICP slice: food_beverage, health_beauty, etc.

    # Outreach enrichment
    company_website: Optional[str] = None      # apex domain, e.g. "olipop.com"
    company_linkedin: Optional[str] = None     # linkedin.com/company/<slug>
    founder_linkedin: Optional[str] = None     # linkedin.com/in/<slug>
    hq_city: Optional[str] = None
    hq_state: Optional[str] = None             # 2-letter US state abbreviation

    # Viability signals
    founding_year: Optional[int] = None
    employee_count: Optional[str] = None       # raw string, e.g. "40", "100-person"
    total_funding: Optional[str] = None        # "$25M to date"
    retail_doors: list = field(default_factory=list)   # retailers the brand is in
    sku_count: Optional[str] = None

    # DOSS fit signals
    ops_pain_signal: bool = False              # article mentions supply-chain pain
    tech_stack: list = field(default_factory=list)     # "shopify", "netsuite", etc.
    three_pl_mention: bool = False             # 3PL / co-packer / fulfillment partner
    channel_mix: Optional[str] = None          # "DTC" | "DTC_PLUS_RETAIL" | "RETAIL"

    # Article body
    description: Optional[str] = None

    # People
    person_name: Optional[str] = None    # Exec hire specifics
    person_title: Optional[str] = None
    founder_name: Optional[str] = None   # Founder mentioned in the article

    # Funding specifics
    funding_amount: Optional[str] = None
    funding_round: Optional[str] = None   # "Series A", "Series B", etc.

    # Matching metadata
    matched_keywords: list = field(default_factory=list)
    relevance_score: float = 0.0
    query: Optional[str] = None          # Google News query that surfaced it

    # Lead workflow
    lead_status: str = "NEW"
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "title": self.title,
            "company_name": self.company_name or "",
            "company_location": self.company_location or "",
            "company_country": self.company_country or "",
            "is_us_company": self.is_us_company,
            "industry": self.industry or "",
            "company_website": self.company_website or "",
            "company_linkedin": self.company_linkedin or "",
            "founder_linkedin": self.founder_linkedin or "",
            "hq_city": self.hq_city or "",
            "hq_state": self.hq_state or "",
            "founding_year": self.founding_year,
            "employee_count": self.employee_count or "",
            "total_funding": self.total_funding or "",
            "retail_doors": ",".join(self.retail_doors),
            "sku_count": self.sku_count or "",
            "ops_pain_signal": self.ops_pain_signal,
            "tech_stack": ",".join(self.tech_stack),
            "three_pl_mention": self.three_pl_mention,
            "channel_mix": self.channel_mix or "",
            "description": (self.description or "")[:2000],
            "source_name": self.source_name or "",
            "source_url": self.url,
            "published_date": self.published_date.isoformat(),
            "discovered_at": self.discovered_date.isoformat(),
            "person_name": self.person_name or "",
            "person_title": self.person_title or "",
            "founder_name": self.founder_name or "",
            "funding_amount": self.funding_amount or "",
            "funding_round": self.funding_round or "",
            "matched_keywords": ",".join(self.matched_keywords),
            "relevance_score": round(self.relevance_score, 2),
            "query": self.query or "",
            "lead_status": self.lead_status,
        }
