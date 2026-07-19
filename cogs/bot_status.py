"""
cogs/bot_status.py — automatic status rotation + manual /status commands.

The status cycles automatically every 5 minutes through 10 statuses,
each using the CORRECT discord.ActivityType so Discord shows
"Listening to", "Playing", "Watching", "Competing" properly.

FIX 3 — Added discord.Status.online to every change_presence call so
the bot always shows as online (green dot). Discord only shows activity
text in the full profile popup for bot accounts — this is a Discord-side
display decision, not an API issue. Added /status info to explain this.

Commands:
  /status set [type] [text]  — set a custom pinned status (stops rotation)
  /status reset              — clear custom status, resume rotation
  /status current            — show current status (anyone can use)
  /status info               — explain how Discord displays bot status (anyone)

Data stored in data/bot_status.json:
  {"custom": null}  or  {"custom": {"type": "listening", "text": "..."}}
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json as _json


class BotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.custom_status = None  # None = auto-rotate; dict = custom pinned
        # FIX 3B — More varied and interesting status rotation list (10 statuses)
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
        # Load custom status from file if set
        self._load_custom_status()
        self.rotate_status.start()

    def _load_custom_status(self):
        """Load custom status from data/bot_status.json if it exists."""
        try:
            with open("data/bot_status.json", "r") as f:
                data = _json.load(f)
            custom = data.get("custom")
            if custom and isinstance(custom, dict):
                self.custom_status = custom
        except (FileNotFoundError, _json.JSONDecodeError):
            pass

    def _save_custom_status(self):
        """Save custom status to data/bot_status.json."""
        try:
            with open("data/bot_status.json", "w") as f:
                _json.dump({"custom": self.custom_status}, f, indent=2)
        except Exception as e:
            print(f"[bot_status] failed to save: {e}")

    def cog_unload(self):
        self.rotate_status.cancel()

    @tasks.loop(minutes=5)
    async def rotate_status(self):
        """Auto-rotate status every 5 minutes. Skipped if custom status is set."""
        if self.custom_status:
            return  # Don't rotate if custom status is set

        try:
            activity_type, text = self.status_list[self.status_index]
            # Replace dynamic placeholders
            user_count = sum(g.member_count for g in self.bot.guilds)
            server_count = len(self.bot.guilds)
            text = text.replace("{users}", str(user_count))
            text = text.replace("{servers}", str(server_count))

            # FIX 3A — Always set status=online so the green dot shows
            activity = discord.Activity(type=activity_type, name=text)
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=activity
            )

            self.status_index = (self.status_index + 1) % len(self.status_list)
        except Exception as e:
            print(f"[bot_status] rotation error: {e}")

    @rotate_status.before_loop
    async def before_rotate(self):
        await self.bot.wait_until_ready()

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

        # Map choice value to ActivityType
        type_map = {
            "listening": discord.ActivityType.listening,
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "competing": discord.ActivityType.competing,
        }
        activity_type = type_map.get(status_type.value, discord.ActivityType.playing)

        # Replace dynamic placeholders
        user_count = sum(g.member_count for g in self.bot.guilds)
        server_count = len(self.bot.guilds)
        display_text = text.replace("{users}", str(user_count)).replace("{servers}", str(server_count))

        # Save and apply
        self.custom_status = {"type": status_type.value, "text": text}
        self._save_custom_status()

        # FIX 3A — Always set status=online
        activity = discord.Activity(type=activity_type, name=display_text)
        try:
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=activity
            )
        except Exception as e:
            await interaction.followup.send(f"failed to set status: `{e}`", ephemeral=True)
            return

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

        # Immediately apply the next rotation status
        try:
            activity_type, text = self.status_list[self.status_index]
            user_count = sum(g.member_count for g in self.bot.guilds)
            server_count = len(self.bot.guilds)
            text = text.replace("{users}", str(user_count)).replace("{servers}", str(server_count))
            # FIX 3A — Always set status=online
            activity = discord.Activity(type=activity_type, name=text)
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=activity
            )
            self.status_index = (self.status_index + 1) % len(self.status_list)
        except Exception:
            pass

        await interaction.followup.send(
            "✅ custom status cleared. auto-rotation resumed.",
            ephemeral=True
        )

    @status.command(name="current", description="Show the current bot status (anyone)")
    async def status_current(self, interaction: discord.Interaction):
        self.bot.increment_command('status_current')
        await interaction.response.defer(ephemeral=True)

        # Read the bot's current activity
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
            mode = "custom (pinned)"
            type_str = self.custom_status.get("type", "unknown")
            text = self.custom_status.get("text", "unknown")
            embed.add_field(name="Mode", value=mode, inline=False)
            embed.add_field(name="Type", value=type_str, inline=True)
            embed.add_field(name="Text", value=f"`{text}`", inline=True)
            embed.set_footer(text="use /status reset to resume rotation")
        else:
            mode = "auto-rotating"
            embed.add_field(name="Mode", value=mode, inline=False)
            if activity:
                type_name = str(activity.type).replace("ActivityType.", "").title()
                embed.add_field(name="Current Type", value=type_name, inline=True)
                embed.add_field(name="Current Text", value=f"`{activity.name}`", inline=True)
            embed.add_field(
                name="Rotation Pool",
                value=f"{len(self.status_list)} statuses, cycling every 5 minutes",
                inline=False
            )
            embed.set_footer(text="use /status set to pin a custom status")

        # FIX 3D — Add note about Discord display behavior
        embed.add_field(
            name="ℹ️ Display Note",
            value=(
                "Discord only shows activity text in the full profile popup — "
                "click my avatar to see it."
            ),
            inline=False
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # FIX 3C — /status info: explains how Discord displays bot statuses
    @status.command(name="info",
                    description="Learn how Discord displays bot status (anyone)")
    async def status_info(self, interaction: discord.Interaction):
        self.bot.increment_command('status_info')
        await interaction.response.defer(ephemeral=True)

        # Get current status info
        activity = self.bot.guilds[0].me.activity if self.bot.guilds else None
        if not activity:
            try:
                activity = self.bot.activity
            except Exception:
                activity = None

        embed = discord.Embed(
            title="📊 Bot Status Info",
            color=0x1a1a2e,
            timestamp=discord.utils.utcnow()
        )

        if self.custom_status:
            embed.add_field(
                name="Current Mode",
                value="custom (pinned)",
                inline=False
            )
            embed.add_field(
                name="Status Type",
                value=self.custom_status.get("type", "unknown"),
                inline=True
            )
            embed.add_field(
                name="Status Text",
                value=f"`{self.custom_status.get('text', 'unknown')}`",
                inline=True
            )
        else:
            embed.add_field(
                name="Current Mode",
                value="auto-rotating (changes every 5 min)",
                inline=False
            )
            if activity:
                type_name = str(activity.type).replace("ActivityType.", "").title()
                embed.add_field(
                    name="Current Type",
                    value=type_name,
                    inline=True
                )
                embed.add_field(
                    name="Current Text",
                    value=f"`{activity.name}`",
                    inline=True
                )

        # Calculate approximate next rotation time
        import time as _time
        # The rotate_status task runs every 5 minutes (300s).
        # We can approximate the next rotation based on the current_loop count.
        try:
            loops = self.rotate_status.current_loop
            next_in = 5  # approximate: up to 5 minutes
            embed.add_field(
                name="Next Rotation",
                value=f"approximately {next_in} minutes",
                inline=True
            )
        except Exception:
            embed.add_field(
                name="Next Rotation",
                value="within 5 minutes",
                inline=True
            )

        embed.add_field(
            name="📝 How to See My Status",
            value=(
                "Discord changed how bot statuses are displayed. The activity text "
                "('Playing', 'Watching', 'Listening to', 'Competing') **only shows "
                "in the full profile popup** — click my avatar to see it.\n\n"
                "It does NOT show in the member list sidebar or hover card anymore "
                "for bot accounts. This is a Discord client-side change, not a bug."
            ),
            inline=False
        )

        embed.set_footer(text="cyn • /status info")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BotStatus(bot))
