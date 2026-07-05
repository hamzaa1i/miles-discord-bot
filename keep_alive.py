"""
keep_alive.py — Flask keep-alive server.

main.py has its own embedded Flask server (with /, /health, /stats) used at
runtime. This module is kept as a standalone, importable alternative for
developers who want to launch the keep-alive server separately (e.g. from
a custom entrypoint). Pass a bot instance to `keep_alive(bot)` and the
/health and /stats routes will report real bot stats.
"""
from flask import Flask
from threading import Thread
from datetime import datetime

app = Flask('')
_bot = None
_start_time = datetime.utcnow()


def set_bot(bot):
    """Inject the bot instance so /health and /stats can read live data."""
    global _bot
    _bot = bot


@app.route('/')
def home():
    return f"""<!doctype html>
<html><head><title>ao</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 60px; background:#0f0f1a; color:#e0e0e0;">
  <h1 style="font-size: 48px; margin: 0;">ao is online ✅</h1>
  <p style="color:#888;">uptime since {_start_time.isoformat()}</p>
  <p style="color:#666;">{datetime.utcnow().isoformat()} UTC</p>
</body></html>"""


@app.route('/health')
def health():
    if _bot is None or not _bot.is_ready():
        return {
            "status": "starting",
            "latency_ms": 0,
            "guilds": 0,
            "users": 0,
            "uptime_seconds": (datetime.utcnow() - _start_time).total_seconds()
        }, 200
    return {
        "status": "ok",
        "latency_ms": round(_bot.latency * 1000, 2),
        "guilds": len(_bot.guilds),
        "users": sum(g.member_count for g in _bot.guilds),
        "uptime_seconds": (datetime.utcnow() - _start_time).total_seconds()
    }, 200


@app.route('/stats')
def stats():
    if _bot is None:
        return {"status": "starting", "command_counts": {}}, 200
    counts = getattr(_bot, 'command_counts', {})
    return {
        "status": "ok" if _bot.is_ready() else "starting",
        "guilds": len(_bot.guilds) if _bot.is_ready() else 0,
        "users": sum(g.member_count for g in _bot.guilds) if _bot.is_ready() else 0,
        "latency_ms": round(_bot.latency * 1000, 2) if _bot.is_ready() else 0,
        "uptime_seconds": (datetime.utcnow() - _start_time).total_seconds(),
        "command_counts": counts
    }, 200


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive(bot=None):
    """Start the keep-alive server. Pass `bot` to enable /health and /stats."""
    if bot is not None:
        set_bot(bot)
    t = Thread(target=run, daemon=True)
    t.start()
