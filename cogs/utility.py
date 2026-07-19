"""
cogs/utility.py — general utility commands (trimmed).

Kept: /math, /snipe, /afk
Removed (to stay under Discord's 100-command limit): /password, /announce,
/weather (moved to weather.py), /encode, /decode, /timestamp, /editsnipe,
/color, /qr, /pin, /unpin.

Snipe cache: module-level dict storing up to 5 most recent deleted
messages per channel.
"""
import discord
from discord.ext import commands
from discord import app_commands
import ast
import math
import aiohttp
from datetime import datetime
from utils.constants import COLOR_INFO, COLOR_ERROR


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
snipe_cache: dict = {}
SNAPE_MAX = 5


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @app_commands.command(name="snipe", description="Show the nth most recent deleted message (1=most recent)")
    async def snipe(self, interaction: discord.Interaction, index: int = 1):
        self.bot.increment_command('snipe')
        cache = snipe_cache.get(interaction.channel.id, [])
        if not cache:
            try:
                await interaction.response.send_message("nothing to snipe here.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        if index < 1 or index > len(cache):
            try:
                await interaction.response.send_message(
                    f"index out of range. only {len(cache)} snipe(s) cached (max {SNAPE_MAX}).",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                pass
            return
        entry = cache[index - 1]
        embed = discord.Embed(
            description=entry['content'][:2048] or "*empty*",
            color=COLOR_ERROR,
            timestamp=entry['deleted_at']
        )
        embed.set_author(name=entry['author_name'], icon_url=entry.get('author_avatar'))
        embed.set_footer(
            text=f"Showing snipe {index} of {min(SNAPE_MAX, len(cache))} • This message was deleted"
        )
        if entry.get('attachments'):
            embed.add_field(name="Attachments", value="\n".join(entry['attachments']), inline=False)
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
        import time

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
            m, s = divmod(remaining, 60)
            h, m = divmod(m, 60)
            if h > 0:
                time_str = f"{h}h {m}m"
            elif m > 0:
                time_str = f"{m}m {s}s"
            else:
                time_str = f"{s}s"
            text = r.get('text', 'no text')[:50]
            lines.append(f"`{i}.` {text} - in {time_str}")

        await interaction.followup.send(
            "**your reminders:**\n" + "\n".join(lines)
        )


async def setup(bot):
    await bot.add_cog(Utility(bot))
