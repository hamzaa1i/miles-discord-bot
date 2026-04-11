import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import random
import os
from utils.database import Database

OWNER_ID = int(os.getenv('OWNER_ID', '0'))

def is_admin():
    async def predicate(interaction: discord.Interaction):
        return (
            interaction.user.guild_permissions.administrator
            or interaction.user.id == OWNER_ID
        )
    return app_commands.check(predicate)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/economy.json')

        self.shop_items = {
            "Fishing Rod": {
                "price": 500,
                "description": "Required to go fishing",
                "emoji": "🎣",
                "type": "tool"
            },
            "Hunting Rifle": {
                "price": 1000,
                "description": "Required to go hunting",
                "emoji": "🔫",
                "type": "tool"
            },
            "Pickaxe": {
                "price": 800,
                "description": "Required to go mining",
                "emoji": "⛏️",
                "type": "tool"
            },
            "Lucky Charm": {
                "price": 3000,
                "description": "Increases luck in all activities",
                "emoji": "🍀",
                "type": "boost"
            },
            "VIP Badge": {
                "price": 10000,
                "description": "Exclusive VIP status",
                "emoji": "⭐",
                "type": "cosmetic"
            },
            "Premium Role": {
                "price": 15000,
                "description": "Get the Premium server role",
                "emoji": "💎",
                "type": "cosmetic"
            },
            "XP Boost": {
                "price": 5000,
                "description": "2x XP for 24 hours",
                "emoji": "🚀",
                "type": "boost"
            },
            "Shovel": {
                "price": 600,
                "description": "Required to dig for treasure",
                "emoji": "🪣",
                "type": "tool"
            }
        }

    def get_user_data(self, user_id: int) -> dict:
        return self.db.get(str(user_id), {
            'balance': 0,
            'bank': 0,
            'inventory': [],
            'last_daily': None,
            'last_work': None,
            'last_fish': None,
            'last_hunt': None,
            'last_mine': None,
            'last_beg': None,
            'last_crime': None,
            'last_dig': None,
            'total_earned': 0,
            'total_spent': 0,
            'daily_streak': 0,
            'last_streak_date': None,
            'gems': 0,
            'fish_caught': 0,
            'animals_hunted': 0,
            'times_mined': 0,
            'successful_crimes': 0,
            'times_robbed': 0
        })

    def save_user_data(self, user_id: int, data: dict):
        self.db.set(str(user_id), data)

    def has_item(self, data: dict, item: str) -> bool:
        return item in data.get('inventory', [])

    def lucky(self, data: dict) -> bool:
        """Check if user has lucky charm for bonus"""
        return "Lucky Charm" in data.get('inventory', [])

    def on_cooldown(self, last_time_str: str, hours: float) -> tuple:
        """Check cooldown. Returns (is_on_cd, remaining_seconds)"""
        if not last_time_str:
            return False, 0
        last = datetime.fromisoformat(last_time_str)
        diff = datetime.utcnow() - last
        cd = timedelta(hours=hours)
        if diff < cd:
            remaining = (cd - diff).seconds
            return True, remaining
        return False, 0

    def format_time(self, seconds: int) -> str:
        """Format seconds to readable time"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}h {mins}m"

    # ==================== BALANCE ====================

    @app_commands.command(name="balance", description="Check your balance")
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        user = user or interaction.user
        data = self.get_user_data(user.id)

        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(
            name=f"{user.display_name}'s Balance",
            icon_url=user.avatar.url if user.avatar else None
        )
        embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
        embed.add_field(
            name="Net Worth",
            value=f"${data['balance'] + data['bank']:,}",
            inline=True
        )
        if data.get('gems', 0) > 0:
            embed.add_field(name="Gems 💎", value=data['gems'], inline=True)
        if data.get('daily_streak', 0) > 1:
            embed.set_footer(text=f"Daily Streak: {data['daily_streak']} days 🔥")

        await interaction.response.send_message(embed=embed)

    # ==================== DAILY ====================

    @app_commands.command(name="daily", description="Claim your daily reward")
    async def daily(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        now = datetime.utcnow()

        if data['last_daily']:
            last = datetime.fromisoformat(data['last_daily'])
            diff = now - last
            if diff < timedelta(days=1):
                remaining = timedelta(days=1) - diff
                h = remaining.seconds // 3600
                m = (remaining.seconds % 3600) // 60
                embed = discord.Embed(
                    description=f"Already claimed. Come back in **{h}h {m}m**",
                    color=0x1a1a2e
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            data['daily_streak'] = (
                data.get('daily_streak', 0) + 1
                if diff < timedelta(days=2)
                else 1
            )
        else:
            data['daily_streak'] = 1

        streak = data['daily_streak']
        base = random.randint(500, 1500)
        streak_bonus = min(streak * 100, 1000)
        lucky_bonus = random.randint(200, 500) if self.lucky(data) else 0
        total = base + streak_bonus + lucky_bonus

        data['balance'] += total
        data['last_daily'] = now.isoformat()
        data['total_earned'] += total
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(title="Daily Reward", color=0x1a1a2e)
        embed.add_field(name="Base", value=f"${base:,}", inline=True)
        embed.add_field(
            name=f"Streak Bonus (Day {streak})",
            value=f"+${streak_bonus:,}",
            inline=True
        )
        if lucky_bonus:
            embed.add_field(
                name="Lucky Charm Bonus",
                value=f"+${lucky_bonus:,}",
                inline=True
            )
        embed.add_field(name="Total", value=f"**${total:,}**", inline=False)
        embed.add_field(name="New Balance", value=f"${data['balance']:,}", inline=True)
        embed.set_footer(text=f"Streak: {streak} days 🔥 | Come back tomorrow for more!")

        await interaction.response.send_message(embed=embed)

    # ==================== WORK ====================

    @app_commands.command(name="work", description="Work to earn coins")
    async def work(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        on_cd, remaining = self.on_cooldown(data['last_work'], 1)

        if on_cd:
            embed = discord.Embed(
                description=f"You need to rest. Try again in **{self.format_time(remaining)}**",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        jobs = [
            ("developed a mobile app", 400, 800),
            ("designed a logo", 300, 600),
            ("wrote a blog post", 250, 500),
            ("fixed a server bug", 500, 900),
            ("taught an online class", 350, 700),
            ("consulted for a startup", 450, 850),
            ("built a website", 400, 750),
            ("created video content", 300, 650),
            ("managed social media", 250, 550),
            ("sold digital art", 350, 700),
            ("coded a Discord bot", 500, 900),
            ("wrote documentation", 200, 450),
            ("did freelance editing", 300, 600),
            ("tutored students online", 350, 650),
        ]

        job, min_pay, max_pay = random.choice(jobs)
        earned = random.randint(min_pay, max_pay)
        if self.lucky(data):
            earned = int(earned * 1.2)

        data['balance'] += earned
        data['last_work'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(
            description=f"You {job} and earned **${earned:,}**",
            color=0x1a1a2e
        )
        embed.add_field(name="Balance", value=f"${data['balance']:,}")
        embed.set_footer(text="Work again in 1 hour")

        await interaction.response.send_message(embed=embed)

    # ==================== FISH ====================

    @app_commands.command(name="fish", description="Go fishing to earn coins")
    async def fish(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)

        if not self.has_item(data, "Fishing Rod"):
            embed = discord.Embed(
                description="You need a **🎣 Fishing Rod** from the shop first!",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        on_cd, remaining = self.on_cooldown(data['last_fish'], 0.5)
        if on_cd:
            embed = discord.Embed(
                description=f"Water is still rippling. Try in **{self.format_time(remaining)}**",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        catches = [
            ("🐟 Common Fish", 50, 150, 60),
            ("🐠 Tropical Fish", 150, 300, 25),
            ("🐡 Pufferfish", 100, 200, 20),
            ("🦈 Shark", 500, 1000, 5),
            ("🦞 Lobster", 300, 600, 10),
            ("💎 Rare Gem", 1000, 2000, 3),
            ("🥾 Old Boot", 0, 10, 15),
            ("🗑️ Trash", 0, 5, 10),
        ]

        total_weight = sum(c[3] for c in catches)
        roll = random.uniform(0, total_weight)
        current = 0
        catch = catches[0]

        for c in catches:
            current += c[3]
            if roll <= current:
                catch = c
                break

        name, min_earn, max_earn, _ = catch
        earned = random.randint(min_earn, max_earn)

        if self.lucky(data):
            earned = int(earned * 1.25)

        data['balance'] += earned
        data['last_fish'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        data['fish_caught'] = data.get('fish_caught', 0) + 1
        self.save_user_data(interaction.user.id, data)

        if earned > 0:
            embed = discord.Embed(
                title="Gone Fishing 🎣",
                description=f"You caught a **{name}** worth **${earned:,}**!",
                color=0x1a1a2e
            )
        else:
            embed = discord.Embed(
                title="Gone Fishing 🎣",
                description=f"You fished up a **{name}**. Nothing today.",
                color=0x1a1a2e
            )
        embed.set_footer(
            text=f"Total fish caught: {data['fish_caught']} | Try again in 30 minutes"
        )

        await interaction.response.send_message(embed=embed)

    # ==================== HUNT ====================

    @app_commands.command(name="hunt", description="Go hunting to earn coins")
    async def hunt(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)

        if not self.has_item(data, "Hunting Rifle"):
            embed = discord.Embed(
                description="You need a **🔫 Hunting Rifle** from the shop first!",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        on_cd, remaining = self.on_cooldown(data['last_hunt'], 1)
        if on_cd:
            embed = discord.Embed(
                description=f"Animals are hiding. Try in **{self.format_time(remaining)}**",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        animals = [
            ("🐇 Rabbit", 100, 250, 40),
            ("🦌 Deer", 300, 600, 25),
            ("🐗 Boar", 400, 700, 20),
            ("🐺 Wolf", 600, 1000, 10),
            ("🦁 Lion", 1000, 2000, 5),
            ("🐲 Dragon", 2000, 5000, 1),
            ("💨 Nothing", 0, 0, 20),
        ]

        total_weight = sum(a[3] for a in animals)
        roll = random.uniform(0, total_weight)
        current = 0
        animal = animals[0]

        for a in animals:
            current += a[3]
            if roll <= current:
                animal = a
                break

        name, min_earn, max_earn, _ = animal
        earned = random.randint(min_earn, max_earn) if max_earn > 0 else 0

        if self.lucky(data):
            earned = int(earned * 1.25)

        data['balance'] += earned
        data['last_hunt'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        data['animals_hunted'] = data.get('animals_hunted', 0) + (1 if earned > 0 else 0)
        self.save_user_data(interaction.user.id, data)

        if earned > 0:
            embed = discord.Embed(
                title="Gone Hunting 🔫",
                description=f"You hunted a **{name}** and earned **${earned:,}**!",
                color=0x1a1a2e
            )
        else:
            embed = discord.Embed(
                title="Gone Hunting 🔫",
                description=f"You searched but found **{name}**. Empty hands today.",
                color=0x1a1a2e
            )
        embed.set_footer(text="Try again in 1 hour")

        await interaction.response.send_message(embed=embed)

    # ==================== MINE ====================

    @app_commands.command(name="mine", description="Mine for coins and gems")
    async def mine(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)

        if not self.has_item(data, "Pickaxe"):
            embed = discord.Embed(
                description="You need a **⛏️ Pickaxe** from the shop first!",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        on_cd, remaining = self.on_cooldown(data['last_mine'], 1.5)
        if on_cd:
            embed = discord.Embed(
                description=f"Still digging. Try in **{self.format_time(remaining)}**",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        finds = [
            ("🪨 Stone", 10, 50, 40),
            ("⚙️ Iron", 100, 200, 30),
            ("🥇 Gold", 300, 600, 15),
            ("💎 Diamond", 800, 1500, 8),
            ("💠 Sapphire", 1000, 2000, 5),
            ("❤️ Ruby", 1500, 3000, 2),
        ]

        total_weight = sum(f[3] for f in finds)
        roll = random.uniform(0, total_weight)
        current = 0
        find = finds[0]

        for f in finds:
            current += f[3]
            if roll <= current:
                find = f
                break

        name, min_earn, max_earn, _ = find
        earned = random.randint(min_earn, max_earn)
        gem_found = False

        if self.lucky(data):
            earned = int(earned * 1.3)

        if "Diamond" in name or "Sapphire" in name or "Ruby" in name:
            gem_found = True
            data['gems'] = data.get('gems', 0) + 1

        data['balance'] += earned
        data['last_mine'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        data['times_mined'] = data.get('times_mined', 0) + 1
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(
            title="Mining ⛏️",
            description=f"You mined **{name}** worth **${earned:,}**!",
            color=0x1a1a2e
        )
        if gem_found:
            embed.add_field(
                name="💎 Gem Found!",
                value=f"Total gems: {data['gems']}",
                inline=False
            )
        embed.set_footer(text="Try again in 1.5 hours")

        await interaction.response.send_message(embed=embed)

    # ==================== BEG ====================

    @app_commands.command(name="beg", description="Beg for coins")
    async def beg(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        on_cd, remaining = self.on_cooldown(data['last_beg'], 0.25)

        if on_cd:
            embed = discord.Embed(
                description=f"You just begged. Wait **{self.format_time(remaining)}**",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        responses = [
            ("Someone felt pity for you", True, 10, 100),
            ("A stranger tossed you some coins", True, 20, 150),
            ("Someone gave you their spare change", True, 5, 80),
            ("Nobody even looked at you", False, 0, 0),
            ("Someone told you to get a job", False, 0, 0),
            ("A rich person walked past", True, 100, 500),
        ]

        resp = random.choice(responses)
        message, success, min_earn, max_earn = resp

        if success:
            earned = random.randint(min_earn, max_earn)
            data['balance'] += earned
            data['total_earned'] += earned
            description = f"{message} — you got **${earned:,}**"
        else:
            earned = 0
            description = f"{message}."

        data['last_beg'] = datetime.utcnow().isoformat()
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(description=description, color=0x1a1a2e)
        if success:
            embed.add_field(name="Balance", value=f"${data['balance']:,}")

        await interaction.response.send_message(embed=embed)

    # ==================== CRIME ====================

    @app_commands.command(name="crime", description="Attempt a crime for coins")
    async def crime(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        on_cd, remaining = self.on_cooldown(data['last_crime'], 2)

        if on_cd:
            embed = discord.Embed(
                description=f"Laying low. Try in **{self.format_time(remaining)}**",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        crimes = [
            ("robbed a convenience store", 300, 700, 60),
            ("hacked into a database", 500, 1200, 50),
            ("pickpocketed someone", 100, 300, 70),
            ("sold counterfeit goods", 400, 900, 55),
            ("broke into a car", 200, 500, 65),
        ]

        crime_text, min_earn, max_earn, success_chance = random.choice(crimes)
        success = random.randint(1, 100) <= success_chance

        if success:
            earned = random.randint(min_earn, max_earn)
            if self.lucky(data):
                earned = int(earned * 1.2)
            data['balance'] += earned
            data['total_earned'] += earned
            data['successful_crimes'] = data.get('successful_crimes', 0) + 1

            embed = discord.Embed(
                title="Crime Successful",
                description=f"You {crime_text} and got away with **${earned:,}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Balance", value=f"${data['balance']:,}")
        else:
            fine = random.randint(100, 500)
            data['balance'] = max(0, data['balance'] - fine)

            embed = discord.Embed(
                title="Crime Failed",
                description=f"You tried to {crime_text} but got caught.\nFined **${fine:,}**",
                color=discord.Color.red()
            )
            embed.add_field(name="Balance", value=f"${data['balance']:,}")

        data['last_crime'] = datetime.utcnow().isoformat()
        self.save_user_data(interaction.user.id, data)
        embed.set_footer(text="Lay low for 2 hours before trying again")

        await interaction.response.send_message(embed=embed)

    # ==================== ROB ====================

    @app_commands.command(name="rob", description="Try to rob another user")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def rob(self, interaction: discord.Interaction, user: discord.Member):
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't rob yourself.",
                ephemeral=True
            )
            return
        if user.bot:
            await interaction.response.send_message(
                "You can't rob bots.",
                ephemeral=True
            )
            return

        robber = self.get_user_data(interaction.user.id)
        victim = self.get_user_data(user.id)

        if victim['balance'] < 100:
            await interaction.response.send_message(
                f"{user.mention} is broke. Nothing to steal.",
                ephemeral=True
            )
            return

        if robber['balance'] < 200:
            await interaction.response.send_message(
                "You need at least $200 to attempt a robbery.",
                ephemeral=True
            )
            return

        success_rate = 0.4
        if self.lucky(robber):
            success_rate = 0.55

        success = random.random() < success_rate

        if success:
            stolen = random.randint(
                int(victim['balance'] * 0.1),
                int(victim['balance'] * 0.35)
            )
            robber['balance'] += stolen
            victim['balance'] -= stolen
            robber['total_earned'] += stolen
            robber['times_robbed'] = robber.get('times_robbed', 0) + 1

            self.save_user_data(interaction.user.id, robber)
            self.save_user_data(user.id, victim)

            embed = discord.Embed(
                title="Robbery Successful",
                description=f"You robbed **${stolen:,}** from {user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Your Balance", value=f"${robber['balance']:,}")

            try:
                dm = discord.Embed(
                    description=f"You were robbed by {interaction.user.mention} for **${stolen:,}**",
                    color=discord.Color.red()
                )
                await user.send(embed=dm)
            except:
                pass
        else:
            fine = random.randint(200, 500)
            robber['balance'] = max(0, robber['balance'] - fine)
            self.save_user_data(interaction.user.id, robber)

            embed = discord.Embed(
                title="Robbery Failed",
                description=f"You got caught robbing {user.mention} and paid a **${fine:,}** fine",
                color=discord.Color.red()
            )
            embed.add_field(name="Your Balance", value=f"${robber['balance']:,}")

        await interaction.response.send_message(embed=embed)

    # ==================== DEPOSIT / WITHDRAW ====================

    @app_commands.command(name="deposit", description="Deposit coins into your bank")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        data = self.get_user_data(interaction.user.id)

        if amount.lower() == 'all':
            amount_int = data['balance']
        else:
            try:
                amount_int = int(amount)
            except ValueError:
                await interaction.response.send_message(
                    "Use a number or 'all'",
                    ephemeral=True
                )
                return

        if amount_int <= 0 or data['balance'] < amount_int:
            await interaction.response.send_message(
                f"Invalid amount. You have ${data['balance']:,} in your wallet.",
                ephemeral=True
            )
            return

        data['balance'] -= amount_int
        data['bank'] += amount_int
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(
            description=f"Deposited **${amount_int:,}** into your bank.",
            color=0x1a1a2e
        )
        embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="withdraw", description="Withdraw coins from your bank")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        data = self.get_user_data(interaction.user.id)

        if amount.lower() == 'all':
            amount_int = data['bank']
        else:
            try:
                amount_int = int(amount)
            except ValueError:
                await interaction.response.send_message(
                    "Use a number or 'all'",
                    ephemeral=True
                )
                return

        if amount_int <= 0 or data['bank'] < amount_int:
            await interaction.response.send_message(
                f"Invalid amount. You have ${data['bank']:,} in your bank.",
                ephemeral=True
            )
            return

        data['bank'] -= amount_int
        data['balance'] += amount_int
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(
            description=f"Withdrew **${amount_int:,}** from your bank.",
            color=0x1a1a2e
        )
        embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)

        await interaction.response.send_message(embed=embed)

    # ==================== PAY ====================

    @app_commands.command(name="pay", description="Send coins to another user")
    async def pay(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int
    ):
        if user.id == interaction.user.id or user.bot or amount <= 0:
            await interaction.response.send_message(
                "Invalid target or amount.",
                ephemeral=True
            )
            return

        sender = self.get_user_data(interaction.user.id)
        if sender['balance'] < amount:
            await interaction.response.send_message(
                f"You only have **${sender['balance']:,}**",
                ephemeral=True
            )
            return

        receiver = self.get_user_data(user.id)
        sender['balance'] -= amount
        receiver['balance'] += amount

        self.save_user_data(interaction.user.id, sender)
        self.save_user_data(user.id, receiver)

        embed = discord.Embed(
            description=f"Sent **${amount:,}** to {user.mention}",
            color=0x1a1a2e
        )
        embed.add_field(name="Your Balance", value=f"${sender['balance']:,}")

        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                description=f"{interaction.user.mention} sent you **${amount:,}**",
                color=0x1a1a2e
            )
            await user.send(embed=dm)
        except:
            pass

    # ==================== SHOP ====================

    @app_commands.command(name="shop", description="View the shop")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Shop",
            description="Buy items using `/buy <item name>`",
            color=0x1a1a2e
        )

        categories = {}
        for name, data in self.shop_items.items():
            cat = data['type']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((name, data))

        cat_names = {
            'tool': '🔧 Tools',
            'boost': '⚡ Boosts',
            'cosmetic': '✨ Cosmetics'
        }

        for cat, items in categories.items():
            items_text = "\n".join([
                f"{d['emoji']} **{n}** — ${d['price']:,}\n{d['description']}"
                for n, d in items
            ])
            embed.add_field(
                name=cat_names.get(cat, cat.title()),
                value=items_text,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Purchase an item from the shop")
    async def buy(self, interaction: discord.Interaction, item: str):
        data = self.get_user_data(interaction.user.id)

        item_found = None
        for shop_item, shop_data in self.shop_items.items():
            if item.lower() in shop_item.lower():
                item_found = (shop_item, shop_data)
                break

        if not item_found:
            await interaction.response.send_message(
                "Item not found. Use `/shop` to see what's available.",
                ephemeral=True
            )
            return

        name, item_data = item_found

        if data['balance'] < item_data['price']:
            await interaction.response.send_message(
                f"You need **${item_data['price']:,}** but have **${data['balance']:,}**",
                ephemeral=True
            )
            return

        # Check if already has tool
        if item_data['type'] == 'tool' and name in data['inventory']:
            await interaction.response.send_message(
                f"You already own a **{name}**.",
                ephemeral=True
            )
            return

        data['balance'] -= item_data['price']
        data['total_spent'] += item_data['price']
        data['inventory'].append(name)
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(
            description=f"Purchased **{item_data['emoji']} {name}** for **${item_data['price']:,}**",
            color=0x1a1a2e
        )
        embed.add_field(name="Balance", value=f"${data['balance']:,}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = self.get_user_data(target.id)

        if not data['inventory']:
            embed = discord.Embed(
                description="Inventory is empty. Use `/shop` to buy items.",
                color=0x1a1a2e
            )
        else:
            from collections import Counter
            counts = Counter(data['inventory'])
            items_text = "\n".join([
                f"{self.shop_items.get(item, {}).get('emoji', '•')} **{item}** x{count}"
                for item, count in counts.items()
            ])
            embed = discord.Embed(
                title=f"{target.display_name}'s Inventory",
                description=items_text,
                color=0x1a1a2e
            )

        await interaction.response.send_message(embed=embed, ephemeral=(user is None))

    # ==================== PROFILE ====================

    @app_commands.command(name="profile", description="View economy profile")
    async def profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        target = user or interaction.user
        data = self.get_user_data(target.id)

        # Get rank
        all_data = self.db.get_all()
        sorted_users = sorted(
            all_data.items(),
            key=lambda x: x[1].get('balance', 0) + x[1].get('bank', 0),
            reverse=True
        )
        rank = next(
            (i + 1 for i, (uid, _) in enumerate(sorted_users) if int(uid) == target.id),
            len(sorted_users)
        )

        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(
            name=f"{target.display_name}'s Profile",
            icon_url=target.avatar.url if target.avatar else None
        )
        embed.set_thumbnail(
            url=target.avatar.url if target.avatar else None
        )

        embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
        embed.add_field(
            name="Net Worth",
            value=f"${data['balance'] + data['bank']:,}",
            inline=True
        )
        embed.add_field(
            name="Total Earned",
            value=f"${data.get('total_earned', 0):,}",
            inline=True
        )
        embed.add_field(
            name="Total Spent",
            value=f"${data.get('total_spent', 0):,}",
            inline=True
        )
        embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        embed.add_field(
            name="Daily Streak",
            value=f"{data.get('daily_streak', 0)} days 🔥",
            inline=True
        )
        embed.add_field(
            name="Gems",
            value=f"{data.get('gems', 0)} 💎",
            inline=True
        )
        embed.add_field(
            name="Items Owned",
            value=len(data.get('inventory', [])),
            inline=True
        )

        stats = []
        if data.get('fish_caught'):
            stats.append(f"Fish Caught: {data['fish_caught']}")
        if data.get('animals_hunted'):
            stats.append(f"Animals Hunted: {data['animals_hunted']}")
        if data.get('times_mined'):
            stats.append(f"Times Mined: {data['times_mined']}")
        if data.get('successful_crimes'):
            stats.append(f"Successful Crimes: {data['successful_crimes']}")
        if data.get('times_robbed'):
            stats.append(f"Successful Robberies: {data['times_robbed']}")

        if stats:
            embed.add_field(
                name="Statistics",
                value="\n".join(stats),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    # ==================== LEADERBOARD ====================

    @app_commands.command(name="richest", description="Top 10 richest users")
    async def richest(self, interaction: discord.Interaction):
        all_data = self.db.get_all()

        sorted_users = sorted(
            all_data.items(),
            key=lambda x: x[1].get('balance', 0) + x[1].get('bank', 0),
            reverse=True
        )[:10]

        if not sorted_users:
            await interaction.response.send_message("No data yet.", ephemeral=True)
            return

        embed = discord.Embed(title="Richest Users", color=0x1a1a2e)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        desc = ""

        for idx, (uid, data) in enumerate(sorted_users, 1):
            try:
                user = await self.bot.fetch_user(int(uid))
                name = user.name
            except:
                name = f"User {uid}"

            net = data.get('balance', 0) + data.get('bank', 0)
            medal = medals.get(idx, f"`#{idx}`")
            desc += f"{medal} **{name}** — ${net:,}\n"

        embed.description = desc
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="streak", description="Check your daily streak")
    async def streak(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        streak = data.get('daily_streak', 0)
        bonus = min(streak * 100, 1000)

        embed = discord.Embed(color=0x1a1a2e)
        embed.add_field(name="Current Streak", value=f"{streak} days 🔥", inline=True)
        embed.add_field(name="Streak Bonus", value=f"+${bonus:,}", inline=True)

        if data.get('last_daily'):
            last = datetime.fromisoformat(data['last_daily'])
            diff = datetime.utcnow() - last
            remaining = timedelta(days=1) - diff
            if remaining.total_seconds() > 0:
                h = int(remaining.total_seconds() // 3600)
                m = int((remaining.total_seconds() % 3600) // 60)
                embed.add_field(
                    name="Next Daily",
                    value=f"In {h}h {m}m",
                    inline=True
                )

        await interaction.response.send_message(embed=embed)

    # ==================== ADMIN COMMANDS ====================

    @app_commands.command(name="setmoney", description="Set a user's balance (Admin)")
    @is_admin()
    async def setmoney(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
        account: str = "wallet"
    ):
        data = self.get_user_data(user.id)

        if account.lower() == "bank":
            data['bank'] = max(0, amount)
        else:
            data['balance'] = max(0, amount)

        self.save_user_data(user.id, data)

        embed = discord.Embed(
            description=f"Set {user.mention}'s **{account}** to **${amount:,}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="addmoney", description="Add coins to a user (Admin)")
    @is_admin()
    async def addmoney(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
        account: str = "wallet"
    ):
        data = self.get_user_data(user.id)

        if account.lower() == "bank":
            data['bank'] += amount
        else:
            data['balance'] += amount

        data['total_earned'] += amount
        self.save_user_data(user.id, data)

        embed = discord.Embed(
            description=f"Added **${amount:,}** to {user.mention}'s **{account}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="removemoney", description="Remove coins from a user (Admin)")
    @is_admin()
    async def removemoney(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
        account: str = "wallet"
    ):
        data = self.get_user_data(user.id)

        if account.lower() == "bank":
            data['bank'] = max(0, data['bank'] - amount)
        else:
            data['balance'] = max(0, data['balance'] - amount)

        self.save_user_data(user.id, data)

        embed = discord.Embed(
            description=f"Removed **${amount:,}** from {user.mention}'s **{account}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reseteconomy", description="Reset a user's economy data (Admin)")
    @is_admin()
    async def reseteconomy(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        self.save_user_data(user.id, {
            'balance': 0,
            'bank': 0,
            'inventory': [],
            'last_daily': None,
            'last_work': None,
            'last_fish': None,
            'last_hunt': None,
            'last_mine': None,
            'last_beg': None,
            'last_crime': None,
            'total_earned': 0,
            'total_spent': 0,
            'daily_streak': 0,
            'gems': 0,
        })

        embed = discord.Embed(
            description=f"Reset {user.mention}'s economy data.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economy(bot))