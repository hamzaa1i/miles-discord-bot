import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from utils.database import Database
import random

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/leveling.json')
        self.config_db = Database('data/level_config.json')
        self.xp_cooldowns = {}
        self.xp_min = 15
        self.xp_max = 25
        self.cooldown = 60

    def get_user_data(self, guild_id, user_id):
        return self.db.get(f"{guild_id}_{user_id}", {'xp': 0, 'level': 0, 'total_xp': 0, 'last_message': None})

    def save_user_data(self, guild_id, user_id, data):
        self.db.set(f"{guild_id}_{user_id}", data)

    def xp_for_level(self, level):
        return 5 * (level ** 2) + 50 * level + 100

    def get_level_from_xp(self, total_xp):
        level = 0
        xp_remaining = total_xp
        while True:
            needed = self.xp_for_level(level)
            if xp_remaining < needed:
                return level, xp_remaining, needed
            xp_remaining -= needed
            level += 1

    def is_on_cooldown(self, guild_id, user_id):
        key = f"{guild_id}_{user_id}"
        if key not in self.xp_cooldowns:
            return False
        return (datetime.utcnow() - self.xp_cooldowns[key]).total_seconds() < self.cooldown

    def set_cooldown(self, guild_id, user_id):
        self.xp_cooldowns[f"{guild_id}_{user_id}"] = datetime.utcnow()

    async def get_rank(self, guild_id, user_id):
        all_data = self.db.get_all()
        guild_users = [(int(k.split('_')[1]), d.get('total_xp', 0)) for k, d in all_data.items() if k.startswith(f"{guild_id}_")]
        guild_users.sort(key=lambda x: x[1], reverse=True)
        for i, (uid, _) in enumerate(guild_users, 1):
            if uid == user_id:
                return i, len(guild_users)
        return len(guild_users) + 1, len(guild_users)

    async def announce_levelup(self, guild, user, new_level):
        config = self.config_db.get(str(guild.id), {})
        ch_id = config.get('levelup_channel')
        if not ch_id: return
        channel = guild.get_channel(int(ch_id))
        if not channel: return
        embed = discord.Embed(description=f"{user.mention} reached **Level {new_level}**", color=0x1a1a2e)
        await channel.send(embed=embed)
        level_roles = config.get('level_roles', {})
        role_id = level_roles.get(str(new_level))
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                try: await user.add_roles(role)
                except: pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        config = self.config_db.get(str(message.guild.id), {})
        if not config.get('enabled', True): return
        if str(message.channel.id) in config.get('ignored_channels', []): return
        if self.is_on_cooldown(message.guild.id, message.author.id): return
        self.set_cooldown(message.guild.id, message.author.id)
        data = self.get_user_data(message.guild.id, message.author.id)
        xp = random.randint(self.xp_min, self.xp_max)
        old_level = data['level']
        data['total_xp'] += xp
        new_level, current_xp, xp_needed = self.get_level_from_xp(data['total_xp'])
        data['level'] = new_level
        data['xp'] = current_xp
        self.save_user_data(message.guild.id, message.author.id, data)
        if new_level > old_level:
            await self.announce_levelup(message.guild, message.author, new_level)

    # Standalone commands (most used)
    @app_commands.command(name="level", description="Check your level")
    async def level(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        data = self.get_user_data(interaction.guild.id, user.id)
        level, current_xp, xp_needed = self.get_level_from_xp(data.get('total_xp', 0))
        rank, total = await self.get_rank(interaction.guild.id, user.id)

        await interaction.response.defer()

        # Get user status
        status = str(user.status) if hasattr(user, 'status') else "offline"

        # Get accent color from user's role color
        role_color = user.color
        if role_color.value != 0:
            accent = (role_color.r, role_color.g, role_color.b)
        else:
            accent = (99, 102, 241)  # Default indigo

        try:
            from utils.rank_card import generate_rank_card

            avatar_url = user.avatar.url if user.avatar else user.default_avatar.url

            card_bytes = await generate_rank_card(
                username=user.display_name,
                discriminator=user.discriminator if hasattr(user, 'discriminator') else "0",
                avatar_url=avatar_url,
                level=level,
                current_xp=current_xp,
                required_xp=xp_needed,
                rank=rank,
                total_users=total,
                status=status,
                accent_color=accent
            )

            file = discord.File(card_bytes, filename="rank.png")
            await interaction.followup.send(file=file)

        except Exception as e:
            print(f"Rank card error: {e}")
            # Fallback to embed
            progress = (current_xp / xp_needed * 100) if xp_needed > 0 else 0
            filled = int((progress / 100) * 20)
            bar = "▰" * filled + "▱" * (20 - filled)

            embed = discord.Embed(color=0x1a1a2e)
            embed.set_author(
                name=user.display_name,
                icon_url=user.avatar.url if user.avatar else None
            )
            embed.add_field(name="Rank", value=f"#{rank} / {total}", inline=True)
            embed.add_field(name="Level", value=str(level), inline=True)
            embed.add_field(name="XP", value=f"{current_xp:,} / {xp_needed:,}", inline=True)
            embed.add_field(
                name="Progress",
                value=f"`{bar}` {progress:.1f}%",
                inline=False
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="leaderboard_levels", description="XP leaderboard")
    async def leaderboard_levels(self, interaction: discord.Interaction):
        await interaction.response.defer()
        all_data = self.db.get_all()
        guild_users = [(int(k.split('_')[1]), d) for k, d in all_data.items() if k.startswith(f"{interaction.guild.id}_")]
        guild_users.sort(key=lambda x: x[1].get('total_xp', 0), reverse=True)
        top = guild_users[:10]
        if not top:
            await interaction.followup.send("no level data yet.")
            return
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        desc = ""
        for idx, (uid, d) in enumerate(top, 1):
            try:
                m = interaction.guild.get_member(uid)
                name = m.display_name if m else f"User {uid}"
            except: name = f"User {uid}"
            level, _, _ = self.get_level_from_xp(d.get('total_xp', 0))
            desc += f"{medals.get(idx, f'`#{idx}`')} **{name}**\nLevel {level} • {d.get('total_xp', 0):,} XP\n\n"
        embed = discord.Embed(title=f"XP Leaderboard — {interaction.guild.name}", description=desc, color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    # Admin group
    xp_admin = app_commands.Group(name="xp", description="XP admin commands")

    @xp_admin.command(name="setup", description="Set level-up channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel, enabled: bool = True):
        config = self.config_db.get(str(interaction.guild.id), {})
        config['enabled'] = enabled
        config['levelup_channel'] = str(channel.id)
        self.config_db.set(str(interaction.guild.id), config)
        embed = discord.Embed(description=f"level ups go to {channel.mention}\nstatus: {'enabled' if enabled else 'disabled'}", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @xp_admin.command(name="role", description="Set level reward role")
    @app_commands.checks.has_permissions(administrator=True)
    async def role(self, interaction: discord.Interaction, level: int, role: discord.Role):
        config = self.config_db.get(str(interaction.guild.id), {})
        if 'level_roles' not in config: config['level_roles'] = {}
        config['level_roles'][str(level)] = str(role.id)
        self.config_db.set(str(interaction.guild.id), config)
        embed = discord.Embed(description=f"{role.mention} given at **Level {level}**", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @xp_admin.command(name="ignore", description="Toggle channel XP ignore")
    @app_commands.checks.has_permissions(administrator=True)
    async def ignore(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.config_db.get(str(interaction.guild.id), {})
        if 'ignored_channels' not in config: config['ignored_channels'] = []
        ch_id = str(channel.id)
        if ch_id in config['ignored_channels']:
            config['ignored_channels'].remove(ch_id)
            action = "removed from"
        else:
            config['ignored_channels'].append(ch_id)
            action = "added to"
        self.config_db.set(str(interaction.guild.id), config)
        embed = discord.Embed(description=f"{channel.mention} {action} XP ignore list", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @xp_admin.command(name="give", description="Give XP to user")
    @app_commands.checks.has_permissions(administrator=True)
    async def give(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        data = self.get_user_data(interaction.guild.id, user.id)
        old_level = data['level']
        data['total_xp'] += amount
        new_level, current_xp, _ = self.get_level_from_xp(data['total_xp'])
        data['level'] = new_level
        data['xp'] = current_xp
        self.save_user_data(interaction.guild.id, user.id, data)
        if new_level > old_level:
            await self.announce_levelup(interaction.guild, user, new_level)
        embed = discord.Embed(description=f"gave **{amount:,} XP** to {user.mention}. now Level {new_level}", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @xp_admin.command(name="remove", description="Remove XP from user")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        data = self.get_user_data(interaction.guild.id, user.id)
        data['total_xp'] = max(0, data['total_xp'] - amount)
        new_level, current_xp, _ = self.get_level_from_xp(data['total_xp'])
        data['level'] = new_level
        data['xp'] = current_xp
        self.save_user_data(interaction.guild.id, user.id, data)
        embed = discord.Embed(description=f"removed **{amount:,} XP** from {user.mention}. now Level {new_level}", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @xp_admin.command(name="reset", description="Reset user XP")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction, user: discord.Member):
        self.save_user_data(interaction.guild.id, user.id, {'xp': 0, 'level': 0, 'total_xp': 0})
        embed = discord.Embed(description=f"reset {user.mention}'s XP", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @xp_admin.command(name="config", description="View leveling config")
    async def config(self, interaction: discord.Interaction):
        cfg = self.config_db.get(str(interaction.guild.id), {})
        embed = discord.Embed(title="Leveling Config", color=0x1a1a2e)
        embed.add_field(name="Status", value="Enabled" if cfg.get('enabled', True) else "Disabled", inline=True)
        embed.add_field(name="XP/Message", value=f"{self.xp_min}-{self.xp_max}", inline=True)
        embed.add_field(name="Cooldown", value=f"{self.cooldown}s", inline=True)
        ch_id = cfg.get('levelup_channel')
        if ch_id:
            ch = interaction.guild.get_channel(int(ch_id))
            embed.add_field(name="Channel", value=ch.mention if ch else "Deleted", inline=True)
        roles = cfg.get('level_roles', {})
        if roles:
            text = "\n".join([f"Level {l}: <@&{r}>" for l, r in sorted(roles.items(), key=lambda x: int(x[0]))])
            embed.add_field(name="Level Roles", value=text, inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))