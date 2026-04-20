from __future__ import annotations

import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

from config import CPG_RELEVANCE_KEYWORDS


class SearchResult:
    def __init__(
        self,
        title: str,
        url: str,
        summary: str,
        source: str,
        published: str,
        category: str,
        query: str,
    ):
        self.title = title
        self.url = url
        self.summary = summary
        self.source = source
        self.published = published
        self.category = category
        self.query = query

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "source": self.source,
            "published": self.published,
            "category": self.category,
            "query": self.query,
        }

    def __repr__(self) -> str:
        return f"<SearchResult [{self.category}] {self.title[:60]}>"


class BaseSearcher(ABC):
    GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"

    def __init__(self, news_api_key: str = "", serp_api_key: str = ""):
        self.news_api_key = news_api_key
        self.serp_api_key = serp_api_key
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "CPGTriggerEventSearch/1.0 (alert bot)"}
        )

    @property
    @abstractmethod
    def category(self) -> str:
        """Human-readable category label for this searcher."""

    @property
    @abstractmethod
    def queries(self) -> list[str]:
        """List of search query strings to run."""

    def run(self) -> list[SearchResult]:
        """Execute all queries and return deduplicated, relevant results."""
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        for query in self.queries:
            for result in self._fetch_google_news(query):
                if result.url not in seen_urls and self._is_relevant(result):
                    seen_urls.add(result.url)
                    results.append(result)

            if self.news_api_key:
                for result in self._fetch_newsapi(query):
                    if result.url not in seen_urls and self._is_relevant(result):
                        seen_urls.add(result.url)
                        results.append(result)

        return results

    def _fetch_google_news(self, query: str) -> list[SearchResult]:
        params = {
            "q": query,
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        }
        url = f"{self.GOOGLE_NEWS_BASE}?{urllib.parse.urlencode(params)}"
        try:
            feed = feedparser.parse(url)
            results = []
            for entry in feed.entries[:10]:
                published = entry.get("published", "")
                results.append(
                    SearchResult(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        summary=self._strip_html(entry.get("summary", "")),
                        source=entry.get("source", {}).get("title", "Google News"),
                        published=published,
                        category=self.category,
                        query=query,
                    )
                )
            return results
        except Exception as exc:
            print(f"[{self.category}] Google News error for '{query}': {exc}")
            return []

    def _fetch_newsapi(self, query: str) -> list[SearchResult]:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": self.news_api_key,
        }
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            results = []
            for art in articles:
                results.append(
                    SearchResult(
                        title=art.get("title") or "",
                        url=art.get("url") or "",
                        summary=art.get("description") or "",
                        source=art.get("source", {}).get("name", "NewsAPI"),
                        published=art.get("publishedAt") or "",
                        category=self.category,
                        query=query,
                    )
                )
            return results
        except Exception as exc:
            print(f"[{self.category}] NewsAPI error for '{query}': {exc}")
            return []

    def _is_relevant(self, result: SearchResult) -> bool:
        """Keyword-based relevance check on title + summary."""
        text = f"{result.title} {result.summary}".lower()
        return any(kw in text for kw in CPG_RELEVANCE_KEYWORDS)

    @staticmethod
    def _strip_html(text: str) -> str:
        import re
        return re.sub(r"<[^>]+>", "", text).strip()
