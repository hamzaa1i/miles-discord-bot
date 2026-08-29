"""
cogs/ai_memory.py — PHASE 4 Feature 1: AI long-term memory commands.

The memory pipeline itself lives in cogs/ai_chat.py:
  - get_ai_response() injects remembered facts into the system prompt
  - _maybe_extract_facts() runs sampled background fact extraction and
    stores facts via utils.db (user_memory table / user_memory.json)

This cog exposes the user-facing controls:
  /memory show   — see what aurelia remembers about you (or about someone,
                   with manage_guild)
  /memory clear  — wipe your own remembered facts

Design notes:
  - Users can only view/clear their OWN memory; staff can view anyone.
  - Everything is per-guild (facts are scoped guild_id + user_id).
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.db import get_user_facts_async, clear_user_facts_async
from utils.veloura_embeds import veloura_embed, COLOR_LAVENDER, COLOR_PINK

logger = logging.getLogger('cyn.memory')


class AIMemory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    memory = app_commands.Group(
        name="memory",
        description="What aurelia remembers about you",
    )

    @memory.command(name="show", description="See what aurelia remembers about you")
    @app_commands.describe(user="Someone else's memory (staff only)")
    async def memory_show(self, interaction: discord.Interaction,
                          user: Optional[discord.Member] = None):
        self.bot.increment_command('memory_show')

        target = user or interaction.user
        # Privacy: viewing someone else's memory requires manage_guild
        if user and user.id != interaction.user.id:
            perms = interaction.user.guild_permissions
            if not (perms.manage_guild or perms.administrator):
                await interaction.response.send_message(
                    "you can only view your own memory.", ephemeral=True
                )
                return

        await interaction.response.defer(ephemeral=True)
        try:
            facts = await get_user_facts_async(interaction.guild.id, target.id)
        except Exception as e:
            logger.error(f"[memory] show failed: {e}")
            facts = []

        if not facts:
            embed = veloura_embed(
                "memory",
                f"i don't have anything stored about **{target.display_name}** yet.\n\n"
                f"talk to me more and i'll start remembering things ༉‧₊˚",
                COLOR_LAVENDER,
            )
        else:
            lines = "\n".join(
                f"✩ {str(f)[:200]}" for f in facts[:10]
            )
            embed = veloura_embed(
                "memory",
                f"things i remember about **{target.display_name}**:\n\n{lines}",
                COLOR_PINK,
            )
            embed.set_footer(
                text=f"{len(facts)} fact(s) • use /memory clear to wipe"
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @memory.command(name="clear", description="Erase everything aurelia remembers about you")
    async def memory_clear(self, interaction: discord.Interaction):
        self.bot.increment_command('memory_clear')
        await interaction.response.defer(ephemeral=True)

        # Users can only clear their OWN memory — no staff override,
        # because memory is personal data, not a moderation artifact.
        try:
            removed = await clear_user_facts_async(
                interaction.guild.id, interaction.user.id
            )
        except Exception as e:
            logger.error(f"[memory] clear failed: {e}")
            removed = 0

        if removed:
            embed = veloura_embed(
                "memory",
                f"done — forgot {removed} thing(s) about you.\n"
                f"clean slate ✦",
                COLOR_LAVENDER,
            )
        else:
            embed = veloura_embed(
                "memory",
                "i don't have anything stored about you anyway.",
                COLOR_LAVENDER,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AIMemory(bot))
