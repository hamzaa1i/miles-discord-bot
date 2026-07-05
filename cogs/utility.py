"""
cogs/utility.py — general utility commands.

Includes: /math, /password, /encode, /decode, /timestamp,
/snipe, /editsnipe, /urban, /color, /qr, /announce, /pin, /unpin.

NOTE: /weather is in cogs/weather.py to avoid command-name conflict.
      /ping, /uptime, /botinfo live in main.py.
      /afk lives in cogs/afk.py.
      /firstmessage lives in cogs/server_stats.py.

Snipe cache (POLISH 7): module-level dict storing up to 5 most recent
deleted messages per channel.
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import ast
import math
import secrets
import string
import base64
import binascii
import io
import aiohttp
import qrcode
from datetime import datetime, timezone
from PIL import Image, ImageDraw
from utils.constants import COLOR_INFO, COLOR_SUCCESS, COLOR_ERROR, COLOR_DEFAULT
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


# ==================== Snipe cache (POLISH 7) ====================
# Module-level dicts: channel_id -> list of entries (most recent first, max 5)
snipe_cache: dict = {}       # deleted messages
edit_snipe_cache: dict = {}  # edited messages
SNAPE_MAX = 5


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==================== Snipe listeners ====================
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        # POLISH 5 — anti-crash guards
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

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        entry = {
            'before': before.content or '',
            'after': after.content or '',
            'author_id': before.author.id,
            'author_name': str(before.author),
            'author_avatar': before.author.avatar.url if before.author.avatar else None,
            'edited_at': datetime.utcnow(),
            'jump_url': after.jump_url,
        }
        cache = edit_snipe_cache.setdefault(before.channel.id, [])
        cache.insert(0, entry)
        if len(cache) > SNAPE_MAX:
            cache[:] = cache[:SNAPE_MAX]

    # ==================== Math ====================
    @app_commands.command(name="math", description="Evaluate a math expression safely")
    async def math(self, interaction: discord.Interaction, expression: str):
        self.bot.increment_command('math')
        try:
            result = _safe_math_eval(expression)
            embed = discord.Embed(title="🧮 Math", color=COLOR_INFO)
            embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
            embed.add_field(name="Result", value=f"`{result}`", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            try:
                await interaction.response.send_message(f"couldn't evaluate: `{e}`", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(f"couldn't evaluate: `{e}`", ephemeral=True)

    # ==================== Password ====================
    @app_commands.command(name="password", description="Generate a random secure password")
    async def password(self, interaction: discord.Interaction, length: int = 16):
        self.bot.increment_command('password')
        if length < 4 or length > 128:
            await interaction.response.send_message("length must be 4-128.", ephemeral=True)
            return
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        pw = ''.join(secrets.choice(alphabet) for _ in range(length))
        await interaction.response.send_message(f"🔐 your password:\n```\n{pw}\n```", ephemeral=True)

    # ==================== Encode / Decode ====================
    @app_commands.command(name="encode", description="Encode text to base64 / binary / hex")
    @app_commands.choices(type=[
        app_commands.Choice(name="Base64", value="base64"),
        app_commands.Choice(name="Binary", value="binary"),
        app_commands.Choice(name="Hex", value="hex"),
    ])
    async def encode(self, interaction: discord.Interaction, type: app_commands.Choice[str], text: str):
        self.bot.increment_command('encode')
        try:
            if type.value == 'base64':
                encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
            elif type.value == 'binary':
                encoded = ' '.join(format(b, '08b') for b in text.encode('utf-8'))
            elif type.value == 'hex':
                encoded = text.encode('utf-8').hex()
            else:
                encoded = 'unknown type'
            if len(encoded) > 1900:
                encoded = encoded[:1900] + '\n... (truncated)'
            embed = discord.Embed(title=f"🔐 Encoded ({type.value})", color=COLOR_INFO)
            embed.add_field(name="Original", value=text[:1024], inline=False)
            embed.add_field(name="Encoded", value=f"```\n{encoded}\n```", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"failed: {e}", ephemeral=True)

    @app_commands.command(name="decode", description="Decode from base64 / binary / hex")
    @app_commands.choices(type=[
        app_commands.Choice(name="Base64", value="base64"),
        app_commands.Choice(name="Binary", value="binary"),
        app_commands.Choice(name="Hex", value="hex"),
    ])
    async def decode(self, interaction: discord.Interaction, type: app_commands.Choice[str], text: str):
        self.bot.increment_command('decode')
        try:
            if type.value == 'base64':
                decoded = base64.b64decode(text).decode('utf-8', errors='replace')
            elif type.value == 'binary':
                bits = text.replace(' ', '').replace('\n', '')
                decoded = ''.join(
                    chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8) if len(bits[i:i+8]) == 8
                )
            elif type.value == 'hex':
                decoded = binascii.unhexlify(text.replace(' ', '')).decode('utf-8', errors='replace')
            else:
                decoded = 'unknown type'
            if len(decoded) > 1900:
                decoded = decoded[:1900] + '\n... (truncated)'
            embed = discord.Embed(title=f"🔓 Decoded ({type.value})", color=COLOR_INFO)
            embed.add_field(name="Encoded", value=text[:1024], inline=False)
            embed.add_field(name="Decoded", value=f"```\n{decoded}\n```", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"failed: {e}", ephemeral=True)

    # ==================== Timestamp ====================
    @app_commands.command(name="timestamp", description="Get Discord timestamp formats for a date/time")
    async def timestamp(self, interaction: discord.Interaction, datetime_string: str):
        self.bot.increment_command('timestamp')
        formats = [
            "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M",
            "%d/%m/%Y", "%m/%d/%Y %H:%M", "%m/%d/%Y",
        ]
        parsed = None
        for fmt in formats:
            try:
                parsed = datetime.strptime(datetime_string, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(datetime_string)
            except Exception:
                await interaction.response.send_message(
                    "couldn't parse that. try formats like `2025-01-30 14:30` or `30/01/2025 14:30:00`.",
                    ephemeral=True
                )
                return
        unix = int(parsed.timestamp())
        formats_out = [
            ("Short time", f"<t:{unix}:t>"),
            ("Long time", f"<t:{unix}:T>"),
            ("Short date", f"<t:{unix}:d>"),
            ("Long date", f"<t:{unix}:D>"),
            ("Short date/time", f"<t:{unix}:f>"),
            ("Long date/time", f"<t:{unix}:F>"),
            ("Relative", f"<t:{unix}:R>"),
        ]
        embed = discord.Embed(title="🕓 Timestamps", color=COLOR_INFO)
        embed.description = f"Parsed: `{parsed.isoformat()}` (unix: `{unix}`)"
        for name, val in formats_out:
            embed.add_field(name=name, value=f"`{val}` → {val}", inline=False)
        await interaction.response.send_message(embed=embed)

    # ==================== Snipe (POLISH 7 — index-based) ====================
    @app_commands.command(name="snipe", description="Show the nth most recent deleted message (1=most recent)")
    async def snipe(self, interaction: discord.Interaction, index: int = 1):
        self.bot.increment_command('snipe')
        cache = snipe_cache.get(interaction.channel.id, [])
        if not cache:
            await interaction.response.send_message("nothing to snipe here.", ephemeral=True)
            return
        if index < 1 or index > len(cache):
            await interaction.response.send_message(
                f"index out of range. only {len(cache)} snipe(s) cached (max {SNAPE_MAX}).",
                ephemeral=True
            )
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
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="editsnipe", description="Show the nth most recent edited message (1=most recent)")
    async def editsnipe(self, interaction: discord.Interaction, index: int = 1):
        self.bot.increment_command('editsnipe')
        cache = edit_snipe_cache.get(interaction.channel.id, [])
        if not cache:
            await interaction.response.send_message("nothing to editsnipe here.", ephemeral=True)
            return
        if index < 1 or index > len(cache):
            await interaction.response.send_message(
                f"index out of range. only {len(cache)} edit-snipe(s) cached (max {SNAPE_MAX}).",
                ephemeral=True
            )
            return
        entry = cache[index - 1]
        embed = discord.Embed(color=0xfee75c, timestamp=entry['edited_at'])
        embed.set_author(name=entry['author_name'], icon_url=entry.get('author_avatar'))
        embed.add_field(name="Before", value=entry['before'][:1024] or "*empty*", inline=False)
        embed.add_field(name="After", value=entry['after'][:1024] or "*empty*", inline=False)
        embed.add_field(name="Jump", value=f"[Click]({entry['jump_url']})", inline=False)
        embed.set_footer(
            text=f"Showing edit-snipe {index} of {min(SNAPE_MAX, len(cache))} • This message was edited"
        )
        await interaction.response.send_message(embed=embed)

    # ==================== Urban Dictionary ====================
    @app_commands.command(name="urban", description="Look up a word on Urban Dictionary")
    async def urban(self, interaction: discord.Interaction, word: str):
        self.bot.increment_command('urban')
        await interaction.response.defer()
        try:
            url = f"https://api.urbandictionary.com/v0/define?term={word}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200:
                        await interaction.followup.send(
                            f"couldn't reach urban dictionary (status {r.status})."
                        )
                        return
                    data = await r.json()
            items = data.get('list', [])
            if not items:
                await interaction.followup.send(f"no results for `{word}`.")
                return
            top = items[0]
            definition = (top.get('definition') or '')[:500]
            example = (top.get('example') or '')[:300]
            thumbs_up = top.get('thumbs_up', 0)
            permalink = top.get('permalink', '')

            embed = discord.Embed(
                title=f"📖 {top.get('word', word)}",
                url=permalink,
                color=COLOR_INFO
            )
            embed.add_field(name="Definition", value=definition or "*no definition*", inline=False)
            if example:
                embed.add_field(name="Example", value=example, inline=False)
            embed.set_footer(text=f"👍 {thumbs_up} • Urban Dictionary")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"couldn't fetch definition: {e}")

    # ==================== Color ====================
    @app_commands.command(name="color", description="Show a color swatch from a hex code")
    async def color(self, interaction: discord.Interaction, hex_code: str):
        self.bot.increment_command('color')
        # Normalize: accept #FF5733 or FF5733
        clean = hex_code.lstrip('#').strip()
        if len(clean) == 3:
            clean = ''.join(c * 2 for c in clean)
        if len(clean) != 6 or not all(c in '0123456789abcdefABCDEF' for c in clean):
            await interaction.response.send_message(
                "invalid hex. use formats like `#FF5733` or `FF5733`.", ephemeral=True
            )
            return
        r = int(clean[0:2], 16)
        g = int(clean[2:4], 16)
        b = int(clean[4:6], 16)
        int_color = (r << 16) | (g << 8) | b

        # Generate 100x100 solid color PNG
        img = Image.new('RGB', (100, 100), (r, g, b))
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        buf.seek(0)
        file = discord.File(buf, filename='color.png')

        embed = discord.Embed(title=f"🎨 #{clean.upper()}", color=int_color)
        embed.add_field(name="Hex", value=f"`#{clean.upper()}`", inline=True)
        embed.add_field(name="RGB", value=f"`{r}, {g}, {b}`", inline=True)
        embed.set_thumbnail(url="attachment://color.png")
        await interaction.response.send_message(embed=embed, file=file)

    # ==================== QR code ====================
    @app_commands.command(name="qr", description="Generate a QR code from text")
    async def qr(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('qr')
        try:
            qr_obj = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr_obj.add_data(text)
            qr_obj.make(fit=True)
            img = qr_obj.make_image(fill_color='black', back_color='white')
            buf = io.BytesIO()
            img.save(buf, 'PNG')
            buf.seek(0)
            file = discord.File(buf, filename='qr.png')
            embed = discord.Embed(title="🔳 QR Code", color=COLOR_INFO)
            embed.set_image(url="attachment://qr.png")
            embed.add_field(name="Content", value=f"`{text[:200]}`", inline=False)
            await interaction.response.send_message(embed=embed, file=file)
        except Exception as e:
            try:
                await interaction.response.send_message(f"couldn't generate QR: {e}", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(f"couldn't generate QR: {e}", ephemeral=True)

    # ==================== Announce ====================
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
            await interaction.response.send_message(
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

    # ==================== Pin / Unpin ====================
    @app_commands.command(name="pin", description="Pin a message by ID in the current channel")
    @is_mod()
    async def pin(self, interaction: discord.Interaction, message_id: str):
        self.bot.increment_command('pin')
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            await msg.pin()
            await interaction.response.send_message("📌 pinned.", ephemeral=True)
        except discord.NotFound:
            try:
                await interaction.response.send_message("message not found in this channel.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("message not found in this channel.", ephemeral=True)
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission to pin messages.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("i don't have permission to pin messages.", ephemeral=True)

    @app_commands.command(name="unpin", description="Unpin a message by ID in the current channel")
    @is_mod()
    async def unpin(self, interaction: discord.Interaction, message_id: str):
        self.bot.increment_command('unpin')
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            await msg.unpin()
            await interaction.response.send_message("📌 unpinned.", ephemeral=True)
        except discord.NotFound:
            try:
                await interaction.response.send_message("message not found in this channel.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("message not found in this channel.", ephemeral=True)
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission to unpin messages.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("i don't have permission to unpin messages.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Utility(bot))
