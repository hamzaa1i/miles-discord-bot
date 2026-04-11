import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database

class ModMail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/modmail.json')
        self.open_tickets = {}
    
    def get_config(self, guild_id: int):
        """Get modmail config for guild"""
        return self.db.get(str(guild_id), {
            'enabled': False,
            'channel_id': None,
            'category_id': None,
            'log_channel_id': None
        })
    
    @app_commands.command(name="modmail_setup", description="Setup modmail system")
    @app_commands.checks.has_permissions(administrator=True)
    async def modmail_setup(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel,
        category: discord.CategoryChannel = None
    ):
        """Setup modmail"""
        config = {
            'enabled': True,
            'log_channel_id': str(log_channel.id),
            'category_id': str(category.id) if category else None
        }
        
        self.db.set(str(interaction.guild.id), config)
        
        embed = discord.Embed(
            title="Modmail Setup Complete",
            description=(
                f"Log Channel: {log_channel.mention}\n"
                f"Category: {category.name if category else 'Default'}\n\n"
                "Users can now DM me to open a ticket."
            ),
            color=0x1a1a2e
        )
        
        await interaction.response.send_message(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle DMs as modmail"""
        # Only process DMs from non-bots
        if message.author.bot:
            return
        
        if not isinstance(message.channel, discord.DMChannel):
            return
        
        # Check each guild the bot is in
        for guild in self.bot.guilds:
            if message.author in guild.members:
                config = self.get_config(guild.id)
                
                if not config.get('enabled'):
                    continue
                
                log_channel_id = config.get('log_channel_id')
                if not log_channel_id:
                    continue
                
                log_channel = guild.get_channel(int(log_channel_id))
                if not log_channel:
                    continue
                
                # Forward message to log channel
                embed = discord.Embed(
                    title="New ModMail Message",
                    description=message.content or "*[No text content]*",
                    color=0x1a1a2e,
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(
                    name=f"{message.author} ({message.author.id})",
                    icon_url=message.author.avatar.url if message.author.avatar else None
                )
                embed.set_footer(text=f"User ID: {message.author.id}")
                
                # Add attachments if any
                if message.attachments:
                    embed.add_field(
                        name="Attachments",
                        value="\n".join([a.url for a in message.attachments]),
                        inline=False
                    )
                
                # Send to mod channel
                view = ModMailView(message.author.id, self.bot)
                await log_channel.send(embed=embed, view=view)
                
                # Confirm to user
                confirm_embed = discord.Embed(
                    description="Your message has been forwarded to the server staff. They will respond shortly.",
                    color=0x1a1a2e
                )
                await message.author.send(embed=confirm_embed)
                break
    
    @app_commands.command(name="dm", description="Send a DM to a user (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def dm_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        message: str,
        anonymous: bool = False
    ):
        """Send DM to a user"""
        embed = discord.Embed(
            description=message.replace('\\n', '\n'),
            color=0x1a1a2e,
            timestamp=discord.utils.utcnow()
        )
        
        if anonymous:
            embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            embed.set_footer(text="Message from Server Staff")
        else:
            embed.set_author(
                name=f"Message from {interaction.user.name}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            embed.set_footer(text=interaction.guild.name)
        
        try:
            await user.send(embed=embed)
            
            confirm = discord.Embed(
                description=f"Message sent to {user.mention}",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=confirm, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message(
                f"Could not send DM to {user.mention}. Their DMs may be closed.",
                ephemeral=True
            )
    
    @app_commands.command(name="announce", description="Send announcement to all members via DM")
    @app_commands.checks.has_permissions(administrator=True)
    async def announce(
        self,
        interaction: discord.Interaction,
        message: str,
        role: discord.Role = None
    ):
        """Mass DM announcement"""
        await interaction.response.defer(ephemeral=True)
        
        if role:
            members = [m for m in role.members if not m.bot]
        else:
            members = [m for m in interaction.guild.members if not m.bot]
        
        embed = discord.Embed(
            title=f"Announcement from {interaction.guild.name}",
            description=message.replace('\\n', '\n'),
            color=0x1a1a2e,
            timestamp=discord.utils.utcnow()
        )
        
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        
        sent = 0
        failed = 0
        
        for member in members:
            try:
                await member.send(embed=embed)
                sent += 1
            except:
                failed += 1
        
        result = discord.Embed(
            title="Announcement Sent",
            description=f"Sent: {sent}\nFailed: {failed}",
            color=0x1a1a2e
        )
        
        await interaction.followup.send(embed=result, ephemeral=True)
    
    @app_commands.command(name="modmail_toggle", description="Enable or disable modmail")
    @app_commands.checks.has_permissions(administrator=True)
    async def modmail_toggle(self, interaction: discord.Interaction, enabled: bool):
        """Toggle modmail"""
        config = self.get_config(interaction.guild.id)
        config['enabled'] = enabled
        self.db.set(str(interaction.guild.id), config)
        
        status = "enabled" if enabled else "disabled"
        embed = discord.Embed(
            description=f"Modmail is now **{status}**.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)


class ModMailView(discord.ui.View):
    def __init__(self, user_id: int, bot):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot
    
    @discord.ui.button(label="Reply", style=discord.ButtonStyle.secondary)
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reply to modmail"""
        await interaction.response.send_modal(ReplyModal(self.user_id, self.bot))
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark as closed"""
        embed = discord.Embed(
            description="Ticket marked as closed.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Notify user
        try:
            user = await self.bot.fetch_user(self.user_id)
            close_embed = discord.Embed(
                description="Your modmail ticket has been closed by staff.",
                color=0x1a1a2e
            )
            await user.send(embed=close_embed)
        except:
            pass


class ReplyModal(discord.ui.Modal, title="Reply to User"):
    reply = discord.ui.TextInput(
        label="Your Reply",
        placeholder="Type your response here...",
        style=discord.TextStyle.long,
        max_length=1000
    )
    
    def __init__(self, user_id: int, bot):
        super().__init__()
        self.user_id = user_id
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        """Send reply to user"""
        try:
            user = await self.bot.fetch_user(self.user_id)
            
            reply_embed = discord.Embed(
                title="Reply from Staff",
                description=self.reply.value,
                color=0x1a1a2e,
                timestamp=discord.utils.utcnow()
            )
            reply_embed.set_footer(text=interaction.guild.name)
            
            await user.send(embed=reply_embed)
            
            confirm = discord.Embed(
                description=f"Reply sent to {user.mention}",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=confirm, ephemeral=True)
            
        except discord.NotFound:
            await interaction.response.send_message("User not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Cannot DM this user.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModMail(bot))