import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import random
from utils.database import Database
from utils.embeds import create_embed

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/economy.json')
        self.shop_items = {
            "Custom Role": {
                "price": 5000,
                "description": "Get a custom colored role in the server",
                "emoji": "🎨"
            },
            "Name Change": {
                "price": 2500,
                "description": "Change your display nickname",
                "emoji": "✏️"
            },
            "VIP Badge": {
                "price": 10000,
                "description": "Exclusive VIP badge on your profile",
                "emoji": "⭐"
            },
            "Premium Role": {
                "price": 15000,
                "description": "Get the Premium server role",
                "emoji": "💎"
            },
            "XP Boost": {
                "price": 3000,
                "description": "2x XP for 24 hours",
                "emoji": "🚀"
            }
        }

    def get_user_data(self, user_id: int) -> dict:
        """Get or create user economy data"""
        return self.db.get(str(user_id), {
            'balance': 0,
            'bank': 0,
            'inventory': [],
            'last_daily': None,
            'last_work': None,
            'total_earned': 0,
            'total_spent': 0,
            'daily_streak': 0,
            'last_streak_date': None
        })

    def save_user_data(self, user_id: int, data: dict):
        """Save user economy data"""
        self.db.set(str(user_id), data)

    @app_commands.command(name="balance", description="Check your balance")
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        """Check wallet and bank balance"""
        user = user or interaction.user
        data = self.get_user_data(user.id)

        embed = discord.Embed(
            title=f"{user.display_name}'s Balance",
            color=0x1a1a2e
        )
        embed.set_thumbnail(
            url=user.avatar.url if user.avatar else None
        )
        embed.add_field(
            name="Wallet",
            value=f"${data['balance']:,}",
            inline=True
        )
        embed.add_field(
            name="Bank",
            value=f"${data['bank']:,}",
            inline=True
        )
        embed.add_field(
            name="Net Worth",
            value=f"${data['balance'] + data['bank']:,}",
            inline=True
        )
        if data.get('daily_streak', 0) > 1:
            embed.set_footer(text=f"Daily Streak: {data['daily_streak']} days 🔥")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily reward")
    async def daily(self, interaction: discord.Interaction):
        """Claim daily coins with streak bonus"""
        data = self.get_user_data(interaction.user.id)
        now = datetime.utcnow()

        if data['last_daily']:
            last_claim = datetime.fromisoformat(data['last_daily'])
            time_diff = now - last_claim

            if time_diff < timedelta(days=1):
                remaining = timedelta(days=1) - time_diff
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60

                embed = discord.Embed(
                    description=f"Daily already claimed. Come back in **{hours}h {minutes}m**",
                    color=0x1a1a2e
                )
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True
                )
                return

            # Check streak (must claim within 48 hours)
            if time_diff < timedelta(days=2):
                data['daily_streak'] = data.get('daily_streak', 0) + 1
            else:
                data['daily_streak'] = 1
        else:
            data['daily_streak'] = 1

        # Base reward + streak bonus
        base_reward = random.randint(500, 1500)
        streak = data.get('daily_streak', 1)
        streak_bonus = min(streak * 50, 500)  # Max 500 bonus
        total_reward = base_reward + streak_bonus

        data['balance'] += total_reward
        data['last_daily'] = now.isoformat()
        data['total_earned'] += total_reward
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(
            title="Daily Reward Claimed",
            color=0x1a1a2e
        )
        embed.add_field(
            name="Base Reward",
            value=f"${base_reward:,}",
            inline=True
        )
        if streak_bonus > 0:
            embed.add_field(
                name=f"Streak Bonus (Day {streak})",
                value=f"+${streak_bonus:,}",
                inline=True
            )
        embed.add_field(
            name="Total Received",
            value=f"${total_reward:,}",
            inline=True
        )
        embed.add_field(
            name="New Balance",
            value=f"${data['balance']:,}",
            inline=False
        )
        embed.set_footer(text=f"Daily Streak: {streak} days 🔥")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Work to earn coins")
    async def work(self, interaction: discord.Interaction):
        """Work for coins with 1 hour cooldown"""
        data = self.get_user_data(interaction.user.id)

        if data['last_work']:
            last_work = datetime.fromisoformat(data['last_work'])
            time_diff = datetime.utcnow() - last_work

            if time_diff < timedelta(hours=1):
                remaining = timedelta(hours=1) - time_diff
                minutes = remaining.seconds // 60

                embed = discord.Embed(
                    description=f"You need to rest for **{minutes} more minutes** before working again.",
                    color=0x1a1a2e
                )
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True
                )
                return

        jobs = [
            ("coded a Discord bot", 300, 600),
            ("designed some graphics", 250, 550),
            ("wrote documentation", 200, 450),
            ("fixed production bugs", 400, 700),
            ("built a website", 350, 650),
            ("created content", 300, 580),
            ("consulted for a client", 450, 750),
            ("taught an online class", 350, 600),
            ("developed an app", 400, 700),
            ("managed a project", 300, 550),
        ]

        job, min_earn, max_earn = random.choice(jobs)
        earned = random.randint(min_earn, max_earn)

        data['balance'] += earned
        data['last_work'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(
            description=f"You {job} and earned **${earned:,}**",
            color=0x1a1a2e
        )
        embed.add_field(
            name="New Balance",
            value=f"${data['balance']:,}"
        )
        embed.set_footer(text="Work again in 1 hour")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="deposit", description="Deposit coins into your bank")
    async def deposit(
        self,
        interaction: discord.Interaction,
        amount: str
    ):
        """Deposit to bank"""
        data = self.get_user_data(interaction.user.id)

        if amount.lower() == 'all':
            amount_int = data['balance']
        else:
            try:
                amount_int = int(amount)
            except ValueError:
                await interaction.response.send_message(
                    "Invalid amount. Use a number or 'all'",
                    ephemeral=True
                )
                return

        if amount_int <= 0:
            await interaction.response.send_message(
                "Amount must be positive.",
                ephemeral=True
            )
            return

        if data['balance'] < amount_int:
            await interaction.response.send_message(
                f"You only have ${data['balance']:,} in your wallet.",
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
    async def withdraw(
        self,
        interaction: discord.Interaction,
        amount: str
    ):
        """Withdraw from bank"""
        data = self.get_user_data(interaction.user.id)

        if amount.lower() == 'all':
            amount_int = data['bank']
        else:
            try:
                amount_int = int(amount)
            except ValueError:
                await interaction.response.send_message(
                    "Invalid amount. Use a number or 'all'",
                    ephemeral=True
                )
                return

        if amount_int <= 0:
            await interaction.response.send_message(
                "Amount must be positive.",
                ephemeral=True
            )
            return

        if data['bank'] < amount_int:
            await interaction.response.send_message(
                f"You only have ${data['bank']:,} in your bank.",
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

    @app_commands.command(name="shop", description="View the shop")
    async def shop(self, interaction: discord.Interaction):
        """Display shop items"""
        embed = discord.Embed(
            title="Shop",
            description="Purchase items with your coins",
            color=0x1a1a2e
        )

        for item_name, item_data in self.shop_items.items():
            embed.add_field(
                name=f"{item_data['emoji']} {item_name} — ${item_data['price']:,}",
                value=item_data['description'],
                inline=False
            )

        embed.set_footer(text="Use /buy <item name> to purchase")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Purchase an item from the shop")
    async def buy(self, interaction: discord.Interaction, item: str):
        """Buy items from shop"""
        data = self.get_user_data(interaction.user.id)

        item_found = None
        for shop_item, shop_data in self.shop_items.items():
            if item.lower() in shop_item.lower():
                item_found = (shop_item, shop_data)
                break

        if not item_found:
            await interaction.response.send_message(
                "Item not found. Use `/shop` to see available items.",
                ephemeral=True
            )
            return

        item_name, item_data = item_found
        price = item_data['price']

        if data['balance'] < price:
            await interaction.response.send_message(
                f"You need **${price:,}** but only have **${data['balance']:,}**",
                ephemeral=True
            )
            return

        data['balance'] -= price
        data['total_spent'] += price
        data['inventory'].append(item_name)
        self.save_user_data(interaction.user.id, data)

        embed = discord.Embed(
            description=f"You purchased **{item_data['emoji']} {item_name}** for **${price:,}**",
            color=0x1a1a2e
        )
        embed.add_field(name="New Balance", value=f"${data['balance']:,}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction):
        """Show user's items"""
        data = self.get_user_data(interaction.user.id)

        if not data['inventory']:
            embed = discord.Embed(
                description="Your inventory is empty. Use `/shop` to buy items.",
                color=0x1a1a2e
            )
        else:
            from collections import Counter
            item_counts = Counter(data['inventory'])
            items_list = "\n".join([
                f"• **{item}** x{count}"
                for item, count in item_counts.items()
            ])

            embed = discord.Embed(
                title=f"{interaction.user.display_name}'s Inventory",
                description=items_list,
                color=0x1a1a2e
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pay", description="Send coins to another user")
    async def pay(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int
    ):
        """Transfer money to another user"""
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't pay yourself.",
                ephemeral=True
            )
            return

        if user.bot:
            await interaction.response.send_message(
                "You can't pay bots.",
                ephemeral=True
            )
            return

        if amount <= 0:
            await interaction.response.send_message(
                "Amount must be positive.",
                ephemeral=True
            )
            return

        sender_data = self.get_user_data(interaction.user.id)

        if sender_data['balance'] < amount:
            await interaction.response.send_message(
                f"You only have **${sender_data['balance']:,}** in your wallet.",
                ephemeral=True
            )
            return

        receiver_data = self.get_user_data(user.id)
        sender_data['balance'] -= amount
        receiver_data['balance'] += amount

        self.save_user_data(interaction.user.id, sender_data)
        self.save_user_data(user.id, receiver_data)

        embed = discord.Embed(
            description=f"Sent **${amount:,}** to {user.mention}",
            color=0x1a1a2e
        )
        embed.add_field(
            name="Your New Balance",
            value=f"${sender_data['balance']:,}"
        )

        await interaction.response.send_message(embed=embed)

        try:
            notify = discord.Embed(
                description=f"{interaction.user.mention} sent you **${amount:,}**",
                color=0x1a1a2e
            )
            await user.send(embed=notify)
        except:
            pass

async def setup(bot):
    await bot.add_cog(Economy(bot))