"""
X / Twitter post scraper — via Google Search (SerpApi), not the official X API.

X's official API requires a paid tier (Basic, ~$200/mo) to search post content
at all, and unofficial scraping (logged-in session libraries, Nitter) is both
unreliable and against X's ToS. Instead, this scraper queries Google for posts
Google has indexed under `site:x.com`, using SerpApi (the same optional
SERP_API_KEY already documented in .env.example).

Coverage is a fraction of what the official API would return — X blocks most
crawling, so only a subset of public posts ever get indexed — so treat this as
a low-recall bonus signal, not a primary channel. No ToS/ban risk to DOSS: we
never touch x.com directly, only Google's search index.

Silently skipped (no events, a "skipped" source_status) if SERP_API_KEY isn't set.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from ..models import EventSource, EventType, TriggerEvent
from .base import BaseScraper

SERPAPI_URL = "https://serpapi.com/search"


class TwitterScraper(BaseScraper):

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = os.environ.get("SERP_API_KEY", "")
        self.queries_by_type: dict[str, list[str]] = config.get("twitter_queries", {})
        self.source_statuses: list[dict] = []

    def scrape(self) -> list[TriggerEvent]:
        events: list[TriggerEvent] = []
        seen_urls: set[str] = set()
        self.source_statuses = []

        if not self.api_key:
            self.source_statuses.append({
                "source_name": "X / Twitter (via Google Search)",
                "source_type": "serpapi_twitter",
                "status": "skipped",
                "events_found": 0,
                "error_message": "SERP_API_KEY not set",
            })
            return events

        type_map = {
            "product_launch":   EventType.PRODUCT_LAUNCH,
            "retail_expansion": EventType.RETAIL_EXPANSION,
            "funding":          EventType.FUNDING,
            "exec_hire":        EventType.EXEC_HIRE,
        }

        for type_key, queries in self.queries_by_type.items():
            # Buckets with no direct EventType (e.g. ops_pain) auto-classify
            # off the post text instead, same as news_scraper's unmapped
            # query buckets (supply_chain_footprint, integration_stack).
            event_type = type_map.get(type_key)
            found_this_type = 0
            status = "success"

            for query in queries:
                try:
                    results = self._fetch(query, event_type)
                except Exception as exc:
                    print(f"  [TwitterScraper] Error for '{query}': {exc}")
                    status = "error"
                    continue
                for r in results:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        events.append(r)
                        found_this_type += 1
                self._sleep()

            self.source_statuses.append({
                "source_name": f"X / Twitter — {type_key.replace('_', ' ').title()}",
                "source_type": "serpapi_twitter",
                "status": status,
                "events_found": found_this_type,
            })

        return events

    def _fetch(self, query: str, event_type: Optional[EventType]) -> list[TriggerEvent]:
        params = {
            "engine": "google",
            "q": f"site:x.com {query}",
            "api_key": self.api_key,
            "num": 10,
            "hl": "en",
            "gl": "us",
        }
        resp = self.session.get(SERPAPI_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        results: list[TriggerEvent] = []
        for item in data.get("organic_results", [])[:10]:
            link = item.get("link", "")
            title = item.get("title", "")
            if not link or not title or "x.com" not in link:
                continue

            snippet = item.get("snippet", "") or ""
            published = self._parse_date(item.get("date", ""))

            event = self._make_event(
                title=title,
                url=link,
                description=snippet,
                source_name="X / Twitter (via Google Search)",
                published_date=published,
                event_type=event_type,
                query=query,
            )
            if event:
                event.source = EventSource.TWITTER
                results.append(event)

        return results
