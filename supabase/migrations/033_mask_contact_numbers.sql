-- Let a member hide their mobile and WhatsApp numbers from other members.
-- Admins still read the stored numbers. Existing rows stay visible (flags default to false).

ALTER TABLE community_hub.profiles
  ADD COLUMN IF NOT EXISTS mask_phone BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS mask_whatsapp BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE community_hub.vendors
  ADD COLUMN IF NOT EXISTS mask_phone BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS mask_whatsapp BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE community_hub.local_businesses
  ADD COLUMN IF NOT EXISTS mask_phone BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS mask_whatsapp BOOLEAN NOT NULL DEFAULT false;

CREATE OR REPLACE FUNCTION community_hub.set_profile_contact_mask()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'auth', 'public'
AS $$
DECLARE
  meta jsonb;
BEGIN
  SELECT u.raw_user_meta_data INTO meta
  FROM auth.users u
  WHERE u.id = NEW.id;

  IF meta IS NULL THEN
    RETURN NEW;
  END IF;

  IF meta ? 'mask_phone' THEN
    NEW.mask_phone := COALESCE((meta->>'mask_phone')::boolean, false);
  END IF;
  IF meta ? 'mask_whatsapp' THEN
    NEW.mask_whatsapp := COALESCE((meta->>'mask_whatsapp')::boolean, false);
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS profiles_apply_signup_contact_mask ON community_hub.profiles;
CREATE TRIGGER profiles_apply_signup_contact_mask
  BEFORE INSERT ON community_hub.profiles
  FOR EACH ROW
  EXECUTE FUNCTION community_hub.set_profile_contact_mask();

DROP FUNCTION IF EXISTS public.get_admin_contacts();

CREATE OR REPLACE FUNCTION public.get_admin_contacts()
RETURNS TABLE (
  first_name text,
  last_name text,
  title text,
  phone text,
  email text,
  mask_phone boolean
)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
  SELECT
    p.first_name,
    p.last_name,
    p.title,
    p.phone,
    p.email,
    p.mask_phone
  FROM community_hub.profiles p
  WHERE p.role = 'admin'
    AND p.status = 'approved'
  ORDER BY p.first_name, p.last_name;
$$;

REVOKE ALL ON FUNCTION public.get_admin_contacts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_admin_contacts() TO anon, authenticated;

NOTIFY pgrst, 'reload schema';
