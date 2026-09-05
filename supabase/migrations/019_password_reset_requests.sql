-- Password reset requests submitted from the login screen (admin-handled).

CREATE TABLE community_hub.password_reset_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL,
  whatsapp_number TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'completed', 'cancelled')),
  profile_id UUID REFERENCES community_hub.profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  completed_by UUID REFERENCES community_hub.profiles(id) ON DELETE SET NULL,
  admin_note TEXT
);

CREATE INDEX password_reset_requests_status_idx
  ON community_hub.password_reset_requests (status, created_at DESC);

CREATE OR REPLACE FUNCTION community_hub.link_password_reset_profile()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub'
AS $$
BEGIN
  NEW.email := lower(trim(NEW.email));
  NEW.whatsapp_number := regexp_replace(NEW.whatsapp_number, '[^0-9+]', '', 'g');
  IF NEW.profile_id IS NULL THEN
    SELECT p.id INTO NEW.profile_id
    FROM community_hub.profiles p
    WHERE lower(p.email) = NEW.email
    LIMIT 1;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER password_reset_requests_link_profile
  BEFORE INSERT ON community_hub.password_reset_requests
  FOR EACH ROW
  EXECUTE FUNCTION community_hub.link_password_reset_profile();

ALTER TABLE community_hub.password_reset_requests ENABLE ROW LEVEL SECURITY;

-- Anyone (login screen) can submit a pending request.
CREATE POLICY password_reset_requests_insert_public
  ON community_hub.password_reset_requests
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (status = 'pending');

-- Only admins can read / update / delete requests.
CREATE POLICY password_reset_requests_admin_all
  ON community_hub.password_reset_requests
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON community_hub.password_reset_requests TO authenticated;
GRANT INSERT ON community_hub.password_reset_requests TO anon;
