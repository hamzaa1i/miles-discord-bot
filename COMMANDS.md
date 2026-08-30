# Aurelia — Complete Command Reference

Every slash command, prefix command, natural-language @mention intent, and
reaction/button interaction in Aurelia — the Veloura community bot.

> **Quick facts** · 39 cogs · 147 slash commands (144 cog commands + 3 hybrid
> in `main.py`) · AI powered by Groq (`qwen/qwen3.6-27b` for chat,
> `openai/gpt-oss-20b` for fast tasks, `openai/gpt-oss-120b` for reasoning)
> · data in Supabase PostgreSQL with JSON-file fallback.

**Talk to her three ways:**
1. **Slash commands** — `/help`, `/level`, `/mod ban`, …
2. **@mention natural language** — `@Aurelia mute @user for 10m`,
   `@Aurelia snipe`, or just `@Aurelia hey what's up`
3. **Custom prefix** (if set) — `a!roll`, `a!welcome show`, `a!any question`

## Table of Contents

- [AI & Chat](#ai--chat)
- [Moderation](#moderation)
- [Community & Engagement](#community--engagement)
- [Roles & Permissions](#roles--permissions)
- [Voice](#voice)
- [Utility](#utility)
- [Server Info](#server-info)
- [Settings & Configuration](#settings--configuration)
- [Fun & Games](#fun--games)
- [Owner Commands](#owner-commands)
- [@Mention Natural-Language Intents](#mention-natural-language-intents)
- [Prefix Commands](#prefix-commands)
- [Reactions & Buttons](#reactions--buttons)
- [Template Variables Reference](#template-variables-reference)
- [Permission Matrix](#permission-matrix)
- [Cooldown Summary](#cooldown-summary)

---

## AI & Chat

Conversational AI features. Chat history is persistent per user per channel
(last 20 messages, stored in Supabase `conversation_memory`), and Aurelia
remembers durable facts about you automatically.

### /aurelia
Talk to Aurelia or run commands naturally (slash form of @mention chat).
- **Permissions:** any user
- **Cooldown:** 1 use / 8s per user
- **Parameters:**
  - `message` (string, required): what you want to say or do
- **Example usage:**
  ```
  /aurelia message: what's the vibe of this server?
  /aurelia message: snipe
  ```
- **Example response:** a natural reply, or the snipe embed if an intent was
  detected. Shows "Aurelia is thinking…" while the AI works.

### /forget
Clear Aurelia's memory of your conversation history in this server.
- **Permissions:** any user
- **Cooldown:** 1 use / 10s per user
- **Example usage:** `/forget`
- **Example response:** *ephemeral* — "i've forgotten our conversation
  history in this server."

### /memory
What Aurelia remembers about you (long-term AI memory facts).
- **Permissions:** any user
- **Subcommands:**

**/memory show**
- Show the durable facts Aurelia has learned about you (or someone else).
- Parameters: `user` (member, optional) — someone else's memory (**staff
  only**: Manage Messages / Manage Guild / server owner)
- Example: `/memory show user:@diva`
- Example response: an embed listing remembered facts ("diva is from
  karachi", "diva likes nightcore") or "i don't remember anything yet ♡".

**/memory clear**
- Erase everything Aurelia remembers about you.
- Example: `/memory clear` → "your memory has been cleared. ✦"

### /summarize
Summarize text in 3-5 bullet points.
- **Permissions:** any user · **Cooldown:** 1 / 15s per user
- Parameters: `text` (string, required)
- Example: `/summarize text:<paste a long paragraph>`
- Example response: "• point one • point two • point three…"

### /translate
Translate text to a target language.
- **Permissions:** any user · **Cooldown:** 1 / 15s per user
- Parameters: `language` (string, required) · `text` (string, required)
- Example: `/translate language:spanish text:good morning everyone`
- Example response: "buenos días a todos"

### /explain
Explain a topic like you're 12.
- **Permissions:** any user · **Cooldown:** 1 / 15s per user
- Parameters: `topic` (string, required)
- Example: `/explain topic:how vaccines work`
- Example response: a short, simple explanation.

### /advice
Blunt, sarcastic-but-useful advice.
- **Permissions:** any user · **Cooldown:** 1 / 15s per user
- Parameters: `situation` (string, required)
- Example: `/advice situation:i keep procrastinating`
- Example response: direct advice with attitude.

### /roast_server
AI roasts the current server (all in good fun).
- **Permissions:** any user · **Cooldown:** 1 / 10s per channel
- Example: `/roast_server`
- Example response: a playful roast based on server name/channels.

### /code
Generate a code snippet.
- **Permissions:** any user · **Cooldown:** 1 / 30s per user
- Parameters: `language` (string, required) · `description` (string, required)
- Example: `/code language:python description:read a file line by line`
- Example response: a code block with the snippet.

### /recap
Get an AI recap of what happened in a channel.
- **Permissions:** any user · **Cooldown:** 1 / 60s per channel
- Parameters:
  - `channel` (text channel, optional) — defaults to the current channel
  - `hours` (integer, optional) — how many hours back (1-24, default 2)
- Example: `/recap hours:6`
- Example response: "✦ recap — the last 6h: users argued about anime,
  someone hit level 12, 3 memes were posted…"

### /adminrole
Set the role that can use AI moderation (via @mentions).
- **Permissions:** server owner or bot owner only
- **Cooldown:** 1 / 5s per user
- Parameters: `role` (role, required)
- Example: `/adminrole role:@mods`
- Example response: "admin role set to @mods. members with this role can
  use AI moderation."

### /adminrole_remove
Remove the AI moderation role.
- **Permissions:** server owner or bot owner only · **Cooldown:** 1 / 5s per user
- Example: `/adminrole_remove` → "admin role removed."

### @Aurelia chat (mention)
Mention her anywhere to chat — this is the main AI interface. See the
[@Mention Natural-Language Intents](#mention-natural-language-intents)
section for everything she understands (moderation, utility commands, and
plain conversation).
- **Rate limits (built in):** 4s between messages per user; per-hour tiered
  caps — bot owner unlimited, admin role 60, moderators 50, everyone else 25;
  300 messages/hour per server.
- **Example:** `@Aurelia hey, what do you think about the new update?`

---

## Moderation

Classic moderation plus AI-powered automod. All actions are logged to the
mod-log channel and the `warnings` table.

### /mod — group
Moderation commands.

**/mod kick**
- Kick a member. Kicks are DM'd and logged.
- Permissions: **Kick Members** · Parameters: `member` (required),
  `reason` (string, optional, default "No reason")
- Example: `/mod kick member:@user reason:spam` → "kicked **user**\nreason: spam"

**/mod ban**
- Ban a member. Permissions: **Ban Members** · `member` (required),
  `reason` (optional)
- Example: `/mod ban member:@user reason:raiding`

**/mod unban**
- Unban a user by ID. Permissions: **Ban Members** · `user_id` (string,
  required)
- Example: `/mod unban user_id:123456789012345678`

**/mod timeout**
- Timeout (mute) a member. Permissions: **Moderate Members** ·
  `member` (required), `duration` (string, required — e.g. `10m`, `1h`,
  `1d`), `reason` (optional)
- Example: `/mod timeout member:@user duration:1h reason:being rowdy`

**/mod mute**
- Server-mute a user in voice channels. Permissions: **Mute Members** ·
  `user` (member, required), `reason` (optional)
- Example: `/mod mute user:@user reason:earrape`

**/mod unmute**
- Remove timeout and/or voice mute from a user. Permissions: any
  (effectively mod) · `user` (member, required)
- Example: `/mod unmute user:@user`

**/mod warnings**
- Add, list, or clear warnings for a user. Permissions: **Moderate
  Members** · `action` (choice: `add` / `list` / `clear`, required),
  `user` (member, required), `reason` (string, optional — for add)
- Example: `/mod warnings action:add user:@user reason:toxicity`
- Example response: "⚠️ warned **user**. case #7. reason: toxicity"
- Cross-reference: warns also stack toward automatic threshold actions
  (see /mod config) and can be managed via `@Aurelia warn` /
  `!warnings` (prefix).

**/mod purge**
- Delete the last N messages in this channel. Permissions: **Manage
  Messages** · `amount` (integer, required)
- Example: `/mod purge amount:25` → "🧹 deleted 25 messages"

**/mod nuke**
- Clone and delete the channel (with a Confirm/Cancel button safety).
  Permissions: **Manage Channels**
- Example: `/mod nuke` → confirm view → "💥 channel nuked"

**/mod slowmode**
- Set channel slowmode (0 disables). Permissions: **Manage Channels** ·
  `seconds` (integer, optional)
- Example: `/mod slowmode seconds:5` → "slowmode set to 5s."

**/mod lock / /mod unlock**
- Lock/unlock the current channel for @everyone. Permissions: **Manage
  Channels** · `reason` (optional, lock only)
- Example: `/mod lock reason:raid cleanup` → "🔒 channel locked."

**/mod tempban**
- Temporarily ban a member (auto-unbans after the duration). Permissions:
  **Ban Members** · `member` (required), `duration` (choice: `1h`, `6h`,
  `12h`, `1d`, `3d`, `7d`, required), `reason` (optional)
- Example: `/mod tempban member:@user duration:1d reason:repeated spam`

**/mod antispam**
- Toggle the antispam automod (7 messages / 10s → timeout, escalating:
  60s → 10m → 1h). Permissions: **Moderate Members** · `enabled`
  (choice: on/off)
- Example: `/mod antispam enabled:on`

**/mod antilink**
- Toggle antilink (blocks non-Discord links) for a channel. Permissions:
  **Manage Messages** · `enabled` (choice: on/off), `channel` (optional)
- Example: `/mod antilink enabled:on`

**/mod config**
- Configure warn thresholds (automatic action after N warnings).
  Permissions: **Moderate Members** · `setting` (choice:
  `warn_threshold_count` / `warn_threshold_action`), `value` (string,
  required — a number for count; `timeout_1h` / `timeout_24h` / `kick` /
  `ban` for action)
- Example: `/mod config setting:warn_threshold_count value:3`
- Example response: "warn threshold set: after **3** warnings →
  timeout_1h."

### /aiautomod — group
AI-powered automod: every message is classified (severity 1-5) by Groq;
severity ≥ configured minimum triggers escalation + a mod alert.

**/aiautomod toggle** — enable/disable. Permissions: **Manage Guild** ·
`state` (choice: on/off). Example: `/aiautomod toggle state:on`
**/aiautomod channel** — set the mod-alert channel. Permissions: **Manage
Guild** · `channel` (required)
**/aiautomod timeout** — set the severity-5 escalation length. Permissions:
**Manage Guild** · `duration` (string — `30m`, `1h`, `2h`, `1d`, or plain
number = minutes)
**/aiautomod status** — show current configuration. Permissions: **Manage
Guild**

---

## Community & Engagement

Leveling, welcomes, birthdays, giveaways, polls, starboard, confessions,
invite tracking, onboarding, custom commands, bump reminders, and
proactive presence.

### /level
Show your level card (or someone else's) — level, rank, XP, progress bar.
- **Permissions:** any user
- Parameters: `user` (member, optional)
- Example: `/level user:@diva`
- Example response: an embed card — "level **12** · rank #3 / 87 ·
  4,210 xp · `▰▰▰▰▱▱…` 62.5%"

> XP: 15-25 per message (× configured multiplier), 60s cooldown per user.
> Level curve: `5·L² + 50·L + 100` XP per level.

### /leaderboard
Top 10 users in this server. · **Permissions:** any user
- Example: `/leaderboard` → "🥇 diva — level 12 · 4,210 xp …"

### /rewards
Show configured level-up role rewards. · **Permissions:** any user
- Example: `/rewards` → "level **5** — @Early Bird · level **10** — @Regular"

### /leveling — group *(Manage Guild)*
Leveling system configuration.

**/leveling config** — one command, eight settings:
- `setting` (choice, required): `channel` / `reward` / `reward_remove` /
  `rate` / `level_message` / `level_channel` / `toggle` / `show`
- `value` (string, optional): depends on setting — level number, multiplier
  (e.g. `1.5`), message template, mode, or `on`/`off`
- `role` (role, optional — for `reward`), `channel` (text channel,
  optional — for `channel`)

Examples:
```
/leveling config setting:channel channel:#level-ups
/leveling config setting:reward value:10 role:@Regular
/leveling config setting:rate value:2.0
/leveling config setting:level_message value:gg {user.name}, you hit lvl {level} ♡
/leveling config setting:level_channel value:dm
/leveling config setting:toggle value:off
/leveling config setting:show
```
Example response: "level-up message set. preview:
> gg diva, you hit lvl 5 ♡"

Level-up channel modes: `active` (where they leveled up — default),
`configured` (the set channel), `dm` (direct message), `none` (disabled).
See [Template Variables](#template-variables-reference) for all tags.

### /daily 🆕 *New in Phase 2*
Claim your daily XP reward and grow your streak — once per user per UTC day,
per server (streaks are per-server).
- **Permissions:** any user · **Cooldown:** 1 / 5s per user (the real limit is
  one claim per UTC day)
- Example: `/daily`
- Example response: an embed — "꒰ა ♡ ໒꒱ daily reward" — "you claimed
  **+80 XP** today ✦ / current streak: **3 day(s)** 🔥" · footer "highest
  streak: 12 days · total claimed: 45"
- **XP math:** 50 base + 10 per streak day (bonus capped at +150, so a
  regular claim maxes at 200 XP), credited to your `/level` XP.
  Milestone bonuses on top: 7-day **+100**, 30-day **+500**, 100-day
  **+2000** bonus XP with a special embed callout.
- Claim twice in one day → *ephemeral*: "you already claimed your daily
  reward today ♡ come back tomorrow at midnight utc" (shows your streak).
  Miss a day and the streak resets to 1.

### /qotd — group *(Manage Guild)* 🆕 *New in Phase 2*
Automated daily conversation starter. Aurelia posts one question per UTC day
to the configured channel after the configured hour, from the server's own
queue first, then from a built-in pool of 40 soft aesthetic questions.

**/qotd config** — set the channel (this enables QOTD). Parameters:
- `channel` (required) · `hour_utc` (int 0-23, optional, default 14) ·
  `auto_thread` (bool, optional, default on — opens a public thread per
  question)
- Example: `/qotd config channel:#chill hour_utc:15 auto_thread:True`

**/qotd toggle** — on/off. `enabled` (optional — flips when omitted)
**/qotd add** — queue a custom question. `question` (required, max 500).
Example: `/qotd add question:what's your comfort movie?`
**/qotd list** — upcoming queued questions (*ephemeral*)
**/qotd post** — force-post the next question immediately
**/qotd show** — current settings card

Posting engine: a 15-minute background loop posts at most one question per
UTC day per server, once `current_hour_utc >= hour_utc`. Posted questions
from the queue are marked used and never repeat.

### /anniversary — group *(Manage Guild)* 🆕 *New in Phase 2*
Passive join-anniversary celebrations.
**/anniversary config** — set the celebration channel and enable/disable.
`channel` (required) · `enabled` (required, on/off)
Example: `/anniversary config channel:#general enabled:True`
**/anniversary show** — current settings

Daily background loop: members hitting **1 month** (30d), **6 months**
(182d), **1 year** (365d), **2 years** (730d), or **every full year from 3
years** up get a "꒰ა 🍰 ໒꒱ happy server anniversary!" card with their
avatar and join date. One scan per UTC day (restart-safe via
`last_run_date`).

### /birthday — group
**/birthday set** — set your birthday (month + day). Parameters: `month`
(int 1-12), `day` (int). Example: `/birthday set month:3 day:14`
**/birthday upcoming** — the next 5 birthdays in this server.
**/birthday channel** — set the announcement channel. **Manage Guild** ·
`channel` (required). Aurelia posts a birthday embed on the day.

### /giveaway — group *(Manage Guild for start/end/reroll)*
Giveaways with entry requirements (role, account age, level).

**/giveaway start** — start one. Parameters:
- `prize` (string, required) — what they're winning
- `duration` (string, required) — `30m`, `2h`, `1d`, `3d12h`…
- `winners` (int 1-20, optional, default 1)
- `channel` (optional, default here) · `required_role` (optional) ·
  `min_account_days` (optional) · `min_level` (optional)

Example:
```
/giveaway start prize:discord nitro duration:3d winners:2 min_level:5
```
Example response: an embed with an **enter ✦** button; entries re-verify
requirements when picking winners.

**/giveaway end** — end early. `giveaway_id` (required, from the footer)
**/giveaway reroll** — pick a new winner for an ended giveaway.
`giveaway_id` (required)
**/giveaway list** — list running giveaways in this server (any user).

### /poll — group
**/poll create** — create a poll with up to 4 options. Parameters:
`question`, `option1`, `option2` (required); `option3`, `option4`,
`duration` (e.g. `10m`, `1h`) optional. Options get 🇦🇧🇨🇩 reactions.
Example: `/poll create question:movie night? option1:friday option2:saturday duration:1h`
**/poll end** — end early and show tallies. `message_id` (required)

### /starboard — group *(Manage Guild)*
Feature the server's best messages.
**/starboard channel** — set the starboard channel (this enables it).
`channel` (required)
**/starboard threshold** — stars needed (1-50, default 5). `stars` (required)
**/starboard emoji** — the counting emoji (default ⭐; unicode or custom).
`emoji` (required)
**/starboard toggle** — on/off · `state` (choice)
**/starboard status** — show the configuration.
Reaction usage: react to any message with ⭐ (or your custom emoji); at
threshold it's reposted to the starboard channel once.

### /confess — group
Anonymous confessions.
**/confess setup** — set the confession channel. **Manage Guild** ·
`channel` (required)
**/confess text** — submit an anonymous confession (goes to the configured
channel with an incrementing number). **Cooldown:** 1 / 5 min per user ·
`text` (string, required)

### /invites — group
Invite tracking (who invited whom, via invite-code diffing).
**/invites show** — your (or someone's) invite count. `user` (optional)
Example: `/invites show user:@diva` → "**diva** has invited **12** members
to **veloura**. ✩"
**/invites set** — set a user's count manually. **Manage Guild** · `user`
(required), `count` (int, required)
**/invite_leaderboard** — top 10 inviters. Example: `/invite_leaderboard`

### /welcome — group *(Manage Guild)*
Welcome & goodbye configuration — 13 settings through one command.

**/welcome config** — configure any setting. Parameters:
- `setting` (choice, required): `channel` · `message` · `embed_mode` ·
  `color` · `image` · `title` · `thumbnail` · `footer` · `dm` · `toggle` ·
  `goodbye_channel` · `goodbye_message` · `goodbye_toggle`
- `value` (string, optional): text / mode / hex color / URL / `on`/`off`
  (`reset` clears style settings)
- `channel` (optional — for the channel settings)

Examples:
```
/welcome config setting:channel channel:#welcome
/welcome config setting:message value:welcome {user} to {server} ♡
/welcome config setting:color value:#FFB6C1
/welcome config setting:embed_mode value:hybrid
/welcome config setting:dm value:hey {user.name}, welcome to {server}!
/welcome config setting:toggle value:on
/welcome config setting:goodbye_message value:see you {user.name} ✦
```
Example response: "✅ welcome message updated" (+ preview).

**/welcome test** — preview welcome / goodbye / DM. `type` (choice, default
welcome). Example: `/welcome test type:dm`
**/welcome show** — rich overview card of the current config.
**/welcome tags** — every variable you can use in welcome messages.
**/welcome reset** — reset ALL welcome settings to defaults (with a confirm
button).

Related: **/toggledms** — toggle whether Aurelia may DM you (any user).

### /onboarding — group *(Manage Guild)*
DM onboarding with role buttons for new members.
**/onboarding toggle** — `state` (on/off)
**/onboarding addrole** — `role` (required), `label` (required, button
text), `emoji` (optional)
**/onboarding removerole** — `role` (required)
**/onboarding message** — DM intro text · `text` (tags: `{user}`
`{user.name}` `{server}` `{membercount}`)
**/onboarding test** — DM yourself a preview of the panel.

### /custom — group
Custom trigger commands.
**/custom add** — **Manage Guild** · `trigger` (required, e.g. `hi veloura`)
· `response` (required, tags: `{user}` `{user.name}` `{server}`
`{membercount}`). Example: `/custom add trigger:hi veloura response:hey {user} ♡`
**/custom remove** — **Manage Guild** · `trigger` (required)
**/custom list** — list this server's custom commands (any user).

### /bump — group
**/bump remind** — manually schedule a 2-hour Disboard bump reminder in
this channel. **Manage Guild**. Automatic reminders also trigger whenever
someone bumps (Disboard "bump done" message detected); the bot pings
@here after 2 hours.

### /proactive — group *(Manage Guild)*
Let Aurelia speak on her own.
**/proactive toggle** — `state` (on/off). When enabled she drops a natural
line into rotation channels roughly once every 1-2 hours (min 3h apart).
**/proactive channel** — add a channel to the rotation. `channel` (required)
**/proactive status** — show settings.

---

## Roles & Permissions

### /autorole — group
**/autorole set** — assign a role to all new members on join. **Manage
Roles** · `role` (required). Example: `/autorole set role:@newbie`
**/autorole remove** — disable autorole. **Manage Roles**
**/autorole show** — show the configured autorole (any user).

### /selfroles — group
**/selfroles setup** — post a self-role button panel. **Manage Roles** ·
`category` (choice: `notifications` / `pronouns` / `age` / `dms` /
`location`), `role1` (required), `role2`-`role4` (optional).
Example: `/selfroles setup category:pronouns role1:@she/her role2:@he/him role3:@they/them`
→ a button panel; clicking toggles the role.

### /rules — group
**/rules set** — set the server rules (newlines = list items). **Manage
Guild** · `text` (required)
**/rules show** — show the rules (any user)
**/rules agree** — post a rules panel with an "I Agree" button (any user
can post it; agreement grants the configured role)
**/rules agree_role** — set the role granted on agreement. **Manage
Guild** · `role` (required)

---

## Voice

### /voice
Manage your current voice channel. **Manage Channels** · `action` (choice,
required): `lock` / `unlock` / `hide` / `unhide` / `limit` / `rename` ·
`value` (string, optional — new name for rename, member limit for limit).
Example: `/voice action:rename value:anime night ♡`

Voice moderation lives in /mod: **/mod mute** (server voice-mute) and
**/mod unmute**. Voice join/leave events feed the logging system.

---

## Utility

### /math
Evaluate a math expression safely (whitelisted AST — no code execution).
- **Permissions:** any user
- Parameters: `expression` (string, required)
- Example: `/math expression:sqrt(144) + 2**10` → "🧮 Result: `1030.0`"

### /snipe
Show a recently deleted message in this channel.
- **Permissions:** any user
- Parameters: `index` (integer, optional — 1 = most recent, up to 10)
- Example: `/snipe index:2`
- Example response: an embed with the deleted content, author, deletion
  time, attachments. Snipes expire after 5 minutes; showing one does NOT
  remove it. If nothing is cached: "no recently deleted messages here
  (snipes expire after 5 minutes)."

### /reminders
List your active reminders (*ephemeral*) — recurring ones carry a 🔁 badge.
· **Permissions:** any user
- Example: `/reminders` → "your reminders: `1.` drink water - in 9m · 🔁 daily"
- Create reminders conversationally: `@Aurelia remind me in 10 minutes to
  drink water`, or with `/remind create`.

### /remind — group 🆕 *New in Phase 2*
Create and manage reminders, including recurring ones.

**/remind create** — set a reminder. Parameters:
- `what` (string, required — what to remind you about)
- `when` (string, required — duration: `30m`, `2h`, `1d`, `1h30m`, `45`
  (bare numbers = minutes); 10 seconds … 365 days)
- `repeat` (choice, optional, default none): `none` / `daily` / `weekly` /
  `monthly`
- Example: `/remind create what:take your vitamins when:12h repeat:daily`
- Example response: "got it ♡ i'll remind you in 12h and repeating
  **daily** 🔁: *take your vitamins*"

**/remind list** — your active reminders with their ids (*ephemeral*)
**/remind delete** — cancel one. `id` (int, required — the `#id` from
`/remind list`, or its position in the list)

When a recurring reminder fires (DM, or channel ping if DMs are closed)
it re-arms itself: daily +24h, weekly +7d, monthly +30d. One-shot reminders
are removed after firing. Missed occurrences during downtime are skipped
silently (no DM bursts).

### /time — group 🆕 *New in Phase 2*
Timezone utilities (stdlib `zoneinfo` — no external APIs).

**/time for** — see someone's current local time and how far ahead/behind
you they are. `user` (member, required)
- Example: `/time for user:@diva` → "diva's local time is **09:45 PM**
  (Asia/Karachi) · 5h ahead of you"
- If they haven't set a timezone: "@diva hasn't set their timezone yet.
  they can set it with /time set timezone:America/New_York ♡" (*ephemeral*)

**/time convert** — convert a clock time between zones. `time` (required,
e.g. `8:00 PM` or `14:30`) · `from_tz` (required) · `to_tz` (required)
- Accepted zone names: abbreviations (`EST`, `PST`, `CST`, `GMT`, `UTC`,
  `CET`, `JST`, `AEST`, `BST`…), offsets (`UTC+3`, `GMT-5`), and full IANA
  names (`America/New_York`, `Europe/London`, `Asia/Tokyo`)
- Example: `/time convert time:8:00 PM from_tz:EST to_tz:GMT` →
  "**8:00 PM EST (UTC−5)** → **1:00 AM GMT** (next day)"

**/time set** — set YOUR timezone (shared with `/profile_set timezone`,
used by `/time for`). `timezone` (required)
- Example: `/time set timezone:America/New_York` → "✅ your timezone has
  been set to **America/New_York** (current time: 03:45 PM) ♡"

### /weather
Get current weather for a city (OpenWeather-style embed).
- **Permissions:** any user
- Parameters: `city` (string, required)
- Example: `/weather city:tokyo`
- Also available via mention: `@Aurelia weather in tokyo`

### /afk
Set your AFK status. Aurelia replies with your reason + duration whenever
someone mentions you while you're AFK.
- **Permissions:** any user
- Parameters: `reason` (string, optional, default "AFK")
- Example: `/afk reason:studying for exams`

### /profile
View a user's profile (bio, pronouns, timezone).
- **Permissions:** any user · Parameters: `user` (member, optional)
- Example: `/profile user:@diva`

### /profile_set — group
**/profile_set bio** — set your bio (max 200 chars). `text` (required)
**/profile_set pronouns** — set your pronouns. `text` (required)
**/profile_set timezone** — set your timezone (e.g. `UTC-5 / EST`,
`Europe/London`). `text` (required)

### /prefix — group
Custom text-prefix management (also available as prefix text commands).
**/prefix set** — set a custom prefix (max 10 chars). **Manage Guild** ·
`prefix` (required). Example: `/prefix set prefix:a!`
**/prefix remove** — remove the custom prefix. **Manage Guild**
**/prefix list** — show the current prefix (any user).

### /help
Show all commands (interactive menu). · **Permissions:** any user
- Parameters: `command` (string, optional — filter by name)
- Example: `/help command:leveling`

### /ping · /uptime · /botinfo *(hybrid — also work as `!ping` etc.)*
**/ping** — websocket latency with a color-coded embed. Example: "🏓 Pong —
Websocket latency: **87ms**"
**/uptime** — "Running for **2d 14h 3m**"
**/botinfo** — *(Manage Server)* sleek system-status card: Overview
(servers · members · latency · uptime), Cache & Storage (cache entries +
hit rate · Supabase health), Engine (Python · discord.py · Groq).

---

## Server Info

### /serverinfo
Server information embed (members, channels, roles, owner, creation date,
ID) with toggleable detail buttons.
- **Permissions:** any user · Example: `/serverinfo`

### /whois
Complete info about a user — join/created dates, roles, top role, booster
status, ID.
- **Permissions:** any user · Parameters: `user` (member, optional)
- Example: `/whois user:@diva`

### /avatar
Show a user's avatar (full-size).
- **Permissions:** any user · Parameters: `user` (member, optional)
- Example: `/avatar user:@diva`

---

## Settings & Configuration

### /log — group *(Manage Channels)*
Log event configuration — message deletes/edits, member join/leave,
ban/unban, role & nickname changes, voice join/leave.
**/log setup** — set the log channel. `channel` (required)
**/log disable** — disable logging
**/log show** — show current settings
**/log toggle** — toggle a specific event on/off. `event` (choice:
message_delete / message_edit / member_join / member_leave / member_ban /
member_unban / role_change / nickname_change / voice_join / voice_leave)

### /status — group
Bot status management.
**/status set** — set a custom pinned status (**bot owner only**).
`status_type` (choice: listening / playing / watching / competing), `text`
(dynamic tags: `{users}`, `{servers}`)
**/status reset** — clear custom status, resume auto-rotation (**owner**)
**/status current** — show current status (anyone)
**/status info** — how Discord displays bot status (anyone)

When no custom status is set, Aurelia rotates through a Veloura-themed
status list automatically.

---

## Fun & Games

### /roll
Roll a dice. · **Permissions:** any user
- Parameters: `sides` (integer, optional, default 6, 2-1000)
- Example: `/roll sides:20` → "🎲 rolled a **17** (d20)"

### /flip
Flip a coin. · Example: `/flip` → "🪙 heads"

### /joke
Get a random joke (curated list). · Example: `/joke`

### /meme
Random meme from r/dankmemes (embed with title, image, author, upvotes).
· Example: `/meme`

### /vibe 🆕 *New in Phase 1*
Read the channel's recent conversation and describe the current vibe in one
soft, aesthetic sentence.
- **Permissions:** any user · **Cooldown:** 1 / 5 min per channel
- Example: `/vibe`
- Example response: an embed — "꒰ა ♡ ໒꒱ channel vibe" — "sleepy lo-fi
  study session 🌙" · footer "read 18 messages · #study-room"
- Needs at least 5 recent human messages, otherwise: "not enough activity
  to read the vibe yet ♡"

### /pick 🆕 *New in Phase 1*
Let Aurelia choose between 2-10 comma-separated options (with a soft reason).
- **Permissions:** any user · **Cooldown:** 1 / 10s per user
- Parameters: `options` (string, required — comma-separated, 2-10 items)
- Example: `/pick options:pizza, sushi, tacos`
- Example response: an embed titled "꒰ა ♡ ໒꒱ sushi" — "the stars say
  ocean food tonight ✦" · footer "chose from 3 options"

### /askstars 🆕 *New in Phase 1*
Ask the celestial oracle a question — a short poetic, starry answer.
- **Permissions:** any user · **Cooldown:** 1 / 60s per user
- Parameters: `question` (string, required, max 500 chars)
- Example: `/askstars question:will this week get better?`
- Example response: an embed — "✦ the stars whisper ✦" — "*the moon
  wanes, but your season rises soon ✦*"

### /fortune 🆕 *New in Phase 1*
Your daily fortune from Aurelia 🥠 — one per user per UTC day (persisted in
the `fortune_history` table; asking again before midnight UTC shows the
same one *ephemerally*).
- **Permissions:** any user · **Cooldown:** 1 / 10s per user
- Example: `/fortune`
- Example response: an embed — "🥠 your fortune" — "*today, someone will
  notice your quiet magic ♡*" · footer "for diva · valid until midnight utc"

---

## Owner Commands

Only the bot owner (the `OWNER_ID` environment variable) can use these.

### /owner — group
**/owner status** — bot statistics dashboard (servers, users, memory,
latency, command counts)
**/owner reload** — reload a cog by name. `cog_name` (required, e.g. `ai_chat`)
**/owner sync** — force re-sync slash commands to all guilds
**/owner shutdown** — shut the bot down gracefully
**/owner dm** — DM any user by ID. `user_id` (required), `message` (required)
**/owner announce** — send an announcement to one channel or all servers.
`message` (required), `channel` (optional), `embed` (bool, optional, default yes)
**/owner createrole** — create a role. `name` (required), `color` (hex,
optional), `admin` (bool, optional)
**/owner giverole / /owner removerole** — give/remove a role.
`role` (required), `member` (optional, defaults to you)
**/owner servers** — list every server the bot is in
**/owner say** — send a message as the bot. `message` (required),
`channel` (optional)
**/owner personality** — set this server's personality note (feeds the AI
system prompt as context). `note` (required, e.g. "Valorant gaming server")
**/owner personality_clear** — clear the personality note
**/owner leave** — make the bot leave a server by ID (with confirm
button). `guild_id` (required)

---

## @Mention Natural-Language Intents

Mention Aurelia and write naturally. Parsing is tiered for speed and
reliability:

1. **Deterministic fast-path** — regex-only, 0 ms, no API cost. Handles
   moderation commands (with @mention targets) and utility commands.
2. **Casual-chat shortcut** — obviously conversational messages skip
   parsing and go straight to the chat model.
3. **LLM intent parser** — everything ambiguous is classified by Groq
   (`openai/gpt-oss-20b`) into a JSON intent.

Anything not matching an intent is answered conversationally. Moderation
intents **require an @mention of the target** and respect permissions
(bot owner / server owner / configured admin role / matching Discord
permission). Destructive actions (ban / kick / timeout / warn / purge)
show a **Confirm / Cancel** button first.

### Moderation intents
| Say | What happens |
|---|---|
| `@Aurelia mute @user for 10m` / `timeout @user 5m` | Timeout (confirm view) — durations like `90s`, `10m`, `2h`, `1d` |
| `@Aurelia unmute @user` | Remove timeout |
| `@Aurelia ban @user for spamming` | Ban (confirm view) |
| `@Aurelia kick @user` | Kick (confirm view) |
| `@Aurelia warn @user for spam` | Warn + DM + case number |
| `@Aurelia show warnings for @user` | List warnings (`warn_list`) |
| `@Aurelia clear warnings for @user` | Clear warnings (`warn_clear`, admin) |
| `@Aurelia purge 10` / `delete 50 messages` | Bulk delete (confirm view) |
| `@Aurelia delete this message` *(as a reply)* | Deletes the replied-to message |
| `@Aurelia slowmode 5` | Set slowmode (`0` disables) |
| `@Aurelia lock` / `unlock` | Lock/unlock the channel |
| `@Aurelia nuke` *(bot owner)* | Clone + delete the channel |
| `@Aurelia hide` / `show` *(bot owner)* | Hide/show the channel for @everyone |
| `@Aurelia add role @user @role` *(bot owner)* | Give a role |
| `@Aurelia remove role @user @role` *(bot owner)* | Take a role |

### Utility intents
| Say | What happens |
|---|---|
| `@Aurelia snipe` / `snipe 3` | Show deleted message (same cache as /snipe) |
| `@Aurelia flip` | 🪙 heads/tails |
| `@Aurelia roll` / `roll 20` | 🎲 dice (d6-d1000) |
| `@Aurelia joke` | Random joke |
| `@Aurelia meme` | Random meme embed |
| `@Aurelia weather in tokyo` | Weather embed (also bare `weather`) |
| `@Aurelia whois @user` | Profile embed |
| `@Aurelia avatar @user` | Avatar embed |
| `@Aurelia serverinfo` | Server info embed |
| `@Aurelia remind me in 10 minutes to drink water` | Sets a reminder (DMs you) |
| `@Aurelia cancel reminders` | Lists / cancels your reminders |
| `@Aurelia` *(bare mention)* | Random greeting ("i'm here ♡", "listening ✧"…) |

Questions *about* moderation ("can you mute someone?") never trigger
actions — they're answered conversationally. Unmatched command-like words
(`fact`, `truth`, `dare`, `ping`…) also fall through to chat and get a
natural answer.

---

## Prefix Commands

Two prefix systems:

1. **Default Discord prefix `!`** — works out of the box for the hybrid
   commands: `!ping`, `!uptime`, `!botinfo`.
2. **Custom prefix** — set one per server with `/prefix set prefix:a!` (or
   `a!prefix set a!` once it exists). Everything below then works with your
   prefix. If no custom prefix is set, @mention is the way to talk.

| Prefix command | What it does |
|---|---|
| `a!help` | Quick command overview |
| `a!ping` | "pong. 87ms" |
| `a!uptime` | "uptime: 2d 14h 3m" |
| `a!botinfo` | Compact bot info |
| `a!weather tokyo` | Weather embed |
| `a!flip` · `a!roll` · `a!joke` · `a!fact` · `a!meme` · `a!truth` · `a!dare` | Fun quick-fire (routed through the intent system) |
| `a!prefix set a?` / `a!prefix remove` / `a!prefix list` | Manage the prefix itself (Manage Guild) |
| `a!welcome config <setting> <value>` | Same 13 settings as /welcome config (Manage Guild) |
| `a!welcome show` | Text overview of welcome config |
| `a!welcome test [welcome\|goodbye\|dm]` | Preview a message |
| `a!welcome message <text>` · `a!welcome channel #chan` | Welcome shortcuts |
| `a!goodbye message <text>` · `a!goodbye channel #chan` | Goodbye shortcuts |
| `a!warn @user <reason>` | Warn (via AI flow) |
| `a!warnings add @user [reason]` / `list @user` / `clear @user` | Warning management |
| `a!purge 25` | Bulk delete (Manage Messages) |
| `a!lock` / `a!unlock` | Channel lock toggle |
| `a!slowmode 5` | Slowmode |
| `a!ban @user` / `a!kick @user` | Routed to the AI confirm flow |
| *anything else* (`a!hey what's up`) | Falls through to AI chat |

---

## Reactions & Buttons

| Interaction | Where | What it does |
|---|---|---|
| ⭐ *(or custom emoji)* reaction | any message | Starboard: at the configured threshold the message is reposted to the starboard channel (once) |
| 🌸 / ♡ reaction | a newcomer's first message | Soft first-message welcome (members who joined within 14 days; silent when reactions aren't permitted) |
| 🇦 🇧 🇨 🇩 reactions | polls | Poll votes — counted by /poll end or expiry |
| 👍 / 👎 reactions | AI-created poll intent | Simple two-option poll |
| **enter ✦** button | giveaways | Toggle your entry (requirements re-checked at draw) |
| Role buttons | onboarding DM panel | New members pick their own roles |
| Role buttons | /selfroles panels | Toggle roles by category (pronouns, notifications…) |
| **I Agree** button | /rules agree panel | Grants the configured agreement role |
| **Confirm / Cancel** buttons | AI mod intents, /mod nuke, /owner leave, /welcome reset | Two-step confirmation for destructive actions |
| 🎉 reaction | welcome messages | Decorative greeting flourish |

---

## Template Variables Reference

All templates use safe `{tag}` substitution — unknown tags are left
as-is, and unbalanced braces never crash rendering.

### Welcome / goodbye / DM messages (`/welcome config`)
| Tag | Renders as |
|---|---|
| `{user}` | @mention (clickable) |
| `{user.name}` | display name |
| `{user.id}` | user ID |
| `{user.avatar}` | avatar URL |
| `{server}` | server name |
| `{server.id}` | server ID |
| `{server.icon}` | server icon URL |
| `{membercount}` | member count |

### Level-up messages (`/leveling config setting:level_message`)
| Tag | Renders as |
|---|---|
| `{user}` | @mention |
| `{user.name}` | display name |
| `{level}` | new level |
| `{next_level}` | level + 1 |
| `{xp}` | total XP (thousands-separated) |
| `{server}` | server name |
| `{membercount}` | member count |

Default: `🎉 {user} just reached level {level}! ✦`

### Custom commands (`/custom add`) & onboarding message
`{user}` · `{user.name}` · `{server}` · `{membercount}`

### Bot status (`/status set`)
`{users}` — total users Aurelia can see · `{servers}` — server count

---

## Permission Matrix

| Command group | Discord permission required |
|---|---|
| /mod kick · ban · unban · tempban | Kick Members / Ban Members |
| /mod timeout · mute · unmute · warnings · antispam · config | Moderate Members / Mute Members |
| /mod purge · antilink | Manage Messages |
| /mod nuke · slowmode · lock · unlock · /voice | Manage Channels |
| /aiautomod (all) · /leveling config · /giveaway start/end/reroll · /starboard (all) · /confess setup · /invites set · /welcome (all) · /onboarding (all) · /proactive (all) · /rules set/agree_role · /autorole set/remove · /selfroles setup · /birthday channel · /custom add/remove · /bump remind · /prefix set/remove · /qotd (all) · /anniversary (all) · /botinfo | Manage Guild (or the noted role/permission) |
| /log (all) | Manage Channels |
| /moderate via @mention (`@Aurelia ban …`) | matching mod permission, the /adminrole role, server owner, or bot owner |
| /memory show (other users) | staff (Manage Messages / Manage Guild / server owner) |
| /owner (all) · /status set/reset | bot owner only (OWNER_ID) |
| /owner personality · personality_clear | bot owner only |
| Everything else (chat, fun, profiles, leveling, utility…) | any user |

---

## Cooldown Summary

| Command | Cooldown |
|---|---|
| /daily 🆕 | 1 / 5s per user (one claim per UTC day) |
| /vibe 🆕 | 1 / 5 min · per channel |
| /askstars 🆕 | 1 / 60s · per user |
| /pick 🆕 | 1 / 10s · per user |
| /fortune 🆕 | 1 / 10s · per user |
| /confess text | 1 / 5 min · per user |
| /recap | 1 / 60s · per channel |
| /roast_server | 1 / 10s · per channel |
| /summarize · /translate · /explain · /advice | 1 / 15s · per user |
| /code | 1 / 30s · per user |
| /aurelia | 1 / 8s · per user |
| /forget | 1 / 10s · per user |
| /adminrole · /adminrole_remove | 1 / 5s · per user |
| @Aurelia chat | 4s between messages · tiered hourly caps (owner ∞ / admin 60 / mod 50 / user 25) · 300/h per server |

## Command Count Summary

| Category | Commands |
|---|---|
| Top-level tree entries | 63 (36 commands + 27 groups) — was 58 before Phase 2 |
| Hybrid commands (main.py) | 3 |
| Subcommands (all groups, incl. nested) | 108 |
| **Total invocable slash commands** | **147** (144 cog + 3 hybrid; 132 before Phase 2) |
| Prefix text commands | 25+ routes |
| Natural-language @mention intents | 30+ |
| New in Phase 1 | /vibe · /pick · /askstars · /fortune |
| New in Phase 2 | /daily · /qotd · /anniversary · /remind · /time |

Discord's hard limit is 100 **top-level** commands — Aurelia is at 63.

**Supabase migration (Phase 2):** run the `PHASE 2 (ENGAGEMENT CORE)` SQL
block at the top of `utils/db.py` — it adds `repeat_interval` to
`reminders` and creates `daily_streaks`, `qotd_settings`, `qotd_queue`, and
`anniversary_settings`. Until then, all five features fall back to local
JSON files automatically.



