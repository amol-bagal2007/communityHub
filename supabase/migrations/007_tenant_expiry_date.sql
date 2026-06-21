-- Tenant expiry date on profiles; required when role is tenant.

ALTER TABLE community_hub.profiles
  ADD COLUMN tenant_expiry_date DATE;

ALTER TABLE community_hub.profiles
  ADD CONSTRAINT profiles_tenant_expiry_check
  CHECK (role <> 'tenant' OR tenant_expiry_date IS NOT NULL);

CREATE OR REPLACE FUNCTION community_hub.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'auth'
AS $function$
BEGIN
  INSERT INTO community_hub.profiles (
    id, email, first_name, last_name, phone, role, society_id, tower_id,
    flat_number, tenant_expiry_date, status
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
    'pending'
  );
  UPDATE auth.users
  SET email_confirmed_at = COALESCE(email_confirmed_at, now()),
      updated_at = now()
  WHERE id = NEW.id;
  RETURN NEW;
END;
$function$;
