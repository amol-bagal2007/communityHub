-- Status changes (approve / reject) must not be blocked by the duplicate-number
-- check when the phone and WhatsApp values themselves are unchanged.

CREATE OR REPLACE FUNCTION community_hub.reject_duplicate_contact_numbers()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  d text;
  nums text[];
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF TG_TABLE_NAME = 'vendors' THEN
      IF community_hub.normalize_contact_digits(NEW.contact_phone)
           IS NOT DISTINCT FROM community_hub.normalize_contact_digits(OLD.contact_phone)
         AND community_hub.normalize_contact_digits(NEW.personal_whatsapp)
           IS NOT DISTINCT FROM community_hub.normalize_contact_digits(OLD.personal_whatsapp)
      THEN
        RETURN NEW;
      END IF;
    ELSIF TG_TABLE_NAME = 'profiles' THEN
      IF community_hub.normalize_contact_digits(NEW.phone)
           IS NOT DISTINCT FROM community_hub.normalize_contact_digits(OLD.phone)
         AND community_hub.normalize_contact_digits(NEW.personal_whatsapp)
           IS NOT DISTINCT FROM community_hub.normalize_contact_digits(OLD.personal_whatsapp)
      THEN
        RETURN NEW;
      END IF;
    ELSE
      IF community_hub.normalize_contact_digits(NEW.phone)
           IS NOT DISTINCT FROM community_hub.normalize_contact_digits(OLD.phone)
         AND community_hub.normalize_contact_digits(NEW.whatsapp_number)
           IS NOT DISTINCT FROM community_hub.normalize_contact_digits(OLD.whatsapp_number)
      THEN
        RETURN NEW;
      END IF;
    END IF;
  END IF;

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

NOTIFY pgrst, 'reload schema';
