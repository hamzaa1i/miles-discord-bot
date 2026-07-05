"""
cogs/auto_responder.py — auto-responder + custom commands.

Stores per-guild trigger/response pairs and custom commands in
data/autorespond.json.

Auto-responder: any message (case-insensitive substring match) that
contains a registered trigger gets the matching response posted.
Custom commands: !name or @bot name → response.

Supported response variables: {user}, {server}, {channel}.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database


class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/autorespond.json')

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'triggers': {},     # trigger_lower -> response
            'commands': {},     # name_lower -> response
        })

    def save_config(self, guild_id: int, config: dict):
        self.db.set(str(guild_id), config)

    def _format_response(self, text: str, message: discord.Message) -> str:
        return text.format(
            user=message.author.display_name,
            server=message.guild.name if message.guild else "DM",
            channel=message.channel.name if hasattr(message.channel, 'name') else "DM",
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = self.get_config(message.guild.id)
        content_lower = message.content.lower()

        # Custom command via prefix
        prefix = '!'
        try:
            cp = self.bot.command_prefix
            if isinstance(cp, (list, tuple)):
                prefix = cp[0] if cp else '!'
            elif isinstance(cp, str):
                prefix = cp
        except Exception:
            pass
        if message.content.startswith(prefix):
            cmd_name = message.content[len(prefix):].split()[0].lower()
            if cmd_name in config.get('commands', {}):
                response = self._format_response(config['commands'][cmd_name], message)
                await message.channel.send(response)
                return

        # Custom command via mention
        if self.bot.user in message.mentions:
            stripped = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            stripped = stripped.replace(f'<@!{self.bot.user.id}>', '').strip()
            if stripped:
                first_word = stripped.split()[0].lower()
                if first_word in config.get('commands', {}):
                    response = self._format_response(config['commands'][first_word], message)
                    await message.channel.send(response)
                    return

        # Auto-responder whole-word match (DESIGN FIX 4)
        import re as _re
        for trigger, response in config.get('triggers', {}).items():
            if _re.search(rf'\b{_re.escape(trigger)}\b', message.content, _re.IGNORECASE):
                formatted = self._format_response(response, message)
                await message.channel.send(formatted)
                return

    # ==================== /autorespond commands ====================

    autorespond = app_commands.Group(name="autorespond", description="Auto-responder management")

    @autorespond.command(name="add", description="Add a trigger-response pair")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def autorespond_add(self, interaction: discord.Interaction, trigger: str, response: str):
        self.bot.increment_command('autorespond_add')
        config = self.get_config(interaction.guild.id)
        config['triggers'][trigger.lower()] = response
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(
            f"✅ trigger added.\n**trigger:** `{trigger}`\n**response:** `{response}`"
        )

    @autorespond.command(name="remove", description="Remove a trigger-response pair")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def autorespond_remove(self, interaction: discord.Interaction, trigger: str):
        self.bot.increment_command('autorespond_remove')
        config = self.get_config(interaction.guild.id)
        if trigger.lower() in config['triggers']:
            del config['triggers'][trigger.lower()]
            self.save_config(interaction.guild.id, config)
            await interaction.response.send_message(f"✅ removed trigger `{trigger}`")
        else:
            await interaction.response.send_message(f"no trigger matching `{trigger}`.", ephemeral=True)

    @autorespond.command(name="list", description="List all triggers for this server")
    async def autorespond_list(self, interaction: discord.Interaction):
        self.bot.increment_command('autorespond_list')
        config = self.get_config(interaction.guild.id)
        triggers = config.get('triggers', {})
        if not triggers:
            await interaction.response.send_message("no triggers set.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📢 Auto-responders",
            color=0x1a1a2e,
            description=f"{len(triggers)} trigger(s) configured."
        )
        # Paginate to stay under field length limits
        items = list(triggers.items())
        per_page = 10
        for i in range(0, len(items), per_page):
            chunk = items[i:i+per_page]
            value = "\n".join(f"**{t}** → {r[:80]}" for t, r in chunk)
            embed.add_field(name=f"Page {i//per_page + 1}", value=value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== /customcmd commands ====================

    customcmd = app_commands.Group(name="customcmd", description="Custom command management")

    @customcmd.command(name="add", description="Add a custom command")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def customcmd_add(self, interaction: discord.Interaction, name: str, response: str):
        self.bot.increment_command('customcmd_add')
        name = name.lower()
        if len(name) > 32 or not name.replace('_', '').isalnum():
            await interaction.response.send_message("name must be alphanumeric (underscores ok), max 32 chars.", ephemeral=True)
            return
        config = self.get_config(interaction.guild.id)
        config['commands'][name] = response
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(
            f"✅ custom command added.\nuse `!{name}` or `@{self.bot.user.name} {name}` to trigger it."
        )

    @customcmd.command(name="remove", description="Remove a custom command")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def customcmd_remove(self, interaction: discord.Interaction, name: str):
        self.bot.increment_command('customcmd_remove')
        config = self.get_config(interaction.guild.id)
        if name.lower() in config['commands']:
            del config['commands'][name.lower()]
            self.save_config(interaction.guild.id, config)
            await interaction.response.send_message(f"✅ removed custom command `{name}`")
        else:
            await interaction.response.send_message(f"no custom command named `{name}`.", ephemeral=True)

    @customcmd.command(name="list", description="List all custom commands")
    async def customcmd_list(self, interaction: discord.Interaction):
        self.bot.increment_command('customcmd_list')
        config = self.get_config(interaction.guild.id)
        commands = config.get('commands', {})
        if not commands:
            await interaction.response.send_message("no custom commands set.", ephemeral=True)
            return
        embed = discord.Embed(
            title="⚡ Custom commands",
            color=0x1a1a2e,
            description=", ".join(f"`!{name}`" for name in commands.keys())
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
