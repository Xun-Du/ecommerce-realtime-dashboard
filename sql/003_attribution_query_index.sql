-- Keep the 30-day click/buy scan below Supabase statement-timeout limits.
CREATE INDEX IF NOT EXISTS idx_events_attribution_window
ON events (created_at, user_id)
WHERE event_type IN ('click', 'buy');
