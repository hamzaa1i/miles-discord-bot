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
        
        # Verb is now INCLUDED in the text
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
            "Playing ao — /help",
        ]
    
    def cog_unload(self):
        self.status_rotation.cancel()

    async def apply_status(self, text: str):
        """Apply status with text that includes the verb"""
        activity = discord.Game(name=text)
        await self.bot.change_presence(
            status=discord.Status.online,
            activity=activity
        )

    @commands.Cog.listener()
    async def on_ready(self):
        """Set status when bot is ready"""
        config = self.db.get('config', {})
        
        if config.get('pinned_status'):
            await self.apply_status(config['pinned_status'])
        else:
            await self.apply_status(self.default_statuses[0])
        
        if not self.status_rotation.is_running():
            self.status_rotation.start()

    @tasks.loop(minutes=5)
    async def status_rotation(self):
        """Rotate status every 5 minutes"""
        config = self.db.get('config', {})
        
        if config.get('pinned_status'):
            await self.apply_status(config['pinned_status'])
            return
        
        saved_extras = config.get('custom_statuses', [])
        all_statuses = self.default_statuses + saved_extras
        status_text = random.choice(all_statuses)
        await self.apply_status(status_text)

    @status_rotation.before_loop
    async def before_status_rotation(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="setstatus", description="Set a custom pinned bot status")
    @app_commands.describe(
        status_type="Choose the display prefix",
        text="The status text after the prefix"
    )
    @app_commands.choices(status_type=status_choices)
    @app_commands.checks.has_permissions(administrator=True)
    async def setstatus(
        self,
        interaction: discord.Interaction,
        status_type: app_commands.Choice[str],
        text: str
    ):
        """Pin a custom bot status"""
        # Build the full status string with verb included
        type_prefix = {
            "playing": "Playing",
            "watching": "Watching",
            "listening": "Listening to",
            "competing": "Competing in",
            "streaming": "Streaming",
        }.get(status_type.value, "Playing")
        
        full_status = f"{type_prefix} {text}"
        
        # Save as pinned
        config = self.db.get('config', {})
        config['pinned_status'] = full_status
        self.db.set('config', config)
        
        # Apply immediately
        await self.apply_status(full_status)
        
        embed = discord.Embed(
            title="Status Updated",
            color=0x1a1a2e
        )
        embed.add_field(
            name="Now showing",
            value=f"`{full_status}`",
            inline=False
        )
        embed.set_footer(text="Pinned. Use /resetstatus to rotate again.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setstatus_custom", description="Set a fully custom status text")
    @app_commands.describe(text="The exact text to display as status")
    @app_commands.checks.has_permissions(administrator=True)
    async def setstatus_custom(
        self,
        interaction: discord.Interaction,
        text: str
    ):
        """Set any custom text without prefix dropdown"""
        config = self.db.get('config', {})
        config['pinned_status'] = text
        self.db.set('config', config)
        
        await self.apply_status(text)
        
        embed = discord.Embed(
            title="Status Updated",
            description=f"Now showing: `{text}`",
            color=0x1a1a2e
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="resetstatus", description="Resume automatic status rotation")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetstatus(self, interaction: discord.Interaction):
        """Remove pinned status"""
        config = self.db.get('config', {})
        
        if 'pinned_status' in config:
            del config['pinned_status']
            self.db.set('config', config)
        
        status_text = random.choice(self.default_statuses)
        await self.apply_status(status_text)
        
        embed = discord.Embed(
            description="Pinned status removed. Rotating every 5 minutes.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="addstatus", description="Add a status to the rotation pool")
    @app_commands.describe(
        status_type="Choose the display prefix",
        text="The status text after the prefix"
    )
    @app_commands.choices(status_type=status_choices)
    @app_commands.checks.has_permissions(administrator=True)
    async def addstatus(
        self,
        interaction: discord.Interaction,
        status_type: app_commands.Choice[str],
        text: str
    ):
        """Add to rotation pool"""
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
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="liststatus", description="View all statuses in rotation")
    async def liststatus(self, interaction: discord.Interaction):
        """List all statuses"""
        config = self.db.get('config', {})
        
        embed = discord.Embed(
            title="Status Pool",
            color=0x1a1a2e
        )
        
        # Pinned
        if config.get('pinned_status'):
            embed.add_field(
                name="📌 Pinned",
                value=f"`{config['pinned_status']}`",
                inline=False
            )
        
        # Default
        default_list = "\n".join([f"`{s}`" for s in self.default_statuses])
        embed.add_field(
            name="Default Rotation",
            value=default_list,
            inline=False
        )
        
        # Custom
        custom_statuses = config.get('custom_statuses', [])
        if custom_statuses:
            custom_list = "\n".join([f"`{s}`" for s in custom_statuses])
            embed.add_field(
                name="Custom Added",
                value=custom_list,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearstatuses", description="Remove all custom statuses")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearstatuses(self, interaction: discord.Interaction):
        """Clear custom statuses"""
        config = self.db.get('config', {})
        config['custom_statuses'] = []
        self.db.set('config', config)
        
        embed = discord.Embed(
            description="All custom statuses cleared.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BotStatus(bot))