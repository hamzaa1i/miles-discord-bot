import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.database import Database

class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/suggestions.json')

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(f"config_{guild_id}", {
            'channel_id': None,
            'enabled': False,
            'review_channel': None
        })

    @app_commands.command(name="suggest", description="Submit a suggestion")
    async def suggest(
        self,
        interaction: discord.Interaction,
        suggestion: str
    ):
        config = self.get_config(interaction.guild.id)

        if not config['enabled'] or not config['channel_id']:
            await interaction.response.send_message(
                "suggestions aren't set up yet.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(int(config['channel_id']))
        if not channel:
            await interaction.response.send_message(
                "suggestion channel not found.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            description=suggestion,
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        embed.set_footer(text=f"ID: {interaction.user.id}")
        embed.add_field(name="Status", value="Pending", inline=True)

        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        # Save suggestion
        suggestions = self.db.get(str(interaction.guild.id), {})
        suggestions[str(msg.id)] = {
            'user_id': str(interaction.user.id),
            'content': suggestion,
            'status': 'pending',
            'submitted_at': datetime.utcnow().isoformat()
        }
        self.db.set(str(interaction.guild.id), suggestions)

        await interaction.response.send_message(
            f"suggestion submitted to {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="suggestion_approve",
        description="Approve a suggestion"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def suggestion_approve(
        self,
        interaction: discord.Interaction,
        message_id: str,
        reason: str = "Approved"
    ):
        config = self.get_config(interaction.guild.id)
        if not config['channel_id']:
            await interaction.response.send_message(
                "suggestions not set up.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(int(config['channel_id']))
        if not channel:
            return

        try:
            msg = await channel.fetch_message(int(message_id))
            embed = msg.embeds[0] if msg.embeds else discord.Embed()

            for i, field in enumerate(embed.fields):
                if field.name == "Status":
                    embed.set_field_at(
                        i,
                        name="Status",
                        value="✅ Approved",
                        inline=True
                    )
                    break
            else:
                embed.add_field(name="Status", value="✅ Approved", inline=True)

            embed.add_field(
                name="Reviewed by",
                value=interaction.user.mention,
                inline=True
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.color = discord.Color.green()

            await msg.edit(embed=embed)

            await interaction.response.send_message(
                "suggestion approved.",
                ephemeral=True
            )
        except:
            await interaction.response.send_message(
                "couldn't find that message.",
                ephemeral=True
            )

    @app_commands.command(
        name="suggestion_deny",
        description="Deny a suggestion"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def suggestion_deny(
        self,
        interaction: discord.Interaction,
        message_id: str,
        reason: str = "Denied"
    ):
        config = self.get_config(interaction.guild.id)
        if not config['channel_id']:
            await interaction.response.send_message(
                "suggestions not set up.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(int(config['channel_id']))
        if not channel:
            return

        try:
            msg = await channel.fetch_message(int(message_id))
            embed = msg.embeds[0] if msg.embeds else discord.Embed()

            for i, field in enumerate(embed.fields):
                if field.name == "Status":
                    embed.set_field_at(
                        i,
                        name="Status",
                        value="❌ Denied",
                        inline=True
                    )
                    break
            else:
                embed.add_field(name="Status", value="❌ Denied", inline=True)

            embed.add_field(
                name="Reviewed by",
                value=interaction.user.mention,
                inline=True
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.color = discord.Color.red()

            await msg.edit(embed=embed)

            await interaction.response.send_message(
                "suggestion denied.",
                ephemeral=True
            )
        except:
            await interaction.response.send_message(
                "couldn't find that message.",
                ephemeral=True
            )

    @app_commands.command(
        name="suggestions_setup",
        description="Setup the suggestion system"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def suggestions_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        config = self.get_config(interaction.guild.id)
        config['channel_id'] = str(channel.id)
        config['enabled'] = True
        self.db.set(f"config_{interaction.guild.id}", config)

        embed = discord.Embed(
            description=(
                f"suggestions will be sent to {channel.mention}\n"
                f"users can submit with `/suggest`"
            ),
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Suggestions(bot))