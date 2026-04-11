import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/starboard.json')

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'enabled': False,
            'channel_id': None,
            'threshold': 3,
            'emoji': '⭐',
            'starred': {}
        })

    def save_config(self, guild_id: int, data: dict):
        self.db.set(str(guild_id), data)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return

        config = self.get_config(payload.guild_id)

        if not config['enabled']:
            return

        if not config['channel_id']:
            return

        if str(payload.emoji) != config['emoji']:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except:
            return

        # Don't star bot messages
        if message.author.bot:
            return

        # Count star reactions
        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == config['emoji']:
                star_count = reaction.count
                break

        if star_count < config['threshold']:
            return

        starboard_channel = guild.get_channel(int(config['channel_id']))
        if not starboard_channel:
            return

        message_id_str = str(message.id)

        # Check if already starred
        if message_id_str in config.get('starred', {}):
            # Update existing star message
            try:
                star_msg = await starboard_channel.fetch_message(
                    int(config['starred'][message_id_str])
                )
                await star_msg.edit(
                    content=f"{config['emoji']} **{star_count}** | {channel.mention}"
                )
            except:
                pass
            return

        # Create starboard embed
        embed = discord.Embed(
            description=message.content or "*no text*",
            color=0x1a1a2e,
            timestamp=message.created_at
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.avatar.url if message.author.avatar else None
        )

        if message.attachments:
            embed.set_image(url=message.attachments[0].url)

        embed.add_field(
            name="original",
            value=f"[jump]({message.jump_url})"
        )
        embed.set_footer(text=f"ID: {message.id}")

        try:
            star_msg = await starboard_channel.send(
                content=f"{config['emoji']} **{star_count}** | {channel.mention}",
                embed=embed
            )

            if 'starred' not in config:
                config['starred'] = {}
            config['starred'][message_id_str] = str(star_msg.id)
            self.save_config(payload.guild_id, config)
        except:
            pass

    @app_commands.command(name="starboard_setup", description="Setup the starboard")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        threshold: int = 3,
        emoji: str = "⭐"
    ):
        config = self.get_config(interaction.guild.id)
        config['enabled'] = True
        config['channel_id'] = str(channel.id)
        config['threshold'] = max(1, threshold)
        config['emoji'] = emoji
        self.save_config(interaction.guild.id, config)

        embed = discord.Embed(
            description=(
                f"starboard set up in {channel.mention}\n"
                f"threshold: **{threshold}** {emoji}"
            ),
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="starboard_toggle", description="Enable/disable starboard")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_toggle(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):
        config = self.get_config(interaction.guild.id)
        config['enabled'] = enabled
        self.save_config(interaction.guild.id, config)

        status = "enabled" if enabled else "disabled"
        embed = discord.Embed(
            description=f"starboard is now **{status}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Starboard(bot))