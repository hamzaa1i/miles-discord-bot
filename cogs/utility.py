"""
cogs/utility.py — general utility commands.

NOTE: /ping, /uptime, /botinfo live in main.py to avoid conflicts.
/afk lives in cogs/afk.py.
/firstmessage lives in cogs/server_stats.py.
This cog adds: /weather, /math, /password, /encode, /decode, /timestamp,
/snipe, /editsnipe.

Snipe and editsnipe store data in memory (per-channel dicts on the cog).
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
import aiohttp
from datetime import datetime, timezone


def _safe_math_eval(expression: str) -> float:
    """Safely evaluate a math expression using ast. No eval()."""
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


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # In-memory snipe storage — per channel, latest only
        self.sniped_messages = {}     # channel_id -> {author, content, deleted_at}
        self.edited_messages = {}     # channel_id -> {author, before, after, edited_at}

    # ---- snipe listeners ----
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not message.content:
            return
        self.sniped_messages[message.channel.id] = {
            'author': message.author,
            'content': message.content,
            'deleted_at': datetime.utcnow(),
            'attachments': [a.url for a in message.attachments]
        }

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        self.edited_messages[before.channel.id] = {
            'author': before.author,
            'before': before.content,
            'after': after.content,
            'edited_at': datetime.utcnow(),
            'jump_url': after.jump_url,
        }

    @app_commands.command(name="weather", description="Get current weather for a city")
    async def weather(self, interaction: discord.Interaction, city: str):
        self.bot.increment_command('weather')
        await interaction.response.defer()
        embed = await self._fetch_weather_embed(city)
        await interaction.followup.send(embed=embed)

    async def _fetch_weather_embed(self, city: str) -> discord.Embed:
        """Helper used by both /weather and the intent parser."""
        try:
            url = f"https://wttr.in/{city}?format=j1"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200:
                        return discord.Embed(
                            description=f"couldn't fetch weather for {city} (status {r.status})",
                            color=0xff5555
                        )
                    data = await r.json()
            current = data.get('current_condition', [{}])[0]
            area = data.get('nearest_area', [{}])[0]
            temp = current.get('temp_C', '?')
            feels = current.get('FeelsLikeC', '?')
            humidity = current.get('humidity', '?')
            wind = current.get('windspeedKmph', '?')
            desc_list = current.get('weatherDesc', [{}])
            desc = desc_list[0].get('value', 'unknown') if desc_list else 'unknown'

            embed = discord.Embed(
                title=f"🌤️ Weather — {area.get('areaName', [{}])[0].get('value', city)}",
                color=0x1a1a2e
            )
            embed.add_field(name="Condition", value=desc, inline=True)
            embed.add_field(name="Temperature", value=f"{temp}°C (feels {feels}°C)", inline=True)
            embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
            embed.add_field(name="Wind", value=f"{wind} km/h", inline=True)
            embed.set_footer(text="data: wttr.in")
            return embed
        except Exception as e:
            return discord.Embed(
                description=f"couldn't fetch weather for {city}. ({e})",
                color=0xff5555
            )

    @app_commands.command(name="math", description="Evaluate a math expression safely")
    async def math(self, interaction: discord.Interaction, expression: str):
        self.bot.increment_command('math')
        try:
            result = _safe_math_eval(expression)
            embed = discord.Embed(
                title="🧮 Math",
                color=0x1a1a2e
            )
            embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
            embed.add_field(name="Result", value=f"`{result}`", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"couldn't evaluate: `{e}`", ephemeral=True)

    @app_commands.command(name="password", description="Generate a random secure password")
    async def password(self, interaction: discord.Interaction, length: int = 16):
        self.bot.increment_command('password')
        if length < 4 or length > 128:
            await interaction.response.send_message("length must be 4-128.", ephemeral=True)
            return
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        pw = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Send ephemeral so others can't see it
        await interaction.response.send_message(f"🔐 your password:\n```\n{pw}\n```", ephemeral=True)

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
            embed = discord.Embed(title=f"🔐 Encoded ({type.value})", color=0x1a1a2e)
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
            embed = discord.Embed(title=f"🔓 Decoded ({type.value})", color=0x1a1a2e)
            embed.add_field(name="Encoded", value=text[:1024], inline=False)
            embed.add_field(name="Decoded", value=f"```\n{decoded}\n```", inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"failed: {e}", ephemeral=True)

    @app_commands.command(name="timestamp", description="Get Discord timestamp formats for a date/time")
    async def timestamp(self, interaction: discord.Interaction, datetime_string: str):
        self.bot.increment_command('timestamp')
        # Try several formats
        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
        ]
        parsed = None
        for fmt in formats:
            try:
                parsed = datetime.strptime(datetime_string, fmt)
                break
            except ValueError:
                continue

        if parsed is None:
            # Try fromisoformat
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
        embed = discord.Embed(title="🕓 Timestamps", color=0x1a1a2e)
        embed.description = f"Parsed: `{parsed.isoformat()}` (unix: `{unix}`)"
        for name, val in formats_out:
            embed.add_field(name=name, value=f"`{val}` → {val}", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="snipe", description="Show the last deleted message in this channel")
    async def snipe(self, interaction: discord.Interaction):
        self.bot.increment_command('snipe')
        data = self.sniped_messages.get(interaction.channel.id)
        if not data:
            await interaction.response.send_message("nothing to snipe here.", ephemeral=True)
            return
        embed = discord.Embed(
            description=data['content'][:2048],
            color=0xff5555,
            timestamp=data['deleted_at']
        )
        embed.set_author(name=str(data['author']), icon_url=data['author'].avatar.url if data['author'].avatar else None)
        embed.set_footer(text="deleted message")
        if data.get('attachments'):
            embed.add_field(name="Attachments", value="\n".join(data['attachments']), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="editsnipe", description="Show the last edited message in this channel (before edit)")
    async def editsnipe(self, interaction: discord.Interaction):
        self.bot.increment_command('editsnipe')
        data = self.edited_messages.get(interaction.channel.id)
        if not data:
            await interaction.response.send_message("nothing to editsnipe here.", ephemeral=True)
            return
        embed = discord.Embed(color=0xffa500, timestamp=data['edited_at'])
        embed.set_author(name=str(data['author']), icon_url=data['author'].avatar.url if data['author'].avatar else None)
        embed.add_field(name="Before", value=data['before'][:1024] or "*empty*", inline=False)
        embed.add_field(name="After", value=data['after'][:1024] or "*empty*", inline=False)
        embed.add_field(name="Jump", value=f"[Click]({data['jump_url']})", inline=False)
        embed.set_footer(text="edited message")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))
