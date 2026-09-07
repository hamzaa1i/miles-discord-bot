# aurelia ✦ dashboard

The veloura-themed web dashboard for the [Aurelia Discord bot](../README.md).
Configure every feature through a browser instead of slash commands.

**stack** — Next.js 14 (App Router, TypeScript, Tailwind CSS) · Discord OAuth2 · Flask API on Render · Supabase (Realtime)

---

## how it fits together

```
browser ──(same-origin, httpOnly cookie)──▶ Next.js on Vercel
                                              │
                                              ├── /api/auth/*   — Discord OAuth code exchange
                                              └── /api/proxy/*  — relays requests with the
                                                                 Bearer token + CSRF header
                                                        │
                                                        ▼
                                    Flask API on Render (/api/dashboard/*)
                                              │            │
                                   utils/db.py │            │ action queue (5s poll)
                                              ▼            ▼
                                        Supabase        running bot (cogs)
```

- The Discord token lives ONLY in an `httpOnly` cookie on the dashboard's own
  domain — client JavaScript never sees it. The proxy route attaches it
  server-side on every API call.
- Every Flask endpoint verifies the bearer token, checks **manage server** on
  the target guild, requires a CSRF token on mutations, rate-limits to
  60 req/min/IP and writes to the `dashboard_audit` table.
- Live actions ("post QOTD now", "test welcome", "end giveaway", "reload cog")
  are enqueued on a thread-safe queue; a worker on the bot's event loop
  executes them within ~5 seconds.

---

## prerequisites

- Node.js **18+** and npm
- The bot running (locally or on Render) — it serves the API
- A Supabase project (optional — same one the bot uses)

## local development

```bash
# 1. install
cd dashboard
npm install

# 2. configure
cp .env.example .env.local
```

Fill in `.env.local`:

| var | where to get it | needed for |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8080` for local bot | everything |
| `NEXT_PUBLIC_DISCORD_CLIENT_ID` | Developer Portal → your app → Application ID | login |
| `DISCORD_CLIENT_SECRET` | Developer Portal → OAuth2 → Client Secret | login (server-side only) |
| `NEXTAUTH_URL` | `http://localhost:3000` locally | OAuth redirect + cookies |
| `NEXTAUTH_SECRET` | any random string (e.g. `openssl rand -hex 32`) | cookie signing |
| `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Settings → API | realtime (optional) |

```bash
# 3. run the bot's flask api (from the repo root, with your bot env)
python main.py            # serves :8080 (bot + flask together)

# 4. run the dashboard
npm run dev               # http://localhost:3000
```

Log in with Discord → you'll see every server where you have **manage server**
and Aurelia is a member.

> **Discord OAuth setup (one-time):** Developer Portal → your application →
> **OAuth2** → *Redirects* → add `http://localhost:3000/oauth/callback`
> (and `<YOUR_DASHBOARD_URL>/oauth/callback` once deployed). Copy the
> **Client ID** and **Client Secret** into your env files. The bot's own token
> is unchanged — this uses the same *application*, only its OAuth side.

## deploying to Vercel

1. Push the repo (the `dashboard/` folder is detected automatically as a
   Next.js project root — Vercel asks once; set **Root Directory = `dashboard`**).
2. In Vercel → project → **Settings → Environment Variables**, add:

   ```
   NEXT_PUBLIC_API_URL     = https://miles-discord-bot.onrender.com
   API_BASE_URL            = https://miles-discord-bot.onrender.com   (same, server-side)
   NEXT_PUBLIC_DISCORD_CLIENT_ID = <application id>
   DISCORD_CLIENT_SECRET   = <client secret>       (server-side only)
   NEXTAUTH_URL            = <YOUR_DASHBOARD_URL>      (your Vercel domain)
   NEXTAUTH_SECRET         = <openssl rand -hex 32>
   NEXT_PUBLIC_SUPABASE_URL       = <optional — realtime>
   NEXT_PUBLIC_SUPABASE_ANON_KEY  = <optional — realtime>
   ```
