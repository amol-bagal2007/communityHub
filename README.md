# CommunityHub

Streamlit PWA for society/community management, backed by Supabase project **comm_hub** with all data in the **`community_hub`** schema.

## Features

### Admin Dashboard
- Add/edit/delete **societies** (name, area, road, pin code) and **towers**
- **Approve or reject** user registrations from sign-up
- Manage **users** (residents & tenants)
- Manage **vendors** (admin-added and user-added)
- Create/edit/delete/publish **events**

### User Dashboard
- View **published events**
- Browse and add **vendors**
- View **society details**
- Update **profile**

## Database schema

All tables live under `community_hub`:

| Table | Purpose |
|-------|---------|
| `community_hub.societies` | Society name, area, road, pin code |
| `community_hub.towers` | Towers per society |
| `community_hub.profiles` | User profiles linked to `auth.users` |
| `community_hub.vendors` | Community vendors |
| `community_hub.events` | Society events (published to users) |

Migrations are applied via Supabase MCP. Local reference: `supabase/migrations/`.

## Setup

```bash
pip install -r requirements.txt
```

Configure `.env` (see `.env.example`):

```
SUPABASE_URL=https://gbtehdbjqmoelejgdfqd.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SCHEMA=community_hub
```

### Create the first admin

1. Supabase Dashboard → **Authentication → Users → Add user**
2. SQL Editor:

```sql
UPDATE community_hub.profiles
SET role = 'admin', status = 'approved'
WHERE email = 'your-admin@email.com';
```

3. Log in as admin and add society/tower details before users sign up.

### Run

```bash
streamlit run app.py
```

## PWA

Deploy over **HTTPS only** for install prompts and production use. Manifest: `static/manifest.json`.

## Security

See **[SECURITY.md](SECURITY.md)** for:

- Database RLS hardening (profile privilege escalation prevention)
- Auto email confirm on sign-up and admin approval
- Password rules (7+ alphanumeric characters)
- Supabase Dashboard steps (disable email confirmation, leaked password protection)
- Secrets and deployment guidance

**Never commit `.env`** — only use the anon/publishable key in the app, never the service role key.

## Verify schema exposure

If API calls fail with schema errors, confirm `community_hub` is listed under **Project Settings → API → Exposed schemas** in the Supabase Dashboard.
