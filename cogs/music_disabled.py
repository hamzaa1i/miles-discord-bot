"""
cogs/music.py — music stub.

The full music cog (Spotify status viewer + future yt-dlp player) lives in
cogs/music_disabled.py. It is not auto-loaded because main.py skips any
file ending in `_disabled.py`. Music commands that depend on FFmpeg
cannot run on Render's free tier (FFmpeg is not installed there).

To re-enable locally:
  1. Make sure FFmpeg is installed on your system:
       - macOS:  `brew install ffmpeg`
       - Ubuntu: `sudo apt install ffmpeg`
       - Windows: download from https://ffmpeg.org/download.html
  2. Install yt-dlp: `pip install yt-dlp`
  3. Rename cogs/music_disabled.py to cogs/music.py
       (or copy the contents of music_disabled.py over this file)
  4. Restart the bot

This stub keeps the /music command available so users get a friendly
message instead of a silent failure.
"""
import discord
from discord.ext import commands
from discord import app_commands


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="music", description="Music feature availability")
    async def music(self, interaction: discord.Interaction):
        self.bot.increment_command('music')
        embed = discord.Embed(
            title="🎵 Music — unavailable on this host",
            description=(
                "Music is currently unavailable on this hosting plan. "
                "Self-host the bot to enable music features.\n\n"
                "See `cogs/music_disabled.py` for the full implementation "
                "and instructions on how to re-enable it locally with "
                "FFmpeg installed."
            ),
            color=0x1a1a2e
        )
        embed.set_footer(text="cyn — music module")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Music(bot))
