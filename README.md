# cyn — Discord Bot

A dark, natural-sounding Discord companion with server tools, economy, AI features, and quality-of-life commands.

## Features

### 🧠 AI Chat (Groq API — free at console.groq.com)
- Mention-based chat: `@cyn <message>` (with natural-language intent parsing)
- Slash: `/cyn <message>`, `/chat`, `/ask`
- AI features: `/summarize`, `/translate`, `/explain`, `/code`, `/debug`, `/story`, `/poem`, `/advice`, `/define`, `/tldr`, `/roast_server`

### 💰 Economy (Guild-Scoped)
- `/balance`, `/daily` (streak + weekly/monthly bonuses + marriage bonus), `/work` (20+ jobs), `/pay`
- `/earn fish/hunt/mine/beg/crime/rob` — all with cooldowns and item requirements
- `/bank deposit/withdraw`
- `/shop`, `/buy`, `/inventory`, `/richest` (per-guild only)
- `/eco_admin set/add/remove/reset` (admin)

### 🎮 Games
- `/rps`, `/ttt <user>`, `/numguess`, `/typerace`, `/reaction`, `/wordle`
- `/blackjack`, `/coinflip`, `/slots`

### 🎉 Fun
- `/joke`, `/meme`, `/fact`, `/quote`, `/8ball`, `/pickup`, `/wouldyourather`, `/rizz`, `/topic`
- `/roast`, `/compliment`, `/roastme`, `/ship`, `/rate`, `/battle`, `/vibe`
- `/roll`, `/flip`, `/say` (owner only), `/truth`, `/dare`

### 🛡️ Moderation
- `/mod kick/ban/unban/timeout/untimeout/warn/purge/nuke/slowmode/lock/unlock/hide/show/nickname/softban/role/massrole/warn_list/warn_clear/case/logs`

### 🔧 Utility
- `/weather`, `/math`, `/password`, `/snipe`, `/urban`, `/color`, `/announce`

### 🌍 Community
- `/suggest`, `/suggest_approve`, `/suggest_deny`, `/suggest_list`, `/suggest_setup`
- `/giveaway start/end/reroll/list`
- `/poll create/end/results`
- `/birthday set/check/upcoming/channel`
- `/counting setup/reset/score/toggle_save`
- `/rep give/check/leaderboard/reset`
- `/marry`, `/divorce`, `/marriage`, `/marriage_top`, `/proposal cancel/list`
- `/confess`, `/confess_setup`, `/toggledms`

### ⚙️ Settings
- `/welcome channel/message/toggle/test`, `/goodbye channel/message/toggle`, `/autorole`
- `/setlog`, `/log toggle/list`
- `/reactionrole add/remove/list`
- `/autorespond add/remove/list`, `/customcmd add/remove/list`
- `/starboard setup/ignore`

### ℹ️ Info
- `/botinfo`, `/ping`, `/uptime`, `/serverinfo`, `/whois`, `/avatar`, `/roleinfo`, `/channelinfo`, `/banner`, `/membercount`

## Quick Start (Local)

1. Clone the repo
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`
4. Set `DISCORD_TOKEN`, `GROQ_API_KEY` (free at console.groq.com), `OWNER_ID`
5. `python main.py`

## Hosting (Render + UptimeRobot)

### Render Setup
1. Connect GitHub repo to Render → New Web Service
2. Runtime: Python 3.11.9
3. Build: `pip install -r requirements.txt`
4. Start: `python main.py`
5. Env vars: `DISCORD_TOKEN`, `GROQ_API_KEY`, `OWNER_ID`, `PYTHON_VERSION=3.11.9`

### UptimeRobot
- Monitor: HTTP(s)
- URL: `https://your-service.onrender.com/health`
- Interval: every 5 minutes

### Important Render notes
- ⚠️ Free tier sleeps after 15 min — UptimeRobot prevents this
- ⚠️ `/data` folder is ephemeral — data resets on redeploy
- ⚠️ Music is disabled (no FFmpeg on Render free tier)
- For persistent data, upgrade to Render paid tier or use external DB

## License
MIT
