"""
cogs/autorole.py — multi-autorole listener.

This cog ONLY provides the on_member_join listener that assigns multiple
roles from data/autorole.json. The /autorole slash command for setting a
single auto-role lives in cogs/welcome.py.

The old /autorole_add, /autorole_remove, /autorole_list top-level
commands were removed to stay under Discord's 100 global slash command
limit. The listener still works for any roles previously saved to
data/autorole.json.
"""
import discord
from discord.ext import commands
from utils.database import Database


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/autorole.json')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Give all configured roles on join."""
        try:
            config = self.db.get(str(member.guild.id), {})
        except Exception:
            return
        role_ids = config.get('roles', [])
        for role_id in role_ids:
            try:
                role = member.guild.get_role(int(role_id))
                if role:
                    await member.add_roles(role, reason="Auto Role")
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(AutoRole(bot))
