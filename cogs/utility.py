"""
cogs/utility.py — general utility commands (trimmed).

Kept: /math, /snipe, /afk, /reminders
Removed (to stay under Discord's 100-command limit): /password, /announce,
/weather (moved to weather.py), /encode, /decode, /timestamp, /editsnipe,
/color, /qr, /pin, /unpin.

PHASE 2 / PART 4 — recurring reminders:
  /remind create what:<text> when:<duration> [repeat:none|daily|weekly|monthly]
  /remind list            — your active reminders with ids
  /remind delete id:<n>   — cancel one (by id or position)
The firing loop lives in cogs/ai_chat.py (check_reminders) and snoozes
recurring reminders via utils.db.snooze_reminder instead of deleting.

Snipe cache: module-level dict storing up to 5 most recent deleted
messages per channel.
"""
import discord
import logging
from discord.ext import commands, tasks
from discord import app_commands
import ast
import math
import re
import time
import aiohttp
from datetime import datetime
from utils.constants import COLOR_INFO, COLOR_ERROR

log = logging.getLogger('cyn.utility')


# ==================== Safe math evaluator ====================
def _safe_math_eval(expression: str) -> float:
    allowed_nodes = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.BitOr, ast.BitAnd, ast.BitXor, ast.Invert,
        ast.LShift, ast.RShift, ast.Call, ast.Name, ast.Load,
    )
    allowed_funcs = {
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'sqrt': math.sqrt, 'pow': pow, 'log': math.log, 'log10': math.log10,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'floor': math.floor, 'ceil': math.ceil, 'factorial': math.factorial,
        'gcd': math.gcd, 'pi': math.pi, 'e': math.e,
    }
    tree = ast.parse(expression, mode='eval')
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"Disallowed expression element: {type(node).__name__}")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            ops = {
                ast.Add: left + right, ast.Sub: left - right,
                ast.Mult: left * right, ast.Div: left / right,
                ast.FloorDiv: left // right, ast.Mod: left % right,
                ast.Pow: left ** right,
                ast.BitOr: left | right, ast.BitAnd: left & right,
                ast.BitXor: left ^ right,
                ast.LShift: left << right, ast.RShift: left >> right,
            }
            return ops[type(node.op)]
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.Invert):
                return ~operand
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Call):
            func = allowed_funcs.get(node.func.id)
            if not func:
                raise ValueError(f"Function not allowed: {node.func.id}")
            args = [_eval(a) for a in node.args]
            return func(*args)
        if isinstance(node, ast.Name):
            if node.id in allowed_funcs:
                return allowed_funcs[node.id]
            raise ValueError(f"Unknown variable: {node.id}")
        raise ValueError(f"Cannot evaluate node: {type(node).__name__}")

    return _eval(tree)


# ==================== Snipe cache ====================
# FIX 1.4 — per-channel rolling cache of deleted messages.
#   * limit raised 5 → 10 per channel
#   * entries expire after SNIPE_TTL_SECONDS (5 minutes) — checked lazily
#     on write AND on /snipe, so nothing needs a background timer
#   * showing a snipe does NOT evict it; only the TTL removes entries
snipe_cache: dict = {}
SNAPE_MAX = 10
SNIPE_TTL_SECONDS = 300  # 5 minutes


def _prune_snipe_cache(cache: list):
    """Drop entries older than the TTL (in place). Lazy — called on write
    and on read, so no background loop is needed."""
    import datetime as _dt
    now = _dt.datetime.utcnow()
    cache[:] = [
        e for e in cache
        if isinstance(e, dict) and e.get('deleted_at')
        and (now - e['deleted_at']).total_seconds() <= SNIPE_TTL_SECONDS
    ]


# ==================== PHASE 2 / PART 4 — recurring reminders ====================

# Repeat intervals (seconds) — 'monthly' is the spec-fixed 30-day month.
REPEAT_INTERVALS = {
    "daily": 86400,
    "weekly": 604800,
    "monthly": 2592000,
}

