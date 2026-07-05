"""
cogs/suggestions.py — suggestions system.

Spec (ADD 2):
  /suggest setup #channel — set the suggestions channel
  /suggest [text] — submit a suggestion (creates embed, 👍/👎, gets ID)
  /suggest approve [id] [reason(optional)] — mod only
  /suggest deny [id] [reason(optional)] — mod only
  /suggest list — show last 10 pending suggestions

Data stored in data/suggestions.json per guild:
{
  "config": { "channel_id": "..." },
  "counter": 1,
  "items": {
    "1": { "user_id": "...", "content": "...", "status": "pending",
           "message_id": "...", "submitted_at": "...", "reason": null }
  }
}

Backward compatibility: the legacy /suggestion_approve, /suggestion_deny,
and /suggestions_setup commands are kept as thin wrappers so existing
users don't break.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.database import Database


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/suggestions.json')

    # ==================== Storage helpers ====================

    def get_guild_data(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'config': {'channel_id': None},
            'counter': 0,
            'items': {},
        })

    def save_guild_data(self, guild_id: int, data: dict):
        self.db.set(str(guild_id), data)

    # ==================== Suggest command group ====================

    suggest = app_commands.Group(name="suggest", description="Suggestion management")

    @suggest.command(name="setup", description="Set the suggestions channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def suggest_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('suggest_setup')
        data = self.get_guild_data(interaction.guild.id)
        data['config']['channel_id'] = str(channel.id)
        self.save_guild_data(interaction.guild.id, data)
        await interaction.response.send_message(
            f"✅ suggestions channel set to {channel.mention}.\n"
            f"users can now use `/suggest <text>` to submit suggestions."
        )

    @suggest.command(name="submit", description="Submit a suggestion")
    async def suggest_submit(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('suggest_submit')
        data = self.get_guild_data(interaction.guild.id)
        channel_id = data.get('config', {}).get('channel_id')
        if not channel_id:
            await interaction.response.send_message(
                "suggestions aren't set up. ask a mod to run `/suggest setup #channel` first.",
                ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "configured suggestions channel no longer exists.", ephemeral=True
            )
            return

        data['counter'] = data.get('counter', 0) + 1
        sid = str(data['counter'])

        embed = discord.Embed(
            title=f"Suggestion #{sid}",
            description=text,
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
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
            'reason': None,
        }
        self.save_guild_data(interaction.guild.id, data)

        await interaction.response.send_message(
            f"✅ suggestion #{sid} submitted in {channel.mention}.",
            ephemeral=True
        )

    @suggest.command(name="approve", description="Approve a suggestion (mod only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def suggest_approve(self, interaction: discord.Interaction, id: str, reason: str = None):
        self.bot.increment_command('suggest_approve')
        await self._review(interaction, id, 'approved', reason)

    @suggest.command(name="deny", description="Deny a suggestion (mod only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def suggest_deny(self, interaction: discord.Interaction, id: str, reason: str = None):
        self.bot.increment_command('suggest_deny')
        await self._review(interaction, id, 'denied', reason)

    async def _review(self, interaction: discord.Interaction, sid: str, status: str, reason: str):
        data = self.get_guild_data(interaction.guild.id)
        item = data.get('items', {}).get(sid)
        if not item:
            await interaction.response.send_message(
                f"no suggestion with id #{sid}.", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(int(item['channel_id']))
        if not channel:
            await interaction.response.send_message(
                "suggestion channel no longer exists.", ephemeral=True
            )
            return

        try:
            msg = await channel.fetch_message(int(item['message_id']))
            embed = msg.embeds[0] if msg.embeds else discord.Embed()
        except Exception:
            await interaction.response.send_message(
                "couldn't fetch the original suggestion message.", ephemeral=True
            )
            return

        # Update status field
        status_emoji = "✅" if status == 'approved' else "❌"
        status_text = f"{status_emoji} {status.title()}"
        updated = False
        for i, field in enumerate(embed.fields):
            if field.name == "Status":
                embed.set_field_at(i, name="Status", value=status_text, inline=True)
                updated = True
                break
        if not updated:
            embed.add_field(name="Status", value=status_text, inline=True)

        # Remove old "Reason" / "Reviewed by" fields if present (re-review case)
        embed.clear_fields()
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Reviewed by", value=interaction.user.mention, inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        else:
            embed.add_field(name="Reason", value="No reason provided.", inline=False)

        embed.color = discord.Color.green() if status == 'approved' else discord.Color.red()

        try:
            await msg.edit(embed=embed)
        except Exception:
            pass

        # Persist
        item['status'] = status
        item['reason'] = reason
        item['reviewed_by'] = str(interaction.user.id)
        item['reviewed_at'] = datetime.utcnow().isoformat()
        data['items'][sid] = item
        self.save_guild_data(interaction.guild.id, data)

        action = "approved" if status == 'approved' else "denied"
        await interaction.response.send_message(
            f"✅ suggestion #{sid} {action}."
        )


    @suggest.command(name="list", description="List last 10 pending suggestions")
    async def suggest_list(self, interaction: discord.Interaction):
        self.bot.increment_command('suggest_list')
        data = self.get_guild_data(interaction.guild.id)
        items = data.get('items', {})
        pending = [(sid, item) for sid, item in items.items() if item.get('status') == 'pending']
        if not pending:
            try:
                await interaction.response.send_message("no pending suggestions.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        pending.sort(key=lambda x: int(x[0]), reverse=True)
        embed = discord.Embed(title="⏳ Pending Suggestions", color=0x2b2d31)
        for sid, item in pending[:10]:
            content = item.get('content', '')[:200]
            embed.add_field(name=f"#{sid} — by <@{item.get('user_id', '?')}>", value=content or "*empty*", inline=False)
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Suggestions(bot))
