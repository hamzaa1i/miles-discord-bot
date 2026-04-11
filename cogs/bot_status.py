import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
from utils.database import Database

# Status type choices for slash command dropdown
status_choices = [
    app_commands.Choice(name="Playing", value="playing"),
    app_commands.Choice(name="Watching", value="watching"),
    app_commands.Choice(name="Listening to", value="listening"),
    app_commands.Choice(name="Competing in", value="competing"),
]

class BotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/bot_config.json')
        self.status_rotation.start()
        
        # Default rotating statuses
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

    def get_activity(self, activity_type: str, text: str) -> discord.Activity:
        """Convert type string to proper discord Activity"""
        type_map = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
            "competing": discord.ActivityType.competing,
        }
        
        discord_type = type_map.get(activity_type, discord.ActivityType.playing)
        
        return discord.Activity(type=discord_type, name=text)

    @tasks.loop(minutes=5)
    async def status_rotation(self):
        """Rotate status every 5 minutes"""
        config = self.db.get('config', {})
        
        # If custom status is pinned, don't rotate
        if config.get('pinned_status'):
            status_data = config['pinned_status']
            activity = self.get_activity(status_data['type'], status_data['text'])
            await self.bot.change_presence(activity=activity)
            return
        
        # Load any saved custom statuses added via /addstatus
        saved_extras = config.get('custom_statuses', [])
        all_statuses = self.default_statuses + saved_extras
        
        # Pick random status
        status_data = random.choice(all_statuses)
        activity = self.get_activity(status_data['type'], status_data['text'])
        await self.bot.change_presence(activity=activity)

    @status_rotation.before_loop
    async def before_status_rotation(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="setstatus", description="Set a custom pinned bot status")
    @app_commands.describe(
        status_type="Choose the type of status",
        text="What the status should say"
    )
    @app_commands.choices(status_type=status_choices)
    @app_commands.checks.has_permissions(administrator=True)
    async def setstatus(
        self,
        interaction: discord.Interaction,
        status_type: app_commands.Choice[str],
        text: str
    ):
        """Set and pin a custom status"""
        config = self.db.get('config', {})
        
        # Save as pinned status
        config['pinned_status'] = {
            'type': status_type.value,
            'text': text
        }
        self.db.set('config', config)
        
        # Apply immediately
        activity = self.get_activity(status_type.value, text)
        await self.bot.change_presence(activity=activity)
        
        # Show preview text
        type_display = {
            "playing": "Playing",
            "watching": "Watching",
            "listening": "Listening to",
            "competing": "Competing in"
        }.get(status_type.value, status_type.value.title())
        
        embed = discord.Embed(
            title="Status Updated",
            description=(
                f"**Type:** {type_display}\n"
                f"**Text:** {text}\n\n"
                f"Preview: `{type_display} {text}`"
            ),
            color=0x1a1a2e
        )
        embed.set_footer(text="Status is now pinned. Use /resetstatus to rotate again.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="resetstatus", description="Remove pinned status and resume rotation")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetstatus(self, interaction: discord.Interaction):
        """Remove pinned status, go back to rotation"""
        config = self.db.get('config', {})
        
        if 'pinned_status' in config:
            del config['pinned_status']
            self.db.set('config', config)
        
        # Set a random one immediately
        status_data = random.choice(self.default_statuses)
        activity = self.get_activity(status_data['type'], status_data['text'])
        await self.bot.change_presence(activity=activity)
        
        embed = discord.Embed(
            description="Pinned status removed. Back to rotating every 5 minutes.",
            color=0x1a1a2e
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="addstatus", description="Add a status to the rotation pool")
    @app_commands.describe(
        status_type="Choose the type of status",
        text="What the status should say"
    )
    @app_commands.choices(status_type=status_choices)
    @app_commands.checks.has_permissions(administrator=True)
    async def addstatus(
        self,
        interaction: discord.Interaction,
        status_type: app_commands.Choice[str],
        text: str
    ):
        """Add status to rotation"""
        config = self.db.get('config', {})
        custom_statuses = config.get('custom_statuses', [])
        
        new_status = {
            'type': status_type.value,
            'text': text
        }
        custom_statuses.append(new_status)
        config['custom_statuses'] = custom_statuses
        self.db.set('config', config)
        
        type_display = {
            "playing": "Playing",
            "watching": "Watching",
            "listening": "Listening to",
            "competing": "Competing in"
        }.get(status_type.value, status_type.value.title())
        
        embed = discord.Embed(
            description=f"Added to rotation: `{type_display} {text}`",
            color=0x1a1a2e
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="liststatus", description="View all statuses in rotation")
    async def liststatus(self, interaction: discord.Interaction):
        """List all statuses"""
        config = self.db.get('config', {})
        
        type_display = {
            "playing": "Playing",
            "watching": "Watching",
            "listening": "Listening to",
            "competing": "Competing in"
        }
        
        embed = discord.Embed(
            title="Status Rotation Pool",
            color=0x1a1a2e
        )
        
        # Show pinned status if exists
        if config.get('pinned_status'):
            pinned = config['pinned_status']
            display = type_display.get(pinned['type'], pinned['type'].title())
            embed.add_field(
                name="Pinned Status",
                value=f"`{display} {pinned['text']}`",
                inline=False
            )
        
        # Default statuses
        default_list = "\n".join([
            f"`{type_display.get(s['type'], s['type'].title())} {s['text']}`"
            for s in self.default_statuses
        ])
        embed.add_field(
            name="Default Rotation",
            value=default_list,
            inline=False
        )
        
        # Custom statuses
        custom_statuses = config.get('custom_statuses', [])
        if custom_statuses:
            custom_list = "\n".join([
                f"`{type_display.get(s['type'], s['type'].title())} {s['text']}`"
                for s in custom_statuses
            ])
            embed.add_field(
                name="Custom Added",
                value=custom_list,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearstatuses", description="Remove all custom added statuses")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearstatuses(self, interaction: discord.Interaction):
        """Clear custom statuses"""
        config = self.db.get('config', {})
        config['custom_statuses'] = []
        self.db.set('config', config)
        
        embed = discord.Embed(
            description="All custom statuses removed from rotation.",
            color=0x1a1a2e
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BotStatus(bot))