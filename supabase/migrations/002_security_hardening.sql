-- Security hardening migration (applied to comm_hub Supabase project)
-- See SECURITY.md for full documentation

-- profiles_update_own: users may only change full_name, phone, flat_number
-- prevent_profile_privilege_escalation trigger: blocks role/status/society/tower/email changes
-- confirm_email_on_approval trigger: sets auth.users.email_confirmed_at on admin approve
-- handle_new_user: auto-confirms email on sign-up
-- REVOKE EXECUTE on internal functions from anon
