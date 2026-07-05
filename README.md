# cyn — Discord Bot

A dark, natural-sounding Discord companion with server tools, economy, AI features, and quality-of-life commands.

cyn is designed to feel **human**, **simple to understand**, and **not overwhelming** — with most commands organized into clean slash-command groups.

---

## Features

### 🧠 AI Chat (GitHub Models)
- Mention-based chat: `@cyn <message>` (with natural-language intent parsing — try "ban @user spam" or "weather in Lahore")
- Slash chat: `/chat`, `/ask`
- Dark / sarcastic personality (simple English, short replies)
- AI features: `/summarize`, `/translate`, `/explain`, `/code`, `/debug`, `/story`, `/poem`, `/advice`, `/define`, `/tldr`, `/roast_server`, `/aipoll`
- Rate-limited to prevent spam + API abuse

### 💰 Economy
- Core: `/balance`, `/daily` (streak), `/work`, `/pay`, `/shop`, `/buy`, `/inventory`
- Earnings: `/earn fish`, `/earn hunt`, `/earn mine`, `/earn beg`, `/earn crime`, `/earn rob`
- Banking: `/bank deposit`, `/bank withdraw`
- Admin economy tools: `/eco_admin set|add|remove|reset`
- Image cards:
  - `/profile` → economy profile card (PNG)
  - `/richest` → money leaderboard card (PNG)

### 🎮 Games
- `/rps` (button-based), `/ttt <user>`, `/numguess`, `/typerace`, `/reaction`, `/wordle`
- `/blackjack`, `/coinflip`, `/slots` (optional economy integration)

### 🎉 Fun
- `/joke`, `/meme`, `/fact`, `/quote`, `/pickup`, `/wouldyourather`, `/8ball`
- `/roast`, `/roastme`, `/compliment`, `/hack`, `/howsmart`, `/ship`, `/rate`
- `/roll`, `/flip`, `/mock`, `/clap`, `/reverse`, `/say`, `/ascii`, `/emojify`
- `/truth`, `/dare`, `/tod`, `/choose`, `/topic`, `/would`
- `/pp`, `/iq`, `/rizz`, `/battle`, `/vibe`

### ⭐ Leveling (Image Rank Cards)
- `/level` → rank card image (PNG)
- `/leaderboard_levels` → XP leaderboard image (PNG)
- Admin config (grouped under `/xp`): setup channel, roles, ignore channels, give/remove/reset XP

### 🛡️ Moderation
- `/mod kick|ban|unban|timeout|untimeout|warn|warn list|warn clear|warn case|purge|logs`
- `/mod nuke`, `/mod role add|remove`, `/mod nickname`, `/mod softban`
- `/mod slowmode`, `/mod lock`, `/mod unlock`, `/mod hide`, `/mod show`
- `/mod massrole add|remove` (mass-assign/remove roles across all members)
- AutoMod: anti-spam, word filter, logging channel

### 🔧 Utility
- `/weather`, `/urban`, `/color`, `/qr`, `/math`, `/password`, `/encode`, `/decode`, `/timestamp`
- `/snipe [index]`, `/editsnipe [index]` (up to 5 most recent per channel)
- `/afk`, `/firstmessage`, `/remind`, `/note`, `/notes`
- `/announce <channel> <title> <msg>`, `/pin <id>`, `/unpin <id>`

### 📊 Server Tools
- `/serverinfo`, `/whois`, `/roleinfo`, `/channelinfo`, `/avatar`, `/banner`, `/membercount`

### 🎫 Tickets / Modmail / Community
- Ticket system with buttons
- Modmail forwarding from DMs (staff reply), `/massdm` for mass announcements
- Polls, giveaways, suggestions, starboard, birthdays, counting game, reputation, marriage, trivia, truth/dare
- DM preference toggle to avoid spam: `/toggledms`

