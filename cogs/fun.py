import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import aiohttp
from utils.ai_handler import call_ai_fast


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

        self.ball_responses = [
            "It is certain.", "Without a doubt.", "Yes, definitely.", "Most likely.",
            "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
            "Cannot predict now.", "Don't count on it.", "My sources say no.",
            "Very doubtful.", "Outlook not so good.", "The void says yes.",
            "The shadows are unclear.", "Darkness confirms it.", "Even the void doubts this.",
            "Yes, but at what cost.", "Concentrate and ask again.", "Outlook is grim.",
            "Ask me when the moon rises.",
        ]

    async def _ai_one_liner(self, system_prompt: str, user_prompt: str) -> str:
        """Call AI for a fast one-liner response."""
        return await call_ai_fast([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

    @app_commands.command(name="roll", description="Roll a dice")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        self.bot.increment_command('roll')
        if sides < 2 or sides > 1000:
            await interaction.response.send_message("sides must be between 2 and 1000.", ephemeral=True)
            return
        result = random.randint(1, sides)
        await interaction.response.send_message(f"🎲 rolled a **{result}** (d{sides})")

    @app_commands.command(name="flip", description="Flip a coin")
    async def flip(self, interaction: discord.Interaction):
        self.bot.increment_command('flip')
        result = random.choice(["heads", "tails"])
        await interaction.response.send_message(f"🪙 {result}")

    @app_commands.command(name="say", description="Make the bot say something (owner only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('say')
        owner_id = int(os.getenv('OWNER_ID', '0'))
        if interaction.user.id != owner_id:
            await interaction.response.send_message("❌ only my owner can use this.", ephemeral=True)
            return
        try:
            await interaction.channel.send(text)
            await interaction.response.send_message("done.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"failed: {e}", ephemeral=True)

    @app_commands.command(name="joke", description="Get a random joke")
    async def joke(self, interaction: discord.Interaction):
        self.bot.increment_command('joke')
        await interaction.response.send_message(random.choice(self.jokes))

    @app_commands.command(name="meme", description="Random meme from r/dankmemes")
    async def meme(self, interaction: discord.Interaction):
        self.bot.increment_command('meme')
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://meme-api.com/gimme/dankmemes') as r:
                    if r.status == 200:
                        data = await r.json()
                        embed = discord.Embed(title=data.get('title', 'meme'), url=data.get('postLink', ''), color=0xe91e63)
                        embed.set_image(url=data.get('url', ''))
                        embed.set_footer(text=f"u/{data.get('author', '?')} · r/{data.get('subreddit', 'dankmemes')} • 👍 {data.get('ups', 0)}")
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("couldn't fetch meme.")
        except Exception:
            await interaction.followup.send("failed to fetch meme.")

    @app_commands.command(name="fact", description="Get a random fact")
    async def fact(self, interaction: discord.Interaction):
        self.bot.increment_command('fact')
        await interaction.response.send_message(f"💡 {random.choice(self.facts)}")

    @app_commands.command(name="quote", description="Get a random dark quote")
    async def quote(self, interaction: discord.Interaction):
        self.bot.increment_command('quote')
        quotes = [
            "we are all haunted. the question is by what.",
            "not all who wander in darkness are lost. some just prefer it.",
            "the night is not dark. it is honest.",
            "silence is not empty. it is full of everything unsaid.",
            "stars only exist because darkness surrounds them.",
            "pain is just information. what you do with it matters.",
            "the strongest people carry the darkest storms inside them.",
            "every shadow was once light.",
            "we are all broken. that's how the light gets in.",
            "some birds aren't meant to be caged.",
            "the darkest nights produce the brightest stars.",
            "what we lose in the dark, we find in the silence.",
            "to exist is to haunt and be haunted.",
            "the dead don't speak. they just listen.",
            "we mistake silence for absence.",
            "even broken clocks tell the right time twice a day.",
            "you can't burn what's already ash.",
            "ghosts don't haunt houses. they haunt memories.",
            "the wound is the place where the light enters you.",
            "every ending is a beginning pretending otherwise.",
        ]
        await interaction.response.send_message(f'*"{random.choice(quotes)}"*')

    @app_commands.command(name="8ball", description="Ask the magic 8-ball")
    async def eightball(self, interaction: discord.Interaction, question: str):
        self.bot.increment_command('8ball')
        await interaction.response.send_message(f"🎱 {random.choice(self.ball_responses)}")

    @app_commands.command(name="pickup", description="Get a random pickup line")
    async def pickup(self, interaction: discord.Interaction):
        self.bot.increment_command('pickup')
        await interaction.response.send_message(random.choice(self.pickup_lines))

    @app_commands.command(name="wouldyourather", description="Get a random would-you-rather question")
    async def wouldyourather(self, interaction: discord.Interaction):
        self.bot.increment_command('wouldyourather')
        await interaction.response.send_message(f"🤔 {random.choice(self.wyr_questions)}")

    @app_commands.command(name="rizz", description="Get a random rizz line")
    async def rizz(self, interaction: discord.Interaction):
        self.bot.increment_command('rizz')
        rizz_lines = [
            "are you a magician? because every time i look at you, everyone else disappears.",
            "do you have a map? i keep getting lost in your eyes.",
            "is your name google? because you've got everything i've been searching for.",
            "are you french? because eiffel for you.",
            "do you have a band-aid? because i just scraped my knee falling for you.",
            "are you wi-fi? because i'm feeling a connection.",
            "did the sun come out, or did you just smile at me?",
            "are you a parking ticket? because you've got 'fine' written all over you.",
            "if beauty were time, you'd be eternity.",
            "are you a bank loan? because you got my interest.",
            "is your dad a baker? because you're a cutie pie.",
            "do you play soccer? because you're a keeper.",
            "i'm not a photographer, but i can picture us together.",
            "if you were a triangle, you'd be acute one.",
            "are you made of copper and tellurium? because you're cu-te.",
            "is your name waldo? because someone like you is hard to find.",
            "did you swallow magnets? because you're attractive.",
            "are you a keyboard? because you're just my type.",
            "if i could rearrange the alphabet, i'd put u and i together.",
            "are you a power outage? because you light up my world.",
            "do you have a sunburn, or are you always this hot?",
            "are you a time traveler? because i can see you in my future.",
            "is your dad an alien? because there's nothing else like you on earth.",
            "are you a haunted house? because i'm screaming inside.",
            "did it hurt? when you fell from heaven?",
            "are you a snowstorm? because you're making me melt.",
            "are you a cat? because you're purr-fect.",
            "if you were a fruit, you'd be a fine-apple.",
            "are you an elevator? because you lift me up.",
            "do you like star wars? because yoda only one for me.",
            "are you a volcano? because i lava you.",
            "i'd say god bless you, but it looks like he already did.",
            "are you a gardener? because i'd dig you.",
            "is your name hope? because you're my only one.",
            "if kisses were snowflakes, i'd send you a blizzard.",
        ]
        await interaction.response.send_message(random.choice(rizz_lines))

    @app_commands.command(name="topic", description="Random conversation topic")
    async def topic(self, interaction: discord.Interaction):
        self.bot.increment_command('topic')
        topics = [
            "If you could live in any fictional universe, which would it be?",
            "What's a skill you wish you had learned earlier?",
            "Would you rather know when you'll die or how you'll die?",
            "What's the darkest thought you've had that turned out to be funny?",
            "If money wasn't a factor, what would you do with your life?",
            "What's something everyone pretends to like but secretly hates?",
            "Would you erase one memory if you could?",
            "What do you think happens after death?",
            "If you could master any one skill instantly, what would it be?",
            "What's a truth most people aren't willing to admit?",
            "What's the weirdest dream you've ever had?",
            "If you could have dinner with anyone dead or alive, who would it be?",
            "What's a movie everyone loves that you can't stand?",
            "What's the most embarrassing phase you went through?",
            "If you could relive one day of your life, which would it be?",
            "What's a small thing that brings you unreasonable joy?",
            "What's the worst advice you've ever received?",
            "If you could teleport anywhere right now, where would you go?",
            "What's a hobby you've always wanted to try but haven't?",
            "What's the strangest food combination you actually enjoy?",
            "If you had to teach a college class on any topic, what would it be?",
            "What's a controversial opinion you stand behind?",
            "What's the most spontaneous thing you've ever done?",
            "If you could un-invent one thing, what would it be?",
            "What's a song that instantly puts you in a good mood?",
            "What's the best lesson you've learned the hard way?",
            "If you could swap lives with anyone for a day, who would it be?",
            "What's something you're irrationally afraid of?",
            "What's the best gift you've ever received?",
            "If you could only eat one cuisine for the rest of your life, what would it be?",
            "What's a trend you never understood?",
            "What's the most useless talent you have?",
            "If you could time travel to any era, when would you go?",
            "What's a book that changed how you think?",
            "What's the worst haircut you've ever had?",
            "If you could have any superpower for one day, what would it be?",
            "What's something you're proud of that you don't talk about?",
            "What's the most beautiful place you've ever been?",
            "If you could be fluent in any language instantly, which would you pick?",
            "What's a small kindness someone did for you that you never forgot?",
            "What's the craziest thing on your bucket list?",
            "If you had to describe yourself in three words, what would they be?",
            "What's a question you wish people asked you more often?",
        ]
        await interaction.response.send_message(random.choice(topics))

    @app_commands.command(name="compliment", description="AI compliment")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def compliment(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('compliment')
        await interaction.response.defer()
        target = user or interaction.user
        comp = await self._ai_one_liner(
            f"Give a genuine funny compliment to {target.display_name}. Lowercase, max 2 sentences. No emojis.",
            target.display_name
        )
        if not comp or "something broke" in comp:
            comp = f"{target.mention} you're doing better than you think."
        await interaction.followup.send(comp)

    @app_commands.command(name="roastme", description="Roast yourself")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def roastme(self, interaction: discord.Interaction):
        self.bot.increment_command('roastme')
        await interaction.response.defer()
        target = interaction.user
        roast = await self._ai_one_liner(
            f"Roast {target.display_name} in 1-2 sentences. They asked for it. Funny, savage, not hateful. Lowercase. No emojis.",
            target.display_name
        )
        if not roast or "something broke" in roast:
            roast = f"{target.mention} you asked for this. that's already a red flag."
        await interaction.followup.send(roast)

    @app_commands.command(name="ship", description="Ship two users")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def ship(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        self.bot.increment_command('ship')
        await interaction.response.defer()
        score = random.randint(1, 100)
        bar = "❤️" * (score // 10) + "🖤" * (10 - score // 10)
        if score < 30:
            verdict = "not compatible."
        elif score < 70:
            verdict = "there's potential."
        else:
            verdict = "perfect match."
        comment = await self._ai_one_liner(
            f"Comment on shipping {user1.display_name} and {user2.display_name} ({score}% match). Lowercase, max 15 words. No emojis.",
            f"{user1.display_name} x {user2.display_name} = {score}%"
        )
        msg = f"💖 {user1.mention} 🖤 {user2.mention}\nCompatibility: {score}%\n{bar}\n{verdict}"
        if comment and "something broke" not in comment:
            msg += f"\n*{comment}*"
        await interaction.followup.send(msg)

    @app_commands.command(name="rate", description="AI rates something /10")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def rate(self, interaction: discord.Interaction, thing: str):
        self.bot.increment_command('rate')
        await interaction.response.defer()
        score = random.randint(0, 10)
        comment = await self._ai_one_liner(
            f"You are cyn. Rate '{thing}' a {score}/10 in one sarcastic sentence. Lowercase. No emojis.",
            thing
        )
        msg = f"I rate **{thing}** a **{score}/10**"
        if comment and "something broke" not in comment:
            msg += f"\n*{comment}*"
        await interaction.followup.send(msg)

    @app_commands.command(name="battle", description="AI narrates a funny battle")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def battle(self, interaction: discord.Interaction, user: discord.Member):
        self.bot.increment_command('battle')
        if user.id == interaction.user.id:
            await interaction.response.send_message("you can't battle yourself.", ephemeral=True)
            return
        if user.id == interaction.client.user.id:
            await interaction.response.send_message("can't battle me. pick a human.", ephemeral=True)
            return
        await interaction.response.defer()
        result = await self._ai_one_liner(
            f"Write a short funny battle scene between {interaction.user.display_name} and {user.display_name}. 3-4 sentences. Absurd. Someone wins. Lowercase. No emojis.",
            f"{interaction.user.display_name} vs {user.display_name}"
        )
        if not result or "something broke" in result:
            result = f"{interaction.user.mention} swung. {user.mention} dodged and somehow won. weird."
        await interaction.followup.send(f"⚔️ **Battle**\n\n{result}")

    @app_commands.command(name="vibe", description="AI reads the channel vibe")
    @app_commands.checks.cooldown(1, 20.0, key=lambda i: i.user.id)
    async def vibe(self, interaction: discord.Interaction):
        self.bot.increment_command('vibe')
        await interaction.response.defer()
        messages = []
        try:
            async for m in interaction.channel.history(limit=30):
                if not m.author.bot and m.content:
                    messages.append(f"{m.author.display_name}: {m.content}")
                if len(messages) >= 10:
                    break
        except Exception:
            pass
        if not messages:
            await interaction.followup.send("no recent messages to read the vibe.")
            return
        transcript = "\n".join(reversed(messages))
        result = await self._ai_one_liner(
            "Based on these Discord messages, describe the vibe in one sarcastic sentence. Lowercase. No emojis.",
            transcript
        )
        if not result or "something broke" in result:
            result = "the vibe is... present."
        await interaction.followup.send(f"🔮 {result}")


import os

async def setup(bot):
    await bot.add_cog(Fun(bot))
