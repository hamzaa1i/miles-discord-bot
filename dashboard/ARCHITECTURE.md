# dashboard/ARCHITECTURE.md — why it's built this way

## the problem

Aurelia has 69 root slash commands across 45 cogs. Server owners who want
to tweak a welcome message or a QOTD schedule must remember command names
and option paths. The dashboard mirrors every settings surface in a browser,
against the **same database the bot reads** — no second source of truth.

## top-level shape

```
Next.js 14 (Vercel)          Flask blueprint (Render)         discord.py bot
app/api/proxy  ───────────▶  /api/dashboard/*  ───────────▶   cogs (via queue)
app/api/auth   ───────────▶  Discord OAuth2                   Supabase
                              utils/db.py (shared, cached)
```

**Why a proxy instead of the browser calling Flask directly?**

The spec asked for the token in an *httpOnly cookie* — but httpOnly cookies
can only be set/read by the domain that owns them, and Flask lives on a
different origin (Render) than the dashboard (Vercel). Browsers also can't
put a cookie value into an `Authorization` header (that requires JS, which
can't read httpOnly cookies). The standard solution is a same-origin relay:
the browser talks only to Next.js, which attaches the bearer server-side.
Bonus: no CORS for the dashboard itself, and the token is never exposed to
client-side JavaScript at all (stronger than the spec's letter, same intent).

**Why Next.js route handlers do the OAuth exchange (and a Flask one also exists)**

The primary flow exchanges the code in `app/api/auth/exchange/route.ts`:
the redirect URI is the dashboard's own `/oauth/callback` page, the secret
stays server-side in the Vercel env, and the httpOnly cookie is set on the
dashboard domain in one hop. `GET /api/dashboard/oauth/callback` on Flask
implements the spec's server-side alternative (curl/CLI/static-host flows):
it exchanges the code and redirects to `DASHBOARD_URL#token=…` — a URL
fragment, which never appears in server logs — and the callback page copies
the token into the cookie via `POST /api/auth/session`.

## backend decisions

**Blueprint, not more routes in main.py.** `utils/dashboard_api.py` registers
~17 endpoints through `init_dashboard_api(app)`. main.py gains 2 lines.
The bot is reached via `keep_alive.bot_ref` (already the established
pattern) — importing main.py would be circular.

**Auth model.** Every request: Bearer → `verify_discord_token` (Discord
`/users/@me`, 120s cache). Guild routes also require **manage_guild**
(checked from the OAuth `/users/@me/guilds` permission bitmask, 5-min cache)
and that the bot is actually in the guild. Fail-closed everywhere.

**CSRF.** Because auth rides a cookie (via the proxy), mutations need CSRF
protection: `GET /api/dashboard/csrf` issues a random token bound to a
SHA-256 of the bearer with a 1-hour expiry; PATCH/POST/DELETE must echo it
in `X-CSRF-Token`. The frontend fetches it once per session.

**Rate limiting — deviation from the spec, documented here.** The spec
suggested flask-limiter. flask-limiter's default storage is in-memory for
a single process — which is exactly what Render's free tier runs — so we
implement the same guarantee (60 req/min/IP, sliding window, thread-safe,
JSON 429) with ~20 lines and zero new dependencies. To swap in
flask-limiter later: `pip install flask-limiter`, create
`Limiter(key_func=get_remote_address)` in this module, `init_app(app)` in
`init_dashboard_api`, and decorate `_auth_error`'s wrapper.

**The action queue — deviation from the spec, documented here.** The spec
drafted "an asyncio.Queue in main.py". Flask worker threads cannot safely
`put()` to an asyncio.Queue (it's loop-bound; you'd need
`loop.call_soon_threadsafe` per enqueue). We use a thread-safe
`queue.Queue` with identical semantics (FIFO, bounded at 100, consumed by
a worker coroutine that polls every 5s) — importable under the spec's name
from `utils/dashboard_actions`. This mirrors the documented
asyncio.Lock → threading.RLock deviation in `utils/cache.py`.

**Settings writes go through `utils.db.get/set_guild_setting`.** This
preserves the TTL cache + write-invalidation the bot itself uses, so a
dashboard save is visible to the bot within seconds. PATCH validates
against `_TABLE_COLUMNS` (unknown fields → 400 with the allowed list) plus
type checks for known fields. The two JSON-only stores (autorole) and the
data-only modules (giveaways, colors) get dedicated paths.

**Async helpers from Flask.** A few endpoints need async-only db functions
(qotd queue, nick requests). Flask threads have no event loop, so
`asyncio.run()` spins up a fresh one per call — the bot's loop lives in a
different thread and they never touch. Volume is dashboard-scale; fine.

**Audit.** Every mutation writes `dashboard_audit` (Supabase, JSON fallback
file capped at 500 rows) with user, guild, action, params, IP and UA. The
privacy page shows the last 50 per guild.

**Owner endpoints.** `/owner/logs`, `/owner/<action>` check
`user.id == OWNER_ID` *and* the executor re-checks owner-only action types
at run time. `blacklist_user` writes to `owner_blacklist` storage only —
enforcement hooks are deliberately not wired into existing cogs (the task
forbids modifying bot behavior); this is future-proofing + audit.

## frontend decisions

**Hand-rolled shadcn-style components.** The spec's `components/ui/` folder
is present (button-classes, card, inputs, tabs, badge, skeleton, toast) but
written directly with Tailwind — the shadcn CLI needs network + registry
access and pins you to its generator; veloura styling is ~10 small
components. Zero runtime UI dependencies.

**SVG charts, not a chart library.** `StatsChart.tsx` renders line and bar
charts with hand-computed paths — no recharts/chart.js payload (the whole
first-load JS is ~90 kB), full control of the veloura look, and hover
tooltips via native `<title>`.

**Module registry (`lib/modules.ts`).** Sidebar structure AND the
schema-driven `SettingsForm` (field types → pickers) come from one
registry, so the 8 thin pages (logging, starboard, birthdays, rules, …)
are 8-line files, while rich pages (welcome, leveling, qotd, moderation,
custom commands, giveaways, roles, nick) build custom layouts on the same
`useModuleSettings` lifecycle hook (load → edit → diff-save → revert →
reset-to-defaults).

**Fonts.** `next/font/google` fetches at build time — which fails on
offline builders. Instead the layout `<link>`s Playfair Display + Inter
from Google Fonts at *runtime* (standard practice, zero build dependency);
the Tailwind config keeps serif/sans fallbacks.

**Realtime.** `useRealtime` subscribes to Supabase inserts filtered by
guild (needs the `supabase_realtime` publication — SQL in the README).
When env vars are missing or the channel errors, consumers fall back to
periodic refetch; the UI shows a small ✧ realtime badge when live.

**Security summary.** Token: httpOnly cookie only · CSRF: bound tokens on
all mutations · auth: server-side proxy (client never sees the token) ·
redirects: fixed `NEXTAUTH_URL`/`DASHBOARD_URL` (no open redirects) ·
state: OAuth `state` verified against a short-lived cookie · cookies:
`samesite=lax`, `secure` in production.

**Mobile.** The sidebar collapses to a hamburger drawer (44px touch
targets), forms stack, tables scroll horizontally, the save bar is sticky.

## what's intentionally NOT here

- **Command execution** — the dashboard configures and triggers; it never
  impersonates a user running slash commands.
- **Refresh-token flow** — Discord user tokens live ~7 days; on expiry the
  UI routes to /login. A refresh flow is a small follow-up if wanted.
- **Bot-side blacklist enforcement** — storage + endpoints only (see above).
