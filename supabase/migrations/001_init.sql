-- CPGTriggerEventSearch — initial schema
-- Run this in the Supabase SQL Editor (https://app.supabase.com > SQL Editor).
--
-- After this migration you need TWO keys in your .env / Streamlit secrets:
--   SUPABASE_SERVICE_ROLE_KEY — for the scraper/sync job (full write access)
--   SUPABASE_KEY              — anon key for the dashboard (read + limited write)

-- ============================================
-- 1. Events table
-- ============================================

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

CREATE INDEX IF NOT EXISTS idx_events_discovered_at ON public.events (discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type    ON public.events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_lead_status   ON public.events (lead_status);
CREATE INDEX IF NOT EXISTS idx_events_company_name  ON public.events (company_name);

-- ============================================
-- 2. Source status table (for dashboard health monitoring)
-- ============================================

CREATE TABLE IF NOT EXISTS public.source_status (
    source_name   TEXT PRIMARY KEY,
    source_type   TEXT NOT NULL,      -- google_news | newsapi | serpapi
    last_check    TIMESTAMPTZ,
    status        TEXT,               -- success | partial | error
    error_message TEXT,
    events_found  INTEGER DEFAULT 0
);

-- ============================================
-- 3. Enable Row Level Security
-- ============================================

ALTER TABLE public.events        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_status ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 4. Policies (idempotent)
-- ============================================

DROP POLICY IF EXISTS "anon_read_events"           ON public.events;
DROP POLICY IF EXISTS "anon_update_events_status"  ON public.events;
DROP POLICY IF EXISTS "anon_delete_events"         ON public.events;
DROP POLICY IF EXISTS "service_role_all_events"    ON public.events;
DROP POLICY IF EXISTS "anon_read_source_status"    ON public.source_status;
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

-- ============================================
-- 5. Verify
-- ============================================

SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('events', 'source_status');
