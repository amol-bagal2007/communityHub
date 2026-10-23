-- Share a Ride: drivers offer a routine; passengers request a specific day.

CREATE TABLE IF NOT EXISTS community_hub.ride_offers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  added_by UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  society_id UUID REFERENCES community_hub.societies(id) ON DELETE SET NULL,
  routine TEXT NOT NULL CHECK (routine IN ('daily', 'weekly', 'monthly')),
  week_days TEXT,
  month_day INTEGER CHECK (month_day IS NULL OR month_day BETWEEN 1 AND 31),
  from_place TEXT NOT NULL,
  to_place TEXT NOT NULL,
  travel_time TIME NOT NULL,
  car_details TEXT NOT NULL,
  available_seats INTEGER NOT NULL CHECK (available_seats BETWEEN 1 AND 8),
  charge_mode TEXT NOT NULL CHECK (charge_mode IN ('free', 'paid')),
  charges NUMERIC(10, 2),
  whatsapp_number TEXT NOT NULL,
  group_whatsapp_link TEXT,
  restrictions TEXT,
  pickup_point TEXT NOT NULL,
  drop_point TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ride_offers_society_idx
  ON community_hub.ride_offers (society_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ride_offers_added_by_idx
  ON community_hub.ride_offers (added_by);

CREATE TABLE IF NOT EXISTS community_hub.ride_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id UUID NOT NULL REFERENCES community_hub.ride_offers(id) ON DELETE CASCADE,
  requester_id UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  ride_date DATE NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (offer_id, requester_id, ride_date)
);

CREATE INDEX IF NOT EXISTS ride_requests_offer_date_idx
  ON community_hub.ride_requests (offer_id, ride_date, status);

INSERT INTO community_hub.app_feature_flags (key, enabled)
VALUES ('share_ride_tab', false)
ON CONFLICT (key) DO NOTHING;

ALTER TABLE community_hub.ride_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_hub.ride_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ride_offers_read ON community_hub.ride_offers;
CREATE POLICY ride_offers_read ON community_hub.ride_offers
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND (
        added_by = auth.uid()
        OR society_id = community_hub.get_user_society_id()
      )
    )
  );

DROP POLICY IF EXISTS ride_offers_insert ON community_hub.ride_offers;
CREATE POLICY ride_offers_insert ON community_hub.ride_offers
  FOR INSERT
  WITH CHECK (
    added_by = auth.uid()
    AND (community_hub.is_approved_user() OR community_hub.is_admin())
    AND society_id IS NOT DISTINCT FROM community_hub.get_user_society_id()
  );

DROP POLICY IF EXISTS ride_offers_delete ON community_hub.ride_offers;
CREATE POLICY ride_offers_delete ON community_hub.ride_offers
  FOR DELETE
  USING (
    community_hub.is_admin()
    OR (added_by = auth.uid() AND community_hub.is_approved_user())
  );

DROP POLICY IF EXISTS ride_requests_read ON community_hub.ride_requests;
CREATE POLICY ride_requests_read ON community_hub.ride_requests
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR requester_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM community_hub.ride_offers o
      WHERE o.id = offer_id AND o.added_by = auth.uid()
    )
  );

DROP POLICY IF EXISTS ride_requests_insert ON community_hub.ride_requests;
CREATE POLICY ride_requests_insert ON community_hub.ride_requests
  FOR INSERT
  WITH CHECK (
    requester_id = auth.uid()
    AND status = 'pending'
    AND (community_hub.is_approved_user() OR community_hub.is_admin())
    AND EXISTS (
      SELECT 1 FROM community_hub.ride_offers o
      WHERE o.id = offer_id
        AND o.added_by <> auth.uid()
        AND (
          community_hub.is_admin()
          OR o.society_id = community_hub.get_user_society_id()
        )
    )
  );

DROP POLICY IF EXISTS ride_requests_driver_update ON community_hub.ride_requests;
CREATE POLICY ride_requests_driver_update ON community_hub.ride_requests
  FOR UPDATE
  USING (
    community_hub.is_admin()
    OR EXISTS (
      SELECT 1 FROM community_hub.ride_offers o
      WHERE o.id = offer_id AND o.added_by = auth.uid()
    )
  )
  WITH CHECK (
    status IN ('pending', 'approved', 'rejected')
    AND (
      community_hub.is_admin()
      OR EXISTS (
        SELECT 1 FROM community_hub.ride_offers o
        WHERE o.id = offer_id AND o.added_by = auth.uid()
      )
    )
  );

DROP POLICY IF EXISTS ride_requests_reopen ON community_hub.ride_requests;
CREATE POLICY ride_requests_reopen ON community_hub.ride_requests
  FOR UPDATE
  USING (requester_id = auth.uid() AND status = 'rejected')
  WITH CHECK (requester_id = auth.uid() AND status = 'pending');

DROP POLICY IF EXISTS ride_requests_delete ON community_hub.ride_requests;
CREATE POLICY ride_requests_delete ON community_hub.ride_requests
  FOR DELETE
  USING (
    community_hub.is_admin()
    OR requester_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM community_hub.ride_offers o
      WHERE o.id = offer_id AND o.added_by = auth.uid()
    )
  );

CREATE OR REPLACE FUNCTION community_hub.enforce_ride_request_rules()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_offer community_hub.ride_offers%ROWTYPE;
  v_approved integer;
  v_day text;
BEGIN
  SELECT * INTO v_offer
  FROM community_hub.ride_offers
  WHERE id = NEW.offer_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Ride offer was not found';
  END IF;

  IF NEW.requester_id = v_offer.added_by THEN
    RAISE EXCEPTION 'You cannot request your own ride';
  END IF;

  v_day := (ARRAY['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'])
    [EXTRACT(DOW FROM NEW.ride_date)::integer + 1];
  IF v_offer.routine = 'weekly'
     AND position(v_day in COALESCE(v_offer.week_days, '')) = 0 THEN
    RAISE EXCEPTION 'This ride does not run on that day';
  ELSIF v_offer.routine = 'monthly'
     AND EXTRACT(DAY FROM NEW.ride_date)::integer IS DISTINCT FROM v_offer.month_day THEN
    RAISE EXCEPTION 'This ride does not run on that day of the month';
  END IF;

  IF NEW.status = 'approved'
     AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'approved') THEN
    SELECT count(*) INTO v_approved
    FROM community_hub.ride_requests r
    WHERE r.offer_id = NEW.offer_id
      AND r.ride_date = NEW.ride_date
      AND r.status = 'approved'
      AND r.id IS DISTINCT FROM NEW.id;
    IF v_approved >= v_offer.available_seats THEN
      RAISE EXCEPTION 'No seats left for that day';
    END IF;
  END IF;

  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS ride_requests_enforce_rules ON community_hub.ride_requests;
CREATE TRIGGER ride_requests_enforce_rules
  BEFORE INSERT OR UPDATE ON community_hub.ride_requests
  FOR EACH ROW
  EXECUTE FUNCTION community_hub.enforce_ride_request_rules();

GRANT SELECT, INSERT, DELETE ON community_hub.ride_offers TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON community_hub.ride_requests TO authenticated;

NOTIFY pgrst, 'reload schema';
