# changelog

every change to aurelia, newest first ✦

generated from git history by `scripts/generate_changelog.py` — the
api mirror lives at `GET /api/changelog`, the rss feed at
`/changelog.rss`, and the pretty page at [/changelog](/changelog).


## [v1.1.1] — 2026-09-08

> highlights: phase n.1 live repair — ai output safety (the glm meta-leak can never reach discord) · gemini afc disabled on ordinary generation · honest provider health states (configured ≠ healthy) · one-response cooldown fix · /toggledms governs every passive dm · time-capsule 22007 timestamp fix · canonical command counts

phase n.1 — the live-reliability pass. real production traffic exposed six bugs in the freshly deployed multi-provider core; this release traces each one to root cause and fixes it without new features, without a dashboard redesign, without touching phase n's architecture.

### fixes
- **ai output safety (p0):** the exact glm-5.2 meta-reasoning leak that reached discord ("we must not start two responses with same word; …") is now sanitized to empty and triggers provider failover — layered: reasoning-tag strip → leading meta-paragraph removal → sentence-level planning-language removal → last-chance high-confidence meta check → facade final guard before any cog sees text. legitimate prose that merely mentions "we should…" survives untouched
- **success accounting:** http 200 with only hidden reasoning/meta output is a sanitization_empty failure — counted, failed over, never reported green
- gemini: automatic function calling explicitly disabled on every ordinary text generation (root cause of the "afc is enabled with max remote calls: 10" + "direct use of afc … not recommended" startup warnings); verified against google-genai 2.22.0's should_disable_afc path
- mistral: error classification uses the sdk’s numeric status_code (verified against mistralai 2.9.4) — 401→auth, 404→model_unavailable, 400→bad_request so cooldowns and status cards stop mislabeling request-shape errors
- all four provider adapters: 400 (request shape) is bad_request, only real 404/decommissioned signals are model_unavailable; sanitized failure telemetry logs category + numeric status, never error bodies
- duplicate cooldown responses: discord.py 2.7.1 calls both the command-local and global tree error handlers — the global handler now checks interaction.response.is_done() first, so a handled /recap cooldown produces exactly one ephemeral reply (was two)
- time capsules: supabase boundary now converts unix epoch floats ↔ iso-8601 utc (postgres 22007 root cause — the live table column is timestamptz while inserts sent raw floats); json fallback keeps the legacy float format, existing rows keep working, no sql migration required
- /toggledms is now the global passive-dm switch: achievement unlocks (still saved!), level-up dm announcements, onboarding join panels, welcome/join rewards and welcomer coin rewards respect it; explicitly requested dm flows (modmail, reminders, private capsules, /welcome test dm, /privacy export) are never gated

### improvements
- provider health states are honest: unconfigured · unknown · healthy · degraded · cooldown · auth_error · model_unavailable — "healthy" requires a real successful request; configured-but-unverified shows "unknown"
- /owner ai_status + dashboard ai engine card show the sanitized last failure category per provider and the new state vocabulary
- command counts canonicalized: 46 cogs · 73 top-level commands/groups · 169 total invokable paths (discord 100-limit headroom 27) — same helper feeds the startup log, /botinfo, /api/public/stats, the docs/landing copy (168→169) and tests
- live provider diagnostic: scripts/test_ai_providers_live.py (env-gated AURELIA_ALLOW_LIVE_AI_TESTS=true, one 3-word probe per provider, sanitized output only — never run at startup or in test suites)
- 45 new phase n.1 regression tests (scripts/test_phase_n1.py) including the exact production leak string, failover accounting, cooldown single-response, passive-dm gating and the capsule lifecycle

## [v1.1.0] — 2026-09-07

> highlights: multi-provider ai router with four-provider failover · privacy-aware sensitive routing · persistent provider telemetry + /owner ai_status · auth-aware site navigation everywhere · private-source preparation

phase n — the ai core grows up and the public site learns to navigate. aurelia's mind now runs on a four-provider routing architecture with circuit breakers, budgets and observability; the site header finally knows who you are; and the source repository is prepared for private maintenance.

