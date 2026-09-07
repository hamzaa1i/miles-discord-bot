# Aurelia — Veloura's Custom Discord Bot

Aurelia is Veloura's custom community bot — soft-spoken, slightly playful, AI-powered, with a full moderation suite. She/her, lowercase always.

## Features

- **AI Chat** — `@Aurelia` or `/aurelia` to talk to her naturally
- **Natural Language Moderation** — say "warn @user" via AI and she handles it
- **Server Moderation** — full `/mod` command suite (kick, ban, timeout, warn, purge, nuke, lock, slowmode)
- **Weather** — `/weather [city]`
- **Fun** — `/joke`, `/meme`, `/flip`, `/roll`, `/truth`, `/dare`
- **Welcome System** — customizable welcome/goodbye messages
- **Server Info** — `/serverinfo`, `/whois`, `/avatar`
- **AFK System** — `/afk [reason]`

## Setup

### Prerequisites
- Python 3.11+
- A Discord bot token (from the Discord Developer Portal)
- A Groq API key (free at [console.groq.com](https://console.groq.com))

### Installation
1. Clone the repo
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`
4. Set `DISCORD_TOKEN`, `GROQ_API_KEY`, `OWNER_ID`
5. `python main.py`

## Hosting (Render + UptimeRobot)

### Render Setup
1. Connect this GitHub repo to Render → New Web Service
2. Runtime: Python 3.11.9
3. Build: `pip install -r requirements.txt`
4. Start: `python main.py`
5. Env vars: `DISCORD_TOKEN`, `GROQ_API_KEY`, `OWNER_ID`, `PYTHON_VERSION=3.11.9`

### UptimeRobot
- Monitor: HTTP(s)
- URL: `https://your-service.onrender.com/health`
- Interval: every 5 minutes

### Important Render notes
- Free tier sleeps after 15 min — UptimeRobot prevents this
- `/data` folder is ephemeral — data resets on redeploy
- For persistent data, upgrade to Render paid tier or use an external DB

### Discord slash-command cache
When commands are added/removed/changed, Discord's client may still show old
commands in the UI. To force a refresh:
1. **Completely quit and reopen Discord**, OR
2. Wait up to **1 hour** for Discord to refresh automatically

## Web Dashboard

A companion Next.js dashboard lives in [`dashboard/`](./dashboard/README.md) —
server owners can configure every feature (welcome cards, leveling, QOTD,
moderation, giveaways, custom commands, …) through a browser at
`https://aurelia.vercel.app` instead of slash commands.

- **Auth** — Discord OAuth2 (`identify` + `guilds`), token in an httpOnly cookie
- **API** — `/api/dashboard/*` endpoints served by this same Flask app
  (utils/dashboard_api.py), bearer-verified, manage-guild-gated, CSRF-protected,
  rate-limited, fully audit-logged
- **Live actions** — "post QOTD now", "test welcome", "end giveaway",
  "reload cog" reach the running bot through an internal action queue

### Deploying the dashboard (Vercel, free)

1. Discord Developer Portal → your application → **OAuth2**:
   - add redirect `https://aurelia.vercel.app/oauth/callback`
   - add redirect `http://localhost:3000/oauth/callback` (for local dev)
   - copy the **Client ID** and **Client Secret**
2. Vercel → import this repo → set **Root Directory = `dashboard`**
3. Vercel env vars (see `dashboard/README.md` for the full table):
   `NEXT_PUBLIC_API_URL=https://miles-discord-bot.onrender.com`,
   `API_BASE_URL` (same), `NEXT_PUBLIC_DISCORD_CLIENT_ID`,
   `DISCORD_CLIENT_SECRET`, `NEXTAUTH_URL`, `NEXTAUTH_SECRET`
4. On **Render**, add env vars so the API trusts the dashboard origin:
   `DASHBOARD_URL=https://aurelia.vercel.app`, `DISCORD_CLIENT_ID`,
   `DISCORD_CLIENT_SECRET`,
   `OAUTH_REDIRECT_URI=https://miles-discord-bot.onrender.com/api/dashboard/oauth/callback`
5. Run the `dashboard_audit` SQL block (bottom of
   `scripts/supabase_migration.sql`) in the Supabase SQL editor

Full setup guide incl. local dev and custom domain:
[`dashboard/README.md`](./dashboard/README.md) · design notes:
[`dashboard/ARCHITECTURE.md`](./dashboard/ARCHITECTURE.md)

## License
MIT
