import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import aiohttp
import os
import pyfiglet


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.api_url = "https://models.inference.ai.azure.com/chat/completions"

        # 50+ jokes
        self.jokes = [
            "I told my psychiatrist I keep thinking I'm a dog. He told me to get off the couch.",
            "My grief counselor died. He was so good at his job, I don't even care.",
            "I have a lot of growing up to do. I realized that the other day inside my fort.",
            "I used to hate facial hair, but then it grew on me.",
            "My boss told me to have a good day. So I went home.",
            "I asked God for a bike, but I know God doesn't work that way. So I stole a bike and asked for forgiveness.",
            "The cemetery is a popular place. People are dying to get in.",
            "I don't trust stairs. They're always up to something.",
            "My wife told me I had to stop acting like a flamingo. I had to put my foot down.",
            "I told my doctor I broke my arm in two places. He told me to stop going to those places.",
            "Why don't scientists trust atoms? Because they make up everything.",
            "I'm reading a book about anti-gravity. It's impossible to put down.",
            "I used to play piano by ear. Now I use my hands.",
            "What do you call a fish wearing a bowtie? Sofishticated.",
            "I'm on a seafood diet. I see food and I eat it.",
            "Why did the scarecrow win an award? Because he was outstanding in his field.",
            "I don't trust people with graph paper. They're always plotting something.",
            "I told my wife she was drawing her eyebrows too high. She looked surprised.",
            "What's the best thing about Switzerland? I don't know, but the flag is a big plus.",
            "I have a fear of speed bumps. But I'm slowly getting over it.",
            "Why don't skeletons fight each other? They don't have the guts.",
            "I'm reading a horror book in braille. Something bad is going to happen, I can feel it.",
            "What do you call a fake noodle? An impasta.",
            "I used to be a banker, but I lost interest.",
            "Why did the coffee file a police report? It got mugged.",
            "I'd tell you a chemistry joke, but I know I wouldn't get a reaction.",
            "I tried to catch fog yesterday. Mist.",
            "What do you call a can opener that doesn't work? A can't opener.",
            "I told a chemistry joke. There was no reaction.",
            "I'm afraid for the calendar. Its days are numbered.",
            "What do you call a pig that does karate? A pork chop.",
            "I don't trust escalators. They're always up to something.",
            "I have a chicken-proof lawn. It's impeccable.",
            "What do you call a bear with no teeth? A gummy bear.",
            "I tried to sue the airline for losing my luggage. I lost my case.",
            "Why did the bicycle fall over? It was two tired.",
            "I'm not addicted to brake fluid. I can stop whenever I want.",
            "What did the grape say when it got stepped on? Nothing, it just let out a little wine.",
            "I told a time-traveling joke. You guys didn't laugh, but you will.",
            "Why did the man fall down the well? Because he couldn't see that well.",
            "I used to be a shoe salesman, but I just couldn't fit in.",
            "What do you call an alligator detective? An investigator.",
            "I'd tell you a construction joke, but I'm still working on it.",
            "Why did the math book look so sad? Because it had too many problems.",
            "I got hit in the head with a can of soda. Luckily it was a soft drink.",
            "What's the difference between a hippo and a Zippo? One is heavy, the other is a little lighter.",
            "I'd tell you a joke about UDP, but you might not get it.",
            "Why did the cookie go to the hospital? Because it felt crummy.",
            "I have a step ladder because my real ladder left when I was young.",
            "What do you call a snowman with a six-pack? An abdominal snowman.",
            "I'd tell you a joke about a wall, but I'm afraid you won't get over it.",
            "Why don't eggs tell jokes? They'd crack each other up.",
            "I tried to write a joke about a pencil, but it was pointless.",
        ]

        # 60+ facts
        self.facts = [
            "Honey never spoils. Archaeologists found 3000-year-old honey in Egyptian tombs that was still edible.",
            "A day on Venus is longer than a year on Venus.",
            "Octopuses have three hearts, blue blood, and nine brains.",
            "The human brain uses about 20% of the body's total energy.",
            "A group of flamingos is called a flamboyance.",
            "There are more possible iterations of a game of chess than atoms in the observable universe.",
            "Sharks are older than trees. They've existed for 450 million years.",
            "The average person walks about 100,000 miles in their lifetime.",
            "Cleopatra lived closer in time to the Moon landing than to the construction of the Great Pyramid.",
            "A single cloud can weigh more than a million pounds.",
            "Bananas are berries, but strawberries aren't.",
            "The Eiffel Tower grows taller in summer due to thermal expansion.",
            "Wombat poop is cube-shaped.",
            "A group of crows is called a murder.",
            "Honeybees can recognize human faces.",
            "The shortest war in history lasted 38 minutes.",
            "A jiffy is an actual unit of time: 1/100th of a second.",
            "There are more stars in the universe than grains of sand on Earth.",
            "Your stomach gets a new lining every 3-4 days.",
            "Koalas have fingerprints nearly identical to humans.",
            "A bolt of lightning contains enough energy to toast 100,000 slices of bread.",
            "There are more possible games of chess than there are atoms in the universe.",
            "Octopuses can taste with their suckers.",
            "The longest word in English without a vowel is 'rhythms'.",
            "A blue whale's heart is the size of a small car.",
            "Vending machines kill more people than sharks do each year.",
            "Human thigh bones are stronger than concrete.",
            "You produce enough saliva in your lifetime to fill two swimming pools.",
            "The Hawaiian alphabet has only 13 letters.",
            "A group of porcupines is called a prickle.",
            "There's a village in Norway called 'Hell'. It freezes over every winter.",
            "Sharks can detect a single drop of blood in 100 liters of water.",
            "Cows have best friends and get stressed when separated.",
            "The first oranges weren't orange — they were green.",
            "Polar bears have black skin under their white fur.",
            "Some cats are allergic to humans.",
            "A group of owls is called a parliament.",
            "Sloths can hold their breath longer than dolphins — up to 40 minutes.",
            "The unicorn is the national animal of Scotland.",
            "A group of pandas is called an embarrassment.",
            "Hot water can freeze faster than cold water. It's called the Mpemba effect.",
            "The world's oldest known living tree is over 5,000 years old.",
            "There are more bacteria in your mouth than people on Earth.",
            "An ostrich's eye is bigger than its brain.",
            "Butterflies taste with their feet.",
            "The dots on dice are called 'pips'.",
            "A group of hedgehogs is called an array.",
            "Starfish can regrow their arms. Some can grow a new body from a single arm.",
            "Humans share about 50% of their DNA with bananas.",
            "The shortest commercial flight in the world lasts 57 seconds.",
            "Sea otters hold hands while sleeping so they don't drift apart.",
            "A group of kittens is called a kindle.",
            "The inventor of the Frisbee was turned into a Frisbee after he died.",
            "Dolphins have names for each other.",
            "There's a species of jellyfish that is biologically immortal.",
            "A group of rhinos is called a crash.",
            "The first alarm clock could only ring at 4 AM.",
            "Crocodiles can't stick their tongues out.",
            "The word 'nerd' was first coined by Dr. Seuss in 'If I Ran the Zoo'.",
            "Slugs have four noses.",
            "A group of ravens is called an unkindness.",
            "The first computer virus was created in 1983.",
            "Armadillo shells are bulletproof.",
            "The national flag of Nepal is the only one that isn't rectangular.",
        ]

        # 40+ pickup lines
        self.pickup_lines = [
            "Are you French? Because Eiffel for you.",
            "Do you have a name, or can I call you mine?",
            "Are you a parking ticket? Because you've got 'fine' written all over you.",
            "Is your name Google? Because you've got everything I've been searching for.",
            "Are you a magician? Because whenever I look at you, everyone else disappears.",
            "Do you have a Band-Aid? Because I just scraped my knee falling for you.",
            "Are you Wi-Fi? Because I'm feeling a connection.",
            "Did the sun come out, or did you just smile at me?",
            "Are you a camera? Because every time I look at you, I smile.",
            "Do you have a map? I keep getting lost in your eyes.",
            "Are you Australian? Because you meet all of my koala-fications.",
            "If beauty were time, you'd be eternity.",
            "Are you a bank loan? Because you got my interest.",
            "Is your dad a baker? Because you're a cutie pie.",
            "Are you Cinderella? Because I see that dress disappearing at midnight.",
            "Do you play soccer? Because you're a keeper.",
            "Are you a firework? Because you light up my night.",
            "I'm not a photographer, but I can picture us together.",
            "If you were a triangle, you'd be acute one.",
            "Are you made of copper and tellurium? Because you're Cu-Te.",
            "Is your name Waldo? Because someone like you is hard to find.",
            "Did you swallow magnets? Because you're attractive.",
            "Are you a keyboard? Because you're just my type.",
            "If I could rearrange the alphabet, I'd put U and I together.",
            "Are you a power outage? Because you light up my world.",
            "Do you have a sunburn, or are you always this hot?",
            "Are you a time traveler? Because I can see you in my future.",
            "Is your dad an alien? Because there's nothing else like you on Earth.",
            "Are you a haunted house? Because I'm screaming inside.",
            "Did it hurt? When you fell from heaven?",
            "Are you a snowstorm? Because you're making me melt.",
            "Are you a cat? Because you're purr-fect.",
            "If you were a fruit, you'd be a fine-apple.",
            "Are you an elevator? Because you lift me up.",
            "Do you like Star Wars? Because Yoda only one for me.",
            "Are you a volcano? Because I lava you.",
            "I'd say God bless you, but it looks like he already did.",
            "Are you a gardener? Because I'd dig you.",
            "Is your name Hope? Because you're my only one.",
            "If kisses were snowflakes, I'd send you a blizzard.",
            "Are you Netflix? Because I could watch you all day.",
            "Do you believe in love at first sight, or should I walk by again?",
        ]

        # 40+ would you rather
        self.wyr_questions = [
            "Would you rather be able to fly or be invisible?",
            "Would you rather have unlimited money or unlimited time?",
            "Would you rather know how you die or when you die?",
            "Would you rather live without internet or without music?",
            "Would you rather always be 10 minutes late or 20 minutes early?",
            "Would you rather have the ability to speak all languages or play all instruments?",
            "Would you rather never sleep or never eat?",
            "Would you rather be the funniest person in the room or the smartest?",
            "Would you rather lose all your photos or all your messages?",
            "Would you rather be able to read minds or see the future?",
            "Would you rather live in a treehouse or an underground bunker?",
            "Would you rather have free WiFi wherever you go or free coffee wherever you go?",
            "Would you rather be able to talk to animals or speak every language?",
            "Would you rather live without heating or without AC?",
            "Would you rather fight 100 duck-sized horses or 1 horse-sized duck?",
            "Would you rather be famous but hated or unknown but loved?",
            "Would you rather time travel to the past or the future?",
            "Would you rather have a rewind button or a pause button for life?",
            "Would you rather have one wish granted today or three wishes granted in 10 years?",
            "Would you rather always know the truth or never be lied to?",
            "Would you rather have an extra finger or an extra toe?",
            "Would you rather be a famous musician or a famous actor?",
            "Would you rather live forever or die young and happy?",
            "Would you rather give up your phone or give up your friends?",
            "Would you rather only be able to whisper or only be able to shout?",
            "Would you rather live without your favorite food or only eat your favorite food?",
            "Would you rather be able to teleport or read minds?",
            "Would you rather be the worst player on a winning team or the best on a losing team?",
            "Would you rather know everything or be able to do anything?",
            "Would you rather lose your sense of taste or your sense of smell?",
            "Would you rather have a third eye or a third ear?",
            "Would you rather be alone for life or never have alone time?",
            "Would you rather have super strength or super speed?",
            "Would you rather live in a city or a remote cabin?",
            "Would you rather forget your past or know your future?",
            "Would you rather have a personal chef or a personal driver?",
            "Would you rather be the funniest or the most attractive person in any room?",
            "Would you rather fight a bear once a year or fight a goose every day?",
            "Would you rather always have to say what you think or never speak again?",
            "Would you rather never feel pain or never feel fear?",
            "Would you rather have a remote control for life or a fast-forward button?",
            "Would you rather be 5 years old forever or 80 years old forever?",
            "Would you rather have a million dollars now or 10 million in 10 years?",
        ]

        # 20 magic 8ball responses
        self.ball_responses = [
            "It is certain.",
            "Without a doubt.",
            "Yes, definitely.",
            "Most likely.",
            "Signs point to yes.",
            "Reply hazy, try again.",
            "Ask again later.",
            "Cannot predict now.",
            "Don't count on it.",
            "My sources say no.",
            "Very doubtful.",
            "Outlook not so good.",
            "The void says yes.",
            "The shadows are unclear.",
            "Darkness confirms it.",
            "Even the void doubts this.",
            "Yes, but at what cost.",
            "Concentrate and ask again.",
            "Outlook is grim.",
            "Ask me when the moon rises.",
        ]

        # 20+ typing race sentences (used by games.py)
        self.typerace_sentences = [
            "the quick brown fox jumps over the lazy dog.",
            "she sells seashells by the seashore on sunny afternoons.",
            "a journey of a thousand miles begins with a single step.",
            "to be or not to be that is the question we all face.",
            "the early bird catches the worm but the second mouse gets the cheese.",
            "all that glitters is not gold but some of it certainly is.",
            "the pen is mightier than the sword in most situations.",
            "when life gives you lemons make lemonade and sell it.",
            "an apple a day keeps the doctor away most of the time.",
            "beauty is in the eye of the beholder and nowhere else.",
            "actions speak louder than words ever could in this world.",
            "the grass is always greener on the other side of the fence.",
            "rome was not built in a day but it eventually fell.",
            "better late than never unless you are attending a funeral.",
            "every cloud has a silver lining somewhere if you look hard.",
            "the cat sat on the mat while the dog slept on the floor.",
            "music is the universal language of mankind across all cultures.",
            "knowledge is power but only when properly applied to life.",
            "time and tide wait for no man or woman on this earth.",
            "the only thing we have to fear is fear itself and spiders.",
            "you can't judge a book by its cover but you can try anyway.",
            "the best things in life are free but the good ones cost money.",
        ]

    async def _send_joke(self, message):
        """Helper used by intent_parser to send a random joke via a message reply."""
        try:
            embed = discord.Embed(description=random.choice(self.jokes), color=0x1a1a2e)
            await message.reply(embed=embed, mention_author=False)
        except Exception:
            pass

    async def _ai_one_liner(self, system_prompt: str, user_prompt: str) -> str:
        """Helper: call the AI for a one-liner response."""
        if not self.github_token:
            return None
        try:
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.9,
                "max_tokens": 200
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
        except Exception as e:
            print(f"AI helper error: {e}")
        return None

    @app_commands.command(name="roll", description="Roll a dice")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        self.bot.increment_command('roll')
        if sides < 2 or sides > 1000:
            await interaction.response.send_message(
                "Sides must be between 2 and 1000.",
                ephemeral=True
            )
            return
        result = random.randint(1, sides)
        embed = discord.Embed(
            description=f"You rolled a **{result}** out of {sides}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="flip", description="Flip a coin")
    async def flip(self, interaction: discord.Interaction):
        self.bot.increment_command('flip')
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            description=f"**{result}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)




    @app_commands.command(name="say", description="Make the bot say something (owner only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('say')
        # Owner-only check
        owner_id = int(os.getenv('OWNER_ID', '0'))
        if interaction.user.id != owner_id:
            try:
                await interaction.response.send_message("❌ only my owner can use this.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("❌ only my owner can use this.", ephemeral=True)
            return
        try:
            await interaction.channel.send(text)
            try:
                await interaction.response.send_message("done.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("done.", ephemeral=True)
        except Exception as e:
            try:
                await interaction.response.send_message(f"failed: {e}", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(f"failed: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Fun(bot))
