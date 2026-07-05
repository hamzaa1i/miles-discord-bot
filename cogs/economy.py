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