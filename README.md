# cyn — AI Discord Companion

A sarcastic AI companion with moderation tools. She has a sharp tongue, dark humor, and takes no nonsense.

## Features

- **AI Chat** — `@mention` or `/cyn` to talk to cyn naturally
- **Natural Language Moderation** — say "warn @user" via AI and she handles it
- **Server Moderation** — full `/mod` command suite (kick, ban, timeout, warn, purge, nuke, lock, slowmode)
- **Weather** — `/weather [city]`
- **Fun** — `/joke`, `/meme`, `/flip`, `/roll`, `/truth`, `/dare`
- **Welcome System** — customizable welcome/goodbye messages
- **Server Info** — `/serverinfo`, `/whois`, `/avatar`
- **AFK System** — `/afk [reason]`

## Setup

### Prerequisites
- Python 3.11+
- A Discord bot token (from the Discord Developer Portal)
- A Groq API key (free at [console.groq.com](https://console.groq.com))

### Installation
1. Clone the repo
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`
4. Set `DISCORD_TOKEN`, `GROQ_API_KEY`, `OWNER_ID`
5. `python main.py`

## Hosting (Render + UptimeRobot)

### Render Setup
1. Connect this GitHub repo to Render → New Web Service
2. Runtime: Python 3.11.9
3. Build: `pip install -r requirements.txt`
4. Start: `python main.py`
5. Env vars: `DISCORD_TOKEN`, `GROQ_API_KEY`, `OWNER_ID`, `PYTHON_VERSION=3.11.9`

### UptimeRobot
- Monitor: HTTP(s)
- URL: `https://your-service.onrender.com/health`
- Interval: every 5 minutes

### Important Render notes
- Free tier sleeps after 15 min — UptimeRobot prevents this
- `/data` folder is ephemeral — data resets on redeploy
- For persistent data, upgrade to Render paid tier or use an external DB

### Discord slash-command cache
When commands are added/removed/changed, Discord's client may still show old
commands in the UI. To force a refresh:
1. **Completely quit and reopen Discord**, OR
2. Wait up to **1 hour** for Discord to refresh automatically

## License
MIT
