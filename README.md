# ao — Discord Bot

A dark, natural-sounding Discord companion with server tools, economy, and quality-of-life features.

This bot is designed to feel **human**, **simple to understand**, and **not overwhelming**—with most commands organized into clean slash-command groups.

---

## Features

### 🧠 AI Chat (GitHub Models)
- Mention-based chat: `@ao <message>`
- Slash chat: `/chat`, `/ask`
- Dark / sarcastic personality (simple English, short replies)
- Rate-limited to prevent spam + API abuse

### 💰 Economy (No Gambling)
- Core: `/balance`, `/daily` (streak), `/work`, `/pay`, `/shop`, `/buy`, `/inventory`
- Earnings: `/earn fish`, `/earn hunt`, `/earn mine`, `/earn beg`, `/earn crime`, `/earn rob`
- Banking: `/bank deposit`, `/bank withdraw`
- Admin economy tools: `/eco_admin set|add|remove|reset`
- Image cards:
  - `/profile` → economy profile card (PNG)
  - `/richest` → money leaderboard card (PNG)

> Note: Gambling/casino-style features are intentionally excluded.

### ⭐ Leveling (Image Rank Cards)
- `/level` → rank card image (PNG)
- `/leaderboard_levels` → XP leaderboard image (PNG)
- Admin config (grouped under `/xp`): setup channel, roles, ignore channels, give/remove/reset XP

### 🛡️ Moderation & AutoMod
- Moderation grouped under `/mod`:
  - kick/ban/unban/timeout/warn/purge/logs
- AutoMod:
  - Anti-spam configuration
  - Word filter (delete/warn/timeout actions)
  - Optional logging channel
  - Slowmode, lock/unlock tools (where configured)

### 📊 Server Tools (Dyno/Carl-style)
- Compact `/serverinfo` (with server icon)
- One-button UI where useful (e.g., “View Roles”)
- `/whois`, `/roleinfo`, `/channelinfo`, `/avatar`, `/banner`, `/membercount`, etc.

### 📝 Productivity
- `/remind`, `/note`, `/notes`, `/mood`

### 🎫 Tickets / Modmail / Community
- Ticket system with buttons
- Modmail forwarding from DMs (staff reply)
- Polls, giveaways, suggestions, starboard, birthdays, counting game, reputation, marriage, trivia, truth/dare
- DM preference toggle to avoid spam: `/toggledms`

---

## Commands

Use `/help` in Discord to open the interactive help menu (category buttons).

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

## Hosting (Render + UptimeRobot)

### Render
1. Create a Web Service
2. Build Command:
   ```bash
   pip install -r requirements.txt
   ```
3. Start Command:
   ```bash
   python main.py
   ```
4. Add environment variables (`DISCORD_TOKEN`, `GITHUB_TOKEN`, `OWNER_ID`, `PYTHON_VERSION`)

### Keep Alive
This bot includes a small Flask web server (port 8080) with:

- `/` → basic “online” response
- `/health` → JSON health output

Use **UptimeRobot** (free) to ping your Render URL every 5 minutes:

```
Monitor URL: https://<your-service>.onrender.com
```

---

## Notes / Design Goals

- **Not overwhelming**: commands are grouped where possible to keep the UI clean
- **Privacy-first**: data stored locally in JSON files under `/data`
- **No gambling**: avoids casino/lottery style mechanics
- **Natural tone**: simple English, short replies, human feel

## License

MIT License — use, modify, and share freely.