### ⚙️ Settings
- Welcome & goodbye system (`/welcome`, `/goodbye`, `/autorole`)
- Logging system (`/setlog`, `/log toggle`, `/log list`)
- Reaction roles (`/reactionrole`, `/buttonrole`)
- Auto-responder & custom commands (`/autorespond`, `/customcmd`)
- Starboard (`/starboard setup|emoji|threshold|ignore|unignore`)

### 🌍 Community
- Giveaways (`/giveaway start|end|reroll|list`)
- Suggestions (`/suggest setup|submit|approve|deny|list`)
- Polls (`/poll create|end|results`)
- Birthdays (`/birthday set|remove|check|upcoming|channel`)
- Counting game (`/counting setup|reset|score|toggle_save`)
- Reputation (`/rep give|check|leaderboard|reset`)
- Marriage (`/marry`, `/divorce`, `/marriage`, `/marry_status`)

### ℹ️ Info
- `/botinfo`, `/ping`, `/uptime`, `/serverinfo`, `/whois`, `/avatar`, `/roleinfo`, `/channelinfo`, `/membercount`, `/banner`, `/emojis`, `/roles`, `/music`

---

## Commands

Use `/help` in Discord to open the interactive help menu with a **dropdown** of categories. Pick a category to see its commands; categories with more than 10 commands paginate with ◀ ▶ buttons. Use `/help <command>` for detailed help on a specific command.

---

## Quick Start (Local)

1. Clone the repo
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`
4. Add required values (see below)
5. Run:
   ```bash
   python main.py
   ```

### Environment Variables

Create a `.env` file (or set these in your hosting provider):

```env
DISCORD_TOKEN=your_discord_bot_token_here
GITHUB_TOKEN=your_github_models_token_here
OWNER_ID=your_discord_user_id_here
```

Render-specific (recommended):

```env
PYTHON_VERSION=3.11.9
```

---

## Hosting (Render + UptimeRobot)

### Render Setup

1. **Connect GitHub repo to Render**
   - In Render, click **New → Web Service**
   - Connect your GitHub account and select this repo

2. **Runtime:** Python 3.11.9

3. **Build command:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start command:**
   ```bash
   python main.py
   ```

5. **Add environment variables** (Render dashboard → Environment):
   - `DISCORD_TOKEN` — your Discord bot token
   - `GITHUB_TOKEN` — your GitHub Models API token
   - `OWNER_ID` — your Discord user ID (used by AI personality + /owner commands)
   - `PYTHON_VERSION=3.11.9`

### UptimeRobot Setup

- **Monitor type:** HTTP(s)
- **URL:** `https://your-service.onrender.com/health`
- **Interval:** every 5 minutes

This keeps the Render free-tier web service awake (otherwise it sleeps after 15 min of no traffic).

### Important Render notes

- ⚠️ **Free tier sleeps after 15 minutes of no traffic** — UptimeRobot pinging `/health` every 5 min prevents this.
- ⚠️ **`/data` folder is ephemeral on Render free tier** — data resets on every redeploy. User balances, levels, AFK status, etc. will be lost.
  - For persistent data, either:
    - Upgrade to Render's paid tier (persists disk), or
    - Migrate data storage to a free **MongoDB Atlas** cluster
- ⚠️ **Music commands are disabled on Render** — FFmpeg is not installed on Render's free tier. The `/music` command returns an explanatory embed. See `cogs/music_disabled.py` for the full music implementation and instructions on how to re-enable it locally.
- ⚠️ **Image generation (rank cards, profile cards, leaderboard cards)** works on Render because fonts are loaded via a fallback chain (`load_font()` in `utils/rank_card.py` and `utils/image_generator.py`) that includes `/usr/share/fonts/truetype/dejavu/...`.

### Keep-alive endpoints

This bot includes a small Flask web server (port 8080) with:

- `/` → basic HTML "cyn is online" response with current timestamp
- `/health` → JSON: `{"status": "ok", "latency_ms": ..., "guilds": ..., "users": ..., "uptime_seconds": ...}`
- `/stats` → JSON with command usage counts (in-memory counter incremented on every command)

---

## Project Structure

