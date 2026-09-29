-- Vendor ratings (1-5 + required review) and per-user recommendations.

CREATE TABLE community_hub.vendor_ratings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor_id UUID NOT NULL REFERENCES community_hub.vendors(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  review TEXT NOT NULL CHECK (char_length(trim(review)) > 0),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (vendor_id, user_id)
);

CREATE TABLE community_hub.vendor_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor_id UUID NOT NULL REFERENCES community_hub.vendors(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (vendor_id, user_id)
);

CREATE INDEX vendor_ratings_vendor_id_idx ON community_hub.vendor_ratings (vendor_id);
CREATE INDEX vendor_recommendations_vendor_id_idx ON community_hub.vendor_recommendations (vendor_id);

-- Backfill recommendation for the member who added each vendor.
INSERT INTO community_hub.vendor_recommendations (vendor_id, user_id)
SELECT v.id, v.added_by
FROM community_hub.vendors v
WHERE v.added_by IS NOT NULL
ON CONFLICT (vendor_id, user_id) DO NOTHING;

ALTER TABLE community_hub.vendor_ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_hub.vendor_recommendations ENABLE ROW LEVEL SECURITY;

CREATE POLICY vendor_ratings_read ON community_hub.vendor_ratings
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND EXISTS (
        SELECT 1 FROM community_hub.vendors v
        WHERE v.id = vendor_id
          AND v.society_id = community_hub.get_user_society_id()
      )
    )
  );

CREATE POLICY vendor_ratings_insert_own ON community_hub.vendor_ratings
  FOR INSERT
  WITH CHECK (
    user_id = auth.uid()
    AND community_hub.is_approved_user()
    AND EXISTS (
      SELECT 1 FROM community_hub.vendors v
      WHERE v.id = vendor_id
        AND v.society_id = community_hub.get_user_society_id()
    )
  );

CREATE POLICY vendor_ratings_update_own ON community_hub.vendor_ratings
  FOR UPDATE
  USING (user_id = auth.uid() AND community_hub.is_approved_user())
  WITH CHECK (
    user_id = auth.uid()
    AND community_hub.is_approved_user()
  );

CREATE POLICY vendor_ratings_delete_own ON community_hub.vendor_ratings
  FOR DELETE
  USING (user_id = auth.uid() AND community_hub.is_approved_user());

CREATE POLICY vendor_ratings_admin_all ON community_hub.vendor_ratings
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

CREATE POLICY vendor_recommendations_read ON community_hub.vendor_recommendations
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND EXISTS (
        SELECT 1 FROM community_hub.vendors v
        WHERE v.id = vendor_id
          AND v.society_id = community_hub.get_user_society_id()
      )
    )
  );

CREATE POLICY vendor_recommendations_insert_own ON community_hub.vendor_recommendations
  FOR INSERT
  WITH CHECK (
    user_id = auth.uid()
    AND community_hub.is_approved_user()
    AND EXISTS (
      SELECT 1 FROM community_hub.vendors v
      WHERE v.id = vendor_id
        AND (
          community_hub.is_admin()
          OR v.society_id = community_hub.get_user_society_id()
        )
    )
  );

CREATE POLICY vendor_recommendations_delete_own ON community_hub.vendor_recommendations
  FOR DELETE
  USING (user_id = auth.uid() AND community_hub.is_approved_user());

CREATE POLICY vendor_recommendations_admin_all ON community_hub.vendor_recommendations
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON community_hub.vendor_ratings TO authenticated;
GRANT SELECT, INSERT, DELETE ON community_hub.vendor_recommendations TO authenticated;

NOTIFY pgrst, 'reload schema';
