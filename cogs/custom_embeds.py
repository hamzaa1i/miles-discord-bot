import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
import re

class CustomEmbeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/custom_embeds.json')
    
    @app_commands.command(name="embed", description="Create a custom embed message")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create_embed(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        color: str = "dark",
        channel: discord.TextChannel = None
    ):
        """Create a custom embed
        
        Colors: dark, red, blue, green, gold, purple, orange, white
        """
        # Color mapping
        colors = {
            "dark": 0x1a1a2e,
            "red": 0xe74c3c,
            "blue": 0x3498db,
            "green": 0x2ecc71,
            "gold": 0xf1c40f,
            "purple": 0x9b59b6,
            "orange": 0xe67e22,
            "white": 0xffffff,
            "black": 0x000000,
            "pink": 0xff69b4,
            "teal": 0x1abc9c
        }
        
        # Handle hex color
        if color.startswith('#'):
            try:
                embed_color = int(color[1:], 16)
            except ValueError:
                embed_color = 0x1a1a2e
        else:
            embed_color = colors.get(color.lower(), 0x1a1a2e)
        
        # Parse description for newlines
        description = description.replace('\\n', '\n')
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )
        
        target_channel = channel or interaction.channel
        
        await target_channel.send(embed=embed)
        
        confirm = discord.Embed(
            description=f"Embed sent to {target_channel.mention}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)
    
    @app_commands.command(name="embed_advanced", description="Create advanced embed with all options")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_advanced(
        self,
        interaction: discord.Interaction,
        title: str = None,
        description: str = None,
        color: str = "dark",
        footer: str = None,
        thumbnail: str = None,
        image: str = None,
        author: str = None,
        channel: discord.TextChannel = None
    ):
        """Advanced embed builder with full customization"""
        colors = {
            "dark": 0x1a1a2e,
            "red": 0xe74c3c,
            "blue": 0x3498db,
            "green": 0x2ecc71,
            "gold": 0xf1c40f,
            "purple": 0x9b59b6,
            "orange": 0xe67e22,
            "white": 0xffffff,
            "black": 0x000000,
            "pink": 0xff69b4,
            "teal": 0x1abc9c
        }
        
        if color.startswith('#'):
            try:
                embed_color = int(color[1:], 16)
            except ValueError:
                embed_color = 0x1a1a2e
        else:
            embed_color = colors.get(color.lower(), 0x1a1a2e)
        
        if not title and not description:
            await interaction.response.send_message(
                "You need at least a title or description.",
                ephemeral=True
            )
            return
        
        # Parse description
        if description:
            description = description.replace('\\n', '\n')
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )
        
        if footer:
            embed.set_footer(text=footer)
        
        if author:
            embed.set_author(name=author)
        
        if thumbnail:
            if thumbnail.startswith('http'):
                embed.set_thumbnail(url=thumbnail)
        
        if image:
            if image.startswith('http'):
                embed.set_image(url=image)
        
        target_channel = channel or interaction.channel
        
        await target_channel.send(embed=embed)
        
        confirm = discord.Embed(
            description=f"Advanced embed sent to {target_channel.mention}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)
    
    @app_commands.command(name="embed_save", description="Save an embed template")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_save(
        self,
        interaction: discord.Interaction,
        name: str,
        title: str,
        description: str,
        color: str = "dark"
    ):
        """Save embed as template for reuse"""
        templates = self.db.get(str(interaction.guild.id), {})
        
        templates[name] = {
            "title": title,
            "description": description,
            "color": color
        }
        
        self.db.set(str(interaction.guild.id), templates)
        
        embed = discord.Embed(
            description=f"Template **{name}** saved. Use `/embed_use {name}` to send it.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="embed_use", description="Send a saved embed template")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_use(
        self,
        interaction: discord.Interaction,
        name: str,
        channel: discord.TextChannel = None
    ):
        """Use a saved embed template"""
        templates = self.db.get(str(interaction.guild.id), {})
        
        if name not in templates:
            await interaction.response.send_message(
                f"Template **{name}** not found.",
                ephemeral=True
            )
            return
        
        template = templates[name]
        
        colors = {
            "dark": 0x1a1a2e,
            "red": 0xe74c3c,
            "blue": 0x3498db,
            "green": 0x2ecc71,
            "gold": 0xf1c40f,
            "purple": 0x9b59b6,
            "orange": 0xe67e22,
        }
        
        embed_color = colors.get(template.get('color', 'dark'), 0x1a1a2e)
        description = template['description'].replace('\\n', '\n')
        
        embed = discord.Embed(
            title=template.get('title'),
            description=description,
            color=embed_color
        )
        
        target_channel = channel or interaction.channel
        await target_channel.send(embed=embed)
        
        confirm = discord.Embed(
            description=f"Template **{name}** sent to {target_channel.mention}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)
    
    @app_commands.command(name="embed_list", description="List saved embed templates")
    async def embed_list(self, interaction: discord.Interaction):
        """List all saved templates"""
        templates = self.db.get(str(interaction.guild.id), {})
        
        if not templates:
            embed = discord.Embed(
                description="No saved templates. Use `/embed_save` to create one.",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Saved Templates",
            color=0x1a1a2e
        )
        
        for name, data in templates.items():
            embed.add_field(
                name=name,
                value=f"Title: {data.get('title', 'None')}\nColor: {data.get('color', 'dark')}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="embed_delete", description="Delete a saved template")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_delete(self, interaction: discord.Interaction, name: str):
        """Delete saved template"""
        templates = self.db.get(str(interaction.guild.id), {})
        
        if name not in templates:
            await interaction.response.send_message(f"Template **{name}** not found.", ephemeral=True)
            return
        
        del templates[name]
        self.db.set(str(interaction.guild.id), templates)
        
        embed = discord.Embed(
            description=f"Template **{name}** deleted.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CustomEmbeds(bot))