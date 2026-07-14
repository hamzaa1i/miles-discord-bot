"""
cogs/weather.py — weather command (separate from utility.py per spec).

Uses https://wttr.in/{city}?format=j1 with aiohttp, parses the JSON,
and returns an embed with weather emoji based on condition, temperature,
feels-like, condition, humidity, and wind speed.
"""
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
from utils.constants import COLOR_INFO


def weather_emoji(condition: str) -> str:
    """Map a weather condition string to an emoji."""
    c = (condition or '').lower()
    if any(w in c for w in ['snow', 'blizzard', 'sleet']):
        return '❄️'
    if any(w in c for w in ['rain', 'drizzle', 'shower']):
        return '🌧️'
    if any(w in c for w in ['thunder', 'storm', 'lightning']):
        return '⛈️'
    if any(w in c for w in ['fog', 'mist', 'haze', 'smoke']):
        return '🌫️'
    if any(w in c for w in ['cloud', 'overcast']):
        return '☁️'
    if any(w in c for w in ['partly', 'scattered']):
        return '⛅'
    if any(w in c for w in ['clear', 'sunny', 'hot']):
        return '☀️'
    if any(w in c for w in ['wind', 'breeze']):
        return '💨'
    return '🌤️'


class Weather(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="weather", description="Get current weather for a city")
    async def weather(self, interaction: discord.Interaction, city: str):
        self.bot.increment_command('weather')
        await interaction.response.defer()
        embed = await self._fetch_weather_embed(city)
        try:
            await interaction.followup.send(embed=embed)
        except Exception:
            pass

    async def _fetch_weather_embed(self, city: str) -> discord.Embed:
        """Fetch weather from wttr.in and build an embed."""
        try:
            url = f"https://wttr.in/{city}?format=j1"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "curl/7.68.0", "Accept": "application/json"}
                ) as r:
                    if r.status == 404:
                        return discord.Embed(
                            title="❌ City not found",
                            description=f"couldn't find a city called `{city}`.",
                            color=0xed4245
                        )
                    if r.status != 200:
                        return discord.Embed(
                            description=f"couldn't fetch weather for {city} (status {r.status})",
                            color=0xed4245
                        )
                    text_resp = await r.text()
                    if not text_resp.strip().startswith("{"):
                        return discord.Embed(
                            description=f"couldn't find weather for **{city}**.",
                            color=0xed4245
                        )
                    try:
                        data = json.loads(text_resp)
                    except Exception:
                        return discord.Embed(
                            description=f"couldn't parse weather data for **{city}**.",
                            color=0xed4245
                        )

            current = data.get('current_condition', [{}])[0]
            area = data.get('nearest_area', [{}])[0]

            temp_c = current.get('temp_C', '?')
            temp_f = current.get('temp_F', '?')
            feels_c = current.get('FeelsLikeC', '?')
            feels_f = current.get('FeelsLikeF', '?')
            humidity = current.get('humidity', '?')
            wind = current.get('windspeedKmph', '?')
            desc_list = current.get('weatherDesc', [{}])
            desc = desc_list[0].get('value', 'unknown') if desc_list else 'unknown'

            city_name = area.get('areaName', [{}])[0].get('value', city) if area.get('areaName') else city
            country = area.get('country', [{}])[0].get('value', '') if area.get('country') else ''
            region = area.get('region', [{}])[0].get('value', '') if area.get('region') else ''

            emoji = weather_emoji(desc)
            title = f"{emoji} Weather — {city_name}"
            if country:
                title += f", {country}"

            embed = discord.Embed(title=title, color=COLOR_INFO)
            embed.add_field(name="🌡️ Temperature", value=f"**{temp_c}°C** ({temp_f}°F)", inline=True)
            embed.add_field(name="🤔 Feels Like", value=f"**{feels_c}°C** ({feels_f}°F)", inline=True)
            embed.add_field(name="☁️ Condition", value=desc, inline=True)
            embed.add_field(name="💧 Humidity", value=f"{humidity}%", inline=True)
            embed.add_field(name="💨 Wind Speed", value=f"{wind} km/h", inline=True)
            if region:
                embed.add_field(name="📍 Region", value=region, inline=True)
            embed.set_footer(text="Weather data from wttr.in")
            return embed
        except Exception as e:
            return discord.Embed(
                description=f"couldn't fetch weather for {city}. ({e})",
                color=0xed4245
            )


async def setup(bot):
    await bot.add_cog(Weather(bot))
