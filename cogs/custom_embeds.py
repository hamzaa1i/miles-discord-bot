import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database

class CustomEmbeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/custom_embeds.json')

    embed_group = app_commands.Group(name="embed", description="Create and manage custom embeds")

    @embed_group.command(name="create", description="Create a custom embed")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create(self, interaction: discord.Interaction, title: str, description: str, color: str = "dark", channel: discord.TextChannel = None):
        colors = {"dark": 0x1a1a2e, "red": 0xe74c3c, "blue": 0x3498db, "green": 0x2ecc71, "gold": 0xf1c40f, "purple": 0x9b59b6, "orange": 0xe67e22, "white": 0xffffff, "black": 0x000000, "pink": 0xff69b4, "teal": 0x1abc9c}
        if color.startswith('#'):
            try: c = int(color[1:], 16)
            except: c = 0x1a1a2e
        else: c = colors.get(color.lower(), 0x1a1a2e)
        embed = discord.Embed(title=title, description=description.replace('\\n', '\n'), color=c)
        target = channel or interaction.channel
        await target.send(embed=embed)
        await interaction.response.send_message(f"sent to {target.mention}", ephemeral=True)

    @embed_group.command(name="advanced", description="Full embed builder")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def advanced(self, interaction: discord.Interaction, title: str = None, description: str = None, color: str = "dark", footer: str = None, thumbnail: str = None, image: str = None, channel: discord.TextChannel = None):
        if not title and not description:
            await interaction.response.send_message("need title or description.", ephemeral=True)
            return
        colors = {"dark": 0x1a1a2e, "red": 0xe74c3c, "blue": 0x3498db, "green": 0x2ecc71, "gold": 0xf1c40f, "purple": 0x9b59b6}
        c = colors.get(color.lower(), 0x1a1a2e)
        embed = discord.Embed(title=title, description=description.replace('\\n', '\n') if description else None, color=c)
        if footer: embed.set_footer(text=footer)
        if thumbnail and thumbnail.startswith('http'): embed.set_thumbnail(url=thumbnail)
        if image and image.startswith('http'): embed.set_image(url=image)
        target = channel or interaction.channel
        await target.send(embed=embed)
        await interaction.response.send_message(f"sent to {target.mention}", ephemeral=True)

    @embed_group.command(name="save", description="Save embed template")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def save(self, interaction: discord.Interaction, name: str, title: str, description: str, color: str = "dark"):
        templates = self.db.get(str(interaction.guild.id), {})
        templates[name] = {"title": title, "description": description, "color": color}
        self.db.set(str(interaction.guild.id), templates)
        await interaction.response.send_message(f"template **{name}** saved. use `/embed use {name}`", ephemeral=True)

    @embed_group.command(name="use", description="Use saved template")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def use(self, interaction: discord.Interaction, name: str, channel: discord.TextChannel = None):
        templates = self.db.get(str(interaction.guild.id), {})
        if name not in templates:
            await interaction.response.send_message(f"template **{name}** not found.", ephemeral=True)
            return
        t = templates[name]
        colors = {"dark": 0x1a1a2e, "red": 0xe74c3c, "blue": 0x3498db, "green": 0x2ecc71}
        c = colors.get(t.get('color', 'dark'), 0x1a1a2e)
        embed = discord.Embed(title=t.get('title'), description=t['description'].replace('\\n', '\n'), color=c)
        target = channel or interaction.channel
        await target.send(embed=embed)
        await interaction.response.send_message(f"sent **{name}** to {target.mention}", ephemeral=True)

    @embed_group.command(name="list", description="List saved templates")
    async def list_templates(self, interaction: discord.Interaction):
        templates = self.db.get(str(interaction.guild.id), {})
        if not templates:
            await interaction.response.send_message("no templates saved.", ephemeral=True)
            return
        embed = discord.Embed(title="Embed Templates", color=0x1a1a2e)
        for name, data in templates.items():
            embed.add_field(name=name, value=f"Title: {data.get('title', 'None')}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @embed_group.command(name="delete", description="Delete a template")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete(self, interaction: discord.Interaction, name: str):
        templates = self.db.get(str(interaction.guild.id), {})
        if name not in templates:
            await interaction.response.send_message(f"**{name}** not found.", ephemeral=True)
            return
        del templates[name]
        self.db.set(str(interaction.guild.id), templates)
        await interaction.response.send_message(f"**{name}** deleted.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CustomEmbeds(bot))