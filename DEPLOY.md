# CommunityHub — free public deploy (Streamlit Community Cloud)
#
# Why not Vercel?
# Vercel is built for Next.js / serverless APIs. Streamlit needs a long-running
# Python process with WebSockets, which Vercel free hosting does not support.
# Use Streamlit Community Cloud instead (free, official, GitHub-connected).
#
# Deploy steps:
# 1. Push this repo to GitHub (do NOT commit .env).
# 2. Open https://share.streamlit.io and sign in with GitHub.
# 3. Click "New app" → select amol-bagal2007/communityHub → main → app.py
# 4. Advanced settings → Secrets → paste the block below (real values, not placeholders).
# 5. Deploy. After deploy, set APP_URL to your https://….streamlit.app URL and
#    add that URL under Supabase Auth → URL Configuration → Redirect URLs / Site URL.
#
# Streamlit Secrets format (TOML):

# SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
# SUPABASE_KEY = "your-anon-or-publishable-key"
# SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
# SUPABASE_SCHEMA = "community_hub"
# APP_URL = "https://YOUR_APP.streamlit.app"
