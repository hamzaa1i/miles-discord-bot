import discord
from discord.ext import commands
from discord import app_commands
from utils.embeds import create_embed
from utils.database import Database

class EnhancedShop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/economy.json')
        self.shop_db = Database('data/shop.json')
    
    def get_shop_items(self, guild_id: int):
        """Get shop items for a guild"""
        default_items = {
            "🎨 Custom Role": {
                "price": 5000,
                "description": "Get a custom colored role",
                "category": "cosmetic",
                "stock": -1  # Unlimited
            },
            "🎭 Name Change": {
                "price": 2500,
                "description": "Change your nickname",
                "category": "cosmetic",
                "stock": -1
            },
            "🌟 VIP Badge": {
                "price": 10000,
                "description": "Exclusive VIP badge in your profile",
                "category": "premium",
                "stock": -1
            },
            "💎 Premium Role": {
                "price": 15000,
                "description": "Get the Premium role",
                "category": "premium",
                "stock": -1
            },
            "🎁 Mystery Box": {
                "price": 1000,
                "description": "Random reward (500-5000 coins)",
                "category": "gamble",
                "stock": -1
            },
            "🎪 XP Boost": {
                "price": 3000,
                "description": "2x XP for 24 hours",
                "category": "boost",
                "stock": 10
            },
            "💰 Money Boost": {
                "price": 4000,
                "description": "2x coins from work for 24 hours",
                "category": "boost",
                "stock": 10
            }
        }
        
        items = self.shop_db.get(str(guild_id), default_items)
        return items
    
    @app_commands.command(name="shop_view", description="View the enhanced shop")
    async def shop_view(self, interaction: discord.Interaction, category: str = None):
        """View shop by category"""
        items = self.get_shop_items(interaction.guild.id)
        
        categories = {
            "cosmetic": "🎨 Cosmetic Items",
            "premium": "⭐ Premium Items",
            "gamble": "🎲 Gamble Items",
            "boost": "🚀 Boost Items"
        }
        
        if category:
            category = category.lower()
            if category not in categories:
                await interaction.response.send_message("❌ Invalid category! Choose: cosmetic, premium, gamble, boost", ephemeral=True)
                return
            
            filtered_items = {k: v for k, v in items.items() if v.get('category') == category}
            title = categories[category]
        else:
            filtered_items = items
            title = "🏪 Miles Shop - All Items"
        
        embed = create_embed(
            title=title,
            description="Purchase items with your hard-earned coins!",
            color=discord.Color.blue()
        )
        
        for item_name, item_data in filtered_items.items():
            stock_text = f"Stock: {item_data['stock']}" if item_data['stock'] != -1 else "Unlimited"
            embed.add_field(
                name=f"{item_name} - ${item_data['price']:,}",
                value=f"{item_data['description']}\n*{stock_text}*",
                inline=False
            )
        
        embed.set_footer(text="Use /buy <item name> to purchase")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="buy_item", description="Buy an item from the shop")
    async def buy_item(self, interaction: discord.Interaction, item: str):
        """Purchase item"""
        items = self.get_shop_items(interaction.guild.id)
        user_data = self.db.get(str(interaction.user.id), {'balance': 0, 'inventory': []})
        
        # Find item
        item_found = None
        for shop_item, shop_data in items.items():
            if item.lower() in shop_item.lower():
                item_found = (shop_item, shop_data)
                break
        
        if not item_found:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return
        
        item_name, item_data = item_found
        price = item_data['price']
        
        # Check stock
        if item_data['stock'] == 0:
            await interaction.response.send_message("❌ This item is out of stock!", ephemeral=True)
            return
        
        # Check balance
        if user_data['balance'] < price:
            await interaction.response.send_message(f"❌ You need ${price:,} but only have ${user_data['balance']:,}", ephemeral=True)
            return
        
        # Process purchase
        user_data['balance'] -= price
        
        # Handle special items
        if "Mystery Box" in item_name:
            import random
            reward = random.randint(500, 5000)
            user_data['balance'] += reward
            special_msg = f"\n\n🎁 You got **{reward} coins** from the mystery box!"
        else:
            user_data['inventory'].append(item_name)
            special_msg = ""
        
        # Update stock
        if item_data['stock'] != -1:
            items[item_name]['stock'] -= 1
            self.shop_db.set(str(interaction.guild.id), items)
        
        self.db.set(str(interaction.user.id), user_data)
        
        embed = create_embed(
            title="✅ Purchase Successful!",
            description=f"You bought **{item_name}** for **${price:,}**!{special_msg}",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"${user_data['balance']:,}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="use_item", description="Use an item from your inventory")
    async def use_item(self, interaction: discord.Interaction, item: str):
        """Use an item"""
        user_data = self.db.get(str(interaction.user.id), {'inventory': []})
        
        # Find item in inventory
        item_found = None
        for inv_item in user_data['inventory']:
            if item.lower() in inv_item.lower():
                item_found = inv_item
                break
        
        if not item_found:
            await interaction.response.send_message("❌ You don't own this item!", ephemeral=True)
            return
        
        # Handle item usage
        if "Custom Role" in item_found:
            # Give instructions
            embed = create_embed(
                title="🎨 Custom Role",
                description="Ask a server admin to create your custom role!\nShow them this message.",
                color=discord.Color.blue()
            )
            user_data['inventory'].remove(item_found)
            self.db.set(str(interaction.user.id), user_data)
            
        elif "Name Change" in item_found:
            embed = create_embed(
                title="🎭 Name Change",
                description="Use `/nick <new name>` to change your nickname!",
                color=discord.Color.blue()
            )
            user_data['inventory'].remove(item_found)
            self.db.set(str(interaction.user.id), user_data)
        
        else:
            embed = create_embed(
                title="ℹ️ Item Info",
                description=f"You used **{item_found}**!",
                color=discord.Color.green()
            )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(EnhancedShop(bot))