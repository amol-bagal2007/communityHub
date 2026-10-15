-- Allow login/forgot-password screens to detect unknown emails (anon-safe).

CREATE OR REPLACE FUNCTION public.email_exists(p_email text)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM community_hub.profiles p
    WHERE lower(p.email) = lower(trim(COALESCE(p_email, '')))
  );
$$;

REVOKE ALL ON FUNCTION public.email_exists(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.email_exists(text) TO anon, authenticated;

-- Reject password-reset requests for emails that are not registered.
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

  IF v_profile IS NULL THEN
    RAISE EXCEPTION 'EMAIL_NOT_REGISTERED';
  END IF;

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
  TO anon, authenticated;

NOTIFY pgrst, 'reload schema';
