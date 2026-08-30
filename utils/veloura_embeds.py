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


# ─── PHASE 1 / PART 6.4 — Seasonal embed colors ─────────────────
def get_seasonal_color() -> int:
    """Return this month's accent color so new embeds drift with the
    seasons: winter blue (jan) → valentine pink (feb) → spring green
    (mar) → ... → winter lavender (dec).

    Used by the Phase 1 quick-win commands (/vibe /pick /askstars) and
    available to any future cog. Existing cogs keep their hardcoded
    colors — retroactive changes are out of scope."""
    month = datetime.utcnow().month
    colors = {
        1: 0xB0C4DE,   # january - winter blue
        2: 0xFFB6C1,   # february - valentine pink
        3: 0x98FB98,   # march - spring green
        4: 0xFFC0CB,   # april - pastel pink
        5: 0xDDA0DD,   # may - plum
        6: 0xFFD700,   # june - summer gold
        7: 0xFFA07A,   # july - warm coral
        8: 0xFF8C00,   # august - late summer
        9: 0xD2691E,   # september - autumn
        10: 0x8B4513,  # october - deep autumn
        11: 0xCD853F,  # november - warm brown
        12: 0xE6E6FA,  # december - winter lavender
    }
    return colors.get(month, 0xFFC0CB)


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