# Duration parser: "30m", "2h", "1d", "1h30m", "2 days", "1.5h", "45" (min).
_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|"
    r"days?|d|weeks?|w)",
    re.IGNORECASE,
)
_DURATION_UNITS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "week": 604800, "weeks": 604800,
}
MIN_REMINDER_SECONDS = 10
MAX_REMINDER_SECONDS = 365 * 86400  # one year


def parse_duration(spec: str) -> int | None:
    """Parse a human duration into seconds, or None when invalid.

    Supports unit suffixes (s/m/h/d/w, full words), stacked segments
    ("1h30m"), floats ("1.5h"), and a bare number, which is treated as
    minutes ("45" -> 45 minutes). Range-checked 10s .. 365d."""
    if not spec or not str(spec).strip():
        return None
    text = str(spec).strip().lower()
    # Bare number -> minutes
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        total = float(text) * 60
    else:
        matches = _DURATION_RE.findall(text)
        if not matches:
            return None
        # Reject trailing junk (e.g. "10m later") by matching the whole
        # string against the pattern stripped of spaces.
        stripped = re.sub(r"\s+", "", text)
        rebuilt = "".join(f"{n}{u}" for n, u in matches)
        if stripped != rebuilt:
            return None
        total = 0.0
        for num, unit in matches:
            total += float(num) * _DURATION_UNITS[unit.lower()]
    seconds = int(round(total))
    if seconds < MIN_REMINDER_SECONDS or seconds > MAX_REMINDER_SECONDS:
        return None
    return seconds


