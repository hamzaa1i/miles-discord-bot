"""
cogs/music_disabled.py — full music cog (NOT auto-loaded).

This file is intentionally NOT loaded by main.py (any file ending in
`_disabled.py` is skipped during the dynamic cog scan). The active
`cogs/music.py` is a stub that returns an explanatory embed because
music commands that depend on FFmpeg cannot run on Render's free tier.

To re-enable the full music cog locally:
  1. Make sure FFmpeg is installed on your system:
       - macOS:  `brew install ffmpeg`
       - Ubuntu: `sudo apt install ffmpeg`
       - Windows: download from https://ffmpeg.org/download.html
  2. Install yt-dlp: `pip install yt-dlp`
  3. Either:
       - Rename this file to `cogs/music.py` (overwriting the stub), OR
       - Copy the contents of this file over `cogs/music.py`
  4. Restart the bot

The current implementation below is a Spotify-status viewer (no yt-dlp).
If you want full voice playback, replace this file's body with a yt-dlp
+ FFmpegPCMAudio implementation. The /music command below shows the
Spotify activity of the invoking user (or a mentioned user).
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.embeds import create_embed

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="music", description="Show your current Spotify status")
    async def music(self, interaction: discord.Interaction, user: discord.Member = None):
        """Display Spotify activity"""
        user = user or interaction.user
        
        # Find Spotify activity
        spotify = None
        for activity in user.activities:
            if isinstance(activity, discord.Spotify):
                spotify = activity
                break
        
        if not spotify:
            embed = create_embed(
                title="🎵 No Music Playing",
                description=f"{user.name} isn't listening to Spotify right now!",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Create rich embed
        embed = discord.Embed(
            title="🎵 Now Playing on Spotify",
            color=discord.Color.green()
        )
        
        embed.set_thumbnail(url=spotify.album_cover_url)
        embed.add_field(name="🎵 Song", value=spotify.title, inline=False)
        embed.add_field(name="👤 Artist", value=spotify.artist, inline=True)
        embed.add_field(name="💿 Album", value=spotify.album, inline=True)
        
        # Duration
        duration = spotify.duration.seconds
        position = (spotify.end - spotify.start).seconds
        
        duration_str = f"{duration // 60}:{duration % 60:02d}"
        position_str = f"{position // 60}:{position % 60:02d}"
        
        embed.add_field(name="⏱️ Progress", value=f"{position_str} / {duration_str}", inline=False)
        
        # Progress bar
        progress_percent = (position / duration) * 100
        bar_length = 20
        filled = int((progress_percent / 100) * bar_length)
        bar = "▓" * filled + "░" * (bar_length - filled)
        embed.add_field(name="📊", value=f"`{bar}`", inline=False)
        
        embed.set_footer(text=f"Listening since", icon_url=user.avatar.url if user.avatar else None)
        embed.timestamp = spotify.start
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))