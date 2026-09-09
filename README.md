<p align="center">
  <img src="dashboard/marketing/aurelia-icon-transparent.png" width="130" alt="aurelia — a soft pink four-pointed star on transparent background" />
</p>

<h1 align="center">aurelia ✦</h1>

<p align="center"><b>the soft, elegant discord bot</b><br/>
aesthetic moderation, ai chat, and community features for your veloura-vibe server</p>

<p align="center">
  <a href="https://veloura-aurelia.vercel.app"><img alt="dashboard" src="https://img.shields.io/badge/dashboard-veloura--aurelia.vercel.app-FFC0CB?style=flat-square&labelColor=1A1D29"></a>
  <img alt="commands" src="https://img.shields.io/badge/commands-173-E6E6FA?style=flat-square&labelColor=1A1D29">
  <img alt="cogs" src="https://img.shields.io/badge/cogs-47-E6E6FA?style=flat-square&labelColor=1A1D29">
  <img alt="discord.py" src="https://img.shields.io/badge/discord.py-2.7-9CA3AF?style=flat-square&labelColor=1A1D29">
  <img alt="source" src="https://img.shields.io/badge/source-privately%20maintained-E6E6FA?style=flat-square&labelColor=1A1D29">
  <img alt="price" src="https://img.shields.io/badge/price-free%20forever%20%E2%99%A1-FFC0CB?style=flat-square&labelColor=1A1D29">
</p>

<p align="center">
  <a href="https://veloura-aurelia.vercel.app"><b>add to discord ✦</b></a> ·
  <a href="https://veloura-aurelia.vercel.app/docs">documentation</a> ·
  <a href="https://veloura-aurelia.vercel.app/stats">live stats</a> ·
  <a href="https://veloura-aurelia.vercel.app/changelog">changelog</a>
</p>

<p align="center">
  <img src="dashboard/marketing/aurelia-banner-2000x1000.png" alt="aurelia banner — the wordmark, a pink four-pointed star and the tagline 'the soft, elegant discord bot' on a dark navy gradient" width="100%" />
</p>

---

## why aurelia ♡

she's the bot for communities that care about vibes. every feature is
built twice — once as a slash command, once as something soft to look
at. talk to her, let her greet your newcomers, and let moderation be
firm where it matters and gentle everywhere else.

| | |
|---|---|
| **ai chat & memory** | `@aurelia hey what's up` — she keeps the conversation thread and learns durable facts. per-server personality, opt-out per user. |
| **aesthetic welcome cards** | embed / text / hybrid / dm modes, custom colors, live preview in the dashboard. |
| **booster celebrations** | configurable boost announcements (text / embed / hybrid), an optional hierarchy-safe booster role, and once-ever milestone cards at boost thresholds. |
| **smart moderation** | warnings as numbered cases, escalating thresholds, context-aware ai automod (severity 1-5), full audit log. |
| **engagement** | leveling + role rewards, daily streaks, qotd, giveaways with realtime entries, starboard, confessions, ships, achievements. |
| **a real dashboard** | 35 module pages with live discord pickers, one-click live actions and realtime updates. |
| **privacy first** | `/privacy export` (full json) and `/privacy delete` (erase everywhere) built in. |

<p>
  <img src="dashboard/marketing/aurelia-welcome-preview.png" width="30%" alt="welcome card preview — an embed greeting 'miyu' as member #128 with a pink gradient strip" valign="top" />
  <img src="dashboard/marketing/aurelia-chat-preview.png" width="30%" alt="chat preview — a conversation with aurelia about remembering a preference" valign="top" />
  <img src="dashboard/marketing/aurelia-mod-preview.png" width="30%" alt="moderation preview — warning case, ai automod nudge and audit log cards" valign="top" />
</p>

## quick start

1. **invite** — [add to discord ✦](https://veloura-aurelia.vercel.app)
   (curated permissions, never administrator)
2. **run** `/setup` — the interactive wizard configures welcome,
   leveling, qotd and friends in under two minutes
3. **talk** — `/help` for the menu, or just `@aurelia hello`

new servers also get a friendly owner dm with quick-start links, and
everything is configurable visually in the
[dashboard](https://veloura-aurelia.vercel.app).

> aurelia runs as one shared, carefully tended instance — the source is
> privately maintained by volc. adding her to your server is (and stays)
> free; source access is a separate thing.

## the ai core

one router, four providers, failover at every hop:

```
                Discord
                   │
                Aurelia
                   │
             AI Router
      ┌────────────┼────────────┐
   Gemini        Mistral       GLM
  (chat)     (fallback +     (reasoning,
              sensitive)      budget-guarded)
      └────────────┼────────────┘
                   │
                 Groq
             emergency floor
```

- **gemini 3.7 flash** — everyday conversation, low thinking
- **mistral small 4** — fallback, and the default route for sensitive
  work (moderation, automod) chosen for stricter data terms
- **glm-5.2 (openrouter, free)** — hard reasoning: recaps, deep
  analysis, difficult code. daily-budget guarded
- **groq** — the always-on emergency floor; if it's the only configured
  provider, aurelia behaves exactly like her pre-router self

every provider output passes the same sanitization pipeline (reasoning
strips, empty-content failover, discord length caps), every provider
has a circuit breaker, and `/owner ai_status` plus the dashboard's ai
engine page show live health — telemetry is counts and latencies only,
never conversations.

## architecture overview

```
cogs/ (47)              slash + prefix + listeners
utils/ai_router.py      profiles → provider chains, failover, breakers
ai_providers/           gemini · mistral · openrouter · groq adapters
utils/ai_handler.py     compatibility facade (call_ai family)
utils/db.py             supabase + json fallback persistence
utils/dashboard_api.py  flask api — bearer, csrf, rate-limit, audit
utils/public_api.py     public stats + changelog + rss
dashboard/              next.js 14 · react 18 · tailwind · realtime
main.py                 discord.py 2.7 entrypoint + flask keep-alive
```

## tech stack

- **bot** — python 3.11 · discord.py 2.7 · multi-provider ai (gemini ·
  mistral · openrouter/glm · groq failover) · 47 cogs, 173 commands
- **data** — supabase postgres with a json-file fallback so every
  feature works even before the (free) db is wired up
- **dashboard** — next.js 14 · react 18 · tailwind · supabase realtime
- **api** — flask blueprint on the bot process: bearer-auth,
  manage-guild-gated, csrf-protected, rate-limited, audit-logged
- **infra** — render (bot) + vercel (dashboard), both free tier

full docs:
[documentation](https://veloura-aurelia.vercel.app/docs) ·
[command reference](./COMMANDS.md) ·
[api](https://veloura-aurelia.vercel.app/docs/api)

### slash-command cache quirks

when commands change, discord's client may show stale ones for up to an
hour — fully quit and reopen discord to force a refresh.

## contributing ♡

aurelia's source is privately maintained. bug reports, feature ideas
and feedback are very welcome through the
[documentation](https://veloura-aurelia.vercel.app/docs) site and the
support server — they land in the build queue the same day.

## license

source © 2026 hamzaa1i (volc), all rights reserved — see
[LICENSE](./LICENSE) and [NOTICE](./NOTICE). free forever, no premium
tiers, no ads. built by **volc**, wrapped in veloura ✧
