import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
from utils.database import Database

class BotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/bot_config.json')
        self.status_rotation.start()
        
        # Default status messages
        self.default_statuses = [
        {"text": "over the shadows", "type": "watching"},
        {"text": "in the dark", "type": "playing"},
        {"text": "your every move", "type": "watching"},
        {"text": "silence", "type": "listening"},
        {"text": "from the void", "type": "streaming"},
        {"text": "with darkness", "type": "playing"},
        {"text": "the night unfold", "type": "watching"},
        {"text": "your secrets", "type": "listening"},
        {"text": "the abyss", "type": "watching"},
        {"text": "nyx — /help", "type": "playing"}
        ]
    
    def cog_unload(self):
        self.status_rotation.cancel()
    
    @tasks.loop(minutes=5)
    async def status_rotation(self):
        """Rotate status every 5 minutes"""
        config = self.db.get('config', {})
        
        # Check if custom status is set
        if config.get('custom_status'):
            status_data = config['custom_status']
        else:
            # Use random default status
            status_data = random.choice(self.default_statuses)
        
        # Set activity type
        activity_type = {
            'playing': discord.ActivityType.playing,
            'watching': discord.ActivityType.watching,
            'listening': discord.ActivityType.listening,
            'streaming': discord.ActivityType.streaming,
            'competing': discord.ActivityType.competing
        }.get(status_data.get('type', 'playing'), discord.ActivityType.playing)
        
        activity = discord.Activity(
            type=activity_type,
            name=status_data['text']
        )
        
        await self.bot.change_presence(activity=activity)
    
    @status_rotation.before_loop
    async def before_status_rotation(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="setstatus", description="Set custom bot status (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setstatus(
        self,
        interaction: discord.Interaction,
        status_type: str,
        text: str
    ):
        """Set custom bot status
        
        Args:
            status_type: Type of status (playing, watching, listening, streaming, competing)
            text: Status text
        """
        valid_types = ['playing', 'watching', 'listening', 'streaming', 'competing']
        
        if status_type.lower() not in valid_types:
            await interaction.response.send_message(
                f"Invalid status type! Choose from: {', '.join(valid_types)}",
                ephemeral=True
            )
            return
        
        # Save custom status
        config = self.db.get('config', {})
        config['custom_status'] = {
            'type': status_type.lower(),
            'text': text
        }
        self.db.set('config', config)
        
        # Update immediately
        activity_type = {
            'playing': discord.ActivityType.playing,
            'watching': discord.ActivityType.watching,
            'listening': discord.ActivityType.listening,
            'streaming': discord.ActivityType.streaming,
            'competing': discord.ActivityType.competing
        }[status_type.lower()]
        
        activity = discord.Activity(type=activity_type, name=text)
        await self.bot.change_presence(activity=activity)
        
        embed = discord.Embed(
            title="✓ Status Updated",
            description=f"**Type:** {status_type.title()}\n**Text:** {text}",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="resetstatus", description="Reset to default rotating status (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetstatus(self, interaction: discord.Interaction):
        """Reset to default status rotation"""
        config = self.db.get('config', {})
        if 'custom_status' in config:
            del config['custom_status']
            self.db.set('config', config)
        
        # Set random default immediately
        status_data = random.choice(self.default_statuses)
        activity_type = {
            'playing': discord.ActivityType.playing,
            'watching': discord.ActivityType.watching,
            'listening': discord.ActivityType.listening
        }[status_data['type']]
        
        activity = discord.Activity(type=activity_type, name=status_data['text'])
        await self.bot.change_presence(activity=activity)
        
        embed = discord.Embed(
            title="✓ Status Reset",
            description="Bot status reset to default rotation (changes every 5 minutes)",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="addstatus", description="Add custom status to rotation (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def addstatus(
        self,
        interaction: discord.Interaction,
        status_type: str,
        text: str
    ):
        """Add a new status to the rotation pool"""
        valid_types = ['playing', 'watching', 'listening']
        
        if status_type.lower() not in valid_types:
            await interaction.response.send_message(
                f"Invalid status type! Choose from: {', '.join(valid_types)}",
                ephemeral=True
            )
            return
        
        # Add to default statuses
        new_status = {'type': status_type.lower(), 'text': text}
        self.default_statuses.append(new_status)
        
        # Save to database
        config = self.db.get('config', {})
        custom_statuses = config.get('custom_statuses', [])
        custom_statuses.append(new_status)
        config['custom_statuses'] = custom_statuses
        self.db.set('config', config)
        
        embed = discord.Embed(
            title="✓ Status Added",
            description=f"Added to rotation: **{status_type.title()}** {text}",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="liststatus", description="View all status messages in rotation")
    async def liststatus(self, interaction: discord.Interaction):
        """List all status messages"""
        embed = discord.Embed(
            title="Status Rotation List",
            description="Current status messages (rotates every 5 minutes):",
            color=discord.Color.blue()
        )
        
        for idx, status in enumerate(self.default_statuses, 1):
            embed.add_field(
                name=f"{idx}. {status['type'].title()}",
                value=status['text'],
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BotStatus(bot))