-- Include member phone and WhatsApp in the duplicate-number check (signup and profile save).
-- Safe to run after 031, and safe to run if 031 was already applied with the earlier vendor-only function.

CREATE OR REPLACE FUNCTION community_hub.normalize_contact_digits(p_value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN length(regexp_replace(COALESCE(p_value, ''), '\D', '', 'g')) >= 10
      THEN right(regexp_replace(COALESCE(p_value, ''), '\D', '', 'g'), 10)
    ELSE NULLIF(regexp_replace(COALESCE(p_value, ''), '\D', '', 'g'), '')
  END;
$$;

DROP FUNCTION IF EXISTS public.contact_number_exists(text, uuid, uuid);

CREATE OR REPLACE FUNCTION public.contact_number_exists(
  p_number text,
  p_exclude_vendor uuid DEFAULT NULL,
  p_exclude_business uuid DEFAULT NULL,
  p_exclude_profile uuid DEFAULT NULL
)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM community_hub.profiles p
    WHERE (p_exclude_profile IS NULL OR p.id <> p_exclude_profile)
      AND (
        community_hub.normalize_contact_digits(p.phone)
          = community_hub.normalize_contact_digits(p_number)
        OR community_hub.normalize_contact_digits(p.personal_whatsapp)
          = community_hub.normalize_contact_digits(p_number)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM community_hub.vendors v
    WHERE (p_exclude_vendor IS NULL OR v.id <> p_exclude_vendor)
      AND (
        community_hub.normalize_contact_digits(v.contact_phone)
          = community_hub.normalize_contact_digits(p_number)
        OR community_hub.normalize_contact_digits(v.personal_whatsapp)
          = community_hub.normalize_contact_digits(p_number)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM community_hub.local_businesses b
    WHERE (p_exclude_business IS NULL OR b.id <> p_exclude_business)
      AND (
        community_hub.normalize_contact_digits(b.phone)
          = community_hub.normalize_contact_digits(p_number)
        OR community_hub.normalize_contact_digits(b.whatsapp_number)
          = community_hub.normalize_contact_digits(p_number)
      )
  );
$$;

REVOKE ALL ON FUNCTION public.contact_number_exists(text, uuid, uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.contact_number_exists(text, uuid, uuid, uuid)
  TO anon, authenticated;

CREATE OR REPLACE FUNCTION community_hub.reject_duplicate_contact_numbers()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  d text;
  nums text[];
BEGIN
  IF TG_TABLE_NAME = 'vendors' THEN
    nums := ARRAY[
      community_hub.normalize_contact_digits(NEW.contact_phone),
      community_hub.normalize_contact_digits(NEW.personal_whatsapp)
    ];
  ELSIF TG_TABLE_NAME = 'profiles' THEN
    nums := ARRAY[
      community_hub.normalize_contact_digits(NEW.phone),
      community_hub.normalize_contact_digits(NEW.personal_whatsapp)
    ];
  ELSE
    nums := ARRAY[
      community_hub.normalize_contact_digits(NEW.phone),
      community_hub.normalize_contact_digits(NEW.whatsapp_number)
    ];
  END IF;

  FOREACH d IN ARRAY nums LOOP
    IF d IS NULL THEN
      CONTINUE;
    END IF;
    IF public.contact_number_exists(
      d,
      CASE WHEN TG_TABLE_NAME = 'vendors' THEN NEW.id ELSE NULL END,
      CASE WHEN TG_TABLE_NAME = 'local_businesses' THEN NEW.id ELSE NULL END,
      CASE WHEN TG_TABLE_NAME = 'profiles' THEN NEW.id ELSE NULL END
    ) THEN
      RAISE EXCEPTION 'This phone or WhatsApp number already exists';
    END IF;
  END LOOP;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS vendors_reject_duplicate_contact ON community_hub.vendors;
CREATE TRIGGER vendors_reject_duplicate_contact
  BEFORE INSERT OR UPDATE ON community_hub.vendors
  FOR EACH ROW
  EXECUTE FUNCTION community_hub.reject_duplicate_contact_numbers();

DROP TRIGGER IF EXISTS local_businesses_reject_duplicate_contact ON community_hub.local_businesses;
CREATE TRIGGER local_businesses_reject_duplicate_contact
  BEFORE INSERT OR UPDATE ON community_hub.local_businesses
  FOR EACH ROW
  EXECUTE FUNCTION community_hub.reject_duplicate_contact_numbers();

DROP TRIGGER IF EXISTS profiles_reject_duplicate_contact ON community_hub.profiles;
CREATE TRIGGER profiles_reject_duplicate_contact
  BEFORE INSERT OR UPDATE ON community_hub.profiles
  FOR EACH ROW
  EXECUTE FUNCTION community_hub.reject_duplicate_contact_numbers();

NOTIFY pgrst, 'reload schema';
