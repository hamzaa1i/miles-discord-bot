"""
cogs/utility.py — general utility commands (trimmed).

Kept: /math, /password, /snipe, /urban, /announce
Removed (to stay under Discord's 100-command limit): /weather (moved to
weather.py), /encode, /decode, /timestamp, /editsnipe, /color, /qr,
/pin, /unpin.

Snipe cache: module-level dict storing up to 5 most recent deleted
messages per channel.
"""
import discord
from discord.ext import commands
from discord import app_commands
import ast
import math
import secrets
import string
import aiohttp
from datetime import datetime
from utils.constants import COLOR_INFO, COLOR_ERROR
from utils.checks import is_mod


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

    @app_commands.command(name="password", description="Generate a random secure password")
    async def password(self, interaction: discord.Interaction, length: int = 16):
        self.bot.increment_command('password')
        if length < 4 or length > 128:
            try:
                await interaction.response.send_message("length must be 4-128.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        pw = ''.join(secrets.choice(alphabet) for _ in range(length))
        try:
            await interaction.response.send_message(f"🔐 your password:\n```\n{pw}\n```", ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(f"🔐 your password:\n```\n{pw}\n```", ephemeral=True)

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


    @app_commands.command(name="announce", description="Send an announcement embed to a channel")
    @is_mod()
    async def announce(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        message: str
    ):
        self.bot.increment_command('announce')
        embed = discord.Embed(
            title=title,
            description=message,
            color=COLOR_INFO,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Announced by {interaction.user} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        try:
            await channel.send(embed=embed)
            try:
                await interaction.response.send_message(
                    f"✅ announcement sent to {channel.mention}.", ephemeral=True
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    f"✅ announcement sent to {channel.mention}.", ephemeral=True
                )
        except discord.Forbidden:
            try:
                await interaction.response.send_message(
                    "i don't have permission to send to that channel.", ephemeral=True
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "i don't have permission to send to that channel.", ephemeral=True
                )





async def setup(bot):
    await bot.add_cog(Utility(bot))
