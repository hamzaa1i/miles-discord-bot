"""
utils/veloura_embeds.py — Veloura-styled embed helpers.

Soft pinks / lavenders, decorative kawaii accents, and a consistent
footer so every Veloura cog looks the same.

This is a utility module — no class, no setup().
Import helpers directly:
    from utils.veloura_embeds import (
        veloura_embed, announcement_embed,
        welcome_embed, goodbye_embed, level_up_embed,
        COLOR_PINK, COLOR_LAVENDER, COLOR_DEFAULT, FOOTER,
    )
"""
import discord
from datetime import datetime, timezone

# ─── Palette & footer ──────────────────────────────────────────
COLOR_PINK = 0xFFC0CB
COLOR_LAVENDER = 0xE6E6FA
COLOR_DEFAULT = 0xE6E6FA
FOOTER = "✩ ━━ aurelia ༉‧₊˚. ღ"


# ─── Core builder ──────────────────────────────────────────────

def veloura_embed(title="", description="", color=None):
    """Return a discord.Embed pre-styled with the Veloura look."""
    embed = discord.Embed(
        title=f"꒰ა ♡ ໒꒱ {title}" if title else None,
        description=description,
        color=color or COLOR_DEFAULT,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=FOOTER)
    return embed


def announcement_embed(title, description):
    """Pink announcement embed."""
    return veloura_embed(title, description, COLOR_PINK)


def welcome_embed(user, guild):
    """Welcome embed shown when a member joins."""
    desc = (
        f"꒰ა ♡ ໒꒱ welcome to **{guild.name}**!\n\n"
        f"hey {user.mention}, welcome in!\n"
        f"we're currently at **{guild.member_count} members**.\n\n"
        f"make sure to check the rules and roles channels.\n"
        f"enjoy your stay ༉‧₊˚. ღ"
    )
    embed = veloura_embed("welcome", desc, COLOR_PINK)
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    else:
        embed.set_thumbnail(url=user.default_avatar.url)
    return embed


def goodbye_embed(user, guild, duration="some time"):
    """Goodbye embed shown when a member leaves."""
    desc = (
        f"꒰ა ♡ ໒꒱ **goodbye**\n\n"
        f"**{user.display_name}** has left {guild.name}.\n"
        f"was here for {duration}.\n"
        f"we're now at **{guild.member_count} members**."
    )
    return veloura_embed("goodbye", desc, 0xFFB6C1)


def level_up_embed(user, level, role_name=None):
    """Level-up celebration embed."""
    desc = f"congrats {user.mention}!\nyou've reached **level {level}**"
    if role_name:
        desc += f" and unlocked **{role_name}**"
    desc += "\nkeep going ♡"
    return veloura_embed("level up!", desc, COLOR_PINK)
