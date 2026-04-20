from __future__ import annotations

import re
import urllib.parse
from abc import ABC, abstractmethod
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
        event_type: str,
        query: str,
        company_name: str = "",
    ):
        self.title = title
        self.url = url
        self.summary = summary
        self.source = source
        self.published = published
        self.category = category
        self.event_type = event_type
        self.query = query
        self.company_name = company_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "source": self.source,
            "published": self.published,
            "category": self.category,
            "event_type": self.event_type,
            "query": self.query,
            "company_name": self.company_name,
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
        """Human-readable category label."""

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Machine ID matching EVENT_TYPE_* constants in config.py."""

    @property
    @abstractmethod
    def queries(self) -> list[str]:
        """List of search query strings to run."""

    def run(self) -> list[SearchResult]:
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

    # ── Sources ───────────────────────────────────────────────────────────────

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
                title = entry.get("title", "")
                results.append(
                    SearchResult(
                        title=title,
                        url=entry.get("link", ""),
                        summary=self._strip_html(entry.get("summary", "")),
                        source=entry.get("source", {}).get("title", "Google News"),
                        published=entry.get("published", ""),
                        category=self.category,
                        event_type=self.event_type,
                        query=query,
                        company_name=self._extract_company(title),
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
                title = art.get("title") or ""
                results.append(
                    SearchResult(
                        title=title,
                        url=art.get("url") or "",
                        summary=art.get("description") or "",
                        source=art.get("source", {}).get("name", "NewsAPI"),
                        published=art.get("publishedAt") or "",
                        category=self.category,
                        event_type=self.event_type,
                        query=query,
                        company_name=self._extract_company(title),
                    )
                )
            return results
        except Exception as exc:
            print(f"[{self.category}] NewsAPI error for '{query}': {exc}")
            return []

    # ── Filtering & extraction ────────────────────────────────────────────────

    def _is_relevant(self, result: SearchResult) -> bool:
        text = f"{result.title} {result.summary}".lower()
        return any(kw in text for kw in CPG_RELEVANCE_KEYWORDS)

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()

    @staticmethod
    def _extract_company(title: str) -> str:
        """
        Best-effort company name extraction. Google News titles look like:
          "Acme Foods raises $10M in Series A funding - TechCrunch"
        We strip the trailing " - Source" and take the first noun-ish phrase.
        """
        if not title:
            return ""
        clean = re.sub(r"\s+-\s+[^-]+$", "", title)  # strip trailing " - Source"
        clean = re.sub(r"\s+\|\s+[^|]+$", "", clean)  # strip trailing " | Source"

        # Stop at first action verb — everything before is likely the company.
        verbs = [
            " raises ", " announces ", " launches ", " unveils ", " acquires ",
            " hires ", " appoints ", " names ", " secures ", " closes ",
            " taps ", " expands ", " partners ", " debuts ", " introduces ",
            " nets ", " welcomes ", " promotes ", " invests ",
        ]
        lower = clean.lower()
        cut = len(clean)
        for v in verbs:
            idx = lower.find(v)
            if 0 < idx < cut:
                cut = idx
        company = clean[:cut].strip(" ,;:")
        # Cap length — real names are short; long strings are likely headlines.
        if len(company) > 80 or len(company) < 2:
            return ""
        return company
