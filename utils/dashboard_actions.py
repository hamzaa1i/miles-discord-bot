"""
utils/dashboard_actions.py — Bot-to-dashboard action bridge.

The Flask API (utils/dashboard_api.py) runs in its own thread and can't
safely touch the discord.py event loop. When the dashboard asks for a
live bot action (post QOTD now, send a test welcome, end a giveaway,
reload a cog, ...), the Flask endpoint simply puts a payload on this
queue and returns {queued: true} immediately.

A worker coroutine on the bot's event loop polls the queue every 5
seconds (per spec) and executes the action with full access to the bot.

Design deviation from the spec (documented): the spec drafted
"an asyncio.Queue in main.py". An asyncio.Queue is NOT safe to put()
from the Flask worker thread (it would need loop.call_soon_threadsafe
for every enqueue and raises if the loop is busy/closed). A plain
thread-safe queue.Queue gives the exact same semantics — FIFO, size
bounded, poll-consumed — safely from both threads. The queue is still
importable from main.py under the spec's name:
    from utils.dashboard_actions import dashboard_action_queue

Action payload shape (dict):
    {
      "type": "qotd_post_now" | "welcome_test" | "giveaway_end" |
              "purge_cache" | "reload_cog" | "sync_commands" |
              "blacklist_user",
      "guild_id": "123",            # str, target guild
      "user_id": "456",             # str, requesting dashboard user
      "params": { ... },            # action-specific
      "enqueued_at": epoch,         # set by enqueue()
    }

Every action returns {"ok": bool, "detail": str}. Results are logged
(and audited on the Flask side at enqueue time) — the HTTP response is
always {queued: true} because execution happens up to ~5s later.
"""
import asyncio
import logging
import os
import queue as _queue
import time

logger = logging.getLogger('cyn.dashboard_actions')

# Thread-safe FIFO — Flask thread puts, bot loop gets. Bounded so a
# runaway dashboard can never balloon memory.
dashboard_action_queue: "_queue.Queue[dict]" = _queue.Queue(maxsize=100)

# Owner-only action types (Flask side checks the requester id BEFORE
# enqueueing; the executor double-checks at run time).
OWNER_ACTIONS = {"reload_cog", "sync_commands", "blacklist_user", "purge_all_caches"}

_worker_task: asyncio.Task | None = None

# cog name -> exact class name used with bot.get_cog(...)
_COG_CLASS_NAMES = {
    "qotd": "QOTD",
    "welcome": "Welcome",
    "giveaways": "Giveaways",
    "leveling": "Leveling",
    "starboard": "Starboard",
    "ai_automod": "AIAutoMod",
    "custom_commands": "CustomCommands",
}


def enqueue_action(action: dict) -> bool:
    """Thread-safe put. Returns False when the queue is full (dashboard
    should report 503-ish backpressure instead of pretending success)."""
    payload = dict(action)
    payload.setdefault("enqueued_at", time.time())
    try:
        dashboard_action_queue.put_nowait(payload)
        return True
    except _queue.Full:
        logger.warning("[dashboard] action queue full — dropping action "
                       f"{payload.get('type')}")
        return False


async def start_dashboard_action_worker(bot) -> None:
    """Start the background poller on the bot's loop (idempotent)."""
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_worker(bot), name="dashboard_actions")
    logger.info("✅ Dashboard action worker started (5s poll)")


async def _worker(bot) -> None:
    await bot.wait_until_ready()
    while not bot.is_closed():
        drained = 0
        try:
            while True:
                try:
                    action = dashboard_action_queue.get_nowait()
                except _queue.Empty:
                    break
                drained += 1
                try:
                    result = await execute_dashboard_action(bot, action)
                    logger.info(
                        "[dashboard] action %s for guild %s -> %s",
                        action.get("type"), action.get("guild_id"), result,
                    )
                except Exception as e:
                    logger.error(
                        "[dashboard] action %s crashed: %s",
                        action.get("type"), e, exc_info=True,
                    )
        except Exception as e:
            logger.error(f"[dashboard] action worker loop error: {e}")
        # Poll cadence: every 5 seconds (per spec). If we just drained
        # actions, yield immediately so a burst isn't stuck behind sleep.
        await asyncio.sleep(0.05 if drained else 5)


