# aurelia ✦ dashboard

Veloura-themed web dashboard for the Aurelia Discord bot.
Next.js 14 (App Router, TypeScript, Tailwind CSS) + the Flask API on Render.

> **status: phase A (MVP)** — auth flow, server list, overview and the
> welcome module are live. Remaining module pages land in phases B & C.
> Full setup guide arrives with the phase C docs.

## quick start (local)

```bash
cd dashboard
npm install
cp .env.example .env.local   # fill in Discord OAuth + Supabase values
npm run dev                  # http://localhost:3000
```

The bot's Flask API must be reachable (`NEXT_PUBLIC_API_URL`, defaults to
`http://localhost:8080`).
