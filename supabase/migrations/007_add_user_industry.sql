-- Migration 007: Add user-applied industry tag column
-- Run in the Supabase SQL Editor after 006_outreach_and_fit_signals.sql
--
-- This is a sales-controlled tag separate from the auto-detected `industry`
-- column (migration 004). The dashboard exposes a dropdown so reps can
-- bucket each lead into one of: Consumer Goods, Health & Beauty,
-- Food & Beverage, Manufacturing, Distribution.

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS user_industry TEXT;

CREATE INDEX IF NOT EXISTS idx_events_user_industry
  ON public.events (user_industry)
  WHERE user_industry IS NOT NULL;

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'events'
  AND column_name  = 'user_industry';