```
.
├── main.py                  # Bot entrypoint, data-dir setup, error handlers, /ping /uptime /botinfo
├── keep_alive.py            # Standalone Flask keep-alive (mirror of main.py's embedded server)
├── requirements.txt
├── runtime.txt              # python-3.11.9 (Render)
├── .env.example
├── utils/
│   ├── database.py          # JSON-backed key/value store used by every cog
│   ├── embeds.py            # Embed helpers
│   ├── helpers.py           # parse_time / format_time
│   ├── intent_parser.py     # Natural-language → command intent via AI
│   ├── rank_card.py         # Pillow rank/leaderboard/profile card generators
│   ├── image_generator.py   # Shared safe font loader
│   ├── constants.py         # Shared color constants (POLISH 1)
│   ├── checks.py            # is_owner / is_mod / is_admin decorators (POLISH 2)
│   ├── paginator.py         # Reusable pagination View (POLISH 3)
│   └── professional_embeds.py
└── cogs/
    ├── ai_chat.py           # @cyn chat + intent execution + narrate_result
    ├── ai_features.py       # /summarize /translate /explain /code /debug /story /poem /advice /define /tldr /roast_server /aipoll
    ├── fun.py               # /joke /meme /fact /quote /pickup /wouldyourather /8ball /roast /compliment /hack /howsmart /roastme /ship /rate /roll /flip /mock /clap /reverse /say /ascii /emojify /truth /dare /tod /choose /topic /would /pp /iq /rizz /battle /vibe
    ├── games.py             # /rps /ttt /numguess /typerace /reaction /wordle /blackjack /coinflip /slots
    ├── economy.py           # /balance /daily /work /pay /shop /buy /inventory /profile /richest /earn /bank /eco_admin
    ├── leveling.py          # /level /leaderboard_levels /xp ...
    ├── moderation.py        # /mod kick/ban/unban/timeout/warn/warn list/warn clear/warn case/purge/nuke/role/nickname/softban/slowmode/lock/unlock/hide/show/massrole/logs
    ├── utility.py           # /math /password /encode /decode /timestamp /snipe /editsnipe /urban /color /qr /announce /pin /unpin
    ├── weather.py           # /weather (separate file)
    ├── afk.py               # /afk + edge-case-safe listeners
    ├── welcome.py           # /welcome /goodbye /autorole + on_member_join/remove
    ├── logging_system.py    # /setlog /log toggle /log list
    ├── server_logs.py       # Actual log event listeners (re-used by logging_system)
    ├── reaction_roles.py    # /reactionrole /buttonrole
    ├── auto_responder.py    # /autorespond /customcmd
    ├── help.py              # /help with Select dropdown + pagination
    ├── owner.py             # /owner ... (OWNER_ID-gated)
    ├── truth_dare.py        # /truth /dare /tod
    ├── giveaways.py         # /giveaway start/end/reroll/list
    ├── suggestions.py       # /suggest setup/submit/approve/deny/list
    ├── starboard.py         # /starboard setup/emoji/threshold/ignore/unignore
    ├── birthdays.py         # /birthday set/remove/check/upcoming/channel
    ├── polls.py             # /poll create/end/results
    ├── counting.py          # /counting setup/reset/score/toggle_save
    ├── reputation.py        # /rep give/check/leaderboard/reset
    ├── marriage.py          # /marry /divorce /marriage /marry_status
    ├── music.py             # Stub — see music_disabled.py for full impl
    ├── music_disabled.py    # Full music cog (not auto-loaded)
    ├── tickets.py / modmail.py / productivity.py / custom_embeds.py / bot_status.py
    ├── automod.py / server_stats.py / trivia.py / autorole.py
    └── __init__.py
```

---

## Notes / Design Goals

- **Not overwhelming**: commands are grouped where possible to keep the UI clean
- **Privacy-first**: data stored locally in JSON files under `/data`
- **Natural tone**: simple English, short replies, human feel
- **Owner-locked**: the AI personality and `/owner` commands are gated by `OWNER_ID`

## License

MIT License — use, modify, and share freely.
