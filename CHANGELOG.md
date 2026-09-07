# changelog

every change to aurelia, newest first ✦

generated from git history by `scripts/generate_changelog.py` — the
api mirror lives at `GET /api/changelog`, the rss feed at
`/changelog.rss`, and the pretty page at [/changelog](/changelog).


## [v1.0.0] — 2026-09-07

> highlights: public launch — 45 cogs, 167 commands, 34 dashboard modules · ai chat with persistent memory + personality · full veloura web dashboard with live previews · gentle moderation: warnings, ai automod, thresholds · engagement core: leveling, daily rewards, qotd, starboard · privacy-first: /privacy export + delete everywhere

the launch release — everything aurelia is today. five build phases, two live-test repair rounds and a full web dashboard later, she's ready for your server ♡

### features
- phase m — public landing, docs site, stats, changelog, setup wizard, marketing assets (`836dced`)
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