### features
- multi-provider ai router: gemini 3.7 flash primary chat, mistral small 4 fallback + sensitive route, openrouter glm-5.2 free reasoning (45/day budget guard), groq emergency floor
- ai engine status page in the dashboard: route diagram, provider health, latencies, glm budget meter, privacy note
- `/owner ai_status` — compact owner-only provider health card (subcommand, no new root command)
- persistent ai_provider_usage telemetry (supabase + json fallback; metadata only, never prompts)
- auth-aware public site header: avatar + profile dropdown (dashboard · my servers · sign out) when logged in, login when logged out
- home ↔ dashboard navigation: logo links to the landing page from /servers and every guild dashboard; landing hero shows "open dashboard" when signed in
- docs breadcrumbs on every documentation page ("docs / page", docs always clickable)

### improvements
- call_ai / call_ai_fast / call_ai_reasoning / pick_model contracts preserved — zero cog rewrites needed
- sensitive requests (ai automod, nl moderation intents) route mistral → groq; gemini/openrouter excluded unless explicitly allowed by config
- provider circuit breakers: 429 cooldowns with retry-after, 5xx degradation, auth stop-hammering, model-unavailable skipping — one message never triggers more than 4 api calls
- every provider output passes the same sanitization pipeline (cot strip, empty-response failover, 1900-char cap)
- all model ids + routing flags env-overridable from one config layer (utils/ai_config)
- privacy disclosure updated for multi-provider operation; "powered by groq" copy retired
- changelog generator pins the v1.0.0 commit range so launch notes are never rewritten

### breaking changes
- source license changed from MIT to proprietary (All Rights Reserved) for future revisions — releases already distributed under MIT remain governed by that license; see NOTICE
## [v1.0.0] — 2026-09-07

> highlights: public launch — 45 cogs, 167 commands, 34 dashboard modules · ai chat with persistent memory + personality · full veloura web dashboard with live previews · gentle moderation: warnings, ai automod, thresholds · engagement core: leveling, daily rewards, qotd, starboard · privacy-first: /privacy export + delete everywhere

the launch release — everything aurelia is today. five build phases, two live-test repair rounds and a full web dashboard later, she's ready for your server ♡

### features
- phase m — public landing, docs site, stats, changelog, setup wizard, marketing assets (`28734dd`)
- live bot status card, env-driven dashboard domains, helpful login errors (`3a96697`)
- dashboard phase C — all remaining module pages, realtime, privacy (`54c5138`)
- dashboard phase B — leveling, qotd, moderation, custom commands, ai automod, statistics (`568d5c8`)
- dashboard MVP — flask api, oauth flow, welcome module (`4d6ee9d`)
- phase 3 — social & identity systems (ship, capsules, achievements, colors, nick requests, privacy) (`5f05a65`)
- phase 2 — engagement core (daily rewards, qotd, anniversaries, recurring reminders, timezone utils, first-message welcome) (`c8daab6`)
- phase 1 — infra hardening, 4 quick-win commands, aesthetic polish (`a254bdf`)
- phase 4 — 8 new features (AI memory, AI automod, recap, starboard, giveaways, custom commands, proactive, onboarding) (`77102db`)
- phase 2 — warnings migration, security hardening, non-blocking DB, dead-code purge, Aurelia rebrand (`920a716`)

### fixes
- overview Asset 500, dedicated sidebar routes, live polls page (`5279e1f`)
- live-test round — live Discord channel/role pickers, permission-check race, icons, ux polish (`7c2100b`)
- close single-line CoT edge case in _strip_cot_preambles (`1012a81`)
- live-test batch — CoT leak elimination, whois title, /botinfo gating, /vibe freshness, usage-log silence (`4db1dcb`)
- phase 7 — utility intents bypassed by AI chat, custom level-up messages, /welcome config consolidation (`0ba6bd0`)
- phase 6 — live-test bug fixes + welcome UX rework (`d392eda`)
- repair all 8 phase-4 features after live testing (`d0e9d46`)
- moderation intents firing + status visibility + Mimu-style welcome polish (`e8612c8`)
- P0 audit fixes — unified warnings store, prefix routing, intent ordering, prompt repair (`710a722`)
- Mimu-style welcome system + remove /chat duplicate (`8700e0d`)

### improvements
- fix gitignore entry for tsconfig.tsbuildinfo (`96c4bad`)
- update default dashboard domain to aurelia.vercel.app (`d6c3eb2`)
- dashboard setup, architecture and deployment guides (`de91cbf`)
- complete command reference (`61bee44`)
- veloura-aesthetic lowercase status rotation (`da564af`)
- full code audit (10 sections, ~50 findings, P0-P3 roadmap) (`c6cbfe4`)