3. Deploy. Vercel's free tier is enough — this app is static + tiny routes.

Then on **Render** (the bot), add these environment variables so the Flask
API trusts your new dashboard origin:

```
DASHBOARD_URL           = <YOUR_DASHBOARD_URL>
DISCORD_CLIENT_ID       = <application id>
DISCORD_CLIENT_SECRET   = <client secret>
OAUTH_REDIRECT_URI      = https://miles-discord-bot.onrender.com/api/dashboard/oauth/callback
```

`OAUTH_REDIRECT_URI` powers the alternative server-side OAuth flow
(`/api/dashboard/oauth/callback`); the primary flow exchanges the code in
Next.js route handlers and does not need it.

4. In the Discord Developer Portal, add your production redirect:
   `<YOUR_DASHBOARD_URL>/oauth/callback`.

> **changing domains later:** the domain is never hardcoded in the code —
> update `NEXTAUTH_URL` (Vercel), `DASHBOARD_URL` (Render) and the Discord
> OAuth redirect (Developer Portal), redeploy, done. No code changes needed.

## custom domain

On Vercel: Settings → Domains → add `aurelia.bot` (or any domain) → follow the
DNS instructions. Then update:

- `NEXTAUTH_URL` in Vercel env vars
- `DASHBOARD_URL` in Render env vars
- the Discord OAuth redirect (Developer Portal)

## supabase setup (realtime + audit)

Run once in the Supabase SQL editor (idempotent — also at the bottom of
`scripts/supabase_migration.sql`):

```sql
CREATE TABLE IF NOT EXISTS public.dashboard_audit (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  guild_id TEXT NOT NULL,
  action TEXT NOT NULL,
  details JSONB,
  ip_address TEXT,
  user_agent TEXT,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_guild
  ON public.dashboard_audit(guild_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user
  ON public.dashboard_audit(user_id, timestamp DESC);
GRANT ALL ON public.dashboard_audit TO anon;
ALTER TABLE public.dashboard_audit DISABLE ROW LEVEL SECURITY;

-- optional: owner blacklist storage
CREATE TABLE IF NOT EXISTS public.owner_blacklist (
  user_id TEXT PRIMARY KEY,
  added_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
GRANT ALL ON public.owner_blacklist TO anon;
ALTER TABLE public.owner_blacklist DISABLE ROW LEVEL SECURITY;

-- optional: realtime (live warnings / command usage)
ALTER PUBLICATION supabase_realtime ADD TABLE public.warnings;
ALTER PUBLICATION supabase_realtime ADD TABLE public.command_usage;
ALTER PUBLICATION supabase_realtime ADD TABLE public.user_levels;
```

Everything degrades gracefully without these — audit falls back to a local
JSON file and realtime features silently switch to periodic refresh.

## scripts

```bash
npm run dev     # local dev server
npm run build   # production build (also the CI check)
npm run start   # serve the production build
npm run lint    # eslint
```

## cost

$0. Vercel free tier (hobby), Render free tier (already running the bot),
Supabase free tier (already storing the data), the default Vercel domain
(`<your-project>.vercel.app`) or ~$10/yr if you buy `aurelia.bot`.

## project layout

```
dashboard/
├── app/
│   ├── page.tsx                    landing
│   ├── login/                      OAuth login
│   ├── oauth/callback/             code/token handling
│   ├── servers/page.tsx            server list
│   ├── servers/[guildId]/          guild shell + 23 module pages
│   └── api/
│       ├── auth/{state,exchange,session,logout}/
│       └── proxy/[...path]/        bearer relay to Flask
├── components/                     ui primitives + pickers + charts + preview
├── lib/                            api client, auth/guild contexts, module registry
├── styles/globals.css              veloura theme
├── middleware.ts                   cookie route guard
└── public/                         logo + favicon
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the design decisions and
[DEVELOPMENT.md](./DEVELOPMENT.md) to contribute.
