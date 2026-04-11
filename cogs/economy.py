import discord
from discord.ext import commands
from discord import app_commands
import json
import random
from datetime import datetime, timedelta
from utils.database import Database
from utils.embeds import create_embed

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/economy.json')
        self.shop_items = {
            "🎨 Custom Role": {"price": 5000, "description": "Get a custom colored role"},
            "🎭 Name Change": {"price": 2500, "description": "Change your nickname"},
            "🌟 VIP Badge": {"price": 10000, "description": "Exclusive VIP badge"},
            "🎪 Server Boost": {"price": 7500, "description": "Boost server visibility"},
            "🎁 Mystery Box": {"price": 1000, "description": "Random reward box"},
        }
    
    def get_user_data(self, user_id):
        """Get or create user economy data"""
        data = self.db.get(str(user_id), {
            'balance': 0,
            'bank': 0,
            'inventory': [],
            'last_daily': None,
            'last_work': None,
            'total_earned': 0,
            'total_spent': 0
        })
        return data
    
    def save_user_data(self, user_id, data):
        """Save user economy data"""
        self.db.set(str(user_id), data)
    
    @app_commands.command(name="balance", description="Check your balance")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check wallet and bank balance"""
        user = user or interaction.user
        data = self.get_user_data(user.id)
        
        embed = create_embed(
            title=f"💰 {user.name}'s Balance",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="👛 Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"${data['bank']:,}", inline=True)
        embed.add_field(name="💎 Net Worth", value=f"${data['balance'] + data['bank']:,}", inline=True)
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="daily", description="Claim your daily reward")
    async def daily(self, interaction: discord.Interaction):
        """Claim daily coins"""
        data = self.get_user_data(interaction.user.id)
        
        # Check if already claimed today
        if data['last_daily']:
            last_claim = datetime.fromisoformat(data['last_daily'])
            time_diff = datetime.utcnow() - last_claim
            
            if time_diff < timedelta(days=1):
                remaining = timedelta(days=1) - time_diff
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                
                embed = create_embed(
                    title="⏰ Daily Already Claimed!",
                    description=f"Come back in **{hours}h {minutes}m**",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Give reward
        reward = random.randint(500, 1500)
        data['balance'] += reward
        data['last_daily'] = datetime.utcnow().isoformat()
        data['total_earned'] += reward
        self.save_user_data(interaction.user.id, data)
        
        embed = create_embed(
            title="🎁 Daily Reward Claimed!",
            description=f"You received **${reward:,}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"${data['balance']:,}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="work", description="Work to earn coins")
    async def work(self, interaction: discord.Interaction):
        """Work for money"""
        data = self.get_user_data(interaction.user.id)
        
        # Check cooldown (1 hour)
        if data['last_work']:
            last_work = datetime.fromisoformat(data['last_work'])
            time_diff = datetime.utcnow() - last_work
            
            if time_diff < timedelta(hours=1):
                remaining = timedelta(hours=1) - time_diff
                minutes = remaining.seconds // 60
                
                embed = create_embed(
                    title="😓 You're Tired!",
                    description=f"Rest for **{minutes} minutes** before working again",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Work scenarios
        jobs = [
            ("coded a Discord bot", 300, 600),
            ("designed some logos", 250, 500),
            ("wrote documentation", 200, 400),
            ("fixed bugs", 350, 650),
            ("created memes", 150, 350),
            ("streamed on Twitch", 400, 700),
            ("made YouTube videos", 350, 600),
            ("freelanced online", 300, 550),
        ]
        
        job, min_earn, max_earn = random.choice(jobs)
        earned = random.randint(min_earn, max_earn)
        
        data['balance'] += earned
        data['last_work'] = datetime.utcnow().isoformat()
        data['total_earned'] += earned
        self.save_user_data(interaction.user.id, data)
        
        embed = create_embed(
            title="💼 Work Complete!",
            description=f"You {job} and earned **${earned:,}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"${data['balance']:,}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="shop", description="View the shop")
    async def shop(self, interaction: discord.Interaction):
        """Display shop items"""
        embed = create_embed(
            title="🏪 Miles Shop",
            description="Purchase items with your hard-earned coins!",
            color=discord.Color.blue()
        )
        
        for item_name, item_data in self.shop_items.items():
            embed.add_field(
                name=f"{item_name} - ${item_data['price']:,}",
                value=item_data['description'],
                inline=False
            )
        
        embed.set_footer(text="Use /buy <item name> to purchase")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="buy", description="Purchase an item from the shop")
    async def buy(self, interaction: discord.Interaction, item: str):
        """Buy items from shop"""
        data = self.get_user_data(interaction.user.id)
        
        # Find item
        item_found = None
        for shop_item, shop_data in self.shop_items.items():
            if item.lower() in shop_item.lower():
                item_found = (shop_item, shop_data)
                break
        
        if not item_found:
            embed = create_embed(
                title="Item Not Found",
                description="That item doesn't exist in the shop.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        item_name, item_data = item_found
        price = item_data['price']
        
        if data['balance'] < price:
            embed = create_embed(
                title="Insufficient Funds",
                description=f"You need **${price:,}** but only have **${data['balance']:,}**",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        data['balance'] -= price
        data['total_spent'] += price
        
        # Handle mystery box specially
        if "Mystery Box" in item_name:
            reward = random.randint(500, 5000)
            data['balance'] += reward
            data['total_earned'] += reward
            self.save_user_data(interaction.user.id, data)
            
            embed = create_embed(
                title="Mystery Box Opened!",
                description=f"You spent **${price:,}** and got **${reward:,}** back!",
                color=discord.Color.gold() if reward > price else discord.Color.red()
            )
            embed.add_field(
                name="Profit" if reward > price else "Loss",
                value=f"${reward - price:,}" if reward > price else f"-${price - reward:,}"
            )
            embed.add_field(name="New Balance", value=f"${data['balance']:,}")
        else:
            data['inventory'].append(item_name)
            self.save_user_data(interaction.user.id, data)
            
            embed = create_embed(
                title="Purchase Successful",
                description=f"You bought **{item_name}** for **${price:,}**",
                color=discord.Color.green()
            )
            embed.add_field(name="New Balance", value=f"${data['balance']:,}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction):
        """Show user's items"""
        data = self.get_user_data(interaction.user.id)
        
        if not data['inventory']:
            embed = create_embed(
                title="🎒 Empty Inventory",
                description="You don't own any items yet!",
                color=discord.Color.orange()
            )
        else:
            items_list = "\n".join([f"• {item}" for item in data['inventory']])
            embed = create_embed(
                title=f"🎒 {interaction.user.name}'s Inventory",
                description=items_list,
                color=discord.Color.blue()
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="pay", description="Send coins to another user")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Transfer money to another user"""
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't pay yourself!", ephemeral=True)
            return
        
        if user.bot:
            await interaction.response.send_message("❌ You can't pay bots!", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
            return
        
        sender_data = self.get_user_data(interaction.user.id)
        
        if sender_data['balance'] < amount:
            embed = create_embed(
                title="💸 Insufficient Funds",
                description=f"You only have **${sender_data['balance']:,}**",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Process transaction
        receiver_data = self.get_user_data(user.id)
        sender_data['balance'] -= amount
        receiver_data['balance'] += amount
        
        self.save_user_data(interaction.user.id, sender_data)
        self.save_user_data(user.id, receiver_data)
        
        embed = create_embed(
            title="💸 Payment Sent!",
            description=f"You sent **${amount:,}** to {user.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Your New Balance", value=f"${sender_data['balance']:,}")
        
        await interaction.response.send_message(embed=embed)
        
        # Notify receiver
        try:
            receiver_embed = create_embed(
                title="💰 Payment Received!",
                description=f"{interaction.user.mention} sent you **${amount:,}**!",
                color=discord.Color.green()
            )
            await user.send(embed=receiver_embed)
        except:
            pass  # User has DMs disabled
    
    @app_commands.command(name="gamble", description="Gamble your coins (50/50 chance)")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        """Gamble coins with 50/50 odds"""
        data = self.get_user_data(interaction.user.id)
        
        if amount <= 0:
            await interaction.response.send_message("❌ Bet must be positive!", ephemeral=True)
            return
        
        if data['balance'] < amount:
            embed = create_embed(
                title="💸 Insufficient Funds",
                description=f"You only have **${data['balance']:,}**",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Gamble
        win = random.choice([True, False])
        
        if win:
            data['balance'] += amount
            data['total_earned'] += amount
            embed = create_embed(
                title="🎰 You Won!",
                description=f"You won **${amount:,}**!",
                color=discord.Color.green()
            )
        else:
            data['balance'] -= amount
            data['total_spent'] += amount
            embed = create_embed(
                title="💸 You Lost!",
                description=f"You lost **${amount:,}**!",
                color=discord.Color.red()
            )
        
        self.save_user_data(interaction.user.id, data)
        embed.add_field(name="New Balance", value=f"${data['balance']:,}")
        
        await interaction.response.send_message(embed=embed)
    
    # NEW COMMANDS
    
    @app_commands.command(name="deposit", description="Deposit coins into your bank")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        """Deposit to bank"""
        data = self.get_user_data(interaction.user.id)
        
        # Handle "all"
        if amount.lower() == 'all':
            amount_int = data['balance']
        else:
            try:
                amount_int = int(amount)
            except ValueError:
                await interaction.response.send_message("Invalid amount!", ephemeral=True)
                return
        
        if amount_int <= 0:
            await interaction.response.send_message("Amount must be positive!", ephemeral=True)
            return
        
        if data['balance'] < amount_int:
            await interaction.response.send_message(
                f"You only have ${data['balance']:,} in your wallet!",
                ephemeral=True
            )
            return
        
        data['balance'] -= amount_int
        data['bank'] += amount_int
        self.save_user_data(interaction.user.id, data)
        
        embed = create_embed(
            title="💰 Deposit Successful",
            description=f"Deposited **${amount_int:,}** into your bank.",
            color=discord.Color.green()
        )
        embed.add_field(name="👛 Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"${data['bank']:,}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="withdraw", description="Withdraw coins from your bank")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        """Withdraw from bank"""
        data = self.get_user_data(interaction.user.id)
        
        if amount.lower() == 'all':
            amount_int = data['bank']
        else:
            try:
                amount_int = int(amount)
            except ValueError:
                await interaction.response.send_message("Invalid amount!", ephemeral=True)
                return
        
        if amount_int <= 0:
            await interaction.response.send_message("Amount must be positive!", ephemeral=True)
            return
        
        if data['bank'] < amount_int:
            await interaction.response.send_message(
                f"You only have ${data['bank']:,} in your bank!",
                ephemeral=True
            )
            return
        
        data['bank'] -= amount_int
        data['balance'] += amount_int
        self.save_user_data(interaction.user.id, data)
        
        embed = create_embed(
            title="🏦 Withdrawal Successful",
            description=f"Withdrew **${amount_int:,}** from your bank.",
            color=discord.Color.green()
        )
        embed.add_field(name="👛 Wallet", value=f"${data['balance']:,}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"${data['bank']:,}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rob", description="Try to rob another user (5 min cooldown)")
    @app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)
    async def rob(self, interaction: discord.Interaction, user: discord.Member):
        """Rob another user"""
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't rob yourself.", ephemeral=True)
            return
        
        if user.bot:
            await interaction.response.send_message("❌ You can't rob bots.", ephemeral=True)
            return
        
        robber_data = self.get_user_data(interaction.user.id)
        victim_data = self.get_user_data(user.id)
        
        if victim_data['balance'] < 100:
            await interaction.response.send_message(
                f"❌ {user.mention} doesn't have enough coins to rob.",
                ephemeral=True
            )
            return
        
        if robber_data['balance'] < 200:
            await interaction.response.send_message(
                "❌ You need at least **$200** in your wallet to attempt a robbery.",
                ephemeral=True
            )
            return
        
        # 40% success rate
        success = random.random() < 0.4
        
        if success:
            stolen = random.randint(
                int(victim_data['balance'] * 0.1),
                int(victim_data['balance'] * 0.3)
            )
            robber_data['balance'] += stolen
            victim_data['balance'] -= stolen
            
            self.save_user_data(interaction.user.id, robber_data)
            self.save_user_data(user.id, victim_data)
            
            embed = create_embed(
                title="🦹 Robbery Successful!",
                description=f"You stole **${stolen:,}** from {user.mention}!",
                color=discord.Color.green()
            )
            embed.add_field(name="💰 Your Balance", value=f"${robber_data['balance']:,}")
        else:
            fine = random.randint(100, 300)
            robber_data['balance'] = max(0, robber_data['balance'] - fine)
            self.save_user_data(interaction.user.id, robber_data)
            
            embed = create_embed(
                title="🚔 Robbery Failed!",
                description=f"You got caught and paid a **${fine:,}** fine!",
                color=discord.Color.red()
            )
            embed.add_field(name="💰 Your Balance", value=f"${robber_data['balance']:,}")
        
        await interaction.response.send_message(embed=embed)
    
    @rob.error
    async def rob_error(self, interaction: discord.Interaction, error):
        """Handle rob command cooldown"""
        if isinstance(error, app_commands.CommandOnCooldown):
            minutes = error.retry_after / 60
            await interaction.response.send_message(
                f"⏰ You're on cooldown! Try robbing again in **{minutes:.0f} minutes**.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economy(bot))