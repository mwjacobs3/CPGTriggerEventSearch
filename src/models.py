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

    # Article body
    description: Optional[str] = None

    # Exec hire specifics
    person_name: Optional[str] = None
    person_title: Optional[str] = None

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
            "description": (self.description or "")[:2000],
            "source_name": self.source_name or "",
            "source_url": self.url,
            "published_date": self.published_date.isoformat(),
            "discovered_at": self.discovered_date.isoformat(),
            "person_name": self.person_name or "",
            "person_title": self.person_title or "",
            "funding_amount": self.funding_amount or "",
            "funding_round": self.funding_round or "",
            "matched_keywords": ",".join(self.matched_keywords),
            "relevance_score": round(self.relevance_score, 2),
            "query": self.query or "",
            "lead_status": self.lead_status,
        }
