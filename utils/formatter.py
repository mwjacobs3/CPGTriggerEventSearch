from __future__ import annotations

import csv
import os
from typing import TYPE_CHECKING

from config import RESULTS_OUTPUT_FILE

if TYPE_CHECKING:
    from searchers.base_searcher import SearchResult

CATEGORY_ICONS = {
    "New CPG / Product Launch": "🚀",
    "PE / VC Funding": "💰",
    "New Ops / Supply Chain Exec": "👤",
}


def print_digest(results: list[SearchResult]) -> None:
    if not results:
        print("\nNo new CPG trigger events found this run.\n")
        return

    from collections import defaultdict

    grouped: dict[str, list[SearchResult]] = defaultdict(list)
    for r in results:
        grouped[r.category].append(r)

    print(f"\n{'='*70}")
    print(f"  CPG TRIGGER EVENT DIGEST  —  {len(results)} new signals")
    print(f"{'='*70}")

    for category, items in grouped.items():
        icon = CATEGORY_ICONS.get(category, "•")
        print(f"\n{icon}  {category.upper()}  ({len(items)})")
        print("-" * 60)
        for r in items:
            print(f"  {r.title}")
            print(f"  {r.url}")
            print(f"  {r.source}  |  {r.published}")
            if r.summary:
                summary = r.summary[:160] + ("…" if len(r.summary) > 160 else "")
                print(f"  {summary}")
            print()

    print("=" * 70)


def format_results_csv(
    results: list[SearchResult], output_path: str = RESULTS_OUTPUT_FILE
) -> str:
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    file_exists = os.path.exists(output_path)

    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category", "title", "source", "published", "url", "summary", "query"],
        )
        if not file_exists:
            writer.writeheader()
        for r in results:
            writer.writerow(r.to_dict())

    return output_path
