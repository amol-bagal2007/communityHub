-- Event schedule: from/to times and optional break window.

ALTER TABLE community_hub.events
  ADD COLUMN IF NOT EXISTS end_time TIME,
  ADD COLUMN IF NOT EXISTS break_start_time TIME,
  ADD COLUMN IF NOT EXISTS break_end_time TIME;

-- Backfill end_time for existing rows (1 hour after start).
UPDATE community_hub.events
SET end_time = ((event_date AT TIME ZONE 'UTC')::time + INTERVAL '1 hour')::time
WHERE end_time IS NULL;

ALTER TABLE community_hub.events
  ALTER COLUMN end_time SET NOT NULL;

ALTER TABLE community_hub.events
  DROP CONSTRAINT IF EXISTS events_break_window_check;

ALTER TABLE community_hub.events
  ADD CONSTRAINT events_break_window_check CHECK (
    (
      break_start_time IS NULL
      AND break_end_time IS NULL
    )
    OR (
      break_start_time IS NOT NULL
      AND break_end_time IS NOT NULL
      AND break_start_time < break_end_time
    )
  );
