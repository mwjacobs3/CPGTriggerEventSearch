-- Migration 002: Add columns for exec hire and funding detail fields
-- Run in the Supabase SQL Editor after 001_init.sql

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS company_location  TEXT,
  ADD COLUMN IF NOT EXISTS person_name       TEXT,
  ADD COLUMN IF NOT EXISTS person_title      TEXT,
  ADD COLUMN IF NOT EXISTS funding_amount    TEXT,
  ADD COLUMN IF NOT EXISTS funding_round     TEXT,
  ADD COLUMN IF NOT EXISTS matched_keywords  TEXT,
  ADD COLUMN IF NOT EXISTS source_type       TEXT;

-- Index for exec hire lookups by person
CREATE INDEX IF NOT EXISTS idx_events_person_name
  ON public.events (person_name)
  WHERE person_name IS NOT NULL;

-- Index for funding round filtering
CREATE INDEX IF NOT EXISTS idx_events_funding_round
  ON public.events (funding_round)
  WHERE funding_round IS NOT NULL;

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'events'
ORDER BY ordinal_position;
