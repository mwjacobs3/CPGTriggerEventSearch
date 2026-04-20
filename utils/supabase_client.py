from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from config import SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

if TYPE_CHECKING:
    from searchers.base_searcher import SearchResult

try:
    from supabase import Client, create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None  # type: ignore


def event_id(url: str, title: str) -> str:
    key = f"{url}|{title}".lower().strip()
    return hashlib.sha256(key.encode()).hexdigest()


def get_client(write: bool = False) -> Optional["Client"]:
    if not SUPABASE_AVAILABLE:
        return None
    if not SUPABASE_URL:
        return None
    key = SUPABASE_SERVICE_ROLE_KEY if write else (SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY)
    if not key:
        return None
    return create_client(SUPABASE_URL, key)


def upsert_events(results: list["SearchResult"]) -> list["SearchResult"]:
    """
    Upsert results to Supabase.events. Returns the subset that were newly
    inserted (i.e. not seen before), so the caller knows which to email.
    """
    client = get_client(write=True)
    if client is None:
        return results  # Supabase disabled — treat everything as new.

    # Figure out which IDs already exist.
    ids = [event_id(r.url, r.title) for r in results]
    existing: set[str] = set()
    if ids:
        try:
            # Query in chunks to stay within URL length limits
            for chunk_start in range(0, len(ids), 50):
                chunk = ids[chunk_start : chunk_start + 50]
                resp = (
                    client.table("events")
                    .select("id")
                    .in_("id", chunk)
                    .execute()
                )
                for row in resp.data or []:
                    existing.add(row["id"])
        except Exception as exc:
            print(f"[Supabase] lookup error: {exc}")

    new_results = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for r, eid in zip(results, ids):
        payload = {
            "id": eid,
            "event_type": r.event_type,
            "title": r.title[:500],
            "company_name": (r.company_name or "")[:200],
            "description": (r.summary or "")[:2000],
            "source_name": (r.source or "")[:200],
            "source_url": r.url,
            "published_date": r.published or "",
            "discovered_at": now_iso,
            "query": r.query[:200] if r.query else "",
            "lead_status": "NEW",
        }
        try:
            client.table("events").upsert(payload, on_conflict="id").execute()
            if eid not in existing:
                new_results.append(r)
        except Exception as exc:
            print(f"[Supabase] upsert error for {r.url}: {exc}")

    return new_results


def update_source_status(
    source_name: str, source_type: str, status: str, events_found: int, error: str = ""
) -> None:
    client = get_client(write=True)
    if client is None:
        return
    try:
        client.table("source_status").upsert(
            {
                "source_name": source_name,
                "source_type": source_type,
                "last_check": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "error_message": error or None,
                "events_found": events_found,
            },
            on_conflict="source_name",
        ).execute()
    except Exception as exc:
        print(f"[Supabase] source_status error ({source_name}): {exc}")
