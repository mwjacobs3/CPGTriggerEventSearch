"""
Supabase database manager — cloud-only, no local SQLite.

All reads/writes go directly to Supabase using the service-role key so the
scraper has full write access.  The Streamlit dashboard uses the anon key
(read-only via RLS).
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

try:
    from supabase import Client, create_client
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False
    Client = None  # type: ignore

if TYPE_CHECKING:
    from .models import TriggerEvent


def _event_id(url: str, title: str) -> str:
    key = f"{url}|{title}".lower().strip()
    return hashlib.sha256(key.encode()).hexdigest()


class SupabaseManager:
    """Direct Supabase client — replaces SQLite + supabase_sync pattern."""

    def __init__(self):
        self._client: Optional[Client] = None
        self._available = _SUPABASE_AVAILABLE
        self._seen_this_run: set[str] = set()   # in-memory cache for current run

    def _get_client(self) -> Optional[Client]:
        if self._client:
            return self._client
        if not self._available:
            return None
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            return None
        self._client = create_client(url, key)
        return self._client

    # ── Deduplication ─────────────────────────────────────────────────────────

    def has_seen_url(self, url: str, title: str = "") -> bool:
        """Return True if this event is already stored in Supabase."""
        eid = _event_id(url, title)
        if eid in self._seen_this_run:
            return True
        client = self._get_client()
        if not client:
            return False
        try:
            resp = client.table("events").select("id").eq("id", eid).limit(1).execute()
            if resp.data:
                self._seen_this_run.add(eid)
                return True
            return False
        except Exception as exc:
            print(f"[DB] has_seen_url error: {exc}")
            return False

    def mark_url_seen(self, url: str, title: str = "") -> None:
        self._seen_this_run.add(_event_id(url, title))

    # ── Events ────────────────────────────────────────────────────────────────

    def save_event(self, event: "TriggerEvent") -> bool:
        client = self._get_client()
        if not client:
            print("[DB] Supabase not configured — event not saved.")
            return False
        data = event.to_dict()
        data["id"] = _event_id(event.url, event.title)
        try:
            client.table("events").upsert(data, on_conflict="id").execute()
            self._seen_this_run.add(data["id"])
            return True
        except Exception as exc:
            print(f"[DB] save_event error: {exc}")
            return False

    def get_recent_events(self, hours: int = 24) -> list:
        client = self._get_client()
        if not client:
            return []
        try:
            cutoff = (
                datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            )
            resp = (
                client.table("events")
                .select("*")
                .gte(
                    "discovered_at",
                    datetime.utcnow().replace(
                        hour=datetime.utcnow().hour - min(hours, 23)
                    ).isoformat(),
                )
                .order("discovered_at", desc=True)
                .limit(500)
                .execute()
            )
            return resp.data or []
        except Exception as exc:
            print(f"[DB] get_recent_events error: {exc}")
            return []

    def get_stats(self) -> dict:
        client = self._get_client()
        if not client:
            return {"total_events": 0, "events_by_type": {}}
        try:
            resp = client.table("events").select("event_type").execute()
            rows = resp.data or []
            by_type: dict[str, int] = {}
            for r in rows:
                t = r.get("event_type", "other")
                by_type[t] = by_type.get(t, 0) + 1
            return {"total_events": len(rows), "events_by_type": by_type}
        except Exception as exc:
            print(f"[DB] get_stats error: {exc}")
            return {"total_events": 0, "events_by_type": {}}

    # ── Source health ─────────────────────────────────────────────────────────

    def save_source_status(
        self,
        source_name: str,
        source_type: str,
        status: str,
        error_message: Optional[str] = None,
        events_found: int = 0,
    ) -> None:
        client = self._get_client()
        if not client:
            return
        try:
            client.table("source_status").upsert(
                {
                    "source_name": source_name,
                    "source_type": source_type,
                    "last_check": datetime.now(timezone.utc).isoformat(),
                    "status": status,
                    "error_message": error_message,
                    "events_found": events_found,
                },
                on_conflict="source_name",
            ).execute()
        except Exception as exc:
            print(f"[DB] save_source_status error ({source_name}): {exc}")
