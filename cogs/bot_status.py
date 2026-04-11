import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
from utils.database import Database

# Dropdown choices
status_choices = [
    app_commands.Choice(name="🎮 Playing", value="playing"),
    app_commands.Choice(name="👀 Watching", value="watching"),
    app_commands.Choice(name="🎵 Listening to", value="listening"),
    app_commands.Choice(name="🏆 Competing in", value="competing"),
]

class BotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/bot_config.json')
        
        self.default_statuses = [
            {"text": "over the shadows", "type": "watching"},
            {"text": "with the void", "type": "playing"},
            {"text": "your commands", "type": "listening"},
            {"text": "the server grow", "type": "watching"},
            {"text": "in the dark", "type": "playing"},
            {"text": "your secrets", "type": "listening"},
            {"text": "the night unfold", "type": "watching"},
            {"text": "the tournament of chaos", "type": "competing"},
            {"text": "silence", "type": "listening"},
            {"text": "ao — /help", "type": "playing"},
        ]
    
    def cog_unload(self):
        self.status_rotation.cancel()

    def build_activity(self, activity_type: str, text: str) -> discord.Activity:
        """Build a proper discord.Activity object"""
        type_map = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
            "competing": discord.ActivityType.competing,
        }
        return discord.Activity(
            type=type_map.get(activity_type, discord.ActivityType.playing),
            name=text
        )

    def get_type_display(self, activity_type: str) -> str:
        """Get human readable type"""
        display_map = {
            "playing": "Playing",
            "watching": "Watching",
            "listening": "Listening to",
            "competing": "Competing in",
        }
        return display_map.get(activity_type, activity_type.title())

    async def apply_status(self, activity_type: str, text: str):
        """Apply status to bot with proper presence"""
        activity = self.build_activity(activity_type, text)
        await self.bot.change_presence(
            status=discord.Status.online,
            activity=activity
        )

    @tasks.loop(minutes=5)
    async def status_rotation(self):
        """Rotate status every 5 minutes"""
        config = self.db.get('config', {})
        
        # If pinned, always use pinned status
        if config.get('pinned_status'):
            pinned = config['pinned_status']
            await self.apply_status(pinned['type'], pinned['text'])
            return
        
        # Otherwise rotate
        saved_extras = config.get('custom_statuses', [])
        all_statuses = self.default_statuses + saved_extras
        status_data = random.choice(all_statuses)
        await self.apply_status(status_data['type'], status_data['text'])

    @status_rotation.before_loop
    async def before_status_rotation(self):
        await self.bot.wait_until_ready()
        # Small delay to ensure bot is fully ready
        await discord.utils.sleep_until(
            discord.utils.utcnow() + discord.utils.timedelta(seconds=3)
        )

    @commands.Cog.listener()
    async def on_ready(self):
        """Set status immediately when bot is ready"""
        config = self.db.get('config', {})
        
        if config.get('pinned_status'):
            pinned = config['pinned_status']
            await self.apply_status(pinned['type'], pinned['text'])
        else:
            # Set first default status immediately
            status_data = self.default_statuses[0]
            await self.apply_status(status_data['type'], status_data['text'])
        
        # Start rotation after setting initial status
        if not self.status_rotation.is_running():
            self.status_rotation.start()

    @app_commands.command(name="setstatus", description="Set a custom pinned bot status")
    @app_commands.describe(
        status_type="Choose the type of status to display",
        text="The status text to display"
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
        config = self.db.get('config', {})
        config['pinned_status'] = {
            'type': status_type.value,
            'text': text
        }
        self.db.set('config', config)
        
        # Apply immediately
        await self.apply_status(status_type.value, text)
        
        type_display = self.get_type_display(status_type.value)
        
        embed = discord.Embed(
            title="Status Updated",
            color=0x1a1a2e
        )
        embed.add_field(
            name="Now showing",
            value=f"`{type_display} {text}`",
            inline=False
        )
        embed.set_footer(text="Pinned — won't rotate. Use /resetstatus to rotate again.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="resetstatus", description="Resume automatic status rotation")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetstatus(self, interaction: discord.Interaction):
        """Remove pinned status"""
        config = self.db.get('config', {})
        
        if 'pinned_status' in config:
            del config['pinned_status']
            self.db.set('config', config)
        
        # Apply random default immediately
        status_data = random.choice(self.default_statuses)
        await self.apply_status(status_data['type'], status_data['text'])
        
        embed = discord.Embed(
            description="Pinned status removed. Rotating every 5 minutes.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="addstatus", description="Add a status to the rotation pool")
    @app_commands.describe(
        status_type="Choose the type of status",
        text="The status text"
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
        config = self.db.get('config', {})
        custom_statuses = config.get('custom_statuses', [])
        
        custom_statuses.append({
            'type': status_type.value,
            'text': text
        })
        
        config['custom_statuses'] = custom_statuses
        self.db.set('config', config)
        
        type_display = self.get_type_display(status_type.value)
        
        embed = discord.Embed(
            description=f"Added to rotation: `{type_display} {text}`",
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
        
        # Pinned status
        if config.get('pinned_status'):
            pinned = config['pinned_status']
            display = self.get_type_display(pinned['type'])
            embed.add_field(
                name="📌 Pinned",
                value=f"`{display} {pinned['text']}`",
                inline=False
            )
        
        # Default statuses
        default_list = "\n".join([
            f"`{self.get_type_display(s['type'])} {s['text']}`"
            for s in self.default_statuses
        ])
        embed.add_field(
            name="Default Rotation",
            value=default_list,
            inline=False
        )
        
        # Custom added
        custom_statuses = config.get('custom_statuses', [])
        if custom_statuses:
            custom_list = "\n".join([
                f"`{self.get_type_display(s['type'])} {s['text']}`"
                for s in custom_statuses
            ])
            embed.add_field(
                name="Custom Added",
                value=custom_list,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearstatuses", description="Remove all custom statuses from rotation")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearstatuses(self, interaction: discord.Interaction):
        """Clear custom statuses"""
        config = self.db.get('config', {})
        config['custom_statuses'] = []
        self.db.set('config', config)
        
        embed = discord.Embed(
            description="All custom statuses cleared from rotation.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BotStatus(bot))