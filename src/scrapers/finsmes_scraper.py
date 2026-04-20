"""
FinSMEs funding scraper.

FinSMEs (finsmes.com) publishes startup funding announcements with clean
RSS. It's especially good for Series A/B CPG deals that don't always make
TechCrunch but are exactly the DOSS sweet spot.
"""

from __future__ import annotations

from typing import Any

import feedparser

from ..models import EventSource, EventType, TriggerEvent
from .base import BaseScraper


FINSMES_FEEDS = [
    {
        "name": "FinSMEs — Funding News",
        "url": "https://www.finsmes.com/feed",
    },
    {
        "name": "TechCrunch — Startups",
        "url": "https://techcrunch.com/category/startups/feed/",
    },
    {
        "name": "Crunchbase News",
        "url": "https://news.crunchbase.com/feed/",
    },
]

# Round labels worth capturing
ROUND_LABELS = [
    "series a", "series b", "series c",
    "seed round", "pre-seed", "seed funding",
    "growth round", "growth investment",
    "private equity", "pe investment",
    "strategic investment", "minority stake",
    "acqui-hire", "acquisition",
]


class FinSMEsScraper(BaseScraper):
    """
    Monitors funding-focused news feeds for CPG Series A/B deals.
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source_statuses: list[dict] = []

    def scrape(self) -> list[TriggerEvent]:
        events: list[TriggerEvent] = []
        self.source_statuses = []

        for feed_cfg in FINSMES_FEEDS:
            feed_events, status = self._scrape_feed(feed_cfg)
            events.extend(feed_events)
            self.source_statuses.append({
                "source_name": feed_cfg["name"],
                "source_type": "finsmes",
                "status": status,
                "events_found": len(feed_events),
            })
            self._sleep()

        return events

    def _scrape_feed(self, feed_cfg: dict) -> tuple[list[TriggerEvent], str]:
        name = feed_cfg["name"]
        url = feed_cfg["url"]

        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                return [], "error"

            events: list[TriggerEvent] = []
            for entry in feed.entries[:25]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                if not title or not link:
                    continue

                summary = self._strip_html(
                    entry.get("summary", "") or entry.get("description", "")
                )
                combined = f"{title} {summary}".lower()

                # Must mention a funding round type
                has_round = any(r in combined for r in ROUND_LABELS)
                if not has_round:
                    continue

                # Must be CPG-relevant
                if not self._is_cpg_relevant(combined):
                    continue

                if self.exclude_public and self._is_public_company(combined):
                    continue

                if self._is_excluded_location(combined):
                    continue

                published = self._parse_date(
                    entry.get("published", "") or entry.get("updated", "")
                )
                event = self._make_event(
                    title=title,
                    url=link,
                    description=summary,
                    source_name=name,
                    published_date=published,
                    event_type=EventType.FUNDING,
                )
                if event:
                    event.source = EventSource.FINSMES
                    events.append(event)

            return events, "success" if events else "partial"

        except Exception as exc:
            print(f"  [FinSMEs] Error fetching '{name}': {exc}")
            return [], "error"
