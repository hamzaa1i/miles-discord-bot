import discord
from discord.ext import commands
from discord import app_commands
from utils.embeds import create_embed
from utils.database import Database

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/welcome.json')
    
@commands.Cog.listener()
async def on_member_join(self, member: discord.Member):
    """Send welcome message when member joins"""
    # Add debug log
    print(f"Member joined: {member.name} in {member.guild.name}")
    
    config = self.db.get(str(member.guild.id), {})
    print(f"Welcome config: {config}")
    
    if not config.get('enabled', False):
        print("Welcome not enabled")
        return
    
    channel_id = config.get('channel_id')
    if not channel_id:
        print("No channel ID")
        return
    
    channel = member.guild.get_channel(int(channel_id))
    if not channel:
        print("Channel not found")
        return
    
    message = config.get('message', 'Welcome {user} to {server}!')
    message = message.replace('{user}', member.mention)
    message = message.replace('{server}', member.guild.name)
    message = message.replace('{count}', str(member.guild.member_count))
    
    embed = discord.Embed(
        description=message,
        color=0x1a1a2e
    )
    embed.set_thumbnail(
        url=member.avatar.url if member.avatar else member.default_avatar.url
    )
    embed.set_footer(text=f"Member #{member.guild.member_count}")
    
    await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Send goodbye message when member leaves"""
        config = self.db.get(str(member.guild.id), {})
        
        if not config.get('goodbye_enabled', False):
            return
        
        channel_id = config.get('channel_id')
        if not channel_id:
            return
        
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
        
        embed = create_embed(
            title="👋 Goodbye",
            description=f"**{member.name}** has left the server.",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        
        await channel.send(embed=embed)
    
    @app_commands.command(name="welcome_setup", description="Configure welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = None,
        enabled: bool = True
    ):
        """Setup welcome messages"""
        config = {
            'enabled': enabled,
            'channel_id': str(channel.id),
            'message': message or 'Welcome {user} to {server}! We now have {count} members! 🎉'
        }
        
        self.db.set(str(interaction.guild.id), config)
        
        embed = create_embed(
            title="✅ Welcome Messages Configured",
            description=f"**Channel:** {channel.mention}\n**Enabled:** {enabled}",
            color=discord.Color.green()
        )
        embed.add_field(name="Message Preview", value=config['message'])
        embed.add_field(
            name="Variables",
            value="`{user}` - Mentions the user\n`{server}` - Server name\n`{count}` - Member count",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="welcome_test", description="Test welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_test(self, interaction: discord.Interaction):
        """Test the welcome message"""
        config = self.db.get(str(interaction.guild.id), {})
        
        if not config.get('enabled'):
            await interaction.response.send_message("❌ Welcome messages are not enabled!", ephemeral=True)
            return
        
        channel_id = config.get('channel_id')
        if not channel_id:
            await interaction.response.send_message("❌ Welcome channel not configured!", ephemeral=True)
            return
        
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("❌ Welcome channel not found!", ephemeral=True)
            return
        
        message = config.get('message', 'Welcome {user} to {server}! 🎉')
        message = message.replace('{user}', interaction.user.mention)
        message = message.replace('{server}', interaction.guild.name)
        message = message.replace('{count}', str(interaction.guild.member_count))
        
        embed = create_embed(
            title="👋 Welcome! (Test)",
            description=message,
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Test message sent!", ephemeral=True)
    
    @app_commands.command(name="goodbye_toggle", description="Enable/disable goodbye messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_toggle(self, interaction: discord.Interaction, enabled: bool):
        """Toggle goodbye messages"""
        config = self.db.get(str(interaction.guild.id), {})
        config['goodbye_enabled'] = enabled
        self.db.set(str(interaction.guild.id), config)
        
        status = "enabled" if enabled else "disabled"
        embed = create_embed(
            title=f"✅ Goodbye Messages {status.title()}",
            description=f"Goodbye messages are now **{status}**.",
            color=discord.Color.green() if enabled else discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))