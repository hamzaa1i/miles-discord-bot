import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/reaction_roles.json')

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {})

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Give role when reaction added"""
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        config = self.get_config(guild.id)
        message_id = str(payload.message_id)

        if message_id not in config:
            return

        emoji_str = str(payload.emoji)
        role_id = config[message_id].get(emoji_str)

        if not role_id:
            return

        role = guild.get_role(int(role_id))
        if not role:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            return

        try:
            await member.add_roles(role, reason="Reaction Role")
        except:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Remove role when reaction removed"""
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        config = self.get_config(guild.id)
        message_id = str(payload.message_id)

        if message_id not in config:
            return

        emoji_str = str(payload.emoji)
        role_id = config[message_id].get(emoji_str)

        if not role_id:
            return

        role = guild.get_role(int(role_id))
        if not role:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            return

        try:
            await member.remove_roles(role, reason="Reaction Role Removed")
        except:
            pass

    @app_commands.command(
        name="reactionrole_add",
        description="Add a reaction role to a message"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_add(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role,
        channel: discord.TextChannel = None
    ):
        """Add reaction role"""
        target_channel = channel or interaction.channel

        try:
            message = await target_channel.fetch_message(int(message_id))
        except:
            await interaction.response.send_message(
                "Message not found. Make sure the ID is correct and I can see the channel.",
                ephemeral=True
            )
            return

        # Add reaction to message
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await interaction.response.send_message(
                "Invalid emoji. Make sure it's a valid emoji I can use.",
                ephemeral=True
            )
            return

        # Save config
        config = self.get_config(interaction.guild.id)
        message_id_str = str(message.id)

        if message_id_str not in config:
            config[message_id_str] = {}

        config[message_id_str][emoji] = str(role.id)
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description=f"Reaction role added!\n{emoji} → {role.mention}",
            color=0x1a1a2e
        )
        embed.add_field(
            name="Message",
            value=f"[Jump to Message]({message.jump_url})",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="reactionrole_remove",
        description="Remove a reaction role from a message"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_remove(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        channel: discord.TextChannel = None
    ):
        """Remove reaction role"""
        config = self.get_config(interaction.guild.id)
        message_id_str = str(message_id)

        if message_id_str not in config or emoji not in config[message_id_str]:
            await interaction.response.send_message(
                "No reaction role found for that message and emoji.",
                ephemeral=True
            )
            return

        del config[message_id_str][emoji]
        if not config[message_id_str]:
            del config[message_id_str]

        self.db.set(str(interaction.guild.id), config)

        # Remove reaction from message
        try:
            target_channel = channel or interaction.channel
            message = await target_channel.fetch_message(int(message_id))
            await message.clear_reaction(emoji)
        except:
            pass

        embed = discord.Embed(
            description=f"Reaction role removed: {emoji}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="reactionrole_list",
        description="List all reaction roles in this server"
    )
    async def reactionrole_list(self, interaction: discord.Interaction):
        """List all reaction roles"""
        config = self.get_config(interaction.guild.id)

        if not config:
            embed = discord.Embed(
                description="No reaction roles configured.",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="Reaction Roles",
            color=0x1a1a2e
        )

        for message_id, reactions in config.items():
            reaction_text = ""
            for emoji, role_id in reactions.items():
                role = interaction.guild.get_role(int(role_id))
                role_text = role.mention if role else f"Deleted Role ({role_id})"
                reaction_text += f"{emoji} → {role_text}\n"

            if reaction_text:
                embed.add_field(
                    name=f"Message ID: {message_id}",
                    value=reaction_text,
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="reactionrole_clear",
        description="Clear all reaction roles from a message"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_clear(
        self,
        interaction: discord.Interaction,
        message_id: str,
        channel: discord.TextChannel = None
    ):
        """Clear all reaction roles from a message"""
        config = self.get_config(interaction.guild.id)
        message_id_str = str(message_id)

        if message_id_str not in config:
            await interaction.response.send_message(
                "No reaction roles found for that message.",
                ephemeral=True
            )
            return

        del config[message_id_str]
        self.db.set(str(interaction.guild.id), config)

        # Clear all reactions
        try:
            target_channel = channel or interaction.channel
            message = await target_channel.fetch_message(int(message_id))
            await message.clear_reactions()
        except:
            pass

        embed = discord.Embed(
            description="All reaction roles cleared from that message.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))