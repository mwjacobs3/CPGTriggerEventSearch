"""
CPGTriggerEventSearch — main entry point.

Usage:
    python main.py              # run once immediately
    python main.py --schedule   # run on schedule defined in .env (default: daily 07:00)
    python main.py --no-email   # run once, print to console only

Trigger event categories monitored:
  1. New CPG / product launches going to market
  2. PE / VC funding events in CPG & consumer goods
  3. New ops, supply chain, and procurement exec hires
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

import schedule

from alerts import EmailSender
from config import RUN_SCHEDULE, RUN_TIME, USE_AI_FILTER
from searchers import ExecHireSearcher, FundingSearcher, ProductLaunchSearcher
from utils import Deduplicator, format_results_csv, print_digest

SEARCHERS = [
    ProductLaunchSearcher,
    FundingSearcher,
    ExecHireSearcher,
]


def run_search(send_email: bool = True) -> None:
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting CPG trigger event search…")

    all_results = []
    for SearcherClass in SEARCHERS:
        searcher = SearcherClass()
        print(f"  → Searching: {searcher.category}")
        results = searcher.run()
        print(f"     {len(results)} raw results")
        all_results.extend(results)

    print(f"\n  Total raw results: {len(all_results)}")

    dedup = Deduplicator()
    new_results = dedup.filter_new(all_results)
    dedup.save()

    print(f"  New (unseen) results: {len(new_results)}")

    if USE_AI_FILTER and new_results:
        new_results = _ai_relevance_filter(new_results)
        print(f"  After AI filter: {len(new_results)}")

    print_digest(new_results)

    if new_results:
        csv_path = format_results_csv(new_results)
        print(f"  Results appended to: {csv_path}")

        if send_email:
            EmailSender().send_digest(new_results)
    else:
        print("  No new results — skipping email.")


def _ai_relevance_filter(results):
    """Use Claude to score each result and keep only high-relevance ones."""
    try:
        import anthropic
        from config import AI_RELEVANCE_THRESHOLD, ANTHROPIC_API_KEY

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        filtered = []

        for r in results:
            prompt = (
                "You are a B2B sales intelligence assistant. "
                "Score the following news headline and summary on a scale of 0.0–1.0 for "
                "relevance to selling supply chain / operations software (DOSS) to CPG "
                "and consumer products companies. Only respond with a number.\n\n"
                f"Category: {r.category}\n"
                f"Title: {r.title}\n"
                f"Summary: {r.summary[:300]}\n"
            )
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )
            try:
                score = float(message.content[0].text.strip())
                if score >= AI_RELEVANCE_THRESHOLD:
                    filtered.append(r)
            except (ValueError, IndexError):
                filtered.append(r)

        return filtered
    except Exception as exc:
        print(f"  [AI Filter] Error — returning unfiltered results: {exc}")
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="CPG Trigger Event Search")
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run on schedule defined in .env instead of once",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Suppress email sending; print results to console only",
    )
    args = parser.parse_args()

    send_email = not args.no_email

    if not args.schedule:
        run_search(send_email=send_email)
        return

    print(f"[Scheduler] Running on '{RUN_SCHEDULE}' schedule (time: {RUN_TIME})")

    def job():
        run_search(send_email=send_email)

    if RUN_SCHEDULE == "hourly":
        schedule.every().hour.do(job)
    elif RUN_SCHEDULE == "weekly":
        schedule.every().monday.at(RUN_TIME).do(job)
    else:  # daily
        schedule.every().day.at(RUN_TIME).do(job)

    job()  # run immediately on start

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
