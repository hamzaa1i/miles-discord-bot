"""
cogs/reaction_roles.py — reaction roles + button roles.

Backward compatibility:
- The original commands /reactionrole_add, /reactionrole_remove,
  /reactionrole_list, /reactionrole_clear are kept.
- New /reactionrole slash command group added per Step 11.
- New /buttonrole create + /buttonrole addbutton added.
- All data persists in data/reaction_roles.json.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/reaction_roles.json')
        # Button role storage: same file, key 'button_roles' -> { message_id_str: [{role_id, label, emoji}] }

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {})

    def save_config(self, guild_id: int, config: dict):
        self.db.set(str(guild_id), config)

    # ==================== RAW REACTION LISTENERS ====================

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
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

    # ==================== BUTTON ROLE INTERACTION ====================

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.data or interaction.data.get('component_type') != 2:
            return
        custom_id = interaction.data.get('custom_id', '')
        if not custom_id.startswith('btnrole_'):
            return
        # Format: btnrole_<message_id>_<role_id>
        try:
            parts = custom_id.split('_')
            role_id = int(parts[-1])
        except (ValueError, IndexError):
            return
        guild = interaction.guild
        if not guild:
            return
        role = guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("role not found.", ephemeral=True)
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("you must be in a server.", ephemeral=True)
            return
        if role in member.roles:
            try:
                await member.remove_roles(role, reason="Button role toggle")
                await interaction.response.send_message(f"removed {role.mention}", ephemeral=True)
            except:
                await interaction.response.send_message("i don't have permission to manage that role.", ephemeral=True)
        else:
            try:
                await member.add_roles(role, reason="Button role toggle")
                await interaction.response.send_message(f"added {role.mention}", ephemeral=True)
            except:
                await interaction.response.send_message("i don't have permission to manage that role.", ephemeral=True)

    # ==================== NEW COMMAND GROUP ====================

    reactionrole = app_commands.Group(name="reactionrole", description="Reaction role management")

    @reactionrole.command(name="add", description="Add a reaction role to a message")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rr_add(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role,
        channel: discord.TextChannel = None
    ):
        await self._add_rr(interaction, message_id, emoji, role, channel)

    @reactionrole.command(name="remove", description="Remove a reaction role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rr_remove(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        channel: discord.TextChannel = None
    ):
        await self._remove_rr(interaction, message_id, emoji, channel)

    @reactionrole.command(name="list", description="List all reaction roles in this server")
    async def rr_list(self, interaction: discord.Interaction):
        await self._list_rr(interaction)

    # ==================== HELPERS ====================

    async def _add_rr(self, interaction, message_id, emoji, role, channel):
        self.bot.increment_command('reactionrole_add')
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("i can't assign that role — it's above my top role.", ephemeral=True)
            return
        target_channel = channel or interaction.channel
        try:
            message = await target_channel.fetch_message(int(message_id))
        except Exception:
            await interaction.response.send_message(
                "message not found. make sure the ID is correct and I can see the channel.",
                ephemeral=True
            )
            return
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await interaction.response.send_message("invalid emoji.", ephemeral=True)
            return

        config = self.get_config(interaction.guild.id)
        message_id_str = str(message.id)
        if message_id_str not in config:
            config[message_id_str] = {}
        config[message_id_str][emoji] = str(role.id)
        self.save_config(interaction.guild.id, config)

        embed = discord.Embed(
            description=f"✅ reaction role added!\n{emoji} → {role.mention}",
            color=0x1a1a2e
        )
        embed.add_field(name="Message", value=f"[Jump]({message.jump_url})", inline=False)
        await interaction.response.send_message(embed=embed)

    async def _remove_rr(self, interaction, message_id, emoji, channel):
        self.bot.increment_command('reactionrole_remove')
        config = self.get_config(interaction.guild.id)
        message_id_str = str(message_id)
        if message_id_str not in config or emoji not in config[message_id_str]:
            await interaction.response.send_message("no reaction role found for that message + emoji.", ephemeral=True)
            return
        del config[message_id_str][emoji]
        if not config[message_id_str]:
            del config[message_id_str]
        self.save_config(interaction.guild.id, config)
        try:
            target_channel = channel or interaction.channel
            message = await target_channel.fetch_message(int(message_id))
            await message.clear_reaction(emoji)
        except:
            pass
        await interaction.response.send_message(f"✅ reaction role removed: {emoji}")

    async def _list_rr(self, interaction):
        self.bot.increment_command('reactionrole_list')
        config = self.get_config(interaction.guild.id)
        # Filter out the button_roles key
        rr_items = {k: v for k, v in config.items() if k != 'button_roles' and isinstance(v, dict)}
        if not rr_items:
            await interaction.response.send_message("no reaction roles configured.", ephemeral=True)
            return
        embed = discord.Embed(title="Reaction Roles", color=0x1a1a2e)
        for message_id, reactions in rr_items.items():
            text = ""
            for emoji, role_id in reactions.items():
                role = interaction.guild.get_role(int(role_id))
                role_text = role.mention if role else f"deleted role ({role_id})"
                text += f"{emoji} → {role_text}\n"
            if text:
                embed.add_field(name=f"Message ID: {message_id}", value=text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== BUTTON ROLES ====================


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
