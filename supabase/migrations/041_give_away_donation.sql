-- Give Away / Donation: member offers, admin drives, approve/reject, queue or link to a drive.

CREATE TABLE IF NOT EXISTS community_hub.donation_drives (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  location_text TEXT NOT NULL,
  drive_date DATE NOT NULL,
  notes TEXT,
  visibility_days INTEGER NOT NULL DEFAULT 14
    CHECK (visibility_days BETWEEN 1 AND 365),
  is_published BOOLEAN NOT NULL DEFAULT true,
  created_by UUID REFERENCES community_hub.profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS donation_drives_date_idx
  ON community_hub.donation_drives (drive_date DESC);

CREATE TABLE IF NOT EXISTS community_hub.donation_offers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  added_by UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  society_id UUID REFERENCES community_hub.societies(id) ON DELETE SET NULL,
  items TEXT NOT NULL,
  includes_recyclables BOOLEAN NOT NULL DEFAULT false,
  handoff_mode TEXT NOT NULL CHECK (handoff_mode IN ('pickup', 'drop_corridor')),
  pickup_at TIMESTAMPTZ,
  remarks TEXT,
  drive_id UUID REFERENCES community_hub.donation_drives(id) ON DELETE SET NULL,
  in_queue BOOLEAN NOT NULL DEFAULT true,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected')),
  admin_reason TEXT,
  reviewed_by UUID REFERENCES community_hub.profiles(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS donation_offers_status_idx
  ON community_hub.donation_offers (status, created_at DESC);
CREATE INDEX IF NOT EXISTS donation_offers_added_by_idx
  ON community_hub.donation_offers (added_by);
CREATE INDEX IF NOT EXISTS donation_offers_drive_idx
  ON community_hub.donation_offers (drive_id);

INSERT INTO community_hub.app_feature_flags (key, enabled)
VALUES ('give_away_tab', false)
ON CONFLICT (key) DO NOTHING;

ALTER TABLE community_hub.donation_drives ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_hub.donation_offers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS donation_drives_read ON community_hub.donation_drives;
CREATE POLICY donation_drives_read ON community_hub.donation_drives
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND is_published = true
    )
  );

DROP POLICY IF EXISTS donation_drives_admin_all ON community_hub.donation_drives;
CREATE POLICY donation_drives_admin_all ON community_hub.donation_drives
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

DROP POLICY IF EXISTS donation_offers_read ON community_hub.donation_offers;
CREATE POLICY donation_offers_read ON community_hub.donation_offers
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR added_by = auth.uid()
    OR (
      community_hub.is_approved_user()
      AND status = 'approved'
      AND (
        in_queue = true
        OR EXISTS (
          SELECT 1
          FROM community_hub.donation_drives d
          WHERE d.id = drive_id
            AND d.is_published = true
            AND CURRENT_DATE <= (d.drive_date + d.visibility_days)
        )
      )
    )
  );

DROP POLICY IF EXISTS donation_offers_insert ON community_hub.donation_offers;
CREATE POLICY donation_offers_insert ON community_hub.donation_offers
  FOR INSERT
  WITH CHECK (
    added_by = auth.uid()
    AND status = 'pending'
    AND (community_hub.is_approved_user() OR community_hub.is_admin())
    AND society_id IS NOT DISTINCT FROM community_hub.get_user_society_id()
  );

DROP POLICY IF EXISTS donation_offers_update_own ON community_hub.donation_offers;
CREATE POLICY donation_offers_update_own ON community_hub.donation_offers
  FOR UPDATE
  USING (
    added_by = auth.uid()
    AND status = 'pending'
    AND community_hub.is_approved_user()
  )
  WITH CHECK (
    added_by = auth.uid()
    AND status = 'pending'
  );

DROP POLICY IF EXISTS donation_offers_delete_own ON community_hub.donation_offers;
CREATE POLICY donation_offers_delete_own ON community_hub.donation_offers
  FOR DELETE
  USING (
    community_hub.is_admin()
    OR (added_by = auth.uid() AND status = 'pending')
  );

DROP POLICY IF EXISTS donation_offers_admin_update ON community_hub.donation_offers;
CREATE POLICY donation_offers_admin_update ON community_hub.donation_offers
  FOR UPDATE
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON community_hub.donation_offers TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON community_hub.donation_drives TO authenticated;

NOTIFY pgrst, 'reload schema';
