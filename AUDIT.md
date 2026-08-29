# Aurelia (miles-discord-bot) — Full Code Audit

**Repo:** `github.com/hamzaa1i/miles-discord-bot`
**Bot identity:** aurelia (community: Veloura; owner: volc, ID 698142490775257119)
**Audit date:** 2026-08-29
**Auditor scope:** every file in the repository, read line-by-line (71 files, ~19,600 lines). No code changes made.
**Stack:** discord.py 2.x (app_commands), Groq API (qwen3.6-27b / gpt-oss-20b / gpt-oss-120b), Supabase (sync client) + JSON fallback, Flask health server, Render free tier.

---

## 0. Executive Summary

The bot is in better shape than the handover notes imply — but three near-trivial P0 bugs are responsible for most of the visible breakage, and the Supabase layer has silently drifted from what the code expects in **7 places**, which quietly breaks or degrades several features while they *appear* to succeed.

**Headline numbers**

| Metric | Value |
|---|---|
| Files read (full audit) | 71 — 66 Python (19,508 lines) + 5 config/docs |
| Active cogs | 26 (9,750 lines) |
| Disabled cogs | 22 (`*_disabled.py`, 6,165 lines = **31.6% of all Python**) |
| Slash commands (invocable leaves) | **99** |
| Slash commands (top-level, what Discord's 100-limit counts) | **49 → 51 free slots** |
| Total findings | **77** — 15 broken features, 12 missing features, 9 code-quality, 9 database, 9 security, 7 performance, 16 UX |

**The four P0 fixes (each is hours of work, not days):**

1. **Warnings split-brain** (`cogs/moderation.py`) — `/mod warnings add` writes warnings to a legacy JSON file while `list` / `clear` / the auto-escalation threshold / the mod-log "Previous Offenses" count all read a *different* store (Supabase / `utils.db`). Result: **warnings never appear in the list, "clear" always finds nothing, and warn-threshold auto-actions can never fire.** The unified API already exists (`utils/db.py:519 add_warning`) and is simply never called. (B1)
2. **Dead prefix AI routing** (`cogs/prefix.py`) — all 7 call sites do `bot.get_cog("AiChat")` but the cog class is `AIChat` (capital C-h-a-t). Cog lookup is case-sensitive, so every lookup returns `None` and the entire Tier-2 custom-prefix AI path is dead. (B2)
3. **Intent-parser bypass for short commands** (`cogs/ai_chat.py:1372`) — `is_obvious_chat()` returns `True` for any message under 15 chars *before* checking for command keywords, so "ban @user", "kick him", "lock", "purge 10" are treated as small talk and answered conversationally instead of executed. (B3)
4. **Corrupted system prompt** (`cogs/ai_chat.py:220`) — the prompt opens with the byte-verified nonsense string `"CRITICAL: never output ildo, <thinking>, or any XML tags."` — "ildo" is a mangled remnant of what should name the 7-character qwen reasoning tag that `utils/ai_handler.py:159-180` strips. The anti-leak instruction is currently noise. (B4)

**Correcting a premise from the handover:** the repo's own `scripts/count_commands.py` reported "99/100 commands used" by counting every *subcommand* individually. Discord's 100-per-guild limit only counts **top-level** commands (groups count once; subcommands are free). The true count is **49 top-level → 51 free slots**. Past feature deletions done "to make room" (e.g., removing the `poll` intent) were based on a false constraint — nothing needs to be deleted for capacity reasons.

**Biggest structural risks (P1):**

- **Schema drift:** the code's column map (`utils/db.py:291 _TABLE_COLUMNS`) claims 11 tables; 5 have missing columns and 2 tables don't exist at all in Supabase. Because reads are Supabase-first and writes silently fall back to JSON on error, affected settings *report success but never persist* (confession counter, antispam toggle, leveling config, self-role panels, birthdays) — and JSON on Render's ephemeral disk dies on every redeploy. A ready-to-run SQL migration is included in §10. (D1/D2)
- **DB exposure:** the bot ships with the Supabase **anon key** (`.env.example:14`) while RLS is disabled and grants are wide open — anyone who obtains the project URL + anon key gets full read/write access to all 18 tables, including complete AI conversation history. (S6)
- **Confession privacy contradiction:** confess.py's docstring promises the submitter's `user_id` is stored for abuse investigation (it isn't), while `main.py:446` writes the full confession text **and author ID** to Render logs on every `/confess text`. Currently: anonymous to your mods, fully attributable to whoever has the logs. (S4)
- **Permission gaps:** `/poll end` (any member can end any poll), `/welcome test` + `/welcome show` (no permission checks), `/confess text` (no cooldown). (S1-S3)

**What's already healthy:** welcome.py's handover bugs (schema columns, `.format` crash) are fixed at HEAD; the AI moderation path *does* gate actions behind real Discord permissions (`ai_chat.py:489-516 check_mod_permission`); the `/owner` cog is correctly locked to `OWNER_ID` (`owner.py:91,459-461`); automod exempts bots/owner/mods (`automod.py:82`); `data/*.json` is gitignored and no user data is committed.

---

## 0.1 Severity Legend & Finding Index

| ID | Severity | One-liner |
|---|---|---|
| B1-B15 | Broken feature | B1 warnings store, B2 prefix routing, B3 intent bypass, B4 prompt corruption, B5 dead intents, B6 welcome perms, B7 birthdays, B8 confession counter, B9 antispam persist, B10 leveling/selfrole persist, B11 bump state, B12 dead economy, B13 dual autorole, B14 rebrand, B15 owner docstring/psutil |
| M1-M12 | Missing feature | action-history viewer, single-warn removal, appeals, scheduled messages, confession tools, per-channel AI toggle, migrations, tests, backup, sticky roles, streaming, analytics |
| C1-C9 | Code quality | dual data layers, duplication, `dir()` hack, dead code, stale comments, copy-paste 429 blocks, requirements bloat, flawed counter script, silent excepts |
| D1-D9 | Database | 5 column mismatches, 2 missing tables, silent-fallback semantics, sync client on event loop, N+1 deletes, split-brain stores, ephemeral JSON, anon-key exposure, no migrations |
| S1-S9 | Security | poll/welcome/confess gaps, confession attribution, unused checks.py, anon key + no RLS, input trust in AI mod path (mitigated), key hygiene, logging hygiene |
| P1-P7 | Performance | sync DB calls, N+1 deletes, double AI calls, per-action extra reads, polling loops, unbounded dicts, per-message DB round-trips |
| U1-U16 | UX | mostly user-visible symptoms of the above + rebrand strings |

---

## 0.2 Scope & Method

- Every file under the repository root was read in full (manifest in §0.3). Large files (`ai_chat.py`, `db.py`, `moderation.py`, `welcome.py`, `logging_system.py`, `server_stats.py`) were read in multiple offset windows.
- Claims in this document were verified at **byte level** where display artifacts were suspected: the reasoning-tag regexes in `utils/ai_handler.py` and the prompt line `cogs/ai_chat.py:220` were dumped as decimal codepoints and octal UTF-8 bytes to distinguish genuine file corruption from terminal rendering artifacts. Line 220 genuinely contains the ASCII string `ildo`.
- The command inventory (§8) was regenerated with an AST-based scanner (`scripts/count_commands_audit.py` outside the repo) that classifies decorators (`@app_commands.command`, `@<group>.command`, `@commands.hybrid_command`, GroupCog classes, class/module-level `app_commands.Group` instances) — it does not rely on the repo's own flawed counter.
- Cross-checks against Discord platform behavior (the 100-guild-command limit counting top-level commands only) were made against the official discord.py / Discord developer documentation.
- No code was modified. All `file:line` references are to the working tree at audit time.

## 0.3 File Manifest (every file read, with line counts)

**Root & scripts (9 files, 815 lines)**

| File | Lines | Notes |
|---|---|---|
| `main.py` | 642 | Flask `/`, `/health` (46-57), `/stats` (119); hybrid `/ping` `/uptime` `/botinfo`; on_interaction logger (418-449); still "cyn"-branded |
| `keep_alive.py` | 36 | metrics store only; effectively dead code (main.py duplicates it) |
| `README.md` | 56 | outdated — "cyn" identity, stale command list |
| `requirements.txt` | 11 | unused: pyfiglet, PyNaCl, qrcode, yt-dlp; **missing: psutil** |
| `.env.example` | 17 | documents the **anon** Supabase key |
| `runtime.txt` | 0 | empty |
| `.gitignore` | 27 | correctly ignores `.env`, `data/*.json`, `*.db`, `*.log` |
| `scripts/count_commands.py` | 69 | flawed methodology (counts subcommands individually) |

**utils/ (14 files, 2,846 lines)**

| File | Lines | Status |
|---|---|---|
| `db.py` | 1,338 | active — Supabase + JSON fallback, `_TABLE_COLUMNS` (291-336), settings (356-470), warnings (493-577), conversation memory (783-849), birthdays (1104-1124) |
| `ai_handler.py` | 461 | active — Groq wrapper, `pick_model`, tag stripping (148-187) |
| `intent_parser.py` | 184 | active — prompt (9-68), `KNOWN_INTENTS` (70-78) |
| `database.py` | 49 | legacy JSON `Database` class — still imported by 8 active cogs |
| `checks.py` | 99 | `is_owner/is_mod/is_admin` — **zero importers** |
| `rank_card.py` | 394 | used by leveling (image gen) |
| `veloura_embeds.py` | 78 | active |
| `paginator.py` | 60 | unused by active cogs |
| `professional_embeds.py` | 49 | unused by active cogs |
| `embeds.py` | 41 | unused by active cogs |
| `helpers.py` | 36 | unused by active cogs |
| `image_generator.py` | 30 | unused by active cogs |
| `constants.py` | 15 | active |
| `__init__.py` | 12 | — |

**cogs/ — active (26 files, 9,750 lines)**

| File | Lines | File | Lines |
|---|---|---|---|
| `ai_chat.py` | 1,971 | `polls.py` | 276 |
| `moderation.py` | 1,009 | `automod.py` | 267 |
| `welcome.py` | 669 | `self_roles.py` | 249 |
| `owner.py` | 581 | `voice.py` | 226 |
| `prefix.py` | 471 | `utility.py` | 206 |
| `logging_system.py` | 459 | `ai_features.py` | 198 |
| `server_stats.py` | 352 | `birthdays.py` | 192 |
| `help.py` | 345 | `rules.py` | 182 |
| `invites.py` | 327 | `bump_reminder.py` | 179 |
| `leveling.py` | 315 | `confess.py` | 174 |
| `bot_status.py` | 287 | `profiles.py` | 156 |
| `fun.py` | 285 | `weather.py` | 126 |
| `afk.py` | 105 | `autorole.py` | 143 |

**cogs/ — disabled (`*_disabled.py`, 22 files, 6,165 lines)** — full verdicts in §9

`server_logs` 674 · `games` 750 · `automod_disabled` 573 · `economy` 488 · `giveaways` 389 · `marriage` 346 · `leveling_disabled` 283 · `modmail` 277 · `birthdays_disabled` 261 · `reaction_roles` 231 · `tickets` 227 · `trivia` 221 · `counting` 211 · `starboard` 208 · `auto_responder` 182 · `reputation` 160 · `suggestions` 153 · `productivity` 149 · `confess_disabled` 108 · `truth_dare` 137 · `custom_embeds` 87 · `music` 50

**Totals:** 66 Python files / 19,508 lines + 101 lines of config/docs. Active code ≈ 13,343 lines; disabled code 6,165 lines (31.6%).


---

## 1. Broken Features (B1-B15)

### B1 — Warnings system is split-brained: adds go to one store, everything else reads another — **P0**

**Severity: critical.** The single most damaging bug in the repo. Moderators believe they are warning users; the record is written to a legacy JSON file that nothing else ever reads.

**Evidence — `cogs/moderation.py`:**

```python
:17   from utils.database import Database
:18   from utils.db import (get_guild_setting, set_guild_setting, get_warnings, ...)
:38   self.db = Database('data/moderation.json')          # ← legacy JSON store

:192  def add_warning(self, guild_id, user_id, reason, moderator):
:202      data['warnings'][uid].append({...})
:207      self.db.set(str(guild_id), data)                # ← WRITE goes to legacy JSON

:367  self.add_warning(...)                               # /mod warnings add → legacy
:379  from utils.db import get_warnings                   # /mod warnings list → utils.db
:380  warnings = get_warnings(...)                        # ← READ comes from Supabase/warnings.json
:407  clear_warnings(interaction.guild_id, user.id)       # /mod warnings clear → utils.db
```

Four different consumers read the *other* store:

| Consumer | Location | Reads | Consequence |
|---|---|---|---|
| `/mod warnings list` | moderation.py:379-380 | `utils.db.get_warnings` | always empty → "no warnings for X" |
| `/mod warnings clear` | moderation.py:401-407 | `utils.db` | always "no warnings found" |
| Warn-threshold auto-action | moderation.py:145 (`_maybe_apply_threshold`) | `utils.db.get_warnings` | count stays 0 → **timeout/kick/ban escalation can never trigger** |
| Mod-log "Previous Offenses" field | moderation.py:99 (`_send_mod_log`) | `utils.db.get_warnings` | always shows 0 |

**Fix direction:** route the add path through the *existing* unified API — `utils/db.py:519 add_warning(guild_id, user_id, warning: dict)` (it already handles Supabase + JSON fallback and is currently called by nobody). One-time migration: read `data/moderation.json`, push existing `warnings` into `utils.db.add_warning`, then delete `self.db`, `add_warning()`, and `log_action()`'s warnings half from the cog. Keep `log_action` only if you also build the missing history viewer (M1).

---

### B2 — Entire Tier-2 prefix AI routing is dead: `get_cog("AiChat")` vs class `AIChat` — **P0**

**Evidence:**

```python
cogs/prefix.py:107   ai_cog = self.bot.get_cog("AiChat")
cogs/prefix.py:233   ai_cog = self.bot.get_cog("AiChat")   # (also 239, 245, 256, 300, 369)
cogs/ai_chat.py:84   class AIChat(commands.Cog):           # ← actual class name
```

discord.py cog lookup is **case-sensitive**. Every one of the 7 call sites in prefix.py gets `None`, so the custom-prefix conversation path (`cyn.hello`-style, i.e. the whole point of the prefix cog's Tier-2 routing) silently falls through to generic help text instead of the AI.

**Fix direction:** rename the lookup string to `"AIChat"` in all 7 sites (or add a module-level `AI_COG_NAME = "AIChat"` constant). Add a startup assertion in main.py that `bot.get_cog("AIChat")` is not None so class renames can never silently break routing again.

---

### B3 — `is_obvious_chat()` short-circuits command detection for short messages — **P0**

**Evidence — `cogs/ai_chat.py:1372-1408`:**

```python
:1377  # Very short messages are almost always just chat
:1378  if len(content_lower) < 15:
:1379      return True                        # ← fires FIRST
...
:1382  command_keywords = ["ban", "kick", "warn", ...]
:1390  for keyword in command_keywords:
:1391      if keyword in content_lower:
:1392          return False                   # ← never reached for short messages
```

Any command message under 15 characters — `ban @x`, `kick him`, `lock`, `purge 10`, `mute @a` — is classified as "obvious chat" and **skips the intent parser entirely** (call sites: ai_chat.py:1552 for @mentions and :1849 for prefix commands). The AI then answers "ban @x" conversationally ("i can't ban anyone, hehe") instead of executing or explaining. Ironically the *comment* above the function says its purpose is to cut API calls for pure conversation — but the ordering makes it swallow precisely the messages that are commands.

**Fix direction:** move the keyword scan above the length heuristic; only apply the `< 15` shortcut when no command keyword is present.

---

### B4 — Corrupted system prompt: "never output ildo" — **P0**

**Evidence (byte-verified, `cogs/ai_chat.py:220`):**

```python
base = (
    "CRITICAL: never output ildo, <thinking>, or any XML tags. "
```

Codepoint dump of the line confirms the file literally contains `i-l-d-o` (ords 105, 108, 100, 111) — this is genuine file corruption, not a rendering artifact. Context makes the intent obvious: `utils/ai_handler.py:154-187` strips three kinds of reasoning leakage from model output —

```python
:160  re.sub(r'<think>.*?</think>', '', content, ...)   # qwen reasoning tag (7-char open, 8-char close)
:166  re.sub(r'<thinking>.*?</thinking>', '', content, ...)
:176  re.sub(r'<think>.*', '', content, ...)          # unclosed tag variant
```

— and the system prompt was clearly meant to forbid the model from emitting the first tag, but the tag name was mangled (likely during a past find/replace) into the meaningless token "ildo". The instruction is currently noise; leakage is prevented only by post-hoc stripping, and only for the patterns the regexes anticipate.

**Fix direction:** rewrite line 220 to name the actual tags the models emit, e.g. `"CRITICAL: never output <think>...</think> blocks, <thinking> tags, or any XML tags. never explain your reasoning."` Keep the stripper as defense-in-depth.

---

### B5 — 8 advertised intents have no executor; 1 executor has no intent — **P1**

**Evidence — `utils/intent_parser.py:70-78`** declares `KNOWN_INTENTS` including `nick`, `fact`, `truth`, `dare`, `ping`, `botinfo`, `uptime`, `whois`. The intent dispatch chain in **`cogs/ai_chat.py:526-1252`** implements: chat, ban, kick, mute/timeout, unmute, purge, warn, warn_clear, warn_list, delete_message, remind, remind_cancel, serverinfo, avatar, poll, joke, meme, weather, flip, roll, slowmode, lock, unlock, hide, show, nuke, role_add, role_remove — **no branch exists for those 8 intents.** When the parser (correctly, per its own prompt lines 34, 48-59) returns e.g. `ping` or `whois`, the chain falls through and the user gets a chatty AI non-answer instead of latency or a profile.

Inverse case: `poll` **was removed** from the parser (intent_parser.py:66-67: "NOTE: 'poll' intent has been removed") but its executor still exists at **ai_chat.py:1084-1094** — dead code that can never fire.

**Fix direction:** cheapest correct fix is to delete `nick/fact/truth/dare/ping/botinfo/uptime/whois` from `KNOWN_INTENTS` and from the parser prompt; or wire executors (ping/uptime/botinfo/whois already exist as commands in main.py / server_stats.py — delegate like the `joke` intent does via `get_cog('Fun')` at ai_chat.py:1097). Delete the dead poll executor.

---

### B6 — `/welcome test` and `/welcome show` have no permission checks — **P1**

**Evidence — `cogs/welcome.py`:** `/welcome config` is protected (`:441 @app_commands.checks.has_permissions(manage_guild=True)`), but:

```python
:576  @welcome.command(name="test", description="Preview welcome, goodbye, or DM message")
       # no permission decorator
:619  @welcome.command(name="show", description="Show the current welcome & goodbye configuration")
       # no permission decorator
```

Any member can spam test welcome/goodbye/DM previews into any channel the bot can see, and read the full welcome configuration.

**Fix direction:** add `@app_commands.checks.has_permissions(manage_guild=True)` to both (matches the `config` sibling and `/log setup`).

---

### B7 — Birthdays can never persist to Supabase — **P1**

**Evidence — `utils/db.py:1104-1124`:**

```python
:1108  existing = _supabase.table("birthdays").select("id").eq(...)
```

The probe selects an `id` column that does not exist in the live `birthdays` table → PostgREST error (PGRST204) → exception → the whole `set_birthday` falls back to `data/birthdays.json`. Additionally the `birthday_settings` table (expected by `_TABLE_COLUMNS` db.py:324-326) does not exist at all → PGRST205 → `db.py:387-394` permanently marks it missing and routes `/birthday channel` to JSON too. On Render's **ephemeral filesystem**, both files are wiped on every deploy/restart: users set birthdays, bot restarts, birthdays vanish.

**Fix direction:** probe with a column that exists (e.g. `select("guild_id")` or `select("*")`); add the missing table (§10 SQL); ideally key birthdays on `(guild_id, user_id)` with an upsert instead of probe-then-update.

---

### B8 — Confession counter never persists on Supabase: every confession is "#1" — **P1**

**Evidence:** `cogs/confess.py:125-130` increments `config["count"]` and `:163 save_config` → `set_guild_setting(guild, "confess_settings", config)`. The code's own column map expects `count` (`_TABLE_COLUMNS` db.py:318-320) but the live table lacks that column → the sanitized write still includes `count` → PGRST204 → silent JSON fallback (db.py:411-470). Reads, however, are Supabase-first (db.py:374-380) and return the row **without** `count` → `get_config` (confess.py:38-44) re-defaults it to 0. Net effect: the footer `Confession #N` (confess.py:138) is `#1` essentially always once Supabase is up. Numbering is the only way to *reference* a confession ("delete confession #7") — so this also blocks any moderation tooling (M5).

**Fix direction:** `ALTER TABLE confess_settings ADD COLUMN count` (§10 SQL) — one line fixes numbering, and the counter then survives restarts.

---

### B9 — `/mod antispam` toggle reports success but never takes effect — **P1**

**Evidence:** the toggle writes `antispam_enabled` into `mod_settings` via `set_guild_setting`; `_TABLE_COLUMNS` (db.py:306-311) believes the column exists, the live table doesn't → same silent-fallback semantics as B8. Automod reads its settings from Supabase (`get_guild_setting`) → `antispam_enabled` is never present → the feature stays at its default regardless of what the command reported. (The antilink settings in the same table share the risk if their columns are absent.)

**Fix direction:** add the column (§10 SQL). Until then, the command should verify persistence after write and warn on fallback instead of showing a success embed.

---

### B10 — Leveling config and self-role panels don't persist on Supabase — **P2**

**Evidence:** `leveling_settings` expects `enabled/channel_id/rate/rewards` and `self_role_panels` expects `panels` (`_TABLE_COLUMNS` db.py:327-335); the live tables lack them → identical silent-fallback failure as B8/B9. `/leveling config` changes and `/selfroles setup` panel definitions appear to save, then revert / vanish after restarts (they survive only in ephemeral JSON).

**Fix direction:** §10 SQL migration; same "verify after write" hardening as B9.

---

### B11 — Bump reminder state has no table at all — **P2**

**Evidence:** `_TABLE_COLUMNS` expects `bump_reminder_state(guild_id, channel_id, last_bump_message_id, last_bump_at)` (db.py:330-332); table doesn't exist → PGRST205 → permanent JSON fallback (db.py:387-394) → "time since last bump" tracking resets on every Render restart, making the 2-hour reminder cycle unreliable.

**Fix direction:** `CREATE TABLE` (§10 SQL).

---

### B12 — Welcome cog pays into a dead economy and advertises deleted commands — **P2**

**Evidence — `cogs/welcome.py`:**

```python
:55   self.economy_db = Database('data/economy.json')     # economy cog is DISABLED
:318  reward = config.get('welcome_reward', 500)
:320  new_data = self.get_economy_data(member.id)         # credits join reward
:332  f"use `/daily`, `/work`, `/fish`, and more to earn coins.\n\n"   # ← commands don't exist
:360-365  welcomer_reward ...                             # credits welcomer reward
```

Rewards are booked into `data/economy.json`, which no active cog reads; new members are DM'd an advertisement for `/daily`, `/work`, `/fish` — commands that were removed when the economy cog was disabled. Users will try them and get "command not found".

**Fix direction:** gate the economy block on `bot.get_cog("Economy") is not None` (pattern already used at games_disabled.py:24) or strip it until economy is revived; remove the dead-command advertisement from the DM template regardless.

---

### B13 — Two competing autorole systems — **P2**

**Evidence:** welcome.py implements its own autorole (`:70 autorole_id` default, `:266-274` assigns on join, configured via `/welcome config`) while the dedicated `cogs/autorole.py` exposes `/autorole set|remove|show` backed by a *different* settings table (`server_settings.autorole_id`, db.py:315-317 vs `welcome_settings.autorole_id`, db.py:296). Whichever `on_member_join` listener runs first assigns a role; the two configs can point at different roles, and admins can't tell which command is authoritative.

**Fix direction:** pick one (recommend the dedicated cog), delete the other's column + assignment code, and add a startup log line when both are set.

---

### B14 — Rebrand cyn → aurelia is incomplete in ~60 user/staff-visible places — **P2**

**Evidence (grep `cyn` case-insensitive, verified):**

| Surface | Locations |
|---|---|
| **User-visible commands** | `/botinfo` embed title+footer "cyn — built by volc" (main.py:564, 575); `/forget` description "Clear cyn's memory" (ai_chat.py:1759); `/owner personality` "personality note for cyn" (owner.py:452); owner announcement footers (owner.py:259, 297) |
| **Prefix help panel** | "@cyn commands… talk to cyn" (prefix.py:308-313, 361, 405, 413, 420, 447, 465) |
| **Presence** | "@cyn" activity, "being cyn" (bot_status.py:30, 33), footer :282 |
| **Mod surfaces** | "cyn automod" footer + timeout reason string in Discord audit logs (automod.py:121, 180); "cyn logs" footers ×11 (logging_system.py:132-420) |
| **Web** | Landing page `<title>cyn</title>` / "cyn is online ✅" (main.py:49, 51) |
| **Internal (low priority)** | logger names `cyn.*` across 12 files (main.py:31, db.py:219, intent_parser.py:147, ai_handler.py:39, ai_chat.py:15, …) |
| **Docs** | README.md (whole file) |

**Fix direction:** mechanical sed pass for strings + a decision on logger names (renaming loggers is safe; keep `'aurelia'`). Note the display-name rules from the handover (lowercase, she/her) apply to generated copy, not just identifiers.

---

### B15 — `/owner eval` is advertised but doesn't exist; psutil missing from requirements — **P2**

**Evidence:** owner.py's module docstring advertises an `/owner eval` command; the actual cog registers 14 subcommands (status, reload, sync, shutdown, dm, announce, createrole, giverole, removerole, servers, say, personality, personality_clear, leave — verified by AST scan) — no `eval`. Separately, `owner.py:106` imports `psutil` for memory stats with a graceful fallback (`:113 "psutil not installed"`), but **psutil is absent from requirements.txt** → on every clean Render deploy, `/owner status` silently reports degraded memory info.

**Fix direction:** update the docstring; add `psutil` to requirements.txt (or drop the feature).


---

## 2. Missing Features (M1-M12)

Ordered by operational impact. "Verified absent" means grep + full-file read found no implementation in active code.

| ID | Missing feature | Evidence of absence | Impact |
|---|---|---|---|
| M1 | **Moderation action-history viewer.** `log_action()` dutifully appends every kick/ban/warn to `data/moderation.json` `actions` (moderation.py:176-190, capped at 100) — but no command ever reads it back. | mod group has 16 subcommands; none display history | Staff can't answer "what happened in this channel last night?" without raw file access |
| M2 | **Single-warning removal / warning expiry.** `/mod warnings` choices are exactly add/list/clear (moderation.py:352-356). There is no "remove warning #3" and no auto-decay. | choices list verified | One-off warnings follow a user forever; only remedy is clearing all |
| M3 | **Appeals / modmail / tickets.** `modmail_disabled.py` (277 lines) and `tickets_disabled.py` (227) both exist, both disabled, no active equivalent. | disabled-cog manifest §9 | No sanctioned channel for users to contest warnings/bans |
| M4 | **Scheduled / recurring messages.** Only timers are per-user reminders (utility.py) and bump_reminder's disforge-bump cycle. | no scheduler found in active cogs | Common community need (event pings, daily topics) unmet |
| M5 | **Confession moderation tooling.** confess.py docstring promises submitter `user_id` retention for abuse investigation (:7-9) — the code stores only `channel_id` + `count` (:29). No delete-confession, no blacklist, no mod lookup. And since B8 breaks numbering, there isn't even a stable handle to reference. | confess.py read in full | Toxic confessions are unremovable-by-design; promise to mods unfulfilled |
| M6 | **Per-channel AI toggle.** No admin command to disable @mention AI in a specific channel. The only related machinery is *internal* silence detection (ai_chat.py:1572-1583, adds context when a channel is quiet > 60 min) — not a control. | grep for per-channel/channel_toggle/ai_enabled: no hits | Channels that want no AI chatter (announcements) can't opt out |
| M7 | **Schema migration tooling.** No alembic, no `migrations/` dir, no SQL in repo — `_TABLE_COLUMNS` is a hand-maintained duplicate of the live schema (db.py:291-336) and has drifted in 7 places (D1/D2). | repo tree | Every schema change risks another silent-fallback regression |
| M8 | **Tests & CI.** Zero test files; no lint config; no GitHub Action. | repo tree | Every fix above ships blind; regressions (like B2's rename) recur silently |
| M9 | **Backup / export of guild data.** No `/backup`, no export of warnings/settings/memory; JSON fallbacks live on an ephemeral disk with no snapshotting. | grep backup/export: no hits | A bad deploy can irreversibly lose warnings + welcome configs |
| M10 | **Sticky roles on rejoin.** Leaving and rejoining drops all roles except whatever autorole assigns (welcome.py:266-274 / autorole.py). Nothing restores previous roles. | welcome/autorole read in full | Raid-prone communities and returning members lose earned roles |
| M11 | **Streaming / progressive AI responses.** All AI answers are single-shot sends; long generations show only a typing indicator (ai_chat.py:1606 `async with message.channel.typing()`). | ai_chat read | Feels slow for long answers; no early feedback |
| M12 | **Server analytics.** logging_system records events to a channel but nothing aggregates: no join/leave trends, no message-activity stats, no growth view. `/serverinfo` is a point-in-time snapshot only. | server_stats.py read | Staff fly blind on community health |

---

## 3. Code Quality Issues (C1-C9)

### C1 — Two parallel data layers, both live — **structural**

`utils/db.py` (1,338 lines, Supabase + JSON) and `utils/database.py` (49 lines, raw JSON `Database` class) coexist. **8 active cogs** import the legacy class: polls.py:19, moderation.py:17, logging_system.py:34, ai_chat.py:13, afk.py:4, welcome.py:39, autorole.py:20, server_stats.py:5 (plus 19 disabled cogs). Consequences: data invisible to the other layer (this is the *root cause* of B1), two persistence semantics to reason about, and JSON-only data that never reaches Supabase. Consolidation direction: port the 8 cogs to `utils/db.py` helpers, demote `utils/database.py` to the disabled-cog archive.

### C2 — ~100-line duplication between `on_message` and `handle_prefix_command`

`cogs/ai_chat.py` maintains two near-identical pipelines for @mentions (:1410+) and custom-prefix messages (:1785+): mention-stripping, permission resolution, is_obvious_chat, intent dispatch, model selection, memory handling, typing/reply plumbing. B3's call sites (:1552 and :1849) had to be fixed twice-over; the silence-detection FIX block (:1572-1596) exists in only one of them. Direction: extract a shared `_handle_conversation(message, content, via)` and keep the two entrypoints thin.

### C3 — `dir()` used as a defined-check — `ai_chat.py:1599`

```python
:1599  if 'chosen_model' not in dir():
:1600      from utils.ai_handler import pick_model
:1601      chosen_model = pick_model(content, intent)
```

`dir()` with no args returns local-scope names; this "works" but is fragile and obscure — a rename or a refactor that assigns `chosen_model` unconditionally breaks routing silently (and it already depends on an exception-swallowing `try/except` at :1595-1596). Direction: initialize `chosen_model = None` and use `if chosen_model is None:`.

### C4 — Dead code inventory (~5,000+ lines of it)

| Dead artifact | Lines | Why dead |
|---|---|---|
| `utils/checks.py` | 99 | `is_owner/is_mod/is_admin` — zero importers (grep-verified; only match is its own docstring:4) |
| `utils/paginator.py`, `professional_embeds.py`, `embeds.py`, `helpers.py`, `image_generator.py` | 216 | only referenced by disabled cogs or nothing |
| `keep_alive.py` | 36 | metrics store; main.py:60+ reads it but its "keep-alive" purpose is dead (Render + uptime monitor) |
| poll executor | 11 | ai_chat.py:1084-1094 — intent removed from parser (intent_parser.py:66-67) |
| `self.conversation_history` | — | ai_chat.py:91, comment still says "used by /chat and /cyn" — both commands were renamed to `/aurelia` (:1682) |
| 22 `*_disabled.py` cogs | 6,165 | 31.6% of the codebase ships disabled; 7 of them are superseded by active twins (§9) |

### C5 — Stale / corrupted comments and prompts

ai_chat.py:220 "never output ildo" (B4); ai_chat.py:91 stale comment; owner.py docstring advertising `/owner eval` (B15); README.md describing the old cyn identity and stale commands; intent_parser.py:66-67 documents a poll removal that ai_chat.py:1084-1094 never caught up with. Comments that lie are worse than no comments — several of these directly misled past debugging.

### C6 — Copy-pasted HTTP 429 handling blocks in moderation.py

The same `except discord.HTTPException: if e.status == 429: ...` block (moderation.py:424-429 and repeats) is pasted across many commands with slightly drifting wording. Direction: one `_handle_http_error(interaction, e)` helper.

### C7 — requirements.txt doesn't match reality

Unused by any active code: `pyfiglet`, `qrcode`, `yt-dlp`, `PyNaCl` (voice extra — discord.py[voice] pulls PyNaCl itself, but the voice feature is a 226-line stub with no playback). Missing: `psutil` (owner.py:106). Cost: slower cold installs on Render free tier + a degraded `/owner status`.

### C8 — `scripts/count_commands.py` measures the wrong thing

It counts every subcommand as an individual command against Discord's limit → reported "99/100" → drove past deletions. Reality (AST-verified, §8): **49 top-level of 100**. Direction: delete or fix the script; keep the corrected counter in CI so the number is always known.

### C9 — Broad `except Exception: pass` swallows failures

confess.py alone has five bare/broad passes (:71, :93, :106, :118, :148, :159) around critical UX paths; welcome.py and ai_chat.py follow the same pattern; db.py's `_supabase_error_logged` (db.py:228) logs each distinct failure **once** and then goes silent forever. Combined with the JSON fallbacks, the bot can run for weeks in a half-degraded state with no operational signal. Direction: a `metrics.degraded_features` counter surfaced on `/health` and `/stats`, and narrow the passes to expected exceptions.


---

## 4. Database Issues (D1-D9)

### D1 — Five column mismatches between `_TABLE_COLUMNS` and the live Supabase schema — **P1**

`utils/db.py:291-336` declares the columns the code believes exist. Against the live schema, five tables mismatch:

| Table | Code expects (db.py) | Live schema | User-visible symptom |
|---|---|---|---|
| `confess_settings` | `count` (:318-320) | column missing | every confession numbered "#1" (B8) |
| `mod_settings` | `antispam_enabled` (+ `antilink_channels`) (:306-311) | missing | antispam toggle no-ops (B9) |
| `leveling_settings` | `enabled, channel_id, rate, rewards` (:327-329) | missing | leveling config reverts (B10) |
| `self_role_panels` | `panels` (:333-335) | missing | self-role panels lost on restart (B10) |
| `birthdays` | `id` (probed at :1108) | missing | birthdays never reach Supabase (B7) |

**Why this fails silently:** `set_guild_setting` sanitizes the payload against the *code's* map (:445 `_sanitize_columns`), so the offending column is still included → PostgREST rejects with PGRST204 → the write silently degrades to JSON (the function's own docstring, db.py:411-427, describes exactly this trap) → but `get_guild_setting` remains **Supabase-first** (:374-380) and returns the row *without* the column → the setting never round-trips. The command embed said "✅ set". Nothing was set.

### D2 — Two expected tables don't exist at all — **P1**

`birthday_settings` (db.py:324-326) and `bump_reminder_state` (db.py:330-332). First access returns PGRST205 → db.py:387-394 permanently marks the table missing and routes all reads/writes to JSON → on Render's ephemeral disk, both features lose all state on every deploy (B7, B11). The PGRST205 short-circuit (:370-372, :436-440) is good log hygiene, but it also makes the missing table invisible after the first hour of runtime.

### D3 — Silent-fallback semantics are a footgun by design

The architecture (Supabase-first reads + best-effort JSON writes + log-once error dedup) converts every schema/network problem into *eventually-invisible data loss*, not errors. Until D1/D2 are fixed, any new settings key must be accompanied by a column, or it will silently not persist. Direction: after the migration, add a startup `init_db()` schema check that compares `_TABLE_COLUMNS` against `information_schema.columns` and logs loudly on drift; make `set_guild_setting` surface fallback to the caller so commands can warn ("saved locally only — database unavailable").

### D4 — Synchronous Supabase client on the async event loop — **P1**

`db.py:244-245 create_client(url, key)` is the sync `supabase-py` client; every call in the file is blocking REST. These run inline inside `on_message`, intent handling, AI memory writes, reminder polling, automod checks — i.e., the hottest paths in the bot. Each blocking call stalls the entire gateway (heartbeats included) for the round-trip time. On free-tier Supabase cold starts (hundreds of ms), users perceive the bot "typing then freezing"; under Discord-side timeouts it contributes to reconnects. Direction: wrap calls in `asyncio.to_thread(...)` as a low-risk first step (no API change), or move hot paths (memory writes) to a background writer queue.

### D5 — N+1 delete loop on every AI message — **P1**

`save_conversation_message` (db.py:814-849): after **each** insert it SELECTs all ids for the guild+user+channel ordered desc (:834-838), then deletes the overflow rows **one REST call per row** (:840-842). Worst case per user message: 1 insert + 1 select + N deletes ≈ 20+ blocking HTTP round-trips. Direction: single delete with `.in_("id", ids_to_delete)`, or a periodic trimmer task, or a Postgres trigger.

### D6 — The same data concept lives in two stores (warnings) — see B1 for the full anatomy.

### D7 — JSON fallback data lives on an ephemeral disk

Every "fallback" write targets `data/*.json` on the Render instance filesystem, which is wiped on each deploy/restart. Combined with D1/D2, at least seven features currently persist *only* to that disk. This is not hypothetical: it's the mechanism by which birthdays, bump state, leveling config, self-role panels, and confession counters reset.

### D8 — Database security posture (see S6)

Anon key + RLS disabled + wide grants = the persistence layer trusts anyone with two strings. Full detail in §5.

### D9 — No schema management

No migrations, no versioning, and `_TABLE_COLUMNS` is a hand-maintained mirror that has already drifted (D1/D2). Any future "add a setting" change has a high chance of recreating this entire failure class. Direction: even a minimal `migrations/001..00N.sql` + a `schema_version` table + the D3 startup check beats the status quo.

---

## 5. Security Issues (S1-S9)

### S1 — `/poll end` has no permission check — **P1**

`polls.py` contains **zero** permission decorators (grep for `has_permissions`/`default_permissions`: no matches). `/poll end` (:255) lets any member force-end any poll, discarding votes mid-flight. Direction: restrict to the poll's author OR members with `manage_messages`.

### S2 — `/welcome test` / `/welcome show` unauthenticated — **P1** (see B6)

Spammable channel noise (test previews) + config disclosure. Fix is one decorator each.

### S3 — `/confess text` has no cooldown and no content gate — **P1**

`confess.py:82-170`: no `app_commands.checks.cooldown`, no rate limit, no length floor, and no content filter before the bot re-posts the text (:140-141 `channel.send(embed=...)`). Because the confession is posted **by the bot**, Discord server AutoMod rules that apply to member messages do not intercept it — the bot launders arbitrary text into your announcement-grade channel at whatever pace a member chooses. Direction: `@app_commands.checks.cooldown(1, 300.0, key=lambda i: (i.guild_id, i.user.id))` + an optional AI toxicity pass using the existing Groq client.

### S4 — Confession anonymity is a contradiction — **P1**

Two opposite problems at once:

1. **Promised traceability is absent.** confess.py:7-9 docstring: "the user_id is only stored internally in case mods need to investigate abuse" — `get_config`/`save_config` store only `channel_id` + `count` (:29, :42-43). Mods cannot investigate abuse.
2. **Unintended traceability is present.** main.py:418-446 `on_interaction` logs every slash invocation at INFO with full option values: `[SLASH] guild | #channel | Name (id) → /confess text=<full confession>`. Render retains these logs. So confessions are anonymous to your moderation team but fully attributable (author + content) to anyone with dashboard access.

Direction: pick a model and implement it honestly — either (a) store submitter id in a mods-only table + build delete/blacklist commands (M5), or (b) go truly anonymous: exclude `confess` from option-logging in main.py and never store the id. Document the choice in the /confess help text.

### S5 — Permission machinery exists but is unused (`utils/checks.py`)

`is_owner/is_mod/is_admin` (checks.py, 99 lines) have zero importers. S1/S2/B6 are exactly the class of bug these decorators exist to prevent. The handover's per-guild "admin role" concept is only honored in the AI path (`check_mod_permission`, ai_chat.py:489-516) — the slash commands themselves never consult a configured admin role. Direction: either adopt checks.py (parameterized with the mod/admin role ids from `mod_settings`) or delete it; don't keep unreviewed auth code around as a decoy.

### S6 — Supabase anon key + RLS disabled + wide grants — **P1**

`.env.example:13-14` documents `SUPABASE_URL` + `SUPABASE_KEY=your_supabase_anon_key` as the bot's credentials, and per the handover the project has RLS disabled with anon grants on all 18 tables. Impact: the pair (project URL, anon key) — both commonly pasted into support tickets, screenshots, and GitHub issues — grants **full read/write** to every table: complete AI conversation history (`conversation_memory`), warnings, confessions config, welcome DM templates, profiles. That's a doxxing + tampering surface, not a hypothetical. Direction (in order): ① create a dedicated Postgres role for the bot with only the tables/columns it needs; ② enable RLS with policies keyed to that role; ③ rotate the anon key if it has ever been shared; ④ keep the anon key out of any client-shipped code. Minimum viable: `REVOKE ALL ON ALL TABLES FROM anon;` + grant the bot's role only what db.py touches.

### S7 — AI moderation input trust (mitigated, but worth knowing)

The intent parser's JSON output feeds `user_id` values straight into moderation executors (ai_chat.py:557-731). This is *not* currently exploitable by regular members because `check_mod_permission` (:489-516) verifies the **requester's** Discord permissions per action type (ban→ban_members, kick→kick_members, warn/timeout→moderate_members) and owner-only intents are gated at :548 — verified. The residual risk is prompt-injection getting a *moderator* to type "kick @victim" disguised as a joke; the permission check bounds the blast radius to what that moderator could already do. No action needed beyond awareness.

### S8 — `/owner` is correctly locked — verified, no action

owner.py:91 gates every command on `interaction.user.id != OWNER_ID` (with re-checks at :459-461, :496-498 and confirm-views at :43-67). `OWNER_ID` env default is `0` (:38), which no Discord account can match — fail-closed. Good.

### S9 — Secrets hygiene: passing

`.env` is gitignored; no tokens/keys committed anywhere in the tree (grep-verified); `data/*.json` excluded so no user data is committed. The only exposure path is S6 (key *value* leaks) — nothing in-repo leaks it.


---

## 6. Performance Issues (P1-P7)

### P1 — Blocking Supabase calls on the event loop — **the umbrella issue (D4)**

Every db.py function is a synchronous REST call executed inline in async handlers: AI chat memory (`save_conversation_message` runs after every AI reply), automod checks on **every message** (automod.py:136+), leveling XP writes per message, reminder polling, settings cache misses. Each call freezes the whole bot — including Discord heartbeats — for the network round-trip. This is the single highest-leverage perf fix: `asyncio.to_thread` wrapping requires no architectural change.

### P2 — N+1 deletes per AI message (D5, db.py:834-842)

Up to ~22 blocking REST calls per chat message just to trim history to 20 rows. Replace the row-by-row loop with one `.in_("id", ...)` delete or a periodic trim task.

### P3 — Double Groq calls per conversation message

Every non-obvious @mention costs 2 API round-trips: `parse_intent` (intent_parser.py:155-158, `call_ai_fast`, max_tokens=100) **then** the actual chat call. `is_obvious_chat` was built to halve this (:1370-1371 comment) but B3's ordering bug neuters it for exactly the messages that matter; meanwhile its keyword list (:1382-1388) still contains ~14 dead economy keywords ("balance", "daily", "work", "fish", "beg", "crime", "rob", …) that force the extra parser call for commands that no longer exist. Fixing B3 + pruning the keyword list cuts AI latency/cost on a large share of traffic.

### P4 — Extra sync reads per moderation action

`_send_mod_log` (:99) and `_maybe_apply_threshold` (:145) each call `get_warnings` (blocking) per action — 2 redundant Supabase round-trips per kick/ban/warn, both also wrong (B1). With B1 fixed, pass the already-known count instead of re-reading.

### P5 — Polling background tasks

Reminder/bump loops poll on a timer and hit Supabase (sync) each tick; db.py:225-233's log-dedup was added precisely because a background task was spamming 404s "every 30 seconds". Direction: event-driven scheduling (compute next-due timestamps) or at minimum move polling off-thread per P1.

### P6 — Unbounded in-memory dicts

| Structure | Location | Growth |
|---|---|---|
| `message_tracker` (guild→user→timestamps) | automod.py:29 | inner lists pruned per-window, but **outer user/guild keys are never removed** |
| `offense_counts` (guild→user→int) | automod.py:31 | never expires, never reset |
| `join_tracker` (guild→list) | automod.py:33 | appended per join, no pruning found |
| `xp_cooldowns` | leveling.py:24 | one entry per active user, never evicted (:161-164) |
| `rate_limits` | ai_chat.py:92 | per-user entries never expired |

Slow leaks on a community bot (megabytes over months), but they're also correctness debt: `offense_counts` growing stale means "offense #N" labels drift. Direction: TTL-sweeps in an hourly task, or `cachetools.TTLCache`.

### P7 — Per-message DB round-trips in leveling

leveling.py awards XP in `on_message` with sync read+write per message (:161-164 cooldown check, then persistence). Same `to_thread` treatment + batching writes (flush dirty XP every 30s) removes per-keystroke latency for the busiest handler in the bot after AI chat.

---

## 7. UX Issues (U1-U16)

Most entries are the user-facing symptoms of findings above — listed separately because these are what the community actually experiences.

| ID | Symptom | Root |
|---|---|---|
| U1 | Mods warn a user; `/mod warnings list` says "no warnings". Staff conclude the bot is broken and warn manually. | B1 |
| U2 | "ban @user" via mention gets a playful AI reply instead of an action (or a "I can't do that" non-answer). | B3 |
| U3 | Custom-prefix AI (`cyn.hello` style) returns generic help instead of conversation. | B2 |
| U4 | New members' welcome DM advertises `/daily`, `/work`, `/fish` → "command not found". | B12 |
| U5 | `/forget` describes clearing "cyn's memory" — bot doesn't know its own name post-rebrand. | B14 |
| U6 | `/botinfo` title + footer say "cyn — built by volc"; landing page says "cyn is online ✅". | B14 |
| U7 | Every confession is "Confession #1" — no stable handle to report abuse. | B8 |
| U8 | `/mod antispam` confirms "enabled" but spam keeps flowing. | B9 |
| U9 | Birthday reminders and `/birthday channel` config vanish after every deploy. | B7/D7 |
| U10 | Any member can end the community poll mid-vote. | S1 |
| U11 | Prefix help panel (prefix.py:308-313) tells users to "talk to cyn" with "@cyn" examples. | B14 |
| U12 | "@aurelia ping / whois / botinfo / uptime / nick / truth / dare / fact" get chatty non-answers instead of the utility. | B5 |
| U13 | Staff configure leveling/self-roles; settings silently revert — "the bot forgot my config again". | B10/D3 |
| U14 | Discord audit logs record punishment reasons as "cyn automod: spam" — confusing in a post-rebrand moderation trail. | B14 |
| U15 | `/mod warnings list` caps at 15 entries with a "Total: N" footer but no pagination (moderation.py:389-397). | minor |
| U16 | `/owner personality` help text says the note is "for cyn" — owner-facing confusion. | B14 |

---

## 8. Command Inventory — 99 invocable / 49 top-level

**Methodology correction.** `scripts/count_commands.py` counted all 99 leaf commands against Discord's 100-command guild limit. Discord's limit applies to **top-level** commands only: a group (`/mod`) occupies one slot regardless of how many subcommands it has. The AST scan below (verified against every decorator in every active cog) is the real picture:

> **49 top-level slots used · 51 free · 99 invocable commands total · 0 name collisions**

**Full inventory by cog** (`*` = top-level, `>` = subcommand):

| Cog | Commands | Top-level |
|---|---|---|
| main.py (hybrid) | `ping` `uptime` `botinfo` | 3 |
| afk | `afk` | 1 |
| ai_chat | `adminrole` `adminrole_remove` `aurelia` `forget` | 4 |
| ai_features | `summarize` `translate` `explain` `advice` `roast_server` `code` | 6 |
| autorole | `autorole > set/remove/show` | 1 |
| birthdays | `birthday > set/upcoming/channel` | 1 |
| bot_status | `status > set/reset/current/info` | 1 |
| bump_reminder | `bump > remind` | 1 |
| confess | `confess > setup/text` | 1 |
| fun | `roll` `flip` `joke` `meme` | 4 |
| help | `help` | 1 |
| invites | `invites > show/set` + `invite_leaderboard` | 2 |
| leveling | `level` `leaderboard` `rewards` + `leveling > config` | 4 |
| logging_system | `log > setup/disable/show/toggle` | 1 |
| moderation | `mod > kick ban unban timeout warnings purge nuke slowmode lock unlock unmute mute antispam antilink tempban config` | 1 |
| owner | `owner > status reload sync shutdown dm announce createrole giverole removerole servers say personality personality_clear leave` | 1 |
| polls | `poll > create/end` | 1 |
| prefix | `prefix > set/remove/list` | 1 |
| profiles | `profile` + `profile_set > bio/pronouns/timezone` | 2 |
| rules | `rules > set/show/agree/agree_role` | 1 |
| self_roles | `selfroles > setup` | 1 |
| server_stats | `serverinfo` `whois` `avatar` | 3 |
| utility | `math` `snipe` `reminders` | 3 |
| voice | `voice` | 1 |
| weather | `weather` | 1 |
| welcome | `toggledms` + `welcome > config/test/show` | 2 |
| **Total** | **99 invocable** | **49** |

**Capacity conclusion:** the 100-command limit was never a real constraint. Reviving giveaways, tickets, suggestions, or trivia (§9) costs at most 1 top-level slot each. Nothing needs to be deleted or flattened for capacity reasons.

**Consolidation candidates** — recommended for *discoverability*, not for the limit:

1. `/toggledms` → `welcome > toggledms` (groups the entire welcome feature under one prefix; −1 top-level, +1 discoverability) — welcome.py.
2. `/invite_leaderboard` → `invites > leaderboard` (obvious grouping; −1) — invites.py.
3. `/adminrole` + `/adminrole_remove` → single `/adminrole` with an action choice or a group (−1) — ai_chat.py; the add/remove pair mirrors the `/mod warnings` add/list/clear consolidation already done (moderation.py:345-356, "PHASE 2B").
4. `/profile` + `/profile_set` → `/profile` group with `view` implicit (−1) — profiles.py.
5. `/level` `/leaderboard` `/rewards` → `leveling > ...` group (−2) — leveling.py; matches the existing `leveling > config` group.
6. Note `/aurelia` duplicates the @mention channel — intentional as a slash entrypoint; fine to keep.

**A note on the old premise:** the `poll` intent was removed from the parser to "save a command slot" (intent_parser.py:66-67). With the real math in hand, if conversational poll creation was valued, it can come back at zero capacity cost — but do fix B5's orphaned executor either way.


---

## 9. Disabled Cogs — all 22 `*_disabled.py` files, with verdicts

Verified via full read + AST scan (commands/tables each disabled cog would claim). Verdict key: **DELETE** = superseded by an active twin or dead weight; **REVIVE** = fills a real gap, no active equivalent; **DECIDE** = depends on product direction (mostly the economy cluster).

| File | Lines | What it is | Verdict & reasoning |
|---|---|---|---|
| `server_logs_disabled.py` | 674 | pre-logging_system message/member logs | **DELETE** — fully superseded by `logging_system.py` (459 lines, active, covers delete/edit/join/leave/ban/role/voice) |
| `leveling_disabled.py` | 283 | old XP system | **DELETE** — superseded by `leveling.py` (315, active) |
| `automod_disabled.py` | 573 | old automod w/ separate filters | **DELETE** — superseded by `automod.py` (267, active); 573 lines of dead duplicate logic |
| `confess_disabled.py` | 108 | old confessions | **DELETE** — superseded by `confess.py` (174, active) |
| `birthdays_disabled.py` | 261 | old birthdays | **DELETE** — superseded by `birthdays.py` (192, active) |
| `reaction_roles_disabled.py` | 231 | reaction-role panels | **DELETE** — superseded by `self_roles.py` (249, active, button panels). If it has features self_roles lacks (e.g. message-reaction binding), port them, then delete |
| `productivity_disabled.py` | 149 | notes/reminders | **DELETE** — `utility.py` `/reminders` covers the live need |
| `music_disabled.py` | 50 | stub (placeholder, no playback) | **DELETE** — 50-line stub; if music is wanted, start from a maintained lavalink/py-lav lib, not this |
| `custom_embeds_disabled.py` | 87 | /embed builder | **DECIDE** — small; harmless to keep for a future `/embed` revival |
| `economy_disabled.py` | 488 | currency system | **DECIDE (anchor of the economy cluster)** — welcome.py still writes to its data file and advertises its commands (B12). Either revive the cluster (economy+games+marriage+reputation) or strip the welcome integration |
| `games_disabled.py` | 750 | 8+ games; **depends on Economy cog** (`get_cog('Economy')` :24, :32) | **DECIDE** — broken if revived alone; `fun.py` covers basics (roll/flip/joke/meme). Revive only with economy |
| `marriage_disabled.py` | 346 | marriage/social | **DECIDE** — economy-cluster satellite |
| `reputation_disabled.py` | 160 | rep points | **DECIDE** — economy-cluster satellite; overlapping concept with leveling |
| `giveaways_disabled.py` | 389 | giveaways | **REVIVE (best candidate)** — standard community feature, no active equivalent, no economy dependency, self-contained; 1 top-level slot |
| `tickets_disabled.py` | 227 | ticket threads | **REVIVE** — pairs with M3 (appeals); pick this OR modmail, not both |
| `modmail_disabled.py` | 277 | DM-to-mods relay | **REVIVE (one of two)** — alternative to tickets; same gap (M3) |
| `suggestions_disabled.py` | 153 | suggestion queue | **REVIVE** — common need, self-contained, no dependencies |
| `trivia_disabled.py` | 221 | trivia quiz | **REVIVE (cheap)** — no deps; also gives the dead `fact` intent a home |
| `truth_dare_disabled.py` | 137 | truth-or-dare | **DECIDE** — tiny; note the parser *still advertises* truth/dare intents (B5) — if you keep it disabled, remove those intents |
| `starboard_disabled.py` | 208 | starboard | **DECIDE** — nice-to-have; needs no economy |
| `counting_disabled.py` | 211 | counting channel | **DECIDE** — niche; self-contained |
| `auto_responder_disabled.py` | 182 | keyword autoresponses | **DECIDE** — partially overlaps the AI mention handler; likely stays dead |

**Bottom line:** 8 files (~2,320 lines) are safe immediate deletions (superseded twins + stub); that alone removes a third of the disabled mass and every "which one is real?" ambiguity for future maintainers. Four files are strong revive candidates. The economy cluster (4 files, ~1,744 lines) is the one genuine product decision.

---

## 10. Prioritized Recommendations (P0 → P3)

### P0 — this week (each ≤ a few hours, unblocks trust in the bot)

1. **Unify the warnings store (B1).** Swap moderation.py's add path to `utils/db.py:519 add_warning()`; migrate `data/moderation.json` warnings once; delete the legacy helpers. Auto-escalation, list, clear, and mod-log counts start working simultaneously.
2. **Fix the cog-name casing (B2).** `"AiChat"` → `"AIChat"` at prefix.py:107, 233, 239, 245, 256, 300, 369. Add a startup assert `bot.get_cog("AIChat") is not None`.
3. **Reorder `is_obvious_chat` (B3).** Keyword scan before the `< 15` length shortcut (ai_chat.py:1377-1392). Also prune the ~14 dead economy keywords from the list.
4. **Repair the system prompt line (B4).** ai_chat.py:220: replace `ildo` with the actual tag names (`<think>...</think>`, `<thinking>`).

### P1 — next 1-2 weeks (data integrity + security)

5. **Run the schema migration (D1/D2 → fixes B7-B11).** SQL below. Then update `_TABLE_COLUMNS` to match the live schema exactly and add a startup drift check (D3/D9). *Verify column types against the live DB before running — the code sends `guild_id` as text.*
6. **Close the permission/cooldown gaps (S1-S3).** `/poll end` author-or-manage_messages; `manage_guild` on `/welcome test|show`; a 5-minute cooldown on `/confess text`.
7. **Lock down Supabase (S6).** Dedicated role + least-privilege grants (+RLS if feasible); rotate the anon key; update `.env.example` to the new key name.
8. **Resolve the confession privacy contradiction (S4).** Decide: traceable-for-mods or truly anonymous; implement and document it; scrub `confess` options from the main.py interaction logger either way.
9. **Clean up the intent surface (B5).** Remove or wire the 8 dead intents; delete the orphaned poll executor; sync `is_obvious_chat`'s keyword list with reality.

### P2 — next month (architecture & hygiene)

10. **Stop blocking the event loop (D4/P1).** `asyncio.to_thread` wrappers around db.py's Supabase calls; batch the conversation trim (D5/P2); off-thread the polling loops (P5).
11. **Bound the in-memory dicts (P6)** with TTL sweeps; fix the automod "offense #N" drift at the same time.
12. **Consolidate the data layer (C1).** Port the 8 legacy-Database cogs to utils.db; delete `utils/database.py` from active imports.
13. **Finish the rebrand (B14).** Mechanical string sweep (keep the table in §B14 as the checklist); rewrite README.
14. **Strip or gate the dead economy hooks (B12)** and pick one autorole system (B13).
15. **Delete the 8 superseded disabled cogs + dead utils (C4), fix requirements.txt (C7), fix count_commands.py or delete it (C8).**

### P3 — when capacity allows

16. **Consolidation pass on command UX (§8 candidates)** — for discoverability, not capacity.
17. **Revive giveaways → tickets-or-modmail → suggestions → trivia (§9)** — one per sprint, each gets a regression checklist since none has tests to lean on.
18. **Add a minimal test/CI harness (M8):** pytest for db fallback semantics + intent routing + the AST command counter as a CI guard.
19. **Migration tooling + `/backup` export (M7/M9)**; mod action-history viewer and single-warning removal (M1/M2) once the store is unified.

### Ready-to-run SQL migration (for P1 item 5)

```sql
-- Aurelia schema sync — fixes D1/D2 (verify column types against live DB first;
-- the bot sends guild_id/user_id as TEXT)

-- 1) confess_settings: stable confession numbering (B8)
alter table public.confess_settings
  add column if not exists count bigint not null default 0;

-- 2) mod_settings: antispam toggle persistence (B9)
alter table public.mod_settings
  add column if not exists antispam_enabled boolean not null default false;
alter table public.mod_settings
  add column if not exists antilink_channels jsonb not null default '[]';

-- 3) leveling_settings: config persistence (B10)
alter table public.leveling_settings
  add column if not exists enabled boolean not null default true,
  add column if not exists channel_id text,
  add column if not exists rate int not null default 5,
  add column if not exists rewards jsonb not null default '{}';

-- 4) self_role_panels: panel payload persistence (B10)
alter table public.self_role_panels
  add column if not exists panels jsonb not null default '{}';

-- 5) birthdays: the code probes an "id" column (db.py:1108) (B7)
alter table public.birthdays
  add column if not exists id bigint generated by default as identity primary key;

-- 6) missing tables (B7 / B11)
create table if not exists public.birthday_settings (
  guild_id text primary key,
  channel_id text
);
create table if not exists public.bump_reminder_state (
  guild_id text primary key,
  channel_id text,
  last_bump_message_id text,
  last_bump_at timestamptz
);

-- 7) least-privilege start (S6) — replace YOUR_BOT_ROLE
-- grant select, insert, update, delete on all tables in public to YOUR_BOT_ROLE;
-- (RLS policies recommended after this audit)
```

**Suggested commit order** (keeps every deploy small and revertible):
P0-2 + P0-3 (two-line fixes) → P0-1 (warnings + migration script for existing JSON data) → P0-4 (prompt) → P1-5 SQL + `_TABLE_COLUMNS` sync → P1-6 permission decorators → P1-7/8 security → then P2 items in the numbered order.

