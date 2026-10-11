-- Admin-controlled visibility: feature tabs + society/tower enable flags.

CREATE TABLE IF NOT EXISTS community_hub.app_feature_flags (
  key TEXT PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO community_hub.app_feature_flags (key, enabled) VALUES
  ('vendors_tab', false),
  ('events_tab', false)
ON CONFLICT (key) DO NOTHING;

ALTER TABLE community_hub.societies
  ADD COLUMN IF NOT EXISTS is_enabled BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE community_hub.towers
  ADD COLUMN IF NOT EXISTS is_enabled BOOLEAN NOT NULL DEFAULT false;

-- Keep existing societies/towers visible until an admin turns them off.
UPDATE community_hub.societies SET is_enabled = true WHERE is_enabled IS DISTINCT FROM true;
UPDATE community_hub.towers SET is_enabled = true WHERE is_enabled IS DISTINCT FROM true;

ALTER TABLE community_hub.app_feature_flags ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS app_feature_flags_read ON community_hub.app_feature_flags;
CREATE POLICY app_feature_flags_read ON community_hub.app_feature_flags
  FOR SELECT
  USING (true);

DROP POLICY IF EXISTS app_feature_flags_admin_all ON community_hub.app_feature_flags;
CREATE POLICY app_feature_flags_admin_all ON community_hub.app_feature_flags
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

NOTIFY pgrst, 'reload schema';
