import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import random
import os
from utils.database import Database

OWNER_ID = int(os.getenv('OWNER_ID', '0'))

class Economy(commands.Cog):
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
            "XP Boost": {"price": 5000, "description": "2x XP 24hrs", "emoji": "🚀", "type": "boost"},
            "Shovel": {"price": 600, "description": "Required to dig", "emoji": "🪣", "type": "tool"}
        }

    def get_user_data(self, user_id: int) -> dict:
        return self.db.get(str(user_id), {
            'balance': 0, 'bank': 0, 'inventory': [],
            'last_daily': None, 'last_work': None,
            'last_fish': None, 'last_hunt': None,
            'last_mine': None, 'last_beg': None,
            'last_crime': None, 'total_earned': 0,
            'total_spent': 0, 'daily_streak': 0,
            'gems': 0, 'fish_caught': 0,
            'animals_hunted': 0, 'times_mined': 0,
            'successful_crimes': 0, 'times_robbed': 0
        })

    def save_user_data(self, user_id: int, data: dict):
        self.db.set(str(user_id), data)

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

    # ===== STANDALONE COMMANDS (most used, stay as individual) =====

    @app_commands.command(name="balance", description="Check your balance")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        data = self.get_user_data(user.id)
        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(name=f"{user.display_name}'s Balance", icon_url=user.avatar.url if user.avatar else None)
        embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
        embed.add_field(name="Net Worth", value=f"${data['balance'] + data['bank']:,}", inline=True)
        if data.get('gems', 0) > 0:
            embed.add_field(name="Gems", value=f"{data['gems']} 💎", inline=True)
        if data.get('daily_streak', 0) > 1:
            embed.set_footer(text=f"Streak: {data['daily_streak']} days 🔥")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim daily reward")
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
                await interaction.response.send_message(f"come back in **{h}h {m}m**", ephemeral=True)
                return
            data['daily_streak'] = data.get('daily_streak', 0) + 1 if diff < timedelta(days=2) else 1
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
        embed.add_field(name=f"Streak (Day {streak})", value=f"+${streak_bonus:,}", inline=True)
        if lucky_bonus:
            embed.add_field(name="Lucky Bonus", value=f"+${lucky_bonus:,}", inline=True)
        embed.add_field(name="Total", value=f"**${total:,}**", inline=False)
        embed.set_footer(text=f"Streak: {streak} days 🔥")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Work to earn coins")
    async def work(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        on_cd, remaining = self.on_cooldown(data['last_work'], 1)
        if on_cd:
            await interaction.response.send_message(f"rest for **{self.format_time(remaining)}**", ephemeral=True)
            return
        jobs = [
            ("coded a discord bot", 400, 800), ("designed graphics", 300, 600),
            ("fixed bugs", 500, 900), ("built a website", 400, 750),
            ("taught a class", 350, 700), ("freelanced", 450, 850),
        ]
        job, mn, mx = random.choice(jobs)
        earned = random.randint(mn, mx)
        if self.lucky(data): earned = int(earned * 1.2)
        data['balance'] += earned
        data['last_work'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        self.save_user_data(interaction.user.id, data)
        embed = discord.Embed(description=f"you {job} and earned **${earned:,}**", color=0x1a1a2e)
        embed.add_field(name="Balance", value=f"${data['balance']:,}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pay", description="Send coins to someone")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.id == interaction.user.id or user.bot or amount <= 0:
            await interaction.response.send_message("invalid.", ephemeral=True)
            return
        sender = self.get_user_data(interaction.user.id)
        if sender['balance'] < amount:
            await interaction.response.send_message(f"you only have ${sender['balance']:,}", ephemeral=True)
            return
        receiver = self.get_user_data(user.id)
        sender['balance'] -= amount
        receiver['balance'] += amount
        self.save_user_data(interaction.user.id, sender)
        self.save_user_data(user.id, receiver)
        embed = discord.Embed(description=f"sent **${amount:,}** to {user.mention}", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="View the shop")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Shop", description="use `/buy <item>` to purchase", color=0x1a1a2e)
        categories = {}
        for name, d in self.shop_items.items():
            cat = d['type']
            if cat not in categories: categories[cat] = []
            categories[cat].append((name, d))
        cat_names = {'tool': '🔧 Tools', 'boost': '⚡ Boosts', 'cosmetic': '✨ Cosmetics'}
        for cat, items in categories.items():
            text = "\n".join([f"{d['emoji']} **{n}** — ${d['price']:,}\n{d['description']}" for n, d in items])
            embed.add_field(name=cat_names.get(cat, cat.title()), value=text, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Purchase an item")
    async def buy(self, interaction: discord.Interaction, item: str):
        data = self.get_user_data(interaction.user.id)
        found = None
        for si, sd in self.shop_items.items():
            if item.lower() in si.lower():
                found = (si, sd)
                break
        if not found:
            await interaction.response.send_message("item not found.", ephemeral=True)
            return
        name, item_data = found
        if data['balance'] < item_data['price']:
            await interaction.response.send_message(f"need ${item_data['price']:,}, have ${data['balance']:,}", ephemeral=True)
            return
        if item_data['type'] == 'tool' and name in data['inventory']:
            await interaction.response.send_message(f"you already own **{name}**", ephemeral=True)
            return
        data['balance'] -= item_data['price']
        data['total_spent'] += item_data['price']
        data['inventory'].append(name)
        self.save_user_data(interaction.user.id, data)
        embed = discord.Embed(description=f"bought **{item_data['emoji']} {name}** for **${item_data['price']:,}**", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inventory", description="View your items")
    async def inventory(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = self.get_user_data(target.id)
        if not data['inventory']:
            await interaction.response.send_message("empty inventory.", ephemeral=True)
            return
        from collections import Counter
        counts = Counter(data['inventory'])
        text = "\n".join([f"{self.shop_items.get(i, {}).get('emoji', '•')} **{i}** x{c}" for i, c in counts.items()])
        embed = discord.Embed(title=f"{target.display_name}'s Inventory", description=text, color=0x1a1a2e)
        await interaction.response.send_message(embed=embed, ephemeral=(user is None))

    @app_commands.command(name="profile", description="View economy profile")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = self.get_user_data(target.id)
        await interaction.response.defer()

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

        level_db = Database('data/leveling.json')
        level_data = level_db.get(f"{interaction.guild.id}_{target.id}", {})
        level = level_data.get('level', 0)

        role_color = target.color
        accent = (role_color.r, role_color.g, role_color.b) if role_color.value != 0 else (99, 102, 241)

        try:
            from utils.rank_card import generate_profile_card
            avatar_url = target.avatar.url if target.avatar else target.default_avatar.url

            card = await generate_profile_card(
                username=target.display_name,
                avatar_url=avatar_url,
                balance=data.get('balance', 0),
                bank=data.get('bank', 0),
                total_earned=data.get('total_earned', 0),
                rank=rank,
                level=level,
                streak=data.get('daily_streak', 0),
                gems=data.get('gems', 0),
                accent_color=accent
            )
            file = discord.File(card, filename="profile.png")
            await interaction.followup.send(file=file)
        except Exception as e:
            print(f"Profile card error: {e}")
            embed = discord.Embed(color=0x1a1a2e)
            embed.set_author(name=f"{target.display_name}'s Profile", icon_url=target.avatar.url if target.avatar else None)
            embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
            embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
            embed.add_field(name="Net Worth", value=f"${data['balance'] + data['bank']:,}", inline=True)
            embed.add_field(name="Earned", value=f"${data.get('total_earned', 0):,}", inline=True)
            embed.add_field(name="Streak", value=f"{data.get('daily_streak', 0)} days", inline=True)
            embed.add_field(name="Gems", value=f"{data.get('gems', 0)} 💎", inline=True)
            await interaction.followup.send(embed=embed)

    # ===== EARN GROUP (fish, hunt, mine, beg, crime, rob) =====

    earn_group = app_commands.Group(name="earn", description="Ways to earn coins")

    @earn_group.command(name="fish", description="Go fishing")
    async def fish(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        if not self.has_item(data, "Fishing Rod"):
            await interaction.response.send_message("buy a **Fishing Rod** first. `/shop`", ephemeral=True)
            return
        on_cd, rem = self.on_cooldown(data['last_fish'], 0.5)
        if on_cd:
            await interaction.response.send_message(f"wait **{self.format_time(rem)}**", ephemeral=True)
            return
        catches = [("🐟 Common Fish", 50, 150, 60), ("🐠 Tropical Fish", 150, 300, 25), ("🦈 Shark", 500, 1000, 5), ("💎 Rare Gem", 1000, 2000, 3), ("🥾 Old Boot", 0, 10, 15)]
        total_w = sum(c[3] for c in catches)
        roll = random.uniform(0, total_w)
        cur = 0
        catch = catches[0]
        for c in catches:
            cur += c[3]
            if roll <= cur:
                catch = c
                break
        name, mn, mx, _ = catch
        earned = random.randint(mn, mx)
        if self.lucky(data): earned = int(earned * 1.25)
        data['balance'] += earned
        data['last_fish'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        data['fish_caught'] = data.get('fish_caught', 0) + 1
        self.save_user_data(interaction.user.id, data)
        embed = discord.Embed(description=f"caught **{name}** worth **${earned:,}**" if earned > 0 else f"caught **{name}**. nothing.", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @earn_group.command(name="hunt", description="Go hunting")
    async def hunt(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        if not self.has_item(data, "Hunting Rifle"):
            await interaction.response.send_message("buy a **Hunting Rifle** first. `/shop`", ephemeral=True)
            return
        on_cd, rem = self.on_cooldown(data['last_hunt'], 1)
        if on_cd:
            await interaction.response.send_message(f"wait **{self.format_time(rem)}**", ephemeral=True)
            return
        animals = [("🐇 Rabbit", 100, 250, 40), ("🦌 Deer", 300, 600, 25), ("🐺 Wolf", 600, 1000, 10), ("🐲 Dragon", 2000, 5000, 1), ("💨 Nothing", 0, 0, 20)]
        total_w = sum(a[3] for a in animals)
        roll = random.uniform(0, total_w)
        cur = 0
        animal = animals[0]
        for a in animals:
            cur += a[3]
            if roll <= cur:
                animal = a
                break
        name, mn, mx, _ = animal
        earned = random.randint(mn, mx) if mx > 0 else 0
        if self.lucky(data): earned = int(earned * 1.25)
        data['balance'] += earned
        data['last_hunt'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        data['animals_hunted'] = data.get('animals_hunted', 0) + (1 if earned > 0 else 0)
        self.save_user_data(interaction.user.id, data)
        embed = discord.Embed(description=f"hunted **{name}** for **${earned:,}**" if earned > 0 else f"found **{name}**. nothing.", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @earn_group.command(name="mine", description="Mine for coins and gems")
    async def mine(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        if not self.has_item(data, "Pickaxe"):
            await interaction.response.send_message("buy a **Pickaxe** first. `/shop`", ephemeral=True)
            return
        on_cd, rem = self.on_cooldown(data['last_mine'], 1.5)
        if on_cd:
            await interaction.response.send_message(f"wait **{self.format_time(rem)}**", ephemeral=True)
            return
        finds = [("🪨 Stone", 10, 50, 40), ("⚙️ Iron", 100, 200, 30), ("🥇 Gold", 300, 600, 15), ("💎 Diamond", 800, 1500, 8), ("❤️ Ruby", 1500, 3000, 2)]
        total_w = sum(f[3] for f in finds)
        roll = random.uniform(0, total_w)
        cur = 0
        find = finds[0]
        for f in finds:
            cur += f[3]
            if roll <= cur:
                find = f
                break
        name, mn, mx, _ = find
        earned = random.randint(mn, mx)
        if self.lucky(data): earned = int(earned * 1.3)
        gem_found = "Diamond" in name or "Ruby" in name
        if gem_found: data['gems'] = data.get('gems', 0) + 1
        data['balance'] += earned
        data['last_mine'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        data['times_mined'] = data.get('times_mined', 0) + 1
        self.save_user_data(interaction.user.id, data)
        desc = f"mined **{name}** worth **${earned:,}**"
        if gem_found: desc += f"\n💎 gem found! total: {data['gems']}"
        embed = discord.Embed(description=desc, color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @earn_group.command(name="beg", description="Beg for coins")
    async def beg(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        on_cd, rem = self.on_cooldown(data['last_beg'], 0.25)
        if on_cd:
            await interaction.response.send_message(f"wait **{self.format_time(rem)}**", ephemeral=True)
            return
        responses = [
            ("someone tossed you coins", True, 20, 150),
            ("a stranger felt pity", True, 10, 100),
            ("nobody cared", False, 0, 0),
            ("a rich person walked by", True, 100, 500),
        ]
        msg, success, mn, mx = random.choice(responses)
        earned = random.randint(mn, mx) if success else 0
        if success:
            data['balance'] += earned
            data['total_earned'] += earned
        data['last_beg'] = datetime.utcnow().isoformat()
        self.save_user_data(interaction.user.id, data)
        desc = f"{msg} — **${earned:,}**" if success else f"{msg}."
        embed = discord.Embed(description=desc, color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @earn_group.command(name="crime", description="Attempt a crime")
    async def crime(self, interaction: discord.Interaction):
        data = self.get_user_data(interaction.user.id)
        on_cd, rem = self.on_cooldown(data['last_crime'], 2)
        if on_cd:
            await interaction.response.send_message(f"lay low for **{self.format_time(rem)}**", ephemeral=True)
            return
        crimes = [("robbed a store", 300, 700, 60), ("hacked a database", 500, 1200, 50), ("pickpocketed someone", 100, 300, 70)]
        text, mn, mx, chance = random.choice(crimes)
        success = random.randint(1, 100) <= chance
        if success:
            earned = random.randint(mn, mx)
            if self.lucky(data): earned = int(earned * 1.2)
            data['balance'] += earned
            data['total_earned'] += earned
            data['successful_crimes'] = data.get('successful_crimes', 0) + 1
            embed = discord.Embed(description=f"you {text} and got **${earned:,}**", color=discord.Color.green())
        else:
            fine = random.randint(100, 500)
            data['balance'] = max(0, data['balance'] - fine)
            embed = discord.Embed(description=f"caught trying to {text}. fined **${fine:,}**", color=discord.Color.red())
        data['last_crime'] = datetime.utcnow().isoformat()
        self.save_user_data(interaction.user.id, data)
        await interaction.response.send_message(embed=embed)

    @earn_group.command(name="rob", description="Rob another user")
    async def rob(self, interaction: discord.Interaction, user: discord.Member):
        if user.id == interaction.user.id or user.bot:
            await interaction.response.send_message("invalid target.", ephemeral=True)
            return
        robber = self.get_user_data(interaction.user.id)
        victim = self.get_user_data(user.id)
        if victim['balance'] < 100:
            await interaction.response.send_message(f"{user.display_name} is broke.", ephemeral=True)
            return
        if robber['balance'] < 200:
            await interaction.response.send_message("need $200 minimum to rob.", ephemeral=True)
            return
        rate = 0.55 if self.lucky(robber) else 0.4
        if random.random() < rate:
            stolen = random.randint(int(victim['balance'] * 0.1), int(victim['balance'] * 0.35))
            robber['balance'] += stolen
            victim['balance'] -= stolen
            robber['times_robbed'] = robber.get('times_robbed', 0) + 1
            self.save_user_data(interaction.user.id, robber)
            self.save_user_data(user.id, victim)
            embed = discord.Embed(description=f"stole **${stolen:,}** from {user.mention}", color=discord.Color.green())
        else:
            fine = random.randint(200, 500)
            robber['balance'] = max(0, robber['balance'] - fine)
            self.save_user_data(interaction.user.id, robber)
            embed = discord.Embed(description=f"caught robbing {user.mention}. fined **${fine:,}**", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

    # ===== BANK GROUP =====

    bank_group = app_commands.Group(name="bank", description="Banking commands")

    @bank_group.command(name="deposit", description="Deposit to bank")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        data = self.get_user_data(interaction.user.id)
        amt = data['balance'] if amount.lower() == 'all' else int(amount) if amount.isdigit() else 0
        if amt <= 0 or data['balance'] < amt:
            await interaction.response.send_message("invalid amount.", ephemeral=True)
            return
        data['balance'] -= amt
        data['bank'] += amt
        self.save_user_data(interaction.user.id, data)
        embed = discord.Embed(description=f"deposited **${amt:,}**", color=0x1a1a2e)
        embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
        await interaction.response.send_message(embed=embed)

    @bank_group.command(name="withdraw", description="Withdraw from bank")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        data = self.get_user_data(interaction.user.id)
        amt = data['bank'] if amount.lower() == 'all' else int(amount) if amount.isdigit() else 0
        if amt <= 0 or data['bank'] < amt:
            await interaction.response.send_message("invalid amount.", ephemeral=True)
            return
        data['bank'] -= amt
        data['balance'] += amt
        self.save_user_data(interaction.user.id, data)
        embed = discord.Embed(description=f"withdrew **${amt:,}**", color=0x1a1a2e)
        embed.add_field(name="Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="Bank", value=f"${data['bank']:,}", inline=True)
        await interaction.response.send_message(embed=embed)

    # ===== ADMIN GROUP =====

    eco_admin = app_commands.Group(name="eco_admin", description="Economy admin commands")

    @eco_admin.command(name="set", description="Set user balance")
    async def setmoney(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        data = self.get_user_data(user.id)
        data['balance'] = max(0, amount)
        self.save_user_data(user.id, data)
        embed = discord.Embed(description=f"set {user.mention}'s balance to **${amount:,}**", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @eco_admin.command(name="add", description="Add coins to user")
    async def addmoney(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        data = self.get_user_data(user.id)
        data['balance'] += amount
        data['total_earned'] += amount
        self.save_user_data(user.id, data)
        embed = discord.Embed(description=f"added **${amount:,}** to {user.mention}", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @eco_admin.command(name="remove", description="Remove coins from user")
    async def removemoney(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        data = self.get_user_data(user.id)
        data['balance'] = max(0, data['balance'] - amount)
        self.save_user_data(user.id, data)
        embed = discord.Embed(description=f"removed **${amount:,}** from {user.mention}", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @eco_admin.command(name="reset", description="Reset user economy")
    async def reseteconomy(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != OWNER_ID:
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        self.save_user_data(user.id, {'balance': 0, 'bank': 0, 'inventory': [], 'total_earned': 0, 'total_spent': 0, 'daily_streak': 0, 'gems': 0})
        embed = discord.Embed(description=f"reset {user.mention}'s economy.", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="richest", description="Top 10 richest")
    async def richest(self, interaction: discord.Interaction):
        await interaction.response.defer()

        all_data = self.db.get_all()
        sorted_users = sorted(
            all_data.items(),
            key=lambda x: x[1].get('balance', 0) + x[1].get('bank', 0),
            reverse=True
        )[:10]

        if not sorted_users:
            await interaction.followup.send("no data yet.")
            return

        users_list = []
        for idx, (uid, d) in enumerate(sorted_users, 1):
            try:
                u = await self.bot.fetch_user(int(uid))
                name = u.display_name
                avatar = u.avatar.url if u.avatar else u.default_avatar.url
            except:
                name = f"User {uid}"
                avatar = ""
            net = d.get('balance', 0) + d.get('bank', 0)
            users_list.append({
                "name": name,
                "value": f"${net:,}",
                "avatar_url": avatar,
                "rank": idx
            })

        try:
            from utils.rank_card import generate_leaderboard_card
            card = await generate_leaderboard_card(
                title="Richest Users",
                users=users_list,
                accent_color=(99, 102, 241)
            )
            file = discord.File(card, filename="leaderboard.png")
            await interaction.followup.send(file=file)
        except Exception as e:
            print(f"Leaderboard card error: {e}")
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            desc = ""
            for u in users_list:
                r = u['rank']
                medal = medals.get(r, f"`#{r}`")
                desc += f"{medal} **{u['name']}** — {u['value']}\n"
            embed = discord.Embed(title="Richest Users", description=desc, color=0x1a1a2e)
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))