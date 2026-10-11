-- Local businesses listed by members; owner or admin may edit/delete; ratings 1-5.

CREATE TABLE IF NOT EXISTS community_hub.local_businesses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_name TEXT NOT NULL,
  description TEXT,
  whatsapp_number TEXT,
  whatsapp_group_link TEXT,
  timing TEXT,
  week_off TEXT,
  society_id UUID NOT NULL REFERENCES community_hub.societies(id) ON DELETE CASCADE,
  added_by UUID REFERENCES community_hub.profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS local_businesses_society_id_idx
  ON community_hub.local_businesses (society_id);
CREATE INDEX IF NOT EXISTS local_businesses_added_by_idx
  ON community_hub.local_businesses (added_by);
CREATE INDEX IF NOT EXISTS local_businesses_name_idx
  ON community_hub.local_businesses (business_name);

CREATE TABLE IF NOT EXISTS community_hub.local_business_ratings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID NOT NULL REFERENCES community_hub.local_businesses(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  review TEXT NOT NULL CHECK (char_length(trim(review)) > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (business_id, user_id)
);

CREATE INDEX IF NOT EXISTS local_business_ratings_business_id_idx
  ON community_hub.local_business_ratings (business_id);

INSERT INTO community_hub.app_feature_flags (key, enabled) VALUES
  ('local_business_tab', false)
ON CONFLICT (key) DO NOTHING;

ALTER TABLE community_hub.local_businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_hub.local_business_ratings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS local_businesses_read ON community_hub.local_businesses;
CREATE POLICY local_businesses_read ON community_hub.local_businesses
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND society_id = community_hub.get_user_society_id()
    )
  );

DROP POLICY IF EXISTS local_businesses_insert_own ON community_hub.local_businesses;
CREATE POLICY local_businesses_insert_own ON community_hub.local_businesses
  FOR INSERT
  WITH CHECK (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND added_by = auth.uid()
      AND society_id = community_hub.get_user_society_id()
    )
  );

DROP POLICY IF EXISTS local_businesses_update_own ON community_hub.local_businesses;
CREATE POLICY local_businesses_update_own ON community_hub.local_businesses
  FOR UPDATE
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND added_by = auth.uid()
      AND society_id = community_hub.get_user_society_id()
    )
  )
  WITH CHECK (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND added_by = auth.uid()
      AND society_id = community_hub.get_user_society_id()
    )
  );

DROP POLICY IF EXISTS local_businesses_delete_own ON community_hub.local_businesses;
CREATE POLICY local_businesses_delete_own ON community_hub.local_businesses
  FOR DELETE
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND added_by = auth.uid()
      AND society_id = community_hub.get_user_society_id()
    )
  );

DROP POLICY IF EXISTS local_businesses_admin_all ON community_hub.local_businesses;
CREATE POLICY local_businesses_admin_all ON community_hub.local_businesses
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

DROP POLICY IF EXISTS local_business_ratings_read ON community_hub.local_business_ratings;
CREATE POLICY local_business_ratings_read ON community_hub.local_business_ratings
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND EXISTS (
        SELECT 1 FROM community_hub.local_businesses b
        WHERE b.id = business_id
          AND b.society_id = community_hub.get_user_society_id()
      )
    )
  );

DROP POLICY IF EXISTS local_business_ratings_insert_own ON community_hub.local_business_ratings;
CREATE POLICY local_business_ratings_insert_own ON community_hub.local_business_ratings
  FOR INSERT
  WITH CHECK (
    user_id = auth.uid()
    AND community_hub.is_approved_user()
    AND EXISTS (
      SELECT 1 FROM community_hub.local_businesses b
      WHERE b.id = business_id
        AND b.society_id = community_hub.get_user_society_id()
    )
  );

DROP POLICY IF EXISTS local_business_ratings_update_own ON community_hub.local_business_ratings;
CREATE POLICY local_business_ratings_update_own ON community_hub.local_business_ratings
  FOR UPDATE
  USING (user_id = auth.uid() AND community_hub.is_approved_user())
  WITH CHECK (user_id = auth.uid() AND community_hub.is_approved_user());

DROP POLICY IF EXISTS local_business_ratings_delete_own ON community_hub.local_business_ratings;
CREATE POLICY local_business_ratings_delete_own ON community_hub.local_business_ratings
  FOR DELETE
  USING (user_id = auth.uid() AND community_hub.is_approved_user());

DROP POLICY IF EXISTS local_business_ratings_admin_all ON community_hub.local_business_ratings;
CREATE POLICY local_business_ratings_admin_all ON community_hub.local_business_ratings
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON community_hub.local_businesses TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON community_hub.local_business_ratings TO authenticated;

NOTIFY pgrst, 'reload schema';
