"""
cogs/custom_commands.py — PHASE 4 Feature 6: custom trigger→response
commands (Mimu's most-used feature).

Staff define a trigger and a response; anyone in the server can then type
the trigger and aurelia replies with the rendered response.

  /custom add trigger:"hi veloura" response:"welcome home {user} ♡"
  /custom remove trigger:"hi veloura"
  /custom list

Matching: case-insensitive; matches when the message IS the trigger or
STARTS with the trigger followed by a space (so "hi veloura!!" doesn't
fire but "hi veloura everyone" does).

Tags (same family as the welcome system — safe .replace, never .format):
  {user} {user.name} {user.id} {user.avatar}
  {server} {server.id} {membercount}
Plus \\n for line breaks.

Performance: the trigger table is cached per guild in memory (lazy load,
invalidated on add/remove) so the on_message hot path does ZERO database
reads — it's a dict lookup that returns instantly for servers with no
custom commands.
"""
import logging
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from utils.db import get_guild_setting, set_guild_setting
from utils.veloura_embeds import veloura_embed, COLOR_LAVENDER, COLOR_PINK

logger = logging.getLogger('cyn.custom')

MAX_CUSTOM_COMMANDS = 50


class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {guild_id: {trigger_lower: entry}} — in-memory cache, lazy loaded
        self._cache = {}
        # guilds known to have no custom commands (skip hot-path entirely)
        self._empty_guilds = set()

    # ─── storage ─────────────────────────────────────────────────

    def _build_table(self, guild_id: int) -> dict:
        """Blocking: read custom commands for a guild into a trigger table."""
        cfg = get_guild_setting(guild_id, "custom_commands")
        commands_list = cfg.get("commands", []) if isinstance(cfg, dict) else []
        if not isinstance(commands_list, list):
            commands_list = []
        table = {}
        for entry in commands_list:
            if isinstance(entry, dict) and entry.get("trigger"):
                table[str(entry["trigger"]).strip().lower()] = entry
        return table

    async def _aload_triggers(self, guild_id: int) -> dict:
        """Async: load (and cache) the trigger table — never blocks the loop."""
        if guild_id in self._cache:
            return self._cache[guild_id]
        table = await asyncio.to_thread(self._build_table, guild_id)
        self._cache[guild_id] = table
        if not table:
            self._empty_guilds.add(guild_id)
        return table

    async def _asave_triggers(self, guild_id: int, table: dict):
        """Async: persist + cache the trigger table."""
        self._cache[guild_id] = table
        if table:
            self._empty_guilds.discard(guild_id)
        else:
            self._empty_guilds.add(guild_id)
        await asyncio.to_thread(
            set_guild_setting, guild_id, "custom_commands",
            {"commands": list(table.values())},
        )

    # ─── tag rendering (safe .replace, never .format) ────────────

    @staticmethod
    def _render(response: str, member: discord.Member,
                guild: discord.Guild) -> str:
        text = str(response)
        text = text.replace("\\n", "\n")
        text = text.replace("{user.name}", str(member.name))
        text = text.replace("{user.id}", str(member.id))
        text = text.replace("{user.avatar}", str(member.display_avatar.url))
        text = text.replace("{user}", member.mention)
        text = text.replace("{server.id}", str(guild.id))
        if guild.icon:
            text = text.replace("{server.icon}", str(guild.icon.url))
        else:
            text = text.replace("{server.icon}", "")
        text = text.replace("{server}", str(guild.name))
        text = text.replace("{membercount}", str(guild.member_count))
        return text[:2000]

    # ─── listener (hot path — zero DB reads) ─────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.author.bot or not message.guild:
                return
            guild_id = message.guild.id
            if guild_id in self._empty_guilds:
                return
            table = await self._aload_triggers(guild_id)
            if not table:
                return
            content = message.content.strip().lower()
            if not content:
                return
            # exact match first (O(1)), then prefix match for multi-word
            # triggers: "hi veloura" also fires on "hi veloura everyone"
            entry = table.get(content)
            if entry is None:
                for trig, e in table.items():
                    if ' ' in trig and content.startswith(trig + ' '):
                        entry = e
                        break
            if entry is None:
                return
            # re-check permission to speak here
            perms = message.channel.permissions_for(message.guild.me)
            if not perms.send_messages:
                return
            rendered = self._render(entry.get("response", ""), message.author,
                                    message.guild)
            if rendered:
                # bumps the usage counter asynchronously (best effort)
                entry["uses"] = int(entry.get("uses", 0)) + 1
                await message.channel.send(rendered)
                # persist counter occasionally without blocking the reply
                asyncio.create_task(self._persist_uses(guild_id))
        except Exception as e:
            logger.error(f"[custom] on_message error: {type(e).__name__}: {e}")

    async def _persist_uses(self, guild_id: int):
        try:
            table = self._cache.get(guild_id)
            if table is not None:
                await asyncio.to_thread(
                    set_guild_setting, guild_id, "custom_commands",
                    {"commands": list(table.values())},
                )
        except Exception as e:
            logger.debug(f"[custom] persist uses failed: {e}")

    # ─── commands ────────────────────────────────────────────────

    custom = app_commands.Group(
        name="custom",
        description="Custom trigger commands",
    )

    @custom.command(name="add", description="Add a custom command")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        trigger="What people type (e.g. hi veloura)",
        response="What i reply — tags: {user} {user.name} {server} {membercount}",
    )
    async def custom_add(self, interaction: discord.Interaction,
                         trigger: str, response: str):
        self.bot.increment_command('custom_add')
        trigger_clean = trigger.strip().lower()[:100]
        if not trigger_clean or len(trigger_clean) < 2:
            await interaction.response.send_message(
                "trigger needs to be at least 2 characters.", ephemeral=True
            )
            return
        # forbid command prefixes and bare moderation keywords that would
        # collide with the AI intent parser / prefix commands
        if trigger_clean.startswith(('!', '/', '-')):
            await interaction.response.send_message(
                "triggers can't start with !, / or -.", ephemeral=True
            )
            return
        if trigger_clean in {'ban', 'kick', 'mute', 'warn', 'purge',
                             'lock', 'unlock'}:
            await interaction.response.send_message(
                "that trigger collides with built-in commands — pick another.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        table = await self._aload_triggers(interaction.guild.id)
        if trigger_clean not in table and len(table) >= MAX_CUSTOM_COMMANDS:
            await interaction.followup.send(
                f"limit reached — {MAX_CUSTOM_COMMANDS} custom commands max.",
                ephemeral=True,
            )
            return
        table[trigger_clean] = {
            'trigger': trigger_clean,
            'response': response[:2000],
            'created_by': str(interaction.user.id),
            'created_by_name': interaction.user.display_name,
            'uses': 0,
        }
        await self._asave_triggers(interaction.guild.id, table)
        preview = self._render(response, interaction.user, interaction.guild)
        embed = veloura_embed(
            "custom command",
            (
                f"**trigger:** `{trigger_clean}`\n"
                f"**preview:** {preview[:800]}"
            ),
            COLOR_PINK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @custom.command(name="remove", description="Remove a custom command")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(trigger="The trigger to remove")
    async def custom_remove(self, interaction: discord.Interaction,
                            trigger: str):
        self.bot.increment_command('custom_remove')
        trigger_clean = trigger.strip().lower()
        await interaction.response.defer(ephemeral=True)
        table = await self._aload_triggers(interaction.guild.id)
        if trigger_clean not in table:
            await interaction.followup.send(
                "no custom command with that trigger.", ephemeral=True
            )
            return
        del table[trigger_clean]
        await self._asave_triggers(interaction.guild.id, table)
        await interaction.followup.send(
            f"removed `{trigger_clean}` ✦", ephemeral=True
        )

    @custom.command(name="list", description="List this server's custom commands")
    async def custom_list(self, interaction: discord.Interaction):
        self.bot.increment_command('custom_list')
        await interaction.response.defer(ephemeral=True)
        table = await self._aload_triggers(interaction.guild.id)
        if not table:
            embed = veloura_embed(
                "custom commands",
                "none yet — staff can add some with /custom add.",
                COLOR_LAVENDER,
            )
        else:
            lines = []
            for i, entry in enumerate(
                    sorted(table.values(), key=lambda e: -int(e.get('uses', 0)))[:25],
                    start=1):
                uses = int(entry.get('uses', 0))
                lines.append(f"`{entry['trigger']}` — used {uses}x")
            embed = veloura_embed(
                "custom commands",
                "\n".join(lines),
                COLOR_LAVENDER,
            )
            embed.set_footer(
                text=f"{len(table)} total • use /custom remove to delete"
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
