import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import html
import random
from utils.database import Database

class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/trivia.json')
        self.active_games = {}

    def get_user_stats(self, user_id: int) -> dict:
        return self.db.get(str(user_id), {
            'correct': 0,
            'wrong': 0,
            'total': 0,
            'streak': 0,
            'best_streak': 0
        })

    def save_user_stats(self, user_id: int, data: dict):
        self.db.set(str(user_id), data)

    async def fetch_question(self, category: int = None, difficulty: str = None) -> dict:
        """Fetch question from Open Trivia DB (completely free)"""
        url = "https://opentdb.com/api.php?amount=1&type=multiple"
        if category:
            url += f"&category={category}"
        if difficulty:
            url += f"&difficulty={difficulty}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['response_code'] == 0:
                            return data['results'][0]
        except:
            pass
        return None

    @app_commands.command(name="trivia", description="Answer a trivia question")
    @app_commands.describe(
        difficulty="Question difficulty",
        category="Question category"
    )
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy", value="easy"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="Hard", value="hard"),
    ])
    @app_commands.choices(category=[
        app_commands.Choice(name="General Knowledge", value=9),
        app_commands.Choice(name="Science", value=17),
        app_commands.Choice(name="History", value=23),
        app_commands.Choice(name="Geography", value=22),
        app_commands.Choice(name="Sports", value=21),
        app_commands.Choice(name="Music", value=12),
        app_commands.Choice(name="Movies", value=11),
        app_commands.Choice(name="Video Games", value=15),
        app_commands.Choice(name="Computers", value=18),
        app_commands.Choice(name="Anime", value=31),
    ])
    async def trivia(
        self,
        interaction: discord.Interaction,
        difficulty: app_commands.Choice[str] = None,
        category: app_commands.Choice[int] = None
    ):
        if interaction.user.id in self.active_games:
            await interaction.response.send_message(
                "you already have an active question. answer it first.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        question_data = await self.fetch_question(
            category=category.value if category else None,
            difficulty=difficulty.value if difficulty else None
        )

        if not question_data:
            # Fallback questions
            fallbacks = [
                {
                    "question": "What is the capital of France?",
                    "correct_answer": "Paris",
                    "incorrect_answers": ["London", "Berlin", "Madrid"],
                    "difficulty": "easy",
                    "category": "Geography"
                },
                {
                    "question": "What is 2 + 2?",
                    "correct_answer": "4",
                    "incorrect_answers": ["3", "5", "22"],
                    "difficulty": "easy",
                    "category": "Mathematics"
                },
            ]
            question_data = random.choice(fallbacks)

        # Decode HTML entities
        question = html.unescape(question_data['question'])
        correct = html.unescape(question_data['correct_answer'])
        wrong = [html.unescape(a) for a in question_data['incorrect_answers']]

        # Shuffle answers
        all_answers = [correct] + wrong
        random.shuffle(all_answers)

        diff = question_data.get('difficulty', 'medium')
        cat = question_data.get('category', 'General')

        # Reward based on difficulty
        rewards = {'easy': 100, 'medium': 250, 'hard': 500}
        reward = rewards.get(diff, 200)

        letters = ['A', 'B', 'C', 'D']
        options_text = "\n".join([
            f"**{letters[i]}.** {ans}"
            for i, ans in enumerate(all_answers)
        ])

        embed = discord.Embed(
            title="Trivia",
            description=question,
            color=0x1a1a2e
        )
        embed.add_field(name="Options", value=options_text, inline=False)
        embed.add_field(name="Category", value=cat, inline=True)
        embed.add_field(name="Difficulty", value=diff.title(), inline=True)
        embed.add_field(name="Reward", value=f"${reward:,}", inline=True)
        embed.set_footer(text="type A, B, C or D — you have 20 seconds")

        await interaction.followup.send(embed=embed)

        # Mark as active
        self.active_games[interaction.user.id] = True

        def check(m):
            return (
                m.author.id == interaction.user.id
                and m.channel.id == interaction.channel.id
                and m.content.upper() in ['A', 'B', 'C', 'D']
            )

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=20.0)
            user_answer = msg.content.upper()
            idx = letters.index(user_answer)
            chosen = all_answers[idx]

            stats = self.get_user_stats(interaction.user.id)
            stats['total'] += 1

            if chosen == correct:
                stats['correct'] += 1
                stats['streak'] += 1
                if stats['streak'] > stats['best_streak']:
                    stats['best_streak'] = stats['streak']

                # Add reward to economy
                from utils.database import Database
                econ = Database('data/economy.json')
                user_data = econ.get(str(interaction.user.id), {'balance': 0})
                user_data['balance'] = user_data.get('balance', 0) + reward
                econ.set(str(interaction.user.id), user_data)

                result_embed = discord.Embed(
                    title="correct",
                    description=f"**{correct}** was right. +${reward:,}",
                    color=discord.Color.green()
                )
                result_embed.add_field(
                    name="Streak",
                    value=f"{stats['streak']} in a row"
                )
            else:
                stats['wrong'] += 1
                stats['streak'] = 0

                result_embed = discord.Embed(
                    title="wrong",
                    description=f"correct answer was **{correct}**",
                    color=discord.Color.red()
                )

            self.save_user_stats(interaction.user.id, stats)
            await interaction.channel.send(embed=result_embed)

        except asyncio.TimeoutError:
            result_embed = discord.Embed(
                description=f"too slow. answer was **{correct}**",
                color=0x1a1a2e
            )
            await interaction.channel.send(embed=result_embed)

            stats = self.get_user_stats(interaction.user.id)
            stats['wrong'] += 1
            stats['streak'] = 0
            stats['total'] += 1
            self.save_user_stats(interaction.user.id, stats)

        finally:
            if interaction.user.id in self.active_games:
                del self.active_games[interaction.user.id]

    @app_commands.command(name="trivia_stats", description="View your trivia statistics")
    async def trivia_stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        target = user or interaction.user
        stats = self.get_user_stats(target.id)

        if stats['total'] == 0:
            await interaction.response.send_message(
                "no trivia played yet.",
                ephemeral=True
            )
            return

        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0

        embed = discord.Embed(
            title=f"{target.display_name}'s Trivia Stats",
            color=0x1a1a2e
        )
        embed.add_field(name="Correct", value=stats['correct'], inline=True)
        embed.add_field(name="Wrong", value=stats['wrong'], inline=True)
        embed.add_field(name="Total", value=stats['total'], inline=True)
        embed.add_field(name="Accuracy", value=f"{accuracy:.1f}%", inline=True)
        embed.add_field(name="Current Streak", value=stats['streak'], inline=True)
        embed.add_field(name="Best Streak", value=stats['best_streak'], inline=True)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Trivia(bot))