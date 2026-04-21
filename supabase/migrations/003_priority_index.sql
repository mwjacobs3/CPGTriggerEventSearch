-- Migration 003: Indexes for DOSS priority sorting
-- Run in the Supabase SQL Editor after 002_add_event_columns.sql

-- Lets the dashboard cheaply answer:
--   WHERE lead_status = 'NEW' ORDER BY relevance_score DESC
-- which is how sales reps surface the hottest DOSS prospects.
CREATE INDEX IF NOT EXISTS idx_events_status_score
    ON public.events (lead_status, relevance_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_events_relevance_score
    ON public.events (relevance_score DESC NULLS LAST);
