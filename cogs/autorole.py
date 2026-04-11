import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/autorole.json')
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Give role on join"""
        config = self.db.get(str(member.guild.id), {})
        role_ids = config.get('roles', [])
        
        for role_id in role_ids:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto Role")
                except:
                    pass
    
    @app_commands.command(name="autorole_add", description="Add a role to give on join")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_add(self, interaction: discord.Interaction, role: discord.Role):
        """Add autorole"""
        config = self.db.get(str(interaction.guild.id), {'roles': []})
        
        if str(role.id) in config['roles']:
            await interaction.response.send_message(
                f"{role.mention} is already an auto role.",
                ephemeral=True
            )
            return
        
        config['roles'].append(str(role.id))
        self.db.set(str(interaction.guild.id), config)
        
        embed = discord.Embed(
            description=f"{role.mention} will now be given to new members.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="autorole_remove", description="Remove an auto role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_remove(self, interaction: discord.Interaction, role: discord.Role):
        """Remove autorole"""
        config = self.db.get(str(interaction.guild.id), {'roles': []})
        
        if str(role.id) not in config['roles']:
            await interaction.response.send_message(
                f"{role.mention} is not an auto role.",
                ephemeral=True
            )
            return
        
        config['roles'].remove(str(role.id))
        self.db.set(str(interaction.guild.id), config)
        
        embed = discord.Embed(
            description=f"{role.mention} removed from auto roles.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="autorole_list", description="View all auto roles")
    async def autorole_list(self, interaction: discord.Interaction):
        """List autoroles"""
        config = self.db.get(str(interaction.guild.id), {'roles': []})
        
        if not config['roles']:
            embed = discord.Embed(
                description="No auto roles configured.",
                color=0x1a1a2e
            )
        else:
            roles = []
            for role_id in config['roles']:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    roles.append(role.mention)
            
            embed = discord.Embed(
                title="Auto Roles",
                description="\n".join(roles) if roles else "No valid roles found.",
                color=0x1a1a2e
            )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AutoRole(bot))