-- CPGTriggerEventSearch — COMPLETE schema (consolidated, idempotent)
-- =============================================================================
-- Run this ONE file in the Supabase SQL Editor (https://app.supabase.com >
-- SQL Editor) to bring a project fully up to date. It is safe to run on:
--   • a brand-new project           (creates everything)
--   • a partially-migrated project  (adds only what's missing)
--   • an already-current project    (no-ops)
--
-- Every statement is idempotent (CREATE ... IF NOT EXISTS / ADD COLUMN IF NOT
-- EXISTS), so re-running it can never drop data.
--
-- This file is the union of supabase/migrations/001..008. If you add a new
-- migration, append its columns/indexes here too so this stays the single
-- source of truth — the scraper's models.to_dict() expects EVERY column below
-- to exist, and a single missing column makes every insert fail.
--
-- After running this you need TWO keys:
--   SUPABASE_SERVICE_ROLE_KEY — scraper / GitHub Action (full write access)
--   SUPABASE_KEY              — anon key for the Streamlit dashboard (read-only)
-- =============================================================================

-- ── 1. Events table (001) ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.events (
    id              TEXT PRIMARY KEY,                 -- sha256(url|title)
    event_type      TEXT NOT NULL,                    -- product_launch | funding | exec_hire
    title           TEXT NOT NULL,
    company_name    TEXT,
    description     TEXT,
    source_name     TEXT,
    source_url      TEXT NOT NULL,
    published_date  TEXT,
    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query           TEXT,
    relevance_score REAL,
    lead_status     TEXT NOT NULL DEFAULT 'NEW',
    notes           TEXT
);

-- ── 2. Event detail columns (002 exec/funding · 004 industry · 005 country/
--      founder · 006 outreach/viability/fit · 007 user_industry · 008 co-man/
--      integrations) ─────────────────────────────────────────────────────────
ALTER TABLE public.events
  -- 002: exec hire + funding detail
  ADD COLUMN IF NOT EXISTS company_location  TEXT,
  ADD COLUMN IF NOT EXISTS person_name       TEXT,
  ADD COLUMN IF NOT EXISTS person_title      TEXT,
  ADD COLUMN IF NOT EXISTS funding_amount    TEXT,
  ADD COLUMN IF NOT EXISTS funding_round     TEXT,
  ADD COLUMN IF NOT EXISTS matched_keywords  TEXT,
  ADD COLUMN IF NOT EXISTS source_type       TEXT,
  -- 004: auto-detected industry  (the column whose absence froze DOSS)
  ADD COLUMN IF NOT EXISTS industry          TEXT,
  -- 005: location tagging + founder
  ADD COLUMN IF NOT EXISTS company_country   TEXT,       -- "US" | "International"
  ADD COLUMN IF NOT EXISTS is_us_company     BOOLEAN,    -- true=US, false=Intl, null=Unknown
  ADD COLUMN IF NOT EXISTS founder_name      TEXT,
  -- 006: outreach
  ADD COLUMN IF NOT EXISTS company_website   TEXT,
  ADD COLUMN IF NOT EXISTS company_linkedin  TEXT,
  ADD COLUMN IF NOT EXISTS founder_linkedin  TEXT,
  ADD COLUMN IF NOT EXISTS hq_city           TEXT,
  ADD COLUMN IF NOT EXISTS hq_state          TEXT,
  -- 006: viability
  ADD COLUMN IF NOT EXISTS founding_year     INTEGER,
  ADD COLUMN IF NOT EXISTS employee_count    TEXT,
  ADD COLUMN IF NOT EXISTS total_funding     TEXT,
  ADD COLUMN IF NOT EXISTS retail_doors      TEXT,
  ADD COLUMN IF NOT EXISTS sku_count         TEXT,
  -- 006: DOSS fit
  ADD COLUMN IF NOT EXISTS ops_pain_signal   BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS tech_stack        TEXT,
  ADD COLUMN IF NOT EXISTS three_pl_mention  BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS channel_mix       TEXT,       -- DTC | DTC_PLUS_RETAIL | RETAIL
  -- 007: sales-applied industry tag (separate from auto-detected `industry`)
  ADD COLUMN IF NOT EXISTS user_industry     TEXT,
  -- 008: co-manufacturer + DOSS-integration signals
  ADD COLUMN IF NOT EXISTS co_man_mention    BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS integration_match TEXT;       -- comma-separated names

-- ── 3. Source status table (001) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.source_status (
    source_name   TEXT PRIMARY KEY,
    source_type   TEXT NOT NULL,      -- google_news | rss_feed | finsmes | job_board
    last_check    TIMESTAMPTZ,
    status        TEXT,               -- success | partial | error
    error_message TEXT,
    events_found  INTEGER DEFAULT 0
);

-- ── 4. Indexes (001–008) ─────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_events_discovered_at   ON public.events (discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type      ON public.events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_lead_status     ON public.events (lead_status);
CREATE INDEX IF NOT EXISTS idx_events_company_name    ON public.events (company_name);
CREATE INDEX IF NOT EXISTS idx_events_person_name     ON public.events (person_name)     WHERE person_name     IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_funding_round   ON public.events (funding_round)   WHERE funding_round   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_status_score    ON public.events (lead_status, relevance_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_events_relevance_score ON public.events (relevance_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_events_industry        ON public.events (industry)        WHERE industry        IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_is_us_company   ON public.events (is_us_company)   WHERE is_us_company   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_founder_name    ON public.events (founder_name)    WHERE founder_name    IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_status_us_score ON public.events (lead_status, is_us_company DESC NULLS LAST, relevance_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_events_ops_pain_signal ON public.events (ops_pain_signal) WHERE ops_pain_signal IS TRUE;
CREATE INDEX IF NOT EXISTS idx_events_three_pl_mention ON public.events (three_pl_mention) WHERE three_pl_mention IS TRUE;
CREATE INDEX IF NOT EXISTS idx_events_channel_mix     ON public.events (channel_mix)     WHERE channel_mix     IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_founding_year   ON public.events (founding_year)   WHERE founding_year   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_user_industry   ON public.events (user_industry)   WHERE user_industry   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_co_man_mention  ON public.events (co_man_mention)  WHERE co_man_mention  IS TRUE;
CREATE INDEX IF NOT EXISTS idx_events_integration_match ON public.events (integration_match) WHERE integration_match IS NOT NULL AND integration_match <> '';

-- ── 5. Row Level Security + policies (001) ───────────────────────────────────
ALTER TABLE public.events        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_status ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_read_events"               ON public.events;
DROP POLICY IF EXISTS "anon_update_events_status"      ON public.events;
DROP POLICY IF EXISTS "anon_delete_events"             ON public.events;
DROP POLICY IF EXISTS "service_role_all_events"        ON public.events;
DROP POLICY IF EXISTS "anon_read_source_status"        ON public.source_status;
DROP POLICY IF EXISTS "service_role_all_source_status" ON public.source_status;

-- Anon (dashboard) can read, update status/notes, and delete.
CREATE POLICY "anon_read_events"          ON public.events FOR SELECT TO anon USING (true);
CREATE POLICY "anon_update_events_status" ON public.events FOR UPDATE TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_delete_events"        ON public.events FOR DELETE TO anon USING (true);
-- Service role (scraper) has full access.
CREATE POLICY "service_role_all_events"
    ON public.events FOR ALL TO service_role USING (true) WITH CHECK (true);
-- Source status — dashboard reads, service role writes.
CREATE POLICY "anon_read_source_status"
    ON public.source_status FOR SELECT TO anon USING (true);
CREATE POLICY "service_role_all_source_status"
    ON public.source_status FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── 6. Verify: confirm every column the scraper writes exists ─────────────────
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'events'
ORDER BY ordinal_position;
