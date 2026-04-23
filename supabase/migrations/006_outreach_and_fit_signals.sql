-- Migration 006: Outreach + viability + DOSS-fit enrichment columns
-- Run in the Supabase SQL Editor after 005_add_country_and_founder.sql
--
-- Splits every event into three signal axes for the sales team:
--   OUTREACH    — how to reach out (website, LinkedIn, HQ city/state)
--   VIABILITY   — is the company worth the call (age, size, funding, SKUs, doors)
--   DOSS FIT    — do they need what we sell (ops pain, 3PL stage, channel mix,
--                 current tech stack)
--
-- All fields are best-effort parsed from article copy; NULL means "unknown",
-- NOT "no". Free-text fields keep raw extracted strings; lists are stored as
-- comma-separated TEXT (matching the existing matched_keywords convention) so
-- we don't need array types or migration tooling for list diffing.

ALTER TABLE public.events
  -- Outreach
  ADD COLUMN IF NOT EXISTS company_website   TEXT,
  ADD COLUMN IF NOT EXISTS company_linkedin  TEXT,
  ADD COLUMN IF NOT EXISTS founder_linkedin  TEXT,
  ADD COLUMN IF NOT EXISTS hq_city           TEXT,
  ADD COLUMN IF NOT EXISTS hq_state          TEXT,
  -- Viability
  ADD COLUMN IF NOT EXISTS founding_year     INTEGER,
  ADD COLUMN IF NOT EXISTS employee_count    TEXT,
  ADD COLUMN IF NOT EXISTS total_funding     TEXT,
  ADD COLUMN IF NOT EXISTS retail_doors      TEXT,
  ADD COLUMN IF NOT EXISTS sku_count         TEXT,
  -- DOSS fit
  ADD COLUMN IF NOT EXISTS ops_pain_signal   BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS tech_stack        TEXT,
  ADD COLUMN IF NOT EXISTS three_pl_mention  BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS channel_mix       TEXT;   -- DTC | DTC_PLUS_RETAIL | RETAIL

-- Partial indexes — these filters are used in the dashboard sidebar and they
-- only pay off on rows where the flag is actually true.
CREATE INDEX IF NOT EXISTS idx_events_ops_pain_signal
  ON public.events (ops_pain_signal)
  WHERE ops_pain_signal IS TRUE;

CREATE INDEX IF NOT EXISTS idx_events_three_pl_mention
  ON public.events (three_pl_mention)
  WHERE three_pl_mention IS TRUE;

CREATE INDEX IF NOT EXISTS idx_events_channel_mix
  ON public.events (channel_mix)
  WHERE channel_mix IS NOT NULL;

-- For "show me brands founded 2018–2022" queries.
CREATE INDEX IF NOT EXISTS idx_events_founding_year
  ON public.events (founding_year)
  WHERE founding_year IS NOT NULL;

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'events'
  AND column_name IN (
      'company_website', 'company_linkedin', 'founder_linkedin',
      'hq_city', 'hq_state', 'founding_year', 'employee_count',
      'total_funding', 'retail_doors', 'sku_count',
      'ops_pain_signal', 'tech_stack', 'three_pl_mention', 'channel_mix'
  )
ORDER BY column_name;
