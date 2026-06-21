-- Admin-managed sub-groups per member group.

CREATE TABLE community_hub.member_sub_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_group_id UUID NOT NULL REFERENCES community_hub.member_groups(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (member_group_id, name)
);

INSERT INTO community_hub.member_sub_groups (member_group_id, name)
SELECT mg.id, mapping.sub_name
FROM (
  VALUES
    ('Sports', 'Cricket'),
    ('Sports', 'Table Tennis'),
    ('Sports', 'Football'),
    ('Sports', 'Basketball'),
    ('Sports', 'Pool Table'),
    ('Sports', 'Swimming Pool'),
    ('Sports', 'Cycling'),
    ('Sports', 'Running'),
    ('Sports', 'Walking'),
    ('Games', 'Carrom'),
    ('Games', 'Chess'),
    ('Logistic Service', 'Car Pooling'),
    ('Social Cause', 'Tree Plantation')
) AS mapping(group_name, sub_name)
JOIN community_hub.member_groups mg ON mg.name = mapping.group_name
ON CONFLICT (member_group_id, name) DO NOTHING;

ALTER TABLE community_hub.profiles
  ADD COLUMN member_sub_group_id UUID
  REFERENCES community_hub.member_sub_groups(id) ON DELETE SET NULL;

ALTER TABLE community_hub.member_sub_groups ENABLE ROW LEVEL SECURITY;

CREATE POLICY member_sub_groups_read ON community_hub.member_sub_groups
  FOR SELECT
  USING (community_hub.is_approved_user() OR community_hub.is_admin());

CREATE POLICY member_sub_groups_admin_all ON community_hub.member_sub_groups
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());

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
BEGIN
  v_role := COALESCE((NEW.raw_user_meta_data->>'role')::community_hub.user_role, 'resident');
  v_tenant_expiry := NULLIF(NEW.raw_user_meta_data->>'tenant_expiry_date', '')::DATE;
  v_full_name := COALESCE(NEW.raw_user_meta_data->>'full_name', '');
  v_title := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'title', '')), '');
  v_sex := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'sex', '')), '');
  v_age := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'age', '')), '')::INTEGER;
  v_member_group_id := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'member_group_id', '')), '')::UUID;
  v_member_sub_group_id := NULLIF(trim(COALESCE(NEW.raw_user_meta_data->>'member_sub_group_id', '')), '')::UUID;

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

  IF v_role = 'tenant' AND v_tenant_expiry IS NULL THEN
    RAISE EXCEPTION 'tenant_expiry_date is required for tenant registrations';
  END IF;

  IF v_role = 'resident' AND NOT v_staying THEN
    RAISE EXCEPTION 'staying_within_society must be confirmed for owner registrations';
  END IF;

  INSERT INTO community_hub.profiles (
    id, email, title, first_name, last_name, sex, age, phone,
    member_group_id, member_sub_group_id, role,
    society_id, tower_id, flat_number, tenant_expiry_date, staying_within_society, status
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
    'pending'
  );
  UPDATE auth.users
  SET email_confirmed_at = COALESCE(email_confirmed_at, now()),
      updated_at = now()
  WHERE id = NEW.id;
  RETURN NEW;
END;
$function$;