def _format_remaining(seconds: int) -> str:
    """Compact human remaining-time string for reminder lists."""
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m or not parts:
        parts.append(f"{m}m")
    return " ".join(parts)


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # PHASE 1 / PART 4.1 — snipe entries are pruned lazily on write
        # and on read, but a channel that goes quiet after deletes kept
        # its (expired) entries forever. This 5-minute sweep drops every
        # expired entry and deletes now-empty channel keys so the module
        # dict stays bounded.
        if not self.snipe_cleanup.is_running():
            self.snipe_cleanup.start()

    def cog_unload(self):
        if self.snipe_cleanup.is_running():
            self.snipe_cleanup.cancel()

    @tasks.loop(minutes=5)
    async def snipe_cleanup(self):
        now = datetime.utcnow()
        pruned = 0
        for channel_id in list(snipe_cache.keys()):
            entries = snipe_cache.get(channel_id)
            if not entries:
                del snipe_cache[channel_id]
                continue
            keep = [
                e for e in entries
                if isinstance(e, dict) and e.get('deleted_at')
                and (now - e['deleted_at']).total_seconds() <= SNIPE_TTL_SECONDS
            ]
            pruned += len(entries) - len(keep)
            if keep:
                snipe_cache[channel_id] = keep
            else:
                del snipe_cache[channel_id]
        if pruned:
            import logging
            logging.getLogger('cyn.utility').debug(
                f"[SNIPE] pruned {pruned} expired entr{'y' if pruned == 1 else 'ies'}"
            )

    @snipe_cleanup.before_loop
    async def before_snipe_cleanup(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not message.content and not message.attachments:
            return
        entry = {
            'content': message.content or '',
            'author_id': message.author.id,
            'author_name': str(message.author),
            'author_avatar': message.author.avatar.url if message.author.avatar else None,
            'deleted_at': datetime.utcnow(),
            'attachments': [a.url for a in message.attachments],
        }
        cache = snipe_cache.setdefault(message.channel.id, [])
        _prune_snipe_cache(cache)
        cache.insert(0, entry)
        if len(cache) > SNAPE_MAX:
            cache[:] = cache[:SNAPE_MAX]

    @app_commands.command(name="math", description="Evaluate a math expression safely")
    async def math(self, interaction: discord.Interaction, expression: str):
        self.bot.increment_command('math')
        try:
            result = _safe_math_eval(expression)
            embed = discord.Embed(title="🧮 Math", color=COLOR_INFO)
            embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
            embed.add_field(name="Result", value=f"`{result}`", inline=False)
            try:
                await interaction.response.send_message(embed=embed)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed)
        except Exception as e:
            try:
                await interaction.response.send_message(f"couldn't evaluate: `{e}`", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(f"couldn't evaluate: `{e}`", ephemeral=True)

    @app_commands.command(name="snipe", description="Show a recently deleted message (1=most recent)")
    @app_commands.describe(index="Which deleted message to show (1=most recent, 10=oldest)")
    async def snipe(self, interaction: discord.Interaction, index: int = 1):
        self.bot.increment_command('snipe')
        cache = snipe_cache.get(interaction.channel.id, [])
        # FIX 1.4 — lazy TTL pruning, then show the most recent entry by
        # default (index 1). Showing does NOT evict; the TTL handles expiry.
        _prune_snipe_cache(cache)
        if not cache:
            try:
                await interaction.response.send_message(
                    "no recently deleted messages here (snipes expire after "
                    f"{SNIPE_TTL_SECONDS // 60} minutes).",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                pass
            return
        if index < 1 or index > len(cache):
            try:
                await interaction.response.send_message(
                    f"index out of range. only {len(cache)} snipe(s) cached "
                    f"(max {SNAPE_MAX}, newest first).",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                pass
            return
        entry = cache[index - 1]
        deleted_ts = entry['deleted_at']
        embed = discord.Embed(
            description=entry['content'][:2048] or "*empty*",
            color=COLOR_ERROR,
            timestamp=deleted_ts
        )
        embed.set_author(name=entry['author_name'], icon_url=entry.get('author_avatar'))
        # FIX 1.4 — show the deletion time in the footer (plus which snipe
        # of how many this is).
        embed.set_footer(
            text=(
                f"deleted {deleted_ts.strftime('%H:%M:%S')} UTC "
                f"· snipe {index} of {len(cache)}"
            )
        )
        if entry.get('attachments'):
            embed.add_field(name="Attachments", value="\n".join(entry['attachments'])[:1024], inline=False)
        try:
            await interaction.response.send_message(embed=embed)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed)

    # PHASE 1F — /reminders command to list your active reminders
    @app_commands.command(name="reminders",
                          description="List your active reminders")
    async def reminders_list(self, interaction: discord.Interaction):
        self.bot.increment_command('reminders')
        await interaction.response.defer(ephemeral=True)
        from utils.db import get_user_reminders

        user_reminders = get_user_reminders(interaction.user.id)

        if not user_reminders:
            await interaction.followup.send("no active reminders.")
            return

        lines = []
        for i, r in enumerate(user_reminders, 1):
            end_time = r.get("end_time", 0)
            try:
                remaining = max(0, int(end_time) - int(time.time()))
            except (TypeError, ValueError):
                remaining = 0
            text = r.get('text', 'no text')[:50]
            repeat = str(r.get('repeat_interval') or 'none').lower()
            badge = f" · 🔁 {repeat}" if repeat in REPEAT_INTERVALS else ""
            lines.append(f"`{i}.` {text} — in {_format_remaining(remaining)}{badge}")

        await interaction.followup.send(
            "**your reminders:**\n" + "\n".join(lines)
        )

    # ─── PHASE 2 / PART 4 — /remind group (create / list / delete) ──

    remind = app_commands.Group(
        name="remind", description="Set and manage reminders"
    )

    @remind.command(name="create", description="Set a reminder")
    @app_commands.describe(
        what="What to remind you about",
        when="How far from now — e.g. 30m, 2h, 1d, 1h30m (bare numbers = minutes)",
        repeat="Repeat the reminder (none / daily / weekly / monthly)",
    )
    @app_commands.choices(repeat=[
        app_commands.Choice(name="Once (no repeat)", value="none"),
        app_commands.Choice(name="Daily", value="daily"),
        app_commands.Choice(name="Weekly", value="weekly"),
        app_commands.Choice(name="Monthly", value="monthly"),
    ])
    async def remind_create(
        self, interaction: discord.Interaction,
        what: str,
        when: str,
        repeat: app_commands.Choice[str] = None,
    ):
        self.bot.increment_command('remind_create')
        if not what.strip():
            return await interaction.response.send_message(
                "tell me what to remind you about ♡", ephemeral=True
            )
        seconds = parse_duration(when)
        if seconds is None:
            return await interaction.response.send_message(
                "couldn't read that duration — try `30m`, `2h`, `1d`, or "
                "`1h30m` (between 10 seconds and 365 days).",
                ephemeral=True,
            )

        repeat_value = repeat.value if repeat else "none"
        from utils.db import add_reminder
        try:
            add_reminder(interaction.user.id, {
                'text': what.strip()[:500],
                'end_time': int(time.time()) + seconds,
                'channel_id': str(interaction.channel.id)
                    if interaction.channel else None,
                'repeat_interval': repeat_value,
            })
        except Exception as e:
            log.error(f"[remind] failed to save: {e}")
            return await interaction.response.send_message(
                "couldn't save that reminder — try again.", ephemeral=True
            )

        repeat_suffix = ""
        if repeat_value in REPEAT_INTERVALS:
            repeat_suffix = (f" and repeating **{repeat_value}** 🔁")
        await interaction.response.send_message(
            f"got it ♡ i'll remind you in {_format_remaining(seconds)}"
            f"{repeat_suffix}: *{what.strip()[:100]}*"
        )

    @remind.command(name="list", description="List your active reminders")
    async def remind_list(self, interaction: discord.Interaction):
        self.bot.increment_command('remind_list')
        await interaction.response.defer(ephemeral=True)
        from utils.db import get_user_reminders

        user_reminders = get_user_reminders(interaction.user.id)
        if not user_reminders:
            return await interaction.followup.send(
                "no active reminders — set one with `/remind create` ♡"
            )

        lines = []
        for i, r in enumerate(user_reminders, 1):
            end_time = r.get("end_time", 0)
            try:
                remaining = max(0, int(end_time) - int(time.time()))
            except (TypeError, ValueError):
                remaining = 0
            rid = r.get('id')
            text = r.get('text', 'no text')[:50]
            repeat = str(r.get('repeat_interval') or 'none').lower()
            badge = f" · 🔁 {repeat}" if repeat in REPEAT_INTERVALS else ""
            id_str = f"`#{rid}`" if rid is not None else f"`#{i}`"
            lines.append(
                f"{id_str} · {text} — in {_format_remaining(remaining)}{badge}"
            )

        await interaction.followup.send(
            "**your reminders:**\n" + "\n".join(lines)
            + "\n\ncancel one with `/remind delete id:` (the # number or "
              "its position in this list)"
        )

    @remind.command(name="delete", description="Cancel one of your reminders")
    @app_commands.describe(id="The # id from /remind list (or its position)")
    async def remind_delete(self, interaction: discord.Interaction, id: int):
        self.bot.increment_command('remind_delete')
        await interaction.response.defer(ephemeral=True)
        from utils.db import get_user_reminders, remove_reminder

        user_reminders = get_user_reminders(interaction.user.id)
        if not user_reminders:
            return await interaction.followup.send(
                "you have no active reminders."
            )

        # Match by the row's real id first (Supabase serial ids), then by
        # 1-based position (works for JSON-fallback rows whose ids are
        # composite strings).
        target = None
        for r in user_reminders:
            try:
                if int(r.get('id')) == id:
                    target = r
                    break
            except (TypeError, ValueError):
                continue
        if target is None and 1 <= id <= len(user_reminders):
            target = user_reminders[id - 1]
        if target is None:
            return await interaction.followup.send(
                f"no reminder with id `{id}` — check `/remind list`."
            )

        rid = target.get('id')
        try:
            remove_reminder(interaction.user.id, str(rid))
        except Exception:
            return await interaction.followup.send(
                "couldn't delete that reminder — try again."
            )
        text = str(target.get('text', ''))[:60]
        await interaction.followup.send(
            f"✅ deleted: *{text}*"
        )


async def setup(bot):
    await bot.add_cog(Utility(bot))
