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
| `community_hub.vendor_categories` | Admin-maintained vendor category list |
| `community_hub.vendors` | Vendor first/last name, category, recommended by, contact info |
| `community_hub.events` | Society events (published to users) |

Migrations are applied via Supabase MCP. Local reference: `supabase/migrations/`.


`APP_URL` is used for password reset email links. In production, set this to your deployed HTTPS URL.


### Forgot password setup

1. Users open **Forgot Password?** on the login screen.
2. They enter **registered email** + **WhatsApp mobile number** and click **Request Admin For Password Reset**.
3. Admin → **Users** → **Password Reset Requests** shows each pending request.
4. Admin sets a temporary password one by one, then shares it with the user on WhatsApp.
5. Requires migration `019_password_reset_requests.sql` and `SUPABASE_SERVICE_ROLE_KEY` for the actual Auth password update.


### Password rules (Supabase vs app)

CommunityHub validates: **7+ characters**, at least **one letter** and **one number**.

If registration fails with *"Password should contain at least one character of each..."*, that rule comes from **Supabase**, not the app.

**To relax Supabase password rules:**

1. [Supabase Dashboard](https://supabase.com/dashboard/project/gbtehdbjqmoelejgdfqd) → **Authentication**
2. Open **Sign In / Providers** → **Email**
3. Scroll to **Password** / **Password strength** settings
4. Set **Minimum password length** to `7`
5. Change **Required characters** to **No required characters** (or only what you need — not all four types)
6. Save

**Or** keep strict Supabase rules and use passwords like `Pass@123` (upper + lower + number + symbol).

### Enable email sign-ups (required for registration)

If registration fails with **"Email signups are disabled"**:

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → project **comm_hub**
2. Go to **Authentication → Providers → Email**
3. Turn **ON**:
   - **Enable Email provider**
   - **Allow new users to sign up** (under Authentication → **Sign In / Providers** or General settings)
4. Save

Also under **Authentication → URL Configuration**, add your app URL to **Redirect URLs** for password reset.


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
- Password rules (7+ chars with letter and number)
- Supabase Dashboard steps (disable email confirmation, leaked password protection)
- Secrets and deployment guidance

**Never commit `.env`** — only use the anon/publishable key in the app, never the service role key.

## Verify schema exposure

If API calls fail with schema errors, confirm `community_hub` is listed under **Project Settings → API → Exposed schemas** in the Supabase Dashboard.
