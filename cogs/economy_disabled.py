"""
cogs/economy.py — economy system with guild-scoped data.

Data format in data/economy.json:
    {"guild_id": {"user_id": {balance, bank, inventory, ...}}}
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import random
import os
from utils.database import Database

OWNER_ID = int(os.getenv('OWNER_ID', '0'))


class Economy(commands.Cog):
    """Economy commands"""

    earn = app_commands.Group(name="earn", description="Earn coins in various ways")
    bank = app_commands.Group(name="bank", description="Banking operations")
    eco_admin = app_commands.Group(name="eco_admin", description="Economy admin tools")

    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/economy.json')
        self.shop_items = {
            "Fishing Rod": {"price": 500, "description": "Required to fish", "emoji": "🎣", "type": "tool"},
            "Hunting Rifle": {"price": 1000, "description": "Required to hunt", "emoji": "🔫", "type": "tool"},
            "Pickaxe": {"price": 800, "description": "Required to mine", "emoji": "⛏️", "type": "tool"},
            "Lucky Charm": {"price": 3000, "description": "Increases luck", "emoji": "🍀", "type": "boost"},
            "VIP Badge": {"price": 10000, "description": "VIP status", "emoji": "⭐", "type": "cosmetic"},
            "Premium Role": {"price": 15000, "description": "Premium role", "emoji": "💎", "type": "cosmetic"},
        }

    def _get_guild_data(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {})

    def _save_guild_data(self, guild_id: int, data: dict):
        self.db.set(str(guild_id), data)

    def get_user_data(self, guild_id: int, user_id: int) -> dict:
        guild_data = self._get_guild_data(guild_id)
        return guild_data.get(str(user_id), {
            'balance': 0, 'bank': 0, 'inventory': [],
            'last_daily': None, 'last_work': None,
            'last_fish': None, 'last_hunt': None, 'last_mine': None,
            'last_beg': None, 'last_crime': None,
            'total_earned': 0, 'total_spent': 0,
            'daily_streak': 0, 'gems': 0,
        })

    def save_user_data(self, guild_id: int, user_id: int, data: dict):
        guild_data = self._get_guild_data(guild_id)
        guild_data[str(user_id)] = data
        self._save_guild_data(guild_id, guild_data)

    def has_item(self, data, item):
        return item in data.get('inventory', [])

    def lucky(self, data):
        return "Lucky Charm" in data.get('inventory', [])

    def on_cooldown(self, last_time_str, hours):
        if not last_time_str:
            return False, 0
        last = datetime.fromisoformat(last_time_str)
        diff = datetime.utcnow() - last
        cd = timedelta(hours=hours)
        if diff < cd:
            return True, int((cd - diff).total_seconds())
        return False, 0

    def format_time(self, seconds):
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            return f"{seconds // 3600}h {(seconds % 3600) // 60}m"

    def _check_married(self, user_id: int) -> bool:
        """Check if user is married for daily bonus."""
        try:
            marriage_db = Database('data/marriages.json')
            data = marriage_db.get(str(user_id), {})
            return data.get('partner_id') is not None
        except Exception:
            return False

    # ===== STANDALONE COMMANDS =====

    @app_commands.command(name="balance", description="Check your balance")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('balance')
        target = user or interaction.user
        data = self.get_user_data(interaction.guild.id, target.id)
        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(name=f"{target.display_name}'s Balance", icon_url=target.avatar.url if target.avatar else None)
        embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
        embed.add_field(name="Net Worth", value=f"${data['balance'] + data['bank']:,}", inline=True)
        if data.get('inventory'):
            embed.add_field(name="Inventory", value=f"{len(data['inventory'])} items", inline=True)
        if data.get('daily_streak', 0) > 0:
            embed.add_field(name="Streak", value=f"{data['daily_streak']} days", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim daily reward")
    async def daily(self, interaction: discord.Interaction):
        self.bot.increment_command('daily')
        await interaction.response.defer()
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        now = datetime.utcnow()
        if data['last_daily']:
            last = datetime.fromisoformat(data['last_daily'])
            diff = now - last
            if diff < timedelta(days=1):
                remaining = timedelta(days=1) - diff
                h = remaining.seconds // 3600
                m = (remaining.seconds % 3600) // 60
                await interaction.followup.send(f"already claimed. come back in **{h}h {m}m**")
                return
            if diff < timedelta(days=2):
                data['daily_streak'] = data.get('daily_streak', 0) + 1
            else:
                data['daily_streak'] = 1
                await interaction.followup.send("streak lost. back to day 1.")
        else:
            data['daily_streak'] = 1

        streak = data['daily_streak']
        base = random.randint(500, 1000)
        streak_bonus = min(streak * 100, 600)

        # Weekly bonus
        weekly_bonus = 0
        if streak % 7 == 0:
            weekly_bonus = base  # 2x base
        # Monthly bonus
        monthly_bonus = 0
        if streak >= 30 and streak % 30 == 0:
            monthly_bonus = base * 2  # 3x base total

        # Marriage bonus
        marriage_bonus = 50 if self._check_married(interaction.user.id) else 0

        lucky_bonus = random.randint(200, 500) if self.lucky(data) else 0
        total = base + streak_bonus + weekly_bonus + monthly_bonus + marriage_bonus + lucky_bonus

        data['balance'] += total
        data['last_daily'] = now.isoformat()
        data['total_earned'] += total
        self.save_user_data(interaction.guild.id, interaction.user.id, data)

        embed = discord.Embed(title="Daily Reward", color=0x1a1a2e)
        embed.add_field(name="Base", value=f"${base:,}", inline=True)
        embed.add_field(name=f"Streak (Day {streak})", value=f"+${streak_bonus:,}", inline=True)
        if weekly_bonus:
            embed.add_field(name="WEEKLY BONUS", value=f"+${weekly_bonus:,}", inline=True)
        if monthly_bonus:
            embed.add_field(name="MONTHLY BONUS", value=f"+${monthly_bonus:,}", inline=True)
        if marriage_bonus:
            embed.add_field(name="💍 Marriage Bonus", value=f"+${marriage_bonus}", inline=True)
        if lucky_bonus:
            embed.add_field(name="Lucky Bonus", value=f"+${lucky_bonus:,}", inline=True)
        embed.add_field(name="Total", value=f"**${total:,}**", inline=False)
        embed.set_footer(text=f"Streak: {streak} days")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="work", description="Work to earn coins")
    async def work(self, interaction: discord.Interaction):
        self.bot.increment_command('work')
        await interaction.response.defer()
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        on_cd, remaining = self.on_cooldown(data.get('last_work'), 1)
        if on_cd:
            await interaction.followup.send(f"already worked. come back in **{self.format_time(remaining)}**")
            return
        jobs = [
            "drove an Uber", "debugged someone's code", "sold feet pics on the dark web",
            "worked the night shift", "streamed for 6 hours", "walked dogs in the rain",
            "delivered pizzas", "tutored a kid in math", "fixed a leaky faucet",
            "performed at a open mic", "flipped burgers", "did someone's taxes",
            "painted a fence", "organized a closet", "cat-sat for a week",
            "wrote a jingle", "mowed lawns", "bartended a wedding",
            "edited a wedding video", "carried groceries for old people",
        ]
        job = random.choice(jobs)
        earned = random.randint(300, 800)
        if self.lucky(data):
            earned = int(earned * 1.2)
        data['balance'] += earned
        data['last_work'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        self.save_user_data(interaction.guild.id, interaction.user.id, data)
        embed = discord.Embed(description=f"you {job} and earned **${earned:,}**", color=0x1a1a2e)
        embed.add_field(name="Balance", value=f"${data['balance']:,}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="pay", description="Send coins to someone")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        self.bot.increment_command('pay')
        if user.id == interaction.user.id or user.bot or amount <= 0:
            await interaction.response.send_message("invalid.", ephemeral=True)
            return
        sender = self.get_user_data(interaction.guild.id, interaction.user.id)
        if sender['balance'] < amount:
            await interaction.response.send_message(f"you only have ${sender['balance']:,}", ephemeral=True)
            return
        receiver = self.get_user_data(interaction.guild.id, user.id)
        sender['balance'] -= amount
        receiver['balance'] += amount
        self.save_user_data(interaction.guild.id, interaction.user.id, sender)
        self.save_user_data(interaction.guild.id, user.id, receiver)
        embed = discord.Embed(description=f"sent **${amount:,}** to {user.mention}", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)



    @app_commands.command(name="richest", description="Top 10 richest in this server")
    async def richest(self, interaction: discord.Interaction):
        self.bot.increment_command('richest')
        await interaction.response.defer()
        guild_data = self._get_guild_data(interaction.guild.id)
        guild_member_ids = {str(m.id) for m in interaction.guild.members}
        filtered = {uid: d for uid, d in guild_data.items() if uid in guild_member_ids and isinstance(d, dict)}
        sorted_users = sorted(filtered.items(), key=lambda x: x[1].get('balance', 0) + x[1].get('bank', 0), reverse=True)[:10]
        if not sorted_users:
            await interaction.followup.send("no data yet.")
            return
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        desc = ""
        for idx, (uid, d) in enumerate(sorted_users, 1):
            try:
                u = await self.bot.fetch_user(int(uid))
                name = u.display_name
            except Exception:
                name = f"User {uid}"
            net = d.get('balance', 0) + d.get('bank', 0)
            medal = medals.get(idx, f"`#{idx}`")
            desc += f"{medal} **{name}** — ${net:,}\n"
        embed = discord.Embed(title="💰 Richest Users", description=desc, color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    # ===== EARN GROUP =====

    @earn.command(name="fish", description="Go fishing for coins")
    async def earn_fish(self, interaction: discord.Interaction):
        self.bot.increment_command('earn_fish')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        if not self.has_item(data, "Fishing Rod"):
            await interaction.followup.send("buy a **Fishing Rod** first. `/shop`", ephemeral=True)
            return
        on_cd, remaining = self.on_cooldown(data.get('last_fish'), 0.5)
        if on_cd:
            await interaction.followup.send(f"rest for **{self.format_time(remaining)}**", ephemeral=True)
            return
        catch = random.choice(["🐟", "🐠", "🐡", "🦈", "🐙", "🦑", "🦐", "🦀"])
        earned = random.randint(50, 200)
        if self.lucky(data):
            earned = int(earned * 1.3)
        data['balance'] += earned
        data['last_fish'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        self.save_user_data(interaction.guild.id, interaction.user.id, data)
        await interaction.followup.send(f"you caught a {catch} and sold it for **${earned:,}**\nBalance: ${data['balance']:,}", ephemeral=True)

    @earn.command(name="hunt", description="Go hunting for coins")
    async def earn_hunt(self, interaction: discord.Interaction):
        self.bot.increment_command('earn_hunt')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        if not self.has_item(data, "Hunting Rifle"):
            await interaction.followup.send("buy a **Hunting Rifle** first. `/shop`", ephemeral=True)
            return
        on_cd, remaining = self.on_cooldown(data.get('last_hunt'), 0.5)
        if on_cd:
            await interaction.followup.send(f"rest for **{self.format_time(remaining)}**", ephemeral=True)
            return
        prey = random.choice(["🦌", "🐗", "🐰", "🦊", "🦝", "🐿️"])
        earned = random.randint(100, 350)
        if self.lucky(data):
            earned = int(earned * 1.3)
        data['balance'] += earned
        data['last_hunt'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        self.save_user_data(interaction.guild.id, interaction.user.id, data)
        await interaction.followup.send(f"you hunted a {prey} and sold it for **${earned:,}**\nBalance: ${data['balance']:,}", ephemeral=True)

    @earn.command(name="mine", description="Go mining for coins")
    async def earn_mine(self, interaction: discord.Interaction):
        self.bot.increment_command('earn_mine')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        if not self.has_item(data, "Pickaxe"):
            await interaction.followup.send("buy a **Pickaxe** first. `/shop`", ephemeral=True)
            return
        on_cd, remaining = self.on_cooldown(data.get('last_mine'), 0.5)
        if on_cd:
            await interaction.followup.send(f"rest for **{self.format_time(remaining)}**", ephemeral=True)
            return
        earned = random.randint(80, 300)
        if self.lucky(data):
            earned = int(earned * 1.3)
        data['balance'] += earned
        data['last_mine'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        if random.random() < 0.15:
            gems = random.randint(1, 3)
            data['gems'] = data.get('gems', 0) + gems
            await interaction.followup.send(f"you mined and earned **${earned:,}** + **{gems} gems**!\nBalance: ${data['balance']:,}", ephemeral=True)
        else:
            await interaction.followup.send(f"you mined and earned **${earned:,}**\nBalance: ${data['balance']:,}", ephemeral=True)
        self.save_user_data(interaction.guild.id, interaction.user.id, data)

    @earn.command(name="beg", description="Beg for coins")
    async def earn_beg(self, interaction: discord.Interaction):
        self.bot.increment_command('beg')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        on_cd, remaining = self.on_cooldown(data.get('last_beg'), 0.25)  # 15 min
        if on_cd:
            await interaction.followup.send(f"rest for **{self.format_time(remaining)}**", ephemeral=True)
            return
        if random.random() < 0.3:
            await interaction.followup.send("nobody gave you anything. sad.", ephemeral=True)
            data['last_beg'] = datetime.utcnow().isoformat()
            self.save_user_data(interaction.guild.id, interaction.user.id, data)
            return
        earned = random.randint(1, 50)
        data['balance'] += earned
        data['last_beg'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        self.save_user_data(interaction.guild.id, interaction.user.id, data)
        await interaction.followup.send(f"someone tossed you **${earned:,}**\nBalance: ${data['balance']:,}", ephemeral=True)

    @earn.command(name="crime", description="Commit a crime for coins")
    async def earn_crime(self, interaction: discord.Interaction):
        self.bot.increment_command('earn_crime')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        on_cd, remaining = self.on_cooldown(data.get('last_crime'), 1)  # 1 hour
        if on_cd:
            await interaction.followup.send(f"rest for **{self.format_time(remaining)}**", ephemeral=True)
            return
        success = random.random() < 0.6
        if success:
            earned = random.randint(200, 800)
            if self.lucky(data):
                earned = int(earned * 1.3)
            data['balance'] += earned
            data['total_earned'] += earned
            crimes = ["hacked a bank", "stole a painting", "robbed a store", "embezzled funds", "picked pockets"]
            await interaction.followup.send(f"you {random.choice(crimes)} and got **${earned:,}**\nBalance: ${data['balance']:,}", ephemeral=True)
        else:
            fine = 100
            data['balance'] = max(0, data['balance'] - fine)
            fails = [
                "your getaway car wouldn't start. lost $100.",
                "you tripped on the curb running away. lost $100.",
                "the alarm went off. lost $100.",
                "a dog chased you for 3 blocks. lost $100.",
                "you dropped your loot in a sewer. lost $100.",
                "the cops were already there. lost $100.",
                "you robbed the wrong house. lost $100.",
                "your accomplice ratted you out. lost $100.",
                "you forgot your mask at home. lost $100.",
                "the security guard was your mom. lost $100.",
            ]
            await interaction.followup.send(random.choice(fails) + f"\nBalance: ${data['balance']:,}", ephemeral=True)
        data['last_crime'] = datetime.utcnow().isoformat()
        self.save_user_data(interaction.guild.id, interaction.user.id, data)

    @earn.command(name="rob", description="Rob another user")
    async def earn_rob(self, interaction: discord.Interaction, user: discord.Member):
        self.bot.increment_command('earn_rob')
        await interaction.response.defer(ephemeral=True)
        if user.id == interaction.user.id or user.bot:
            await interaction.followup.send("can't rob yourself or bots.", ephemeral=True)
            return
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        on_cd, remaining = self.on_cooldown(data.get('last_crime'), 1)
        if on_cd:
            await interaction.followup.send(f"rest for **{self.format_time(remaining)}**", ephemeral=True)
            return
        target_data = self.get_user_data(interaction.guild.id, user.id)
        if target_data['balance'] < 200:
            await interaction.followup.send(f"{user.mention} doesn't have enough money to rob.", ephemeral=True)
            return
        success = random.random() < 0.4
        if success:
            stolen = random.randint(int(target_data['balance'] * 0.1), int(target_data['balance'] * 0.3))
            data['balance'] += stolen
            target_data['balance'] -= stolen
            data['total_earned'] += stolen
            self.save_user_data(interaction.guild.id, user.id, target_data)
            successes = [
                f"you snatched ${stolen:,} from {user.mention} and got away clean.",
                f"you pickpocketed {user.mention} for ${stolen:,}. smooth.",
                f"you mugged {user.mention} and took ${stolen:,}. brutal.",
                f"you scammed {user.mention} out of ${stolen:,}.",
                f"you hacked {user.mention}'s wallet and took ${stolen:,}.",
            ]
            await interaction.followup.send(random.choice(successes) + f"\nBalance: ${data['balance']:,}", ephemeral=True)
        else:
            fine = 100
            data['balance'] = max(0, data['balance'] - fine)
            await interaction.followup.send(f"you got caught robbing {user.mention}. lost ${fine}.\nBalance: ${data['balance']:,}", ephemeral=True)
        data['last_crime'] = datetime.utcnow().isoformat()
        self.save_user_data(interaction.guild.id, interaction.user.id, data)

    # ===== BANK GROUP =====

    @bank.command(name="deposit", description="Deposit coins into your bank")
    async def bank_deposit(self, interaction: discord.Interaction, amount: int):
        self.bot.increment_command('bank_deposit')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        if amount <= 0 or data['balance'] < amount:
            await interaction.followup.send("invalid amount.", ephemeral=True)
            return
        data['balance'] -= amount
        data['bank'] += amount
        self.save_user_data(interaction.guild.id, interaction.user.id, data)
        await interaction.followup.send(f"deposited **${amount:,}**\nWallet: ${data['balance']:,} · Bank: ${data['bank']:,}", ephemeral=True)

    @bank.command(name="withdraw", description="Withdraw coins from your bank")
    async def bank_withdraw(self, interaction: discord.Interaction, amount: int):
        self.bot.increment_command('bank_withdraw')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, interaction.user.id)
        if amount <= 0 or data['bank'] < amount:
            await interaction.followup.send("invalid amount.", ephemeral=True)
            return
        data['bank'] -= amount
        data['balance'] += amount
        self.save_user_data(interaction.guild.id, interaction.user.id, data)
        await interaction.followup.send(f"withdrew **${amount:,}**\nWallet: ${data['balance']:,} · Bank: ${data['bank']:,}", ephemeral=True)

    # ===== ECO ADMIN GROUP =====

    @eco_admin.command(name="set", description="Set a user's balance")
    @app_commands.checks.has_permissions(administrator=True)
    async def eco_set(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        self.bot.increment_command('eco_set')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, user.id)
        data['balance'] = max(0, amount)
        self.save_user_data(interaction.guild.id, user.id, data)
        await interaction.followup.send(f"set {user.mention}'s balance to **${amount:,}**", ephemeral=True)

    @eco_admin.command(name="add", description="Add coins to a user")
    @app_commands.checks.has_permissions(administrator=True)
    async def eco_add(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        self.bot.increment_command('eco_add')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, user.id)
        data['balance'] += amount
        data['total_earned'] += amount
        self.save_user_data(interaction.guild.id, user.id, data)
        await interaction.followup.send(f"added **${amount:,}** to {user.mention}", ephemeral=True)

    @eco_admin.command(name="remove", description="Remove coins from a user")
    @app_commands.checks.has_permissions(administrator=True)
    async def eco_remove(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        self.bot.increment_command('eco_remove')
        await interaction.response.defer(ephemeral=True)
        data = self.get_user_data(interaction.guild.id, user.id)
        data['balance'] = max(0, data['balance'] - amount)
        self.save_user_data(interaction.guild.id, user.id, data)
        await interaction.followup.send(f"removed **${amount:,}** from {user.mention}", ephemeral=True)

    @eco_admin.command(name="reset", description="Reset a user's economy data")
    @app_commands.checks.has_permissions(administrator=True)
    async def eco_reset(self, interaction: discord.Interaction, user: discord.Member):
        self.bot.increment_command('eco_reset')
        await interaction.response.defer(ephemeral=True)
        self.save_user_data(interaction.guild.id, user.id, {
            'balance': 0, 'bank': 0, 'inventory': [], 'total_earned': 0, 'total_spent': 0, 'daily_streak': 0, 'gems': 0
        })
        await interaction.followup.send(f"reset {user.mention}'s economy.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economy(bot))
