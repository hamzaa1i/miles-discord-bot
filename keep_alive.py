"""
keep_alive.py — Tracking variables for the /health endpoint.

FIX 1 — This module NO LONGER creates its own Flask app. main.py owns
the single Flask app that serves /, /health, and /stats on port 8080.
This module just stores the tracking variables that main.py and
ai_handler.py update, and that main.py's /health route reads.

Tracking variables:
  bot_ref              — the discord.Bot instance (set by main.py on_ready)
  start_time           — bot start time (set by main.py on_ready)
  total_ai_calls       — incremented by ai_handler.py on each successful AI call
  total_errors         — reserved for future error tracking
  recent_response_times — last 100 AI response times in ms
"""
from datetime import datetime

# FIX 1 — tracking variables (NO Flask app here anymore)
bot_ref = None
start_time = datetime.utcnow()
total_ai_calls = 0
total_errors = 0
recent_response_times = []  # last 100 response times in ms


def set_bot(bot):
    """Inject the bot instance so /health can read live data."""
    global bot_ref
    bot_ref = bot


def _format_uptime(seconds: float) -> str:
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    return f"{d}d {h}h {m}m"
