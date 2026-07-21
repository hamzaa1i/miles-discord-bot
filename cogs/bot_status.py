"""
cogs/bot_status.py — automatic status rotation + manual /status commands.

CHANGE 1 — Fixed bot status visibility:
  A) Presence Intent already enabled in main.py (intents.presences = True)
  B) Added 5-second startup delay before first status (gateway handshake)
  C) Added on_ready + on_resumed listeners to force status refresh
  Changed rotation from 5 min to 15 min for more reliable member list updates.
  Added _apply_current_status() helper to deduplicate status logic.

Commands:
  /status set [type] [text]  — set a custom pinned status (stops rotation)
  /status reset              — clear custom status, resume rotation
  /status current            — show current status (anyone can use)
  /status info               — explain how Discord displays bot status (anyone)
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
import json as _json


class BotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.custom_status = None
        self.status_list = [
            (discord.ActivityType.listening, "@cyn"),
            (discord.ActivityType.playing, "with {users} users"),
            (discord.ActivityType.watching, "{servers} servers"),
            (discord.ActivityType.competing, "being cyn"),
            (discord.ActivityType.listening, "your problems"),
            (discord.ActivityType.watching, "you type"),
            (discord.ActivityType.playing, "with fire"),
            (discord.ActivityType.listening, "the void"),
            (discord.ActivityType.competing, "with herself"),
            (discord.ActivityType.watching, "the chaos unfold"),
        ]
        self.status_index = 0
        self._load_custom_status()
        self.rotate_status.start()

    def _load_custom_status(self):
        try:
            with open("data/bot_status.json", "r") as f:
                data = _json.load(f)
            custom = data.get("custom")
            if custom and isinstance(custom, dict):
                self.custom_status = custom
        except (FileNotFoundError, _json.JSONDecodeError):
            pass

    def _save_custom_status(self):
        try:
            with open("data/bot_status.json", "w") as f:
                _json.dump({"custom": self.custom_status}, f, indent=2)
        except Exception as e:
            print(f"[bot_status] failed to save: {e}")

    def cog_unload(self):
        self.rotate_status.cancel()

    # CHANGE 1 — Helper to apply whichever status is currently active
    async def _apply_current_status(self):
        """Apply the current status (custom or auto-rotate)."""
        try:
            if self.custom_status:
                type_map = {
                    "listening": discord.ActivityType.listening,
                    "playing": discord.ActivityType.playing,
                    "watching": discord.ActivityType.watching,
                    "competing": discord.ActivityType.competing,
                }
                activity_type = type_map.get(
                    self.custom_status["type"], discord.ActivityType.playing
                )
                user_count = sum(g.member_count for g in self.bot.guilds)
                server_count = len(self.bot.guilds)
                text = self.custom_status["text"].replace(
                    "{users}", str(user_count)
                ).replace("{servers}", str(server_count))
                activity = discord.Activity(type=activity_type, name=text)
            else:
                activity_type, text = self.status_list[
                    self.status_index % len(self.status_list)
                ]
                user_count = sum(g.member_count for g in self.bot.guilds)
                server_count = len(self.bot.guilds)
                text = text.replace("{users}", str(user_count)).replace(
                    "{servers}", str(server_count)
                )
                activity = discord.Activity(type=activity_type, name=text)

            await self.bot.change_presence(
                status=discord.Status.online,
                activity=activity
            )
        except Exception as e:
            print(f"[bot_status] apply error: {e}")

    # CHANGE 1B — 15 minute rotation + 5 second startup delay
    @tasks.loop(minutes=15)
    async def rotate_status(self):
        """Auto-rotate status every 15 minutes."""
        if self.custom_status:
            return
        self.status_index = (self.status_index + 1) % len(self.status_list)
        await self._apply_current_status()

    @rotate_status.before_loop
    async def before_rotate(self):
        await self.bot.wait_until_ready()
        # CHANGE 1B — 5 second delay to ensure gateway handshake is complete
        await asyncio.sleep(5)

    # CHANGE 1C — Force status refresh on gateway reconnect
    @commands.Cog.listener()
    async def on_resumed(self):
        """Re-apply status after gateway reconnect."""
        await asyncio.sleep(3)
        await self._apply_current_status()

    @commands.Cog.listener()
    async def on_ready(self):
        """Set status immediately when bot becomes ready."""
        await asyncio.sleep(5)
        await self._apply_current_status()

    # ==================== /status command group ====================
    status = app_commands.Group(name="status", description="Bot status management")

    @status.command(name="set", description="Set a custom pinned bot status (owner only)")
    @app_commands.describe(
        status_type="Activity type",
        text="Status text (use {users} or {servers} for dynamic values)"
    )
    @app_commands.choices(status_type=[
        app_commands.Choice(name="Listening to", value="listening"),
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Watching", value="watching"),
        app_commands.Choice(name="Competing in", value="competing"),
    ])
    async def status_set(
        self,
        interaction: discord.Interaction,
        status_type: app_commands.Choice[str],
        text: str
    ):
        self.bot.increment_command('status_set')
        await interaction.response.defer(ephemeral=True)

        owner_id = int(os.getenv("OWNER_ID", "0"))
        if interaction.user.id != owner_id:
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        user_count = sum(g.member_count for g in self.bot.guilds)
        server_count = len(self.bot.guilds)
        display_text = text.replace("{users}", str(user_count)).replace("{servers}", str(server_count))

        self.custom_status = {"type": status_type.value, "text": text}
        self._save_custom_status()
        await self._apply_current_status()

        embed = discord.Embed(
            title="✅ Status Set",
            color=0x2ecc71,
            description=f"Now showing: **{status_type.name}** `{display_text}`"
        )
        embed.set_footer(text="Custom status pinned. Use /status reset to rotate again.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @status.command(name="reset", description="Clear custom status and resume auto-rotation (owner only)")
    async def status_reset(self, interaction: discord.Interaction):
        self.bot.increment_command('status_reset')
        await interaction.response.defer(ephemeral=True)

        owner_id = int(os.getenv("OWNER_ID", "0"))
        if interaction.user.id != owner_id:
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        if not self.custom_status:
            await interaction.followup.send(
                "no custom status set. already auto-rotating.",
                ephemeral=True
            )
            return

        self.custom_status = None
        self._save_custom_status()
        await self._apply_current_status()

        await interaction.followup.send(
            "✅ custom status cleared. auto-rotation resumed.",
            ephemeral=True
        )

    @status.command(name="current", description="Show the current bot status (anyone)")
    async def status_current(self, interaction: discord.Interaction):
        self.bot.increment_command('status_current')
        await interaction.response.defer(ephemeral=True)

        activity = self.bot.guilds[0].me.activity if self.bot.guilds else None
        if not activity:
            try:
                activity = self.bot.activity
            except Exception:
                activity = None

        embed = discord.Embed(
            title="Current Bot Status",
            color=0x1a1a2e,
            timestamp=discord.utils.utcnow()
        )

        if self.custom_status:
            embed.add_field(name="Mode", value="custom (pinned)", inline=False)
            embed.add_field(name="Type", value=self.custom_status.get("type", "unknown"), inline=True)
            embed.add_field(name="Text", value=f"`{self.custom_status.get('text', 'unknown')}`", inline=True)
            embed.set_footer(text="use /status reset to resume rotation")
        else:
            embed.add_field(name="Mode", value="auto-rotating", inline=False)
            if activity:
                type_name = str(activity.type).replace("ActivityType.", "").title()
                embed.add_field(name="Current Type", value=type_name, inline=True)
                embed.add_field(name="Current Text", value=f"`{activity.name}`", inline=True)
            embed.add_field(
                name="Rotation Pool",
                value=f"{len(self.status_list)} statuses, cycling every 15 minutes",
                inline=False
            )
            embed.set_footer(text="use /status set to pin a custom status")

        embed.add_field(
            name="ℹ️ Display Note",
            value="Discord shows activity text in the full profile popup — click my avatar to see it.",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @status.command(name="info", description="Learn how Discord displays bot status (anyone)")
    async def status_info(self, interaction: discord.Interaction):
        self.bot.increment_command('status_info')
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📊 Bot Status Info",
            color=0x1a1a2e,
            timestamp=discord.utils.utcnow()
        )

        if self.custom_status:
            embed.add_field(name="Current Mode", value="custom (pinned)", inline=False)
            embed.add_field(name="Status Type", value=self.custom_status.get("type", "unknown"), inline=True)
            embed.add_field(name="Status Text", value=f"`{self.custom_status.get('text', 'unknown')}`", inline=True)
        else:
            embed.add_field(name="Current Mode", value="auto-rotating (changes every 15 min)", inline=False)
            activity = self.bot.guilds[0].me.activity if self.bot.guilds else None
            if not activity:
                try:
                    activity = self.bot.activity
                except Exception:
                    activity = None
            if activity:
                type_name = str(activity.type).replace("ActivityType.", "").title()
                embed.add_field(name="Current Type", value=type_name, inline=True)
                embed.add_field(name="Current Text", value=f"`{activity.name}`", inline=True)

        embed.add_field(name="Next Rotation", value="within 15 minutes", inline=True)
        embed.add_field(
            name="📝 How to See My Status",
            value=(
                "Discord shows activity text in the full profile popup — click my avatar.\n"
                "It may not show in the member list sidebar for bot accounts.\n"
                "This is a Discord client-side display decision, not a bug."
            ),
            inline=False
        )
        embed.set_footer(text="cyn • /status info")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BotStatus(bot))
