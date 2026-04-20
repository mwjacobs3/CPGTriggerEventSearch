"""
CPGTriggerEventSearch — main entry point.

Usage:
    python main.py              # run once immediately
    python main.py --schedule   # run on schedule defined in .env (default: every 4 hours)
    python main.py --no-email   # run once, skip email
    python main.py --no-supabase  # run once, skip Supabase writes (local-only)

Trigger event categories monitored:
  1. New CPG / product launches (Food, Bev, Health, Beauty)
  2. DTC → Retail expansion (biggest ops complexity spike)
  3. PE / VC funding events (Series A/B sweet spot)
  4. New ops, supply chain, and procurement exec hires

In production, this is invoked every 4 hours by .github/workflows/scraper.yml.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime

import schedule

from alerts import EmailSender
from config import DOSS_ICP_CONTEXT, RUN_SCHEDULE, RUN_TIME, SUPABASE_URL, USE_AI_FILTER
from searchers import (
    ExecHireSearcher,
    FundingSearcher,
    ProductLaunchSearcher,
    RetailExpansionSearcher,
)
from utils import (
    Deduplicator,
    format_results_csv,
    print_digest,
    update_source_status,
    upsert_events,
)

SEARCHERS = [
    ProductLaunchSearcher,
    RetailExpansionSearcher,
    FundingSearcher,
    ExecHireSearcher,
]


def run_search(send_email: bool = True, use_supabase: bool = True) -> None:
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting CPG trigger event search…")

    all_results = []
    for SearcherClass in SEARCHERS:
        searcher = SearcherClass()
        print(f"  → Searching: {searcher.category}")
        try:
            results = searcher.run()
            print(f"     {len(results)} raw results")
            all_results.extend(results)
            if use_supabase and SUPABASE_URL:
                update_source_status(
                    source_name=searcher.category,
                    source_type="google_news",
                    status="success",
                    events_found=len(results),
                )
        except Exception as exc:
            print(f"     ERROR: {exc}")
            if use_supabase and SUPABASE_URL:
                update_source_status(
                    source_name=searcher.category,
                    source_type="google_news",
                    status="error",
                    events_found=0,
                    error=str(exc),
                )

    print(f"\n  Total raw results: {len(all_results)}")

    # Deduplication + persistence
    if use_supabase and SUPABASE_URL:
        new_results = upsert_events(all_results)
        print(f"  New (unseen) results via Supabase: {len(new_results)}")
    else:
        dedup = Deduplicator()
        new_results = dedup.filter_new(all_results)
        dedup.save()
        print(f"  New (unseen) results via local JSON: {len(new_results)}")

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
    """Use Claude to score each result; keep only high-relevance ones."""
    try:
        import anthropic

        from config import AI_RELEVANCE_THRESHOLD, ANTHROPIC_API_KEY

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        filtered = []

        for r in results:
            prompt = (
                "You are a B2B sales intelligence assistant helping identify leads for DOSS.\n\n"
                f"{DOSS_ICP_CONTEXT}\n\n"
                "Score the following news item 0.0–1.0 for how well the company described "
                "matches DOSS's ideal customer profile. High scores (0.8+) for mid-market "
                "CPG/F&B/Health-Beauty companies with supply chain complexity. "
                "Low scores for mega enterprises, non-CPG industries, or very early startups. "
                "Respond with only a single decimal number.\n\n"
                f"Trigger type: {r.category}\n"
                f"Title: {r.title}\n"
                f"Company: {r.company_name or 'unknown'}\n"
                f"Summary: {r.summary[:400]}\n"
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
    parser.add_argument("--schedule", action="store_true", help="Run on schedule")
    parser.add_argument("--no-email", action="store_true", help="Suppress email")
    parser.add_argument("--no-supabase", action="store_true", help="Skip Supabase writes")
    args = parser.parse_args()

    send_email = not args.no_email
    use_supabase = not args.no_supabase

    if not args.schedule:
        run_search(send_email=send_email, use_supabase=use_supabase)
        return

    print(f"[Scheduler] Running on '{RUN_SCHEDULE}' schedule (time: {RUN_TIME})")

    def job():
        run_search(send_email=send_email, use_supabase=use_supabase)

    if RUN_SCHEDULE == "hourly":
        schedule.every().hour.do(job)
    elif RUN_SCHEDULE == "every_4_hours":
        schedule.every(4).hours.do(job)
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
