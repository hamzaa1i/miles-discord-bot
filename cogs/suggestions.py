"""
cogs/suggestions.py — suggestions system with standalone commands.

/suggest [text] — submit a suggestion
/suggest_approve [id] — approve (mod)
/suggest_deny [id] — deny (mod)
/suggest_list — view pending
/suggest_setup #channel — set channel (mod)

Data in data/suggestions.json per guild.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.database import Database


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/suggestions.json')

    def get_guild_data(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'channel_id': None,
            'counter': 0,
            'items': {},
        })

    def save_guild_data(self, guild_id: int, data: dict):
        self.db.set(str(guild_id), data)

    @app_commands.command(name="suggest", description="Submit a suggestion")
    @app_commands.describe(text="Your suggestion")
    async def suggest(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('suggest')
        await interaction.response.defer(ephemeral=True)
        data = self.get_guild_data(interaction.guild.id)
        channel_id = data.get('channel_id')
        if not channel_id:
            await interaction.followup.send("suggestions aren't set up. ask a mod to run `/suggest_setup #channel`.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.followup.send("configured channel not found.", ephemeral=True)
            return

        data['counter'] = data.get('counter', 0) + 1
        sid = str(data['counter'])

        embed = discord.Embed(
            title=f"Suggestion #{sid}",
            description=text,
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        embed.add_field(name="Status", value="⏳ Pending", inline=True)
        embed.set_footer(text=f"Submitter ID: {interaction.user.id} · Suggestion ID: {sid}")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

        data['items'][sid] = {
            'user_id': str(interaction.user.id),
            'content': text,
            'status': 'pending',
            'message_id': str(msg.id),
            'channel_id': str(channel.id),
            'submitted_at': datetime.utcnow().isoformat(),
        }
        self.save_guild_data(interaction.guild.id, data)
        await interaction.followup.send(f"✅ suggestion #{sid} submitted in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="suggest_setup", description="Set the suggestions channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def suggest_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('suggest_setup')
        data = self.get_guild_data(interaction.guild.id)
        data['channel_id'] = str(channel.id)
        self.save_guild_data(interaction.guild.id, data)
        await interaction.response.send_message(f"✅ suggestions channel set to {channel.mention}.")

    @app_commands.command(name="suggest_approve", description="Approve a suggestion (mod only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def suggest_approve(self, interaction: discord.Interaction, suggestion_id: int, reason: str = ""):
        self.bot.increment_command('suggest_approve')
        await interaction.response.defer(ephemeral=True)
        await self._review(interaction, str(suggestion_id), 'approved', reason)

    @app_commands.command(name="suggest_deny", description="Deny a suggestion (mod only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def suggest_deny(self, interaction: discord.Interaction, suggestion_id: int, reason: str = ""):
        self.bot.increment_command('suggest_deny')
        await interaction.response.defer(ephemeral=True)
        await self._review(interaction, str(suggestion_id), 'denied', reason)

    @app_commands.command(name="suggest_list", description="View pending suggestions")
    async def suggest_list(self, interaction: discord.Interaction):
        self.bot.increment_command('suggest_list')
        await interaction.response.defer(ephemeral=True)
        data = self.get_guild_data(interaction.guild.id)
        items = data.get('items', {})
        pending = [(sid, item) for sid, item in items.items() if item.get('status') == 'pending']
        if not pending:
            await interaction.followup.send("no pending suggestions.", ephemeral=True)
            return
        pending.sort(key=lambda x: int(x[0]), reverse=True)
        embed = discord.Embed(title="⏳ Pending Suggestions", color=0x1a1a2e)
        for sid, item in pending[:10]:
            content = item.get('content', '')[:200]
            embed.add_field(name=f"#{sid} — by <@{item.get('user_id', '?')}>", value=content or "*empty*", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _review(self, interaction: discord.Interaction, sid: str, status: str, reason: str):
        data = self.get_guild_data(interaction.guild.id)
        item = data.get('items', {}).get(sid)
        if not item:
            await interaction.followup.send(f"no suggestion with id #{sid}.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(int(item['channel_id']))
        if not channel:
            await interaction.followup.send("suggestion channel not found.", ephemeral=True)
            return
        try:
            msg = await channel.fetch_message(int(item['message_id']))
            embed = msg.embeds[0] if msg.embeds else discord.Embed()
        except Exception:
            await interaction.followup.send("couldn't fetch suggestion message.", ephemeral=True)
            return
        status_emoji = "✅" if status == 'approved' else "❌"
        embed.clear_fields()
        embed.add_field(name="Status", value=f"{status_emoji} {status.title()}", inline=True)
        embed.add_field(name="Reviewed by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided.", inline=False)
        embed.color = discord.Color.green() if status == 'approved' else discord.Color.red()
        try:
            await msg.edit(embed=embed)
        except Exception:
            pass
        item['status'] = status
        item['reason'] = reason
        item['reviewed_by'] = str(interaction.user.id)
        data['items'][sid] = item
        self.save_guild_data(interaction.guild.id, data)
        action = "approved" if status == 'approved' else "denied"
        await interaction.followup.send(f"✅ suggestion #{sid} {action}.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Suggestions(bot))
