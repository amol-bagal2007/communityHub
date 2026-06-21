-- Resident flag: staying within society premises.

ALTER TABLE community_hub.profiles
  ADD COLUMN staying_within_society BOOLEAN NOT NULL DEFAULT false;

CREATE OR REPLACE FUNCTION community_hub.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'auth'
AS $function$
BEGIN
  INSERT INTO community_hub.profiles (
    id, email, first_name, last_name, phone, role, society_id, tower_id,
    flat_number, tenant_expiry_date, staying_within_society, status
  )
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    COALESCE(NEW.raw_user_meta_data->>'first_name', ''),
    COALESCE(NEW.raw_user_meta_data->>'last_name', ''),
    NEW.raw_user_meta_data->>'phone',
    COALESCE((NEW.raw_user_meta_data->>'role')::community_hub.user_role, 'resident'),
    NULLIF(NEW.raw_user_meta_data->>'society_id', '')::UUID,
    NULLIF(NEW.raw_user_meta_data->>'tower_id', '')::UUID,
    NEW.raw_user_meta_data->>'flat_number',
    NULLIF(NEW.raw_user_meta_data->>'tenant_expiry_date', '')::DATE,
    COALESCE((NEW.raw_user_meta_data->>'staying_within_society')::boolean, false),
    'pending'
  );
  UPDATE auth.users
  SET email_confirmed_at = COALESCE(email_confirmed_at, now()),
      updated_at = now()
  WHERE id = NEW.id;
  RETURN NEW;
END;
$function$;
