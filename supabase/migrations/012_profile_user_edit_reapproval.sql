-- Allow users to edit their own profile fields and re-submit for approval (status -> pending).

DROP POLICY IF EXISTS profiles_update_own ON community_hub.profiles;

CREATE POLICY profiles_update_own ON community_hub.profiles
  FOR UPDATE
  USING (id = auth.uid())
  WITH CHECK (
    id = auth.uid()
    AND (
      status IS NOT DISTINCT FROM (
        SELECT p.status FROM community_hub.profiles p WHERE p.id = auth.uid()
      )
      OR status = 'pending'::community_hub.user_status
    )
  );

CREATE OR REPLACE FUNCTION community_hub.prevent_profile_privilege_escalation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'community_hub'
AS $function$
DECLARE
  jwt_role text := current_setting('request.jwt.claim.role', true);
BEGIN
  IF current_user IN ('postgres', 'supabase_admin', 'service_role')
     OR jwt_role = 'service_role' THEN
    RETURN NEW;
  END IF;

  IF community_hub.is_admin() THEN
    RETURN NEW;
  END IF;

  -- Non-admins may set status to pending only (profile re-approval), not approve/reject themselves.
  IF NEW.status IS DISTINCT FROM OLD.status AND NEW.status <> 'pending'::community_hub.user_status THEN
    RAISE EXCEPTION 'Cannot modify protected profile fields';
  END IF;

  RETURN NEW;
END;
$function$;