async def execute_dashboard_action(bot, action: dict) -> dict:
    """Run one dashboard action. Never raises — returns a result dict."""
    atype = str(action.get("type", ""))
    guild_id = str(action.get("guild_id", "") or "")
    user_id = str(action.get("user_id", "") or "")
    params = action.get("params") or {}

    if atype in OWNER_ACTIONS:
        owner = str(os.getenv("OWNER_ID", "0"))
        if not owner or user_id != owner:
            return {"ok": False, "detail": "owner-only action"}

    if atype == "purge_cache":
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if guild is None:
            return {"ok": False, "detail": "guild not found"}
        from utils.cache import cache
        cache.invalidate_prefix_sync(f"gs:")
        return {"ok": True, "detail": f"guild settings cache purged ({guild.name})"}

    if atype == "purge_all_caches":
        from utils.cache import cache
        before = cache.stats()["size"]
        cache.invalidate_prefix_sync("gs:")
        cache.invalidate_prefix_sync("pers:")
        cache.invalidate_prefix_sync("facts:")
        return {"ok": True, "detail": f"purged hot-path caches ({before} entries)"}

    # ── Guild-scoped actions below need a real guild object ─────────
    guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
    if guild is None:
        return {"ok": False, "detail": "aurelia is not in that guild"}

    if atype == "qotd_add":
        question = str(params.get("question", "") or "").strip()
        if not question or len(question) > 300:
            return {"ok": False, "detail": "question required (max 300 chars)"}
        from utils.db import add_qotd_question_async
        await add_qotd_question_async(guild_id, question, added_by=user_id)
        return {"ok": True, "detail": "question added to the queue"}

    if atype == "qotd_post_now":
        cog = bot.get_cog("QOTD")
        if cog is None:
            return {"ok": False, "detail": "QOTD cog not loaded"}
        from utils.db import get_qotd_settings_async
        from datetime import datetime
        settings = await get_qotd_settings_async(guild_id)
        channel_id = settings.get("channel_id")
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if channel is None:
            return {"ok": False, "detail": "qotd channel not configured/missing"}
        ok = await cog._post_qotd(guild, channel, settings, datetime.utcnow())
        return {"ok": bool(ok), "detail": "posted" if ok else "post failed (permissions?)"}

    if atype == "welcome_test":
        cog = bot.get_cog("Welcome")
        if cog is None:
            return {"ok": False, "detail": "Welcome cog not loaded"}
        config = cog.get_config(guild.id)
        kind = str(params.get("type", "welcome"))
        if kind == "goodbye":
            cid = config.get("goodbye_channel_id") or config.get("channel_id")
        else:
            cid = config.get("channel_id")
        channel = guild.get_channel(int(cid)) if cid else None
        if channel is None:
            return {"ok": False, "detail": f"{kind} channel not configured/missing"}
        member = guild.get_member(int(user_id)) if user_id.isdigit() else None
        if member is None:
            member = guild.owner
        try:
            ok = await cog._send_welcome_message(
                channel, config, member, guild, is_goodbye=(kind == "goodbye")
            )
        except Exception as e:
            return {"ok": False, "detail": f"send failed: {e}"}
        return {"ok": bool(ok), "detail": f"test {kind} sent to #{channel.name}"}

    if atype == "giveaway_end":
        cog = bot.get_cog("Giveaways")
        if cog is None:
            return {"ok": False, "detail": "Giveaways cog not loaded"}
        gw_id = str(params.get("giveaway_id", "") or "")
        if not gw_id:
            return {"ok": False, "detail": "giveaway_id required"}
        from utils.db import get_giveaway
        gw = get_giveaway(gw_id)
        if not gw or str(gw.get("guild_id")) != guild_id:
            return {"ok": False, "detail": "giveaway not found in this guild"}
        if gw.get("ended"):
            return {"ok": False, "detail": "giveaway already ended"}
        await cog._end_giveaway(gw, force=True)
        return {"ok": True, "detail": f"giveaway {gw_id} ended"}

    if atype == "reload_cog":
        import re
        name = str(params.get("cog", "") or "")
        if not re.fullmatch(r"[a-z0-9_]{1,40}", name):
            return {"ok": False, "detail": "invalid cog name"}
        try:
            await bot.reload_extension(f"cogs.{name}")
            return {"ok": True, "detail": f"reloaded cogs.{name}"}
        except Exception as e:
            return {"ok": False, "detail": f"reload failed: {type(e).__name__}: {e}"}

    if atype == "sync_commands":
        synced_total = 0
        for g in bot.guilds:
            try:
                bot.tree.copy_global_to(guild=g)
                synced = await bot.tree.sync(guild=g)
                synced_total += len(synced)
            except Exception:
                pass
        return {"ok": True, "detail": f"synced to {len(bot.guilds)} guilds ({synced_total} commands)"}

    if atype == "blacklist_user":
        # Records the blacklist row (owner_blacklist table). Enforcement
        # hooks are deliberately NOT wired into existing cogs — Section 1
        # of the task forbids modifying bot behavior; this is storage +
        # audit only, ready for a future enforcement patch.
        target = str(params.get("user_id", "") or "")
        remove = bool(params.get("remove", False))
        if not target.isdigit():
            return {"ok": False, "detail": "user_id required"}
        try:
            from utils.db import get_supabase
            sb = get_supabase()
            if sb:
                if remove:
                    sb.table("owner_blacklist").delete().eq(
                        "user_id", target).execute()
                else:
                    sb.table("owner_blacklist").upsert({
                        "user_id": target,
                        "added_by": user_id,
                    }).execute()
            return {"ok": True, "detail": (
                f"user {target} {'removed from' if remove else 'added to'} blacklist")}
        except Exception as e:
            return {"ok": False, "detail": f"blacklist write failed: {e}"}

    return {"ok": False, "detail": f"unknown action type: {atype}"}
