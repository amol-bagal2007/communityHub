-- Available Parking tab: shareable profile parking + allocation requests.

INSERT INTO community_hub.app_feature_flags (key, enabled) VALUES
  ('available_parking_tab', false)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS community_hub.parking_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  requester_id UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
  request_message TEXT,
  owner_comment TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT parking_requests_no_self CHECK (owner_id <> requester_id)
);

CREATE INDEX IF NOT EXISTS parking_requests_owner_id_idx
  ON community_hub.parking_requests (owner_id);
CREATE INDEX IF NOT EXISTS parking_requests_requester_id_idx
  ON community_hub.parking_requests (requester_id);
CREATE INDEX IF NOT EXISTS parking_requests_status_idx
  ON community_hub.parking_requests (status);

-- One pending request per owner + requester.
CREATE UNIQUE INDEX IF NOT EXISTS parking_requests_pending_unique
  ON community_hub.parking_requests (owner_id, requester_id)
  WHERE status = 'pending';

-- At most one active allocation per parking owner.
CREATE UNIQUE INDEX IF NOT EXISTS parking_requests_approved_unique
  ON community_hub.parking_requests (owner_id)
  WHERE status = 'approved';

ALTER TABLE community_hub.parking_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS parking_requests_read ON community_hub.parking_requests;
CREATE POLICY parking_requests_read ON community_hub.parking_requests
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND (owner_id = auth.uid() OR requester_id = auth.uid())
    )
  );

DROP POLICY IF EXISTS parking_requests_admin_all ON community_hub.parking_requests;
CREATE POLICY parking_requests_admin_all ON community_hub.parking_requests
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

GRANT SELECT ON community_hub.parking_requests TO authenticated;

