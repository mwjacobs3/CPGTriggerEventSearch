-- Migration 008: Co-manufacturer signal + DOSS integration-stack signal
-- Run in the Supabase SQL Editor after 007_add_user_industry.sql
--
-- DOSS ICP centers on CPG brands that outsource production to co-mans /
-- co-packers and outsource fulfillment to 3PLs — these are the brands
-- with the inventory & PO complexity DOSS is built to manage. Migration
-- 006 captured a single `three_pl_mention` flag that conflated 3PL and
-- co-manufacturing. We split that here so each axis can be filtered.
--
-- We also add `integration_match`: a comma-separated list of products the
-- article mentions that DOSS already integrates with (Shopify, NetSuite,
-- SPS Commerce, ShipBob, …). A non-empty value means the brand is on a
-- stack DOSS plugs into, which short-circuits a major sales objection.

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS co_man_mention      BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS integration_match   TEXT;   -- comma-separated names

-- Partial indexes for sidebar filters in dashboard.py
CREATE INDEX IF NOT EXISTS idx_events_co_man_mention
  ON public.events (co_man_mention)
  WHERE co_man_mention IS TRUE;

CREATE INDEX IF NOT EXISTS idx_events_integration_match
  ON public.events (integration_match)
  WHERE integration_match IS NOT NULL AND integration_match <> '';

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'events'
  AND column_name IN ('co_man_mention', 'integration_match')
ORDER BY column_name;
