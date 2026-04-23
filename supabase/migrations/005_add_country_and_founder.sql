-- Migration 005: Tag (rather than filter) company location and capture founders
-- Run in the Supabase SQL Editor after 004_add_industry_column.sql
--
-- Historically the scraper dropped non-US articles entirely. We now keep them
-- and tag them so the dashboard can prioritize US leads while still surfacing
-- international brands (which can still be valid DOSS prospects if they're
-- entering US retail or building a US supply chain).

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS company_country TEXT,       -- "US" | "International"
  ADD COLUMN IF NOT EXISTS is_us_company   BOOLEAN,    -- true=US, false=Intl, null=Unknown
  ADD COLUMN IF NOT EXISTS founder_name    TEXT;       -- Founder mentioned in the article

-- Fast filter: "show me only US leads"
CREATE INDEX IF NOT EXISTS idx_events_is_us_company
  ON public.events (is_us_company)
  WHERE is_us_company IS NOT NULL;

-- Lookup leads by founder (useful for deduping across multiple launches
-- from the same founder — serial entrepreneurs surface repeatedly).
CREATE INDEX IF NOT EXISTS idx_events_founder_name
  ON public.events (founder_name)
  WHERE founder_name IS NOT NULL;

-- Composite: most dashboard queries filter on lead_status, prefer US, sort
-- by relevance_score. This lets the planner skip international rows first.
CREATE INDEX IF NOT EXISTS idx_events_status_us_score
  ON public.events (lead_status, is_us_company DESC NULLS LAST, relevance_score DESC NULLS LAST);

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'events'
  AND column_name IN ('company_country', 'is_us_company', 'founder_name')
ORDER BY column_name;
