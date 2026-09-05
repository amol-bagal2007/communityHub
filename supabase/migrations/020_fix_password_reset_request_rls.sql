-- Fix password_reset_requests RLS for login-screen submits.
-- Prefer a SECURITY DEFINER RPC so anon users are not blocked by table RLS.

DROP POLICY IF EXISTS password_reset_requests_insert_public
  ON community_hub.password_reset_requests;
DROP POLICY IF EXISTS password_reset_requests_admin_all
  ON community_hub.password_reset_requests;

-- Public insert of pending requests only (backup path).
CREATE POLICY password_reset_requests_insert_public
  ON community_hub.password_reset_requests
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (COALESCE(status, 'pending') = 'pending');

-- Admins manage requests (separate policies; avoid FOR ALL blocking inserts).
CREATE POLICY password_reset_requests_select_admin
  ON community_hub.password_reset_requests
  FOR SELECT
  USING (community_hub.is_admin());

CREATE POLICY password_reset_requests_update_admin
  ON community_hub.password_reset_requests
  FOR UPDATE
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

CREATE POLICY password_reset_requests_delete_admin
  ON community_hub.password_reset_requests
  FOR DELETE
  USING (community_hub.is_admin());

GRANT INSERT ON community_hub.password_reset_requests TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON community_hub.password_reset_requests TO authenticated;

-- Reliable path for the login screen: RPC bypasses table RLS as definer.
CREATE OR REPLACE FUNCTION public.submit_password_reset_request(
  p_email text,
  p_whatsapp text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_id uuid;
  v_email text;
  v_wa text;
  v_profile uuid;
  v_digits text;
BEGIN
  v_email := lower(trim(COALESCE(p_email, '')));
  v_wa := regexp_replace(trim(COALESCE(p_whatsapp, '')), '[^0-9+]', '', 'g');
  v_digits := regexp_replace(v_wa, '\D', '', 'g');

  IF v_email = '' OR position('@' in v_email) = 0 THEN
    RAISE EXCEPTION 'A valid email is required';
  END IF;

  IF length(v_digits) < 10 OR length(v_digits) > 15 THEN
    RAISE EXCEPTION 'Enter a valid WhatsApp mobile number (at least 10 digits)';
  END IF;

  SELECT p.id
  INTO v_profile
  FROM community_hub.profiles p
  WHERE lower(p.email) = v_email
  LIMIT 1;

  INSERT INTO community_hub.password_reset_requests (
    email,
    whatsapp_number,
    status,
    profile_id
  )
  VALUES (
    v_email,
    v_wa,
    'pending',
    v_profile
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.submit_password_reset_request(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.submit_password_reset_request(text, text)
  TO anon, authenticated, service_role;
