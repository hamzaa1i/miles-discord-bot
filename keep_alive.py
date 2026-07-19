"""
keep_alive.py — Flask keep-alive server with enhanced /health endpoint.

main.py has its own embedded Flask server (with /, /health, /stats) used at
runtime. This module is kept as a standalone, importable alternative for
developers who want to launch the keep-alive server separately (e.g. from
a custom entrypoint). Pass a bot instance to `keep_alive(bot)` and the
/health and /stats routes will report real bot stats.

PHASE 1D — Added tracking variables (bot_ref, start_time, total_ai_calls,
total_errors, recent_response_times) that main.py and ai_handler.py update.
The /health endpoint now returns JSON with uptime, latency, guild count,
AI call count, avg response time, active cogs, and Supabase status.
"""
from flask import Flask, jsonify
from threading import Thread
from datetime import datetime

app = Flask('')

# PHASE 1D — tracking variables (set by main.py + ai_handler.py)
bot_ref = None
start_time = datetime.utcnow()
total_ai_calls = 0
total_errors = 0
recent_response_times = []  # last 100 response times in ms

# Legacy compat
_bot = None


def set_bot(bot):
    """Inject the bot instance so /health and /stats can read live data."""
    global _bot, bot_ref
    _bot = bot
    bot_ref = bot


def _format_uptime(seconds: float) -> str:
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    return f"{d}d {h}h {m}m"


@app.route('/')
def home():
    return f"""<!doctype html>
<html><head><title>cyn</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 60px; background:#0f0f1a; color:#e0e0e0;">
  <h1 style="font-size: 48px; margin: 0;">cyn is online ✅</h1>
  <p style="color:#888;">uptime since {start_time.isoformat()}</p>
  <p style="color:#666;">{datetime.utcnow().isoformat()} UTC</p>
</body></html>"""


@app.route('/health')
def health():
    bot = bot_ref or _bot
    uptime_seconds = (datetime.utcnow() - start_time).total_seconds() if start_time else 0

    avg_response = 0
    if recent_response_times:
        avg_response = sum(recent_response_times) / len(recent_response_times)

    # Check Supabase status
    using_supabase = False
    try:
        from utils.db import using_supabase as _using_supabase
        using_supabase = _using_supabase()
    except Exception:
        pass

    if bot is None or not getattr(bot, 'is_ready', lambda: False)():
        return jsonify({
            "status": "starting",
            "uptime_seconds": int(uptime_seconds),
            "uptime_human": _format_uptime(uptime_seconds),
            "guilds": 0,
            "users": 0,
            "latency_ms": 0,
            "ai_calls_total": total_ai_calls,
            "avg_response_ms": round(avg_response, 1),
            "active_cogs": 0,
            "using_supabase": using_supabase
        }), 200

    return jsonify({
        "status": "ok",
        "uptime_seconds": int(uptime_seconds),
        "uptime_human": _format_uptime(uptime_seconds),
        "guilds": len(bot.guilds),
        "users": sum(g.member_count for g in bot.guilds),
        "latency_ms": round(bot.latency * 1000, 1),
        "ai_calls_total": total_ai_calls,
        "avg_response_ms": round(avg_response, 1),
        "active_cogs": len(bot.cogs),
        "using_supabase": using_supabase
    }), 200


@app.route('/stats')
def stats():
    bot = bot_ref or _bot
    if bot is None:
        return jsonify({"status": "starting", "command_counts": {}}), 200
    counts = getattr(bot, 'command_counts', {})
    ready = getattr(bot, 'is_ready', lambda: False)()
    return jsonify({
        "status": "ok" if ready else "starting",
        "guilds": len(bot.guilds) if ready else 0,
        "users": sum(g.member_count for g in bot.guilds) if ready else 0,
        "latency_ms": round(bot.latency * 1000, 2) if ready else 0,
        "uptime_seconds": int((datetime.utcnow() - start_time).total_seconds()) if start_time else 0,
        "command_counts": counts,
        "ai_calls_total": total_ai_calls,
        "avg_response_ms": round(sum(recent_response_times) / len(recent_response_times), 1) if recent_response_times else 0
    }), 200


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive(bot=None):
    """Start the keep-alive server. Pass `bot` to enable /health and /stats."""
    if bot is not None:
        set_bot(bot)
    t = Thread(target=run, daemon=True)
    t.start()
