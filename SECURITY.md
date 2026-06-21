# Security Configuration

This document covers security measures implemented in code/database and manual steps in Supabase Dashboard.

## Implemented in code & database

| Item | Status |
|------|--------|
| Profile UPDATE RLS locks `role`, `status`, `society_id`, `tower_id`, `email` | Done |
| Trigger blocks privilege escalation on profile updates | Done |
| Auto-confirm email on sign-up | Done (`handle_new_user`) |
| Auto-confirm email when admin approves user | Done (`confirm_email_on_approval`) |
| Revoke RPC `EXECUTE` on internal helpers from `anon` | Done |
| Password: min 7 chars, must include letter and number (sign-up UI) | Done |
| `.env` in `.gitignore` | Done |
| App uses anon/publishable key only (never service role) | Done |

## Manual steps in Supabase Dashboard

Complete these before production launch.

### 1. Disable email confirmation (recommended, redundant with auto-confirm)

**Authentication → Providers → Email**

- Turn off **Confirm email**
- Save

Auto-confirm triggers already set `email_confirmed_at` on sign-up and approval; disabling this in Auth avoids duplicate flows.

### 2. Enable leaked password protection

**Authentication → Providers → Email** (or **Auth → Settings**)

- Enable **Leaked password protection** (HaveIBeenPwned check)
- Save

### 3. Set minimum password length in Auth

**Authentication → Providers → Email**

- Set **Minimum password length** to **7**

The app validates min 7 characters with at least one letter and one number at sign-up.

### 4. HTTPS only (deployment)

- Deploy Streamlit on a host with **HTTPS** (Streamlit Community Cloud, Railway, Render, etc.)
- Do **not** expose the app on plain HTTP in production
- PWA install requires HTTPS

### 5. Secrets hygiene

- Never commit `.env` — use `.env.example` as a template only
- Never put the **service_role** key in the app or frontend
- Rotate keys if `.env` was ever committed or shared

## Architecture summary

```
Browser ──HTTPS──► Streamlit server ──HTTPS──► Supabase API ──► community_hub schema
                         │                           │
                   anon key + JWT              RLS enforces access
```

Real authorization is enforced by **Row Level Security** in Postgres, not by Streamlit UI checks alone.

## Bootstrap first admin

```sql
UPDATE community_hub.profiles
SET role = 'admin', status = 'approved'
WHERE email = 'your-admin@example.com';
```

Also confirm email if needed (approval trigger handles this for future approvals):

```sql
UPDATE auth.users SET email_confirmed_at = now()
WHERE email = 'your-admin@example.com' AND email_confirmed_at IS NULL;
```
