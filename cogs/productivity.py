import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
from utils.database import Database
from utils.embeds import create_embed

class Productivity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/users.json')
        self.check_reminders.start()
    
    def cog_unload(self):
        self.check_reminders.cancel()
    
    @tasks.loop(minutes=1)
    async def check_reminders(self):
        """Check for due reminders every minute"""
        all_data = self.db.get_all()
        current_time = datetime.utcnow()
        
        for user_id, data in all_data.items():
            reminders = data.get('reminders', [])
            due_reminders = []
            
            for reminder in reminders[:]:
                remind_time = datetime.fromisoformat(reminder['time'])
                if current_time >= remind_time:
                    due_reminders.append(reminder)
                    reminders.remove(reminder)
            
            if due_reminders:
                data['reminders'] = reminders
                self.db.set(user_id, data)
                
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    for reminder in due_reminders:
                        embed = create_embed(
                            title="⏰ Reminder!",
                            description=reminder['task'],
                            color=discord.Color.blue()
                        )
                        await user.send(embed=embed)
                except:
                    pass
    
    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="remind", description="Set a reminder")
    async def remind(self, interaction: discord.Interaction, time: str, task: str):
        """Set a reminder (e.g., /remind 1h Do homework)"""
        # Parse time
        time_units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }
        
        try:
            unit = time[-1].lower()
            amount = int(time[:-1])
            
            if unit not in time_units:
                raise ValueError
            
            seconds = amount * time_units[unit]
            remind_time = datetime.utcnow() + timedelta(seconds=seconds)
            
        except:
            embed = create_embed(
                title="❌ Invalid Time Format",
                description="Use format like: `1h`, `30m`, `2d`",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Save reminder
        data = self.db.get(str(interaction.user.id), {'reminders': [], 'notes': [], 'moods': []})
        
        data['reminders'].append({
            'task': task,
            'time': remind_time.isoformat(),
            'created': datetime.utcnow().isoformat()
        })
        
        self.db.set(str(interaction.user.id), data)
        
        embed = create_embed(
            title="✅ Reminder Set!",
            description=f"I'll remind you about: **{task}**",
            color=discord.Color.green()
        )
        embed.add_field(name="When", value=f"In {time}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="note", description="Save a quick note")
    async def note(self, interaction: discord.Interaction, text: str):
        """Save a note"""
        data = self.db.get(str(interaction.user.id), {'reminders': [], 'notes': [], 'moods': []})
        
        data['notes'].append({
            'text': text,
            'created': datetime.utcnow().isoformat()
        })
        
        self.db.set(str(interaction.user.id), data)
        
        embed = create_embed(
            title="📝 Note Saved!",
            description=f"Saved: *{text}*",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="notes", description="View all your notes")
    async def notes(self, interaction: discord.Interaction):
        """View saved notes"""
        data = self.db.get(str(interaction.user.id), {'notes': []})
        
        if not data['notes']:
            embed = create_embed(
                title="📝 No Notes",
                description="You haven't saved any notes yet!",
                color=discord.Color.orange()
            )
        else:
            notes_list = ""
            for idx, note in enumerate(data['notes'][-10:], 1):  # Last 10 notes
                created = datetime.fromisoformat(note['created']).strftime("%Y-%m-%d")
                notes_list += f"**{idx}.** {note['text']}\n*{created}*\n\n"
            
            embed = create_embed(
                title="📝 Your Notes",
                description=notes_list,
                color=discord.Color.blue()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="mood", description="Track your mood")
    async def mood(self, interaction: discord.Interaction, emoji: str):
        """Log daily mood"""
        data = self.db.get(str(interaction.user.id), {'reminders': [], 'notes': [], 'moods': []})
        
        today = datetime.utcnow().date().isoformat()
        
        # Check if already logged today
        for mood in data['moods']:
            if mood['date'] == today:
                embed = create_embed(
                    title="✅ Mood Already Logged",
                    description=f"You already logged your mood as {mood['emoji']} today!",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Log mood
        data['moods'].append({
            'emoji': emoji,
            'date': today
        })
        
        self.db.set(str(interaction.user.id), data)
        
        embed = create_embed(
            title="✅ Mood Logged!",
            description=f"Today's mood: {emoji}",
            color=discord.Color.green()
        )
        
        # Show mood trend
        if len(data['moods']) >= 7:
            recent_moods = " ".join([m['emoji'] for m in data['moods'][-7:]])
            embed.add_field(name="Last 7 Days", value=recent_moods)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Productivity(bot))