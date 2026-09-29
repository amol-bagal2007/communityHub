-- Parking, bio, and group interest fields on profiles.

ALTER TABLE community_hub.profiles
  ADD COLUMN IF NOT EXISTS parking_number TEXT,
  ADD COLUMN IF NOT EXISTS parking_floor TEXT,
  ADD COLUMN IF NOT EXISTS parking_share_mode TEXT,
  ADD COLUMN IF NOT EXISTS parking_availability_value INTEGER,
  ADD COLUMN IF NOT EXISTS parking_availability_unit TEXT,
  ADD COLUMN IF NOT EXISTS parking_charges NUMERIC(12, 2),
  ADD COLUMN IF NOT EXISTS bio TEXT,
  ADD COLUMN IF NOT EXISTS group_interests TEXT;

ALTER TABLE community_hub.profiles
  DROP CONSTRAINT IF EXISTS profiles_parking_share_mode_check;
ALTER TABLE community_hub.profiles
  ADD CONSTRAINT profiles_parking_share_mode_check CHECK (
    parking_share_mode IS NULL
    OR parking_share_mode IN ('not_available', 'free', 'paid')
  );

ALTER TABLE community_hub.profiles
  DROP CONSTRAINT IF EXISTS profiles_parking_availability_unit_check;
ALTER TABLE community_hub.profiles
  ADD CONSTRAINT profiles_parking_availability_unit_check CHECK (
    parking_availability_unit IS NULL
    OR parking_availability_unit IN ('hours', 'days', 'months', 'years')
  );

ALTER TABLE community_hub.profiles
  DROP CONSTRAINT IF EXISTS profiles_parking_availability_value_check;
ALTER TABLE community_hub.profiles
  ADD CONSTRAINT profiles_parking_availability_value_check CHECK (
    parking_availability_value IS NULL OR parking_availability_value >= 1
  );

ALTER TABLE community_hub.profiles
  DROP CONSTRAINT IF EXISTS profiles_parking_charges_check;
ALTER TABLE community_hub.profiles
  ADD CONSTRAINT profiles_parking_charges_check CHECK (
    parking_charges IS NULL OR parking_charges >= 0
  );

ALTER TABLE community_hub.profiles
  DROP CONSTRAINT IF EXISTS profiles_bio_length_check;
ALTER TABLE community_hub.profiles
  ADD CONSTRAINT profiles_bio_length_check CHECK (
    bio IS NULL OR char_length(bio) <= 5000
  );

ALTER TABLE community_hub.profiles
  DROP CONSTRAINT IF EXISTS profiles_group_interests_length_check;
ALTER TABLE community_hub.profiles
  ADD CONSTRAINT profiles_group_interests_length_check CHECK (
    group_interests IS NULL OR char_length(group_interests) <= 5000
  );

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
    id, email, title, first_name, last_name, sex, age, phone,
    member_group_id, member_sub_group_id, role,
    society_id, tower_id, flat_number, tenant_expiry_date, staying_within_society, status,
    parking_number, parking_floor, parking_share_mode,
    parking_availability_value, parking_availability_unit, parking_charges,
    bio, group_interests
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
    v_group_interests
  );
  UPDATE auth.users
  SET email_confirmed_at = COALESCE(email_confirmed_at, now()),
      updated_at = now()
  WHERE id = NEW.id;
  RETURN NEW;
END;
$function$;
