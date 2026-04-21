-- Migration 004: Add industry classification column
-- Run in the Supabase SQL Editor after 003_priority_index.sql
--
-- DOSS ICP slices: food_beverage, health_beauty, wellness_supplements,
-- household_home, pet, other_cpg.

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS industry TEXT;

CREATE INDEX IF NOT EXISTS idx_events_industry
  ON public.events (industry)
  WHERE industry IS NOT NULL;

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'events'
  AND column_name  = 'industry';
