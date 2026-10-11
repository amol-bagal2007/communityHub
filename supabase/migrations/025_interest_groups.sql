-- Admin-managed interest group options for multi-select "Interested in groups".

CREATE TABLE IF NOT EXISTS community_hub.interest_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO community_hub.interest_groups (name) VALUES
  ('Sports'),
  ('Games'),
  ('Music'),
  ('Fitness / Yoga'),
  ('Social Cause'),
  ('Logistic Service')
ON CONFLICT (name) DO NOTHING;

ALTER TABLE community_hub.interest_groups ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS interest_groups_read ON community_hub.interest_groups;
CREATE POLICY interest_groups_read ON community_hub.interest_groups
  FOR SELECT
  USING (true);

DROP POLICY IF EXISTS interest_groups_admin_all ON community_hub.interest_groups;
CREATE POLICY interest_groups_admin_all ON community_hub.interest_groups
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

-- group_interests now stores a JSON array of interest_group UUIDs (as text).
-- Length check from migration 021 still applies.

NOTIFY pgrst, 'reload schema';
