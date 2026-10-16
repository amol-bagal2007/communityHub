-- Local business contact/location fields, admin approval, vendor and profile WhatsApp.

ALTER TABLE community_hub.local_businesses
  ADD COLUMN IF NOT EXISTS phone TEXT,
  ADD COLUMN IF NOT EXISTS first_name TEXT,
  ADD COLUMN IF NOT EXISTS last_name TEXT,
  ADD COLUMN IF NOT EXISTS tower_id UUID REFERENCES community_hub.towers(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS flat_number TEXT,
  ADD COLUMN IF NOT EXISTS status TEXT;

UPDATE community_hub.local_businesses
SET status = 'approved'
WHERE status IS NULL;

ALTER TABLE community_hub.local_businesses
  ALTER COLUMN status SET DEFAULT 'pending';

ALTER TABLE community_hub.local_businesses
  ALTER COLUMN status SET NOT NULL;

ALTER TABLE community_hub.local_businesses
  DROP CONSTRAINT IF EXISTS local_businesses_status_check;

ALTER TABLE community_hub.local_businesses
  ADD CONSTRAINT local_businesses_status_check
  CHECK (status IN ('pending', 'approved', 'rejected'));

CREATE INDEX IF NOT EXISTS local_businesses_status_idx
  ON community_hub.local_businesses (status);

ALTER TABLE community_hub.vendors
  ADD COLUMN IF NOT EXISTS personal_whatsapp TEXT;

ALTER TABLE community_hub.profiles
  ADD COLUMN IF NOT EXISTS personal_whatsapp TEXT;

CREATE OR REPLACE FUNCTION community_hub.enforce_local_business_approval()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'community_hub'
AS $$
BEGIN
  IF community_hub.is_admin() THEN
    IF NEW.status IS NULL THEN
      NEW.status := 'approved';
    END IF;
    RETURN NEW;
  END IF;
  -- Member adds and edits stay pending until an admin approves.
  NEW.status := 'pending';
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS local_businesses_approval ON community_hub.local_businesses;
CREATE TRIGGER local_businesses_approval
  BEFORE INSERT OR UPDATE ON community_hub.local_businesses
  FOR EACH ROW
  EXECUTE FUNCTION community_hub.enforce_local_business_approval();

DROP POLICY IF EXISTS local_businesses_read ON community_hub.local_businesses;
CREATE POLICY local_businesses_read ON community_hub.local_businesses
  FOR SELECT
  USING (
    community_hub.is_admin()
    OR (
      community_hub.is_approved_user()
      AND (
        added_by = auth.uid()
        OR (
          status = 'approved'
          AND society_id = community_hub.get_user_society_id()
        )
      )
    )
  );

-- Keep signup trigger in sync with personal WhatsApp.
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
  v_sex text;
  v_age integer;
  v_member_group_id uuid;
  v_member_sub_group_id uuid;
  v_parking_share_mode text;
  v_parking_availability_value integer;
  v_parking_availability_unit text;
  v_parking_charges numeric(12, 2);
  v_bio text;
  v_group_interests text;
  v_disclaimer_accepted boolean;
  v_disclaimer_version text;
  v_personal_whatsapp text;
BEGIN
  v_role := COALESCE((NEW.raw_user_meta_data->>'role')::community_hub.user_role, 'resident');
  v_tenant_expiry := NULLIF(NEW.raw_user_meta_data->>'tenant_expiry_date', '')::DATE;
  v_full_name := COALESCE(NEW.raw_user_meta_data->>'full_name', '');
  v_title := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'title', '')), '');
  v_sex := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'sex', '')), '');
  v_age := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'age', '')), '')::INTEGER;
  v_member_group_id := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'member_group_id', '')), '')::UUID;
  v_member_sub_group_id := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'member_sub_group_id', '')), '')::UUID;
  v_parking_share_mode := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'parking_share_mode', '')), '');
  v_parking_availability_value := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'parking_availability_value', '')), '')::INTEGER;
  v_parking_availability_unit := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'parking_availability_unit', '')), '');
  v_parking_charges := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'parking_charges', '')), '')::NUMERIC;
  v_bio := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'bio', '')), '');
  v_group_interests := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'group_interests', '')), '');
  v_disclaimer_accepted := COALESCE((NEW.raw_user_meta_data->>'disclaimer_accepted')::boolean, false);
  v_disclaimer_version := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'disclaimer_version', '')), '');
  v_personal_whatsapp := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'personal_whatsapp', '')), '');

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

  IF NOT v_disclaimer_accepted THEN
    RAISE EXCEPTION 'disclaimer acceptance is required for registration';
  END IF;

  IF v_title IS NULL THEN
    RAISE EXCEPTION 'title is required for registration';
  END IF;

  IF v_sex IS NULL OR v_sex NOT IN ('Male', 'Female') THEN
    RAISE EXCEPTION 'sex is required for registration';
  END IF;

  IF v_age IS NULL OR v_age < 1 OR v_age > 120 THEN
    RAISE EXCEPTION 'age is required for registration';
  END IF;

  IF v_member_group_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM community_hub.member_groups mg WHERE mg.id = v_member_group_id) THEN
    RAISE EXCEPTION 'invalid member_group_id value';
  END IF;

  IF v_member_sub_group_id IS NOT NULL THEN
    IF v_member_group_id IS NULL
       OR NOT EXISTS (
         SELECT 1 FROM community_hub.member_sub_groups msg
         WHERE msg.id = v_member_sub_group_id
           AND msg.member_group_id = v_member_group_id
       ) THEN
      RAISE EXCEPTION 'invalid member_sub_group_id value';
    END IF;
  END IF;

  IF v_parking_share_mode IS NOT NULL
     AND v_parking_share_mode NOT IN ('not_available', 'free', 'paid') THEN
    RAISE EXCEPTION 'invalid parking_share_mode value';
  END IF;

  IF v_parking_availability_unit IS NOT NULL
     AND v_parking_availability_unit NOT IN ('hours', 'days', 'months', 'years') THEN
    RAISE EXCEPTION 'invalid parking_availability_unit value';
  END IF;

  IF v_bio IS NOT NULL AND char_length(v_bio) > 5000 THEN
    RAISE EXCEPTION 'bio exceeds 5000 characters';
  END IF;

  IF v_group_interests IS NOT NULL AND char_length(v_group_interests) > 5000 THEN
    RAISE EXCEPTION 'group_interests exceeds 5000 characters';
  END IF;

  IF v_role = 'tenant' AND v_tenant_expiry IS NULL THEN
    RAISE EXCEPTION 'tenant_expiry_date is required for tenant registrations';
  END IF;

  IF v_role = 'resident' AND NOT v_staying THEN
    RAISE EXCEPTION 'staying_within_society must be confirmed for owner registrations';
  END IF;

  INSERT INTO community_hub.profiles (
    id, email, title, first_name, last_name, sex, age, phone, personal_whatsapp,
    member_group_id, member_sub_group_id, role,
    society_id, tower_id, flat_number, tenant_expiry_date, staying_within_society, status,
    parking_number, parking_floor, parking_share_mode,
    parking_availability_value, parking_availability_unit, parking_charges,
    bio, group_interests,
    disclaimer_accepted, disclaimer_accepted_at, disclaimer_version
  )
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    v_title,
    COALESCE(v_first_name, ''),
    COALESCE(v_last_name, ''),
    v_sex,
    v_age,
    NEW.raw_user_meta_data->>'phone',
    v_personal_whatsapp,
    v_member_group_id,
    v_member_sub_group_id,
    v_role,
    NULLIF(NEW.raw_user_meta_data->>'society_id', '')::UUID,
    NULLIF(NEW.raw_user_meta_data->>'tower_id', '')::UUID,
    NEW.raw_user_meta_data->>'flat_number',
    v_tenant_expiry,
    v_staying,
    'pending',
    NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'parking_number', '')), ''),
    NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'parking_floor', '')), ''),
    v_parking_share_mode,
    v_parking_availability_value,
    v_parking_availability_unit,
    v_parking_charges,
    v_bio,
    v_group_interests,
    true,
    now(),
    COALESCE(v_disclaimer_version, '1.0')
  );
  UPDATE auth.users
  SET email_confirmed_at = COALESCE(email_confirmed_at, now()),
      updated_at = now()
  WHERE id = NEW.id;
  RETURN NEW;
END;
$function$;

NOTIFY pgrst, 'reload schema';
