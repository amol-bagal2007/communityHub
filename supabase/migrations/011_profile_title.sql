-- Profile title (Mr., Ms., etc.) captured at sign-up.

ALTER TABLE community_hub.profiles
  ADD COLUMN title TEXT NOT NULL DEFAULT 'Mr.';

CREATE OR REPLACE FUNCTION community_hub.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'auth'
AS $function$
DECLARE
  v_role community_hub.user_role;
  v_staying boolean;
  v_tenant_expiry date;
  v_first_name text;
  v_last_name text;
  v_full_name text;
  v_title text;
BEGIN
  v_role := COALESCE((NEW.raw_user_meta_data->>'role')::community_hub.user_role, 'resident');
  v_tenant_expiry := NULLIF(NEW.raw_user_meta_data->>'tenant_expiry_date', '')::DATE;
  v_full_name := COALESCE(NEW.raw_user_meta_data->>'full_name', '');
  v_title := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'title', '')), '');

  v_first_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'first_name', '')), '');
  v_last_name := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'last_name', '')), '');
  IF v_first_name IS NULL AND v_full_name <> '' THEN
    v_first_name := split_part(v_full_name, ' ', 1);
    v_last_name := NULLIF(trim(substring(v_full_name from length(split_part(v_full_name, ' ', 1)) + 2)), '');
  END IF;

  IF v_role = 'resident' THEN
    IF NEW.raw_user_meta_data ? 'staying_within_society' THEN
      v_staying := COALESCE((NEW.raw_user_meta_data->>'staying_within_society')::boolean, false);
    ELSE
      v_staying := true;
    END IF;
  ELSE
    v_staying := false;
  END IF;

  IF v_title IS NULL THEN
    RAISE EXCEPTION 'title is required for registration';
  END IF;

  IF v_role = 'tenant' AND v_tenant_expiry IS NULL THEN
    RAISE EXCEPTION 'tenant_expiry_date is required for tenant registrations';
  END IF;

  IF v_role = 'resident' AND NOT v_staying THEN
    RAISE EXCEPTION 'staying_within_society must be confirmed for owner registrations';
  END IF;

  INSERT INTO community_hub.profiles (
    id, email, title, first_name, last_name, phone, role, society_id, tower_id,
    flat_number, tenant_expiry_date, staying_within_society, status
  )
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    v_title,
    COALESCE(v_first_name, ''),
    COALESCE(v_last_name, ''),
    NEW.raw_user_meta_data->>'phone',
    v_role,
    NULLIF(NEW.raw_user_meta_data->>'society_id', '')::UUID,
    NULLIF(NEW.raw_user_meta_data->>'tower_id', '')::UUID,
    NEW.raw_user_meta_data->>'flat_number',
    v_tenant_expiry,
    v_staying,
    'pending'
  );
  UPDATE auth.users
  SET email_confirmed_at = COALESCE(email_confirmed_at, now()),
      updated_at = now()
  WHERE id = NEW.id;
  RETURN NEW;
END;
$function$;
