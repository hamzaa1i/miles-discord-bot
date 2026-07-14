"""
cogs/bot_status.py — manual bot status management.

NOTE: main.py already has an automatic status rotation task
(change_status, runs every 5 minutes). This cog provides manual override
commands grouped under /status so admins can pin a custom status or
manage the rotation pool.

Converted from 6 top-level commands to a single /status group to stay
under Discord's 100 global slash command limit.
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
from utils.database import Database

status_choices = [
    app_commands.Choice(name="🎮 Playing", value="playing"),
    app_commands.Choice(name="👀 Watching", value="watching"),
    app_commands.Choice(name="🎵 Listening to", value="listening"),
    app_commands.Choice(name="🏆 Competing in", value="competing"),
    app_commands.Choice(name="📺 Streaming", value="streaming"),
]


class BotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/bot_config.json')

        self.default_statuses = [
            "Watching over the shadows",
            "Playing with the void",
            "Listening to your commands",
            "Watching the server grow",
            "Playing in the dark",
            "Listening to your secrets",
            "Watching the night unfold",
            "Competing in the tournament of chaos",
            "Listening to silence",
            "Playing cyn — /help",
        ]

    def cog_unload(self):
        # Don't cancel main.py's task here — it owns the rotation.
        pass

    async def apply_status(self, text: str):
        """Apply status with text that includes the verb."""
        activity = discord.Game(name=text)
        try:
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=activity
            )
        except Exception:
            pass

    # ==================== /status command group ====================
    status = app_commands.Group(name="status", description="Bot status management")

    @status.command(name="set", description="Set a custom pinned bot status")
    @app_commands.describe(
        status_type="Choose the display prefix",
        text="The status text after the prefix"
    )
    @app_commands.choices(status_type=status_choices)
    @app_commands.checks.has_permissions(administrator=True)
    async def status_set(
        self,
        interaction: discord.Interaction,
        status_type: app_commands.Choice[str],
        text: str
    ):
        type_prefix = {
            "playing": "Playing",
            "watching": "Watching",
            "listening": "Listening to",
            "competing": "Competing in",
            "streaming": "Streaming",
        }.get(status_type.value, "Playing")
        full_status = f"{type_prefix} {text}"
        config = self.db.get('config', {})
        config['pinned_status'] = full_status
        self.db.set('config', config)
        await self.apply_status(full_status)
        embed = discord.Embed(title="Status Updated", color=0x2b2d31)
        embed.add_field(name="Now showing", value=f"`{full_status}`", inline=False)
        embed.set_footer(text="Pinned. Use /status reset to rotate again.")
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @status.command(name="custom", description="Set a fully custom status text")
    @app_commands.describe(text="The exact text to display as status")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_custom(self, interaction: discord.Interaction, text: str):
        config = self.db.get('config', {})
        config['pinned_status'] = text
        self.db.set('config', config)
        await self.apply_status(text)
        embed = discord.Embed(
            title="Status Updated",
            description=f"Now showing: `{text}`",
            color=0x2b2d31
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @status.command(name="reset", description="Resume automatic status rotation")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_reset(self, interaction: discord.Interaction):
        config = self.db.get('config', {})
        if 'pinned_status' in config:
            del config['pinned_status']
            self.db.set('config', config)
        status_text = random.choice(self.default_statuses)
        await self.apply_status(status_text)
        embed = discord.Embed(
            description="Pinned status removed. Rotating every 5 minutes.",
            color=0x2b2d31
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @status.command(name="add", description="Add a status to the rotation pool")
    @app_commands.describe(
        status_type="Choose the display prefix",
        text="The status text after the prefix"
    )
    @app_commands.choices(status_type=status_choices)
    @app_commands.checks.has_permissions(administrator=True)
    async def status_add(
        self,
        interaction: discord.Interaction,
        status_type: app_commands.Choice[str],
        text: str
    ):
        type_prefix = {
            "playing": "Playing",
            "watching": "Watching",
            "listening": "Listening to",
            "competing": "Competing in",
            "streaming": "Streaming",
        }.get(status_type.value, "Playing")
        full_status = f"{type_prefix} {text}"
        config = self.db.get('config', {})
        custom_statuses = config.get('custom_statuses', [])
        custom_statuses.append(full_status)
        config['custom_statuses'] = custom_statuses
        self.db.set('config', config)
        embed = discord.Embed(
            description=f"Added to rotation: `{full_status}`",
            color=0x2b2d31
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @status.command(name="list", description="View all statuses in rotation")
    async def status_list(self, interaction: discord.Interaction):
        config = self.db.get('config', {})
        embed = discord.Embed(title="Status Pool", color=0x2b2d31)
        if config.get('pinned_status'):
            embed.add_field(name="📌 Pinned", value=f"`{config['pinned_status']}`", inline=False)
        default_list = "\n".join([f"`{s}`" for s in self.default_statuses])
        embed.add_field(name="Default Rotation", value=default_list, inline=False)
        custom_statuses = config.get('custom_statuses', [])
        if custom_statuses:
            custom_list = "\n".join([f"`{s}`" for s in custom_statuses])
            embed.add_field(name="Custom Added", value=custom_list, inline=False)
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @status.command(name="clear", description="Remove all custom statuses")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_clear(self, interaction: discord.Interaction):
        config = self.db.get('config', {})
        config['custom_statuses'] = []
        self.db.set('config', config)
        embed = discord.Embed(
            description="All custom statuses cleared.",
            color=0x2b2d31
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BotStatus(bot))