-- List shareable parking in the caller's society that is not currently allocated.
CREATE OR REPLACE FUNCTION public.get_available_parking()
RETURNS TABLE (
  owner_id uuid,
  owner_first_name text,
  owner_last_name text,
  owner_title text,
  parking_number text,
  parking_floor text,
  parking_share_mode text,
  parking_availability_value integer,
  parking_availability_unit text,
  parking_charges numeric,
  tower_name text,
  flat_number text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_society uuid;
BEGIN
  IF NOT community_hub.is_approved_user() AND NOT community_hub.is_admin() THEN
    RAISE EXCEPTION 'Not authorized';
  END IF;

  SELECT p.society_id INTO v_society
  FROM community_hub.profiles p
  WHERE p.id = auth.uid();

  IF v_society IS NULL AND NOT community_hub.is_admin() THEN
    RETURN;
  END IF;

  RETURN QUERY
  SELECT
    p.id,
    p.first_name,
    p.last_name,
    p.title,
    p.parking_number,
    p.parking_floor,
    p.parking_share_mode,
    p.parking_availability_value,
    p.parking_availability_unit,
    p.parking_charges,
    t.name,
    p.flat_number
  FROM community_hub.profiles p
  LEFT JOIN community_hub.towers t ON t.id = p.tower_id
  WHERE p.status = 'approved'
    AND p.parking_share_mode IN ('free', 'paid')
    AND NULLIF(trim(COALESCE(p.parking_number, '')), '') IS NOT NULL
    AND (community_hub.is_admin() OR p.society_id = v_society)
    AND NOT EXISTS (
      SELECT 1
      FROM community_hub.parking_requests r
      WHERE r.owner_id = p.id
        AND r.status = 'approved'
    )
  ORDER BY p.parking_number, p.first_name, p.last_name;
END;
$$;

REVOKE ALL ON FUNCTION public.get_available_parking() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_available_parking() TO authenticated;

CREATE OR REPLACE FUNCTION public.submit_parking_request(
  p_owner_id uuid,
  p_message text DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_id uuid;
  v_me uuid := auth.uid();
  v_my_society uuid;
  v_owner community_hub.profiles%ROWTYPE;
BEGIN
  IF v_me IS NULL OR NOT community_hub.is_approved_user() THEN
    RAISE EXCEPTION 'Not authorized';
  END IF;
  IF p_owner_id IS NULL OR p_owner_id = v_me THEN
    RAISE EXCEPTION 'Invalid parking owner';
  END IF;

  SELECT * INTO v_owner
  FROM community_hub.profiles
  WHERE id = p_owner_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Parking owner not found';
  END IF;

  IF v_owner.status <> 'approved'
     OR v_owner.parking_share_mode NOT IN ('free', 'paid')
     OR NULLIF(trim(COALESCE(v_owner.parking_number, '')), '') IS NULL THEN
    RAISE EXCEPTION 'This parking is not available for requests';
  END IF;

  SELECT society_id INTO v_my_society
  FROM community_hub.profiles
  WHERE id = v_me;

  IF v_my_society IS NULL OR v_owner.society_id IS DISTINCT FROM v_my_society THEN
    RAISE EXCEPTION 'Parking is outside your society';
  END IF;

  IF EXISTS (
    SELECT 1 FROM community_hub.parking_requests r
    WHERE r.owner_id = p_owner_id AND r.status = 'approved'
  ) THEN
    RAISE EXCEPTION 'This parking is already allocated';
  END IF;

  IF EXISTS (
    SELECT 1 FROM community_hub.parking_requests r
    WHERE r.owner_id = p_owner_id
      AND r.requester_id = v_me
      AND r.status = 'pending'
  ) THEN
    RAISE EXCEPTION 'You already have a pending request for this parking';
  END IF;

  INSERT INTO community_hub.parking_requests (
    owner_id, requester_id, status, request_message
  )
  VALUES (
    p_owner_id,
    v_me,
    'pending',
    NULLIF(trim(COALESCE(p_message, '')), '')
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.submit_parking_request(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.submit_parking_request(uuid, text) TO authenticated;

CREATE OR REPLACE FUNCTION public.respond_parking_request(
  p_request_id uuid,
  p_approve boolean,
  p_comment text DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_me uuid := auth.uid();
  v_req community_hub.parking_requests%ROWTYPE;
  v_comment text := NULLIF(trim(COALESCE(p_comment, '')), '');
BEGIN
  IF v_me IS NULL OR NOT community_hub.is_approved_user() THEN
    RAISE EXCEPTION 'Not authorized';
  END IF;

  SELECT * INTO v_req
  FROM community_hub.parking_requests
  WHERE id = p_request_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Request not found';
  END IF;

  IF v_req.owner_id <> v_me AND NOT community_hub.is_admin() THEN
    RAISE EXCEPTION 'Only the parking owner can respond';
  END IF;

  IF v_req.status <> 'pending' THEN
    RAISE EXCEPTION 'Request is no longer pending';
  END IF;

  IF p_approve THEN
    IF EXISTS (
      SELECT 1 FROM community_hub.parking_requests r
      WHERE r.owner_id = v_req.owner_id
        AND r.status = 'approved'
        AND r.id <> v_req.id
    ) THEN
      RAISE EXCEPTION 'Parking is already allocated';
    END IF;

    UPDATE community_hub.parking_requests
    SET status = 'approved',
        owner_comment = v_comment,
        updated_at = now()
    WHERE id = v_req.id;

    UPDATE community_hub.parking_requests
    SET status = 'rejected',
        owner_comment = COALESCE(
          v_comment,
          'Automatically rejected because another request was approved.'
        ),
        updated_at = now()
    WHERE owner_id = v_req.owner_id
      AND status = 'pending'
      AND id <> v_req.id;
  ELSE
    UPDATE community_hub.parking_requests
    SET status = 'rejected',
        owner_comment = COALESCE(v_comment, 'Rejected by parking owner.'),
        updated_at = now()
    WHERE id = v_req.id;
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.respond_parking_request(uuid, boolean, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.respond_parking_request(uuid, boolean, text) TO authenticated;

CREATE OR REPLACE FUNCTION public.cancel_parking_allocation(p_request_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_me uuid := auth.uid();
  v_req community_hub.parking_requests%ROWTYPE;
BEGIN
  IF v_me IS NULL OR NOT community_hub.is_approved_user() THEN
    RAISE EXCEPTION 'Not authorized';
  END IF;

  SELECT * INTO v_req
  FROM community_hub.parking_requests
  WHERE id = p_request_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Request not found';
  END IF;

  IF v_req.status <> 'approved' THEN
    RAISE EXCEPTION 'Only an approved allocation can be cancelled';
  END IF;

  IF v_req.owner_id <> v_me
     AND v_req.requester_id <> v_me
     AND NOT community_hub.is_admin() THEN
    RAISE EXCEPTION 'Not allowed to cancel this allocation';
  END IF;

  UPDATE community_hub.parking_requests
  SET status = 'cancelled',
      owner_comment = COALESCE(owner_comment, 'Allocation cancelled.'),
      updated_at = now()
  WHERE id = v_req.id;
END;
$$;

REVOKE ALL ON FUNCTION public.cancel_parking_allocation(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.cancel_parking_allocation(uuid) TO authenticated;

NOTIFY pgrst, 'reload schema';
