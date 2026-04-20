"""
Job/exec-hire scraper via BusinessWire and PR Newswire press releases.

Rather than scraping job boards (which block bots), this scraper monitors
the press-release wire services for exec appointment announcements — the
same signal, but from a more reliable source.  Filters for the DOSS ICP:
supply-chain / operations leaders (VP Supply Chain, COO, Director of
Operations, VP Procurement, Head of Logistics), plus founder-led CPG
brands where the Founder / Founder & CEO is the operational decision-maker.
"""

from __future__ import annotations

from typing import Any

import feedparser

from ..models import EventSource, EventType, TriggerEvent
from .base import BaseScraper


PRESS_RELEASE_FEEDS = [
    {
        "name": "BusinessWire — Consumer Products",
        "url": "https://feed.businesswire.com/rss/home/?rss=G22",
    },
    {
        "name": "BusinessWire — Food & Beverage",
        "url": "https://feed.businesswire.com/rss/home/?rss=G16",
    },
    {
        "name": "BusinessWire — Health & Wellness",
        "url": "https://feed.businesswire.com/rss/home/?rss=G17",
    },
    {
        "name": "BusinessWire — Retail",
        "url": "https://feed.businesswire.com/rss/home/?rss=G25",
    },
    {
        "name": "PR Newswire — Consumer Goods",
        "url": "https://www.prnewswire.com/rss/news-releases-list.rss",
    },
    {
        "name": "GlobeNewswire — Consumer",
        "url": "https://www.globenewswire.com/RssFeed/subjectCode/15",
    },
    {
        "name": "EIN Presswire — Consumer Goods",
        "url": "https://www.einpresswire.com/rss/consumer-goods/",
    },
    {
        "name": "AccessWire",
        "url": "https://www.accesswire.com/rss/news",
    },
]

# DOSS ICP titles: operational decision-makers at mid-market / founder-led CPG brands.
EXEC_TITLE_KEYWORDS = [
    # C-suite ops / supply chain
    "chief supply chain", "chief operations", "chief operating",
    " coo ", " csco ", " cpo ",
    # Founder-led brands (founder IS the ops buyer at sub-$50M CPG)
    "founder and ceo", "founder & ceo", "founder/ceo", "founder, ceo",
    "co-founder and ceo", "co-founder & ceo", "cofounder and ceo",
    "president and ceo", "president & ceo",
    " founder ", "co-founder", "cofounder",
    # VP / SVP / EVP — Supply Chain
    "vp supply chain", "vp of supply chain",
    "svp supply chain", "svp of supply chain",
    "evp supply chain", "evp of supply chain",
    "vice president supply chain", "vice president of supply chain",
    "senior vice president supply chain",
    # VP / SVP / EVP — Operations
    "vp operations", "vp of operations",
    "svp operations", "svp of operations",
    "evp operations", "evp of operations",
    "vice president operations", "vice president of operations",
    "senior vice president operations",
    # VP — Logistics / Procurement / Fulfillment
    "vp logistics", "vp of logistics",
    "vp procurement", "vp of procurement",
    "vp fulfillment", "vp of fulfillment",
    "vice president logistics", "vice president of logistics",
    "vice president procurement", "vice president of procurement",
    # Director
    "director supply chain", "director of supply chain",
    "director operations", "director of operations",
    "director logistics", "director of logistics",
    "director procurement", "director of procurement",
    "director fulfillment", "director of fulfillment",
    # Head of
    "head of supply chain", "head of operations",
    "head of logistics", "head of fulfillment",
    "head of procurement",
]

APPOINTMENT_VERBS = [
    "appoints", "names", "hires", "promotes", "welcomes",
    "announces appointment", "joins as", "appointed as",
]


class JobScraper(BaseScraper):
    """
    Monitors press-release feeds for CPG ops/supply-chain executive hires.
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.source_statuses: list[dict] = []

    def scrape(self) -> list[TriggerEvent]:
        events: list[TriggerEvent] = []
        self.source_statuses = []

        for feed_cfg in PRESS_RELEASE_FEEDS:
            feed_events, status = self._scrape_feed(feed_cfg)
            events.extend(feed_events)
            self.source_statuses.append({
                "source_name": feed_cfg["name"],
                "source_type": "job_board",
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
            for entry in feed.entries[:30]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                if not title or not link:
                    continue

                summary = self._strip_html(
                    entry.get("summary", "") or entry.get("description", "")
                )
                combined = f"{title} {summary}".lower()

                # Must mention an appointment verb AND an exec title
                has_verb = any(v in combined for v in APPOINTMENT_VERBS)
                has_title = any(t in combined for t in EXEC_TITLE_KEYWORDS)

                if not has_verb or not has_title:
                    continue

                # Must also be CPG-relevant
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
                    event_type=EventType.EXEC_HIRE,
                )
                if event:
                    event.source = EventSource.JOB_BOARD
                    events.append(event)

            return events, "success" if events else "partial"

        except Exception as exc:
            print(f"  [JobScraper] Error fetching '{name}': {exc}")
            return [], "error"
