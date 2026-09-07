# support server setup — a guide for volc ✦

this is a **manual, one-time setup** — discord servers can't be created
from code. follow this guide and every support link across the bot,
dashboard and site will light up automatically (they read the
`SUPPORT_SERVER_URL` env var).

expect it to take ~30 minutes.

---

## 1 · create the server

- in discord: **add a server → create my own → for a community**
- name it something like **"aurelia ✦ lounge"** or **"the veloura lounge"**
- upload the icon: `dashboard/marketing/aurelia-icon-transparent.png`
  (or `aurelia-logo-512.png`)
- banner: `dashboard/marketing/aurelia-banner-2000x1000.png`

## 2 · enable community features

**server settings → enable community** (get started):

- onboarding: on
- rules screening: optional (recommended off for a support server)
- this unlocks `#announcements`, `#server-guide`, discovery, and
  welcome screens

## 3 · channel layout

create these (or keep the community defaults and rename):

| channel | type | purpose |
|---|---|---|
| `#announcements` | announcement | release notes — mirror of the changelog |
| `#support` | text | "how do i…" threads — one thread per question |
| `#feedback` | text | feature requests + votes |
| `#showcase` | text | servers showing off their welcome cards / setups |
| `#bot-commands` | text | where members play with aurelia (test commands) |
| `#suggestions` | forum | long-form suggestions with upvote posts |
| `#changelog` | text | bot posts release updates (rss → webhook is fine) |

tips:

- set `#support` to **slowmode 10s** — it keeps thread spam down
- pin a "read first ✦" message in `#support` linking to
  `https://veloura-aurelia.vercel.app/docs/getting-started`
- make `#bot-commands` the **system channel** so join messages are
  contained

## 4 · roles

| role | color | who | notes |
|---|---|---|---|
| `@volc` | pink `#FFC0CB` | you | the badge of honor |
| `@staff` | lavender `#E6E6FA` | helpers | manage messages in support channels |
| `@tester` | navy | opt-in | early access to beta features |
| `@premium` | (future) | — | placeholder for phase 10 — do not create yet |

## 5 · add aurelia (fully configured)

invite her with the production invite link
(`https://veloura-aurelia.vercel.app` → **add to discord**), then in the
support server:

1. run `/setup` — enable welcome, qotd, leveling
2. point `#bot-commands` at itself for the fun stuff
3. set `/log setup #bot-commands` if you want visibility
4. add `/selfroles setup tester @tester` so members self-assign the
   tester role

## 6 · the permanent invite link

1. **server settings → invites**
2. create an invite with **never expires**, unlimited uses
3. enable **vanity url** if available: `discord.gg/aurelia`
4. set **server settings → invites → invite splash** to
   `aurelia-banner-1920x1080.png`

## 7 · wire the env vars (this is what turns the links on)

### on render (the bot)

```
SUPPORT_SERVER_URL=https://discord.gg/your-invite
```

this powers:

- the auto-DM to server owners when aurelia joins (quick-start links)
- the `/setup` wizard's "next steps" panel
- `/help` footer → "need help? support server: <link>"
- error handler messages → gentle fallback with the link

### on vercel (the dashboard)

```
NEXT_PUBLIC_SUPPORT_SERVER_URL=https://discord.gg/your-invite
```

this powers:

- "support" links in the site header + footer
- faq / docs / stats page support references
- the landing page social-proof section

> every support link gracefully hides when the var is unset — nothing
> breaks, the links simply appear on your next deploy.

## 8 · launch day checklist

- [ ] channels + roles created per sections 3-4
- [ ] aurelia invited, `/setup` run in the support server
- [ ] permanent invite created (vanity if possible)
- [ ] `SUPPORT_SERVER_URL` set on render, redeployed
- [ ] `NEXT_PUBLIC_SUPPORT_SERVER_URL` set on vercel, redeployed
- [ ] `#announcements` webhook → point it at `/changelog.rss`
      (e.g. with a free rss-to-webhook monitor)
- [ ] first post in `#announcements`: the v1.0.0 launch note
- [ ] pin `#server-guide` with the docs links:
      `https://veloura-aurelia.vercel.app/docs`
- [ ] optionally set the server's description to the short tagline from
      `dashboard/marketing/description-short.md`
