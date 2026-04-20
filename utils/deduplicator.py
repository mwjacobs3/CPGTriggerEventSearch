from __future__ import annotations

import hashlib
import json
import os
from typing import TYPE_CHECKING

from config import SEEN_RESULTS_FILE

if TYPE_CHECKING:
    from searchers.base_searcher import SearchResult


class Deduplicator:
    """
    Persists a set of seen result fingerprints to disk so repeat runs
    don't re-alert on the same articles.
    """

    def __init__(self, storage_path: str = SEEN_RESULTS_FILE):
        self.storage_path = storage_path
        self._seen: set[str] = self._load()

    def filter_new(self, results: list[SearchResult]) -> list[SearchResult]:
        new_results = []
        for r in results:
            fp = self._fingerprint(r)
            if fp not in self._seen:
                new_results.append(r)
                self._seen.add(fp)
        return new_results

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(list(self._seen), f)

    def _load(self) -> set[str]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path) as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, IOError):
                pass
        return set()

    @staticmethod
    def _fingerprint(result: SearchResult) -> str:
        key = f"{result.url}|{result.title}".lower().strip()
        return hashlib.sha256(key.encode()).hexdigest()
