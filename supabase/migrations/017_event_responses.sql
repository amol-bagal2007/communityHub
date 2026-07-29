-- Event interest responses (interested / not interested + contributor / volunteer).

CREATE TABLE community_hub.event_responses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NOT NULL REFERENCES community_hub.events(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  interest TEXT NOT NULL CHECK (interest IN ('interested', 'not_interested')),
  participation_role TEXT CHECK (
    participation_role IS NULL
    OR participation_role IN ('contributor', 'volunteer')
  ),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (event_id, user_id),
  CONSTRAINT event_responses_role_when_interested CHECK (
    (interest = 'interested' AND participation_role IS NOT NULL)
    OR (interest = 'not_interested' AND participation_role IS NULL)
  )
);

CREATE INDEX event_responses_event_id_idx ON community_hub.event_responses (event_id);
CREATE INDEX event_responses_user_id_idx ON community_hub.event_responses (user_id);

ALTER TABLE community_hub.event_responses ENABLE ROW LEVEL SECURITY;

CREATE POLICY event_responses_read_society ON community_hub.event_responses
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND EXISTS (
        SELECT 1
        FROM community_hub.events e
        WHERE e.id = event_id
          AND e.society_id = community_hub.get_user_society_id()
      )
    )
  );

CREATE POLICY event_responses_insert_own ON community_hub.event_responses
  FOR INSERT
  WITH CHECK (
    user_id = auth.uid()
    AND community_hub.is_approved_user()
    AND EXISTS (
      SELECT 1
      FROM community_hub.events e
      WHERE e.id = event_id
        AND e.is_published = true
        AND e.society_id = community_hub.get_user_society_id()
    )
  );

CREATE POLICY event_responses_update_own ON community_hub.event_responses
  FOR UPDATE
  USING (user_id = auth.uid() AND community_hub.is_approved_user())
  WITH CHECK (
    user_id = auth.uid()
    AND community_hub.is_approved_user()
    AND EXISTS (
      SELECT 1
      FROM community_hub.events e
      WHERE e.id = event_id
        AND e.is_published = true
        AND e.society_id = community_hub.get_user_society_id()
    )
  );

CREATE POLICY event_responses_delete_own ON community_hub.event_responses
  FOR DELETE
  USING (user_id = auth.uid() AND community_hub.is_approved_user());

-- Allow same-society members to see each other's names on event responses.
CREATE POLICY profiles_read_same_society ON community_hub.profiles
  FOR SELECT
  USING (
    community_hub.is_approved_user()
    AND society_id IS NOT NULL
    AND society_id = community_hub.get_user_society_id()
  );
