"""
cogs/marriage.py — marriage system.

Spec (ADD 8):
  Data stored in data/marriages.json per user:
    { "married_to": null, "married_since": "iso", "times_divorced": 0,
      "last_proposal_at": "iso", "last_rejection_at": "iso" }

  /marry @user — propose to a user
    - Target gets a button prompt: Accept / Decline
    - 60 second timeout on the prompt
    - If accepted: store the marriage, announce it with a ❤️ embed
    - Cooldown: cannot propose again for 24 hours after a rejection
  /divorce — end your current marriage
    - Confirmation button required
    - Removes marriage from both users
  /marriage @user — check if a user is married and to whom
  /marry_status — check your own marriage status

  Rules:
    - Can only be married to one person at a time
    - Must divorce before remarrying
    - Bots cannot be married
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from utils.database import Database


class ProposalView(discord.ui.View):
    """Accept/Decline buttons for a marriage proposal."""

    def __init__(self, proposer: discord.Member, target: discord.Member, cog: "Marriage"):
        super().__init__(timeout=60)
        self.proposer = proposer
        self.target = target
        self.cog = cog
        self.decided = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(
                "this proposal isn't for you.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Accept", emoji="❤️", style=discord.ButtonStyle.success, row=0)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.decided = True
        for child in self.children:
            child.disabled = True
        await self.cog._accept_proposal(interaction, self.proposer, self.target, self)

    @discord.ui.button(label="Decline", emoji="💔", style=discord.ButtonStyle.danger, row=0)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.decided = True
        for child in self.children:
            child.disabled = True
        await self.cog._decline_proposal(interaction, self.proposer, self.target, self)

    async def on_timeout(self):
        # Disable buttons after 60s
        for child in self.children:
            child.disabled = True
        if not self.decided and hasattr(self, 'message'):
            try:
                await self.message.edit(
                    content=None,
                    embed=discord.Embed(
                        description=f"{self.target.mention} didn't respond. proposal expired.",
                        color=0x1a1a2e
                    ),
                    view=self
                )
            except Exception:
                pass


class DivorceConfirmView(discord.ui.View):
    """Confirm/Cancel buttons for a divorce."""

    def __init__(self, user: discord.Member):
        super().__init__(timeout=30)
        self.user = user
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "this isn't your divorce.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirm Divorce", emoji="💔", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class Marriage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/marriages.json')
        # In-memory pending proposals: proposer_id -> target_id
        self.pending: dict = {}

    def get_user(self, user_id: int) -> dict:
        return self.db.get(str(user_id), {
            'married_to': None,
            'married_since': None,
            'times_divorced': 0,
            'last_proposal_at': None,
            'last_rejection_at': None,
        })

    def save_user(self, user_id: int, data: dict):
        self.db.set(str(user_id), data)

    def is_married(self, user_id: int) -> bool:
        return self.get_user(user_id).get('married_to') is not None

    # ==================== Commands ====================

    @app_commands.command(name="marry", description="Propose to someone")
    async def marry(self, interaction: discord.Interaction, user: discord.Member):
        self.bot.increment_command('marry')
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "you can't marry yourself. that's not how this works.",
                ephemeral=True
            )
            return
        if user.bot:
            await interaction.response.send_message(
                "bots don't do relationships. we've discussed this.",
                ephemeral=True
            )
            return

        proposer_data = self.get_user(interaction.user.id)
        target_data = self.get_user(user.id)

        if proposer_data.get('married_to'):
            await interaction.response.send_message(
                "you're already married. sort that out first.",
                ephemeral=True
            )
            return
        if target_data.get('married_to'):
            await interaction.response.send_message(
                f"{user.display_name} is already taken.",
                ephemeral=True
            )
            return

        # 24h cooldown after a rejection
        if proposer_data.get('last_rejection_at'):
            try:
                last_rej = datetime.fromisoformat(proposer_data['last_rejection_at'])
                if datetime.utcnow() - last_rej < timedelta(hours=24):
                    remaining = timedelta(hours=24) - (datetime.utcnow() - last_rej)
                    h = remaining.seconds // 3600
                    m = (remaining.seconds % 3600) // 60
                    await interaction.response.send_message(
                        f"you were rejected recently. wait {h}h {m}m before proposing again.",
                        ephemeral=True
                    )
                    return
            except Exception:
                pass

        if interaction.user.id in self.pending:
            await interaction.response.send_message(
                "you already have a pending proposal. wait for a response.",
                ephemeral=True
            )
            return

        self.pending[interaction.user.id] = user.id

        embed = discord.Embed(
            title="💍 Marriage Proposal",
            description=(
                f"{interaction.user.mention} is proposing to {user.mention}!\n\n"
                f"{user.mention}, click **Accept** or **Decline** within 60 seconds."
            ),
            color=discord.Color.pink()
        )
        if interaction.user.avatar:
            embed.set_thumbnail(url=interaction.user.avatar.url)

        view = ProposalView(interaction.user, user, self)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

        proposer_data['last_proposal_at'] = datetime.utcnow().isoformat()
        self.save_user(interaction.user.id, proposer_data)

    async def _accept_proposal(self, interaction, proposer, target, view):
        try:
            await interaction.response.edit_message(view=view)
        except Exception:
            pass

        now = datetime.utcnow().isoformat()
        proposer_data = self.get_user(proposer.id)
        target_data = self.get_user(target.id)

        proposer_data['married_to'] = str(target.id)
        proposer_data['married_since'] = now
        target_data['married_to'] = str(proposer.id)
        target_data['married_since'] = now

        self.save_user(proposer.id, proposer_data)
        self.save_user(target.id, target_data)

        embed = discord.Embed(
            title="❤️ Married!",
            description=f"{proposer.mention} and {target.mention} are now married!",
            color=discord.Color.pink()
        )
        embed.set_footer(text="congrats. or condolences. depends.")
        await interaction.channel.send(embed=embed)

        self.pending.pop(proposer.id, None)

    async def _decline_proposal(self, interaction, proposer, target, view):
        try:
            await interaction.response.edit_message(view=view)
        except Exception:
            pass

        proposer_data = self.get_user(proposer.id)
        proposer_data['last_rejection_at'] = datetime.utcnow().isoformat()
        self.save_user(proposer.id, proposer_data)

        embed = discord.Embed(
            description=f"💔 {target.mention} declined {proposer.mention}'s proposal. rough.",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed)

        self.pending.pop(proposer.id, None)

    @app_commands.command(name="divorce", description="End your current marriage")
    async def divorce(self, interaction: discord.Interaction):
        self.bot.increment_command('divorce')
        data = self.get_user(interaction.user.id)
        if not data.get('married_to'):
            await interaction.response.send_message(
                "you're not married. nothing to end.", ephemeral=True
            )
            return

        view = DivorceConfirmView(interaction.user)
        await interaction.response.send_message(
            embed=discord.Embed(
                description="are you sure you want to divorce? click **Confirm Divorce** within 30 seconds.",
                color=discord.Color.red()
            ),
            view=view
        )
        view.message = await interaction.original_response()
        await view.wait()

        if not view.confirmed:
            try:
                await interaction.followup.send("divorce cancelled.", ephemeral=True)
            except Exception:
                pass
            return

        spouse_id_str = data.get('married_to')
        try:
            spouse_id = int(spouse_id_str)
        except (TypeError, ValueError):
            spouse_id = None

        data['married_to'] = None
        data['married_since'] = None
        data['times_divorced'] = data.get('times_divorced', 0) + 1
        self.save_user(interaction.user.id, data)

        if spouse_id:
            spouse_data = self.get_user(spouse_id)
            spouse_data['married_to'] = None
            spouse_data['married_since'] = None
            spouse_data['times_divorced'] = spouse_data.get('times_divorced', 0) + 1
            self.save_user(spouse_id, spouse_data)

        try:
            spouse = await self.bot.fetch_user(spouse_id) if spouse_id else None
            spouse_name = spouse.mention if spouse else "your ex"
        except Exception:
            spouse_name = "your ex"

        embed = discord.Embed(
            description=f"💔 {interaction.user.mention} divorced {spouse_name}.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="marriage", description="Check if a user is married and to whom")
    async def marriage(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('marriage')
        target = user or interaction.user
        data = self.get_user(target.id)

        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(
            name=target.display_name,
            icon_url=target.avatar.url if target.avatar else None
        )

        if data.get('married_to'):
            try:
                spouse = await self.bot.fetch_user(int(data['married_to']))
                spouse_name = spouse.mention
            except Exception:
                spouse_name = "unknown"
            try:
                since = datetime.fromisoformat(data['married_since'])
                days = (datetime.utcnow() - since).days
            except Exception:
                days = 0
            embed.add_field(name="married to", value=spouse_name, inline=True)
            embed.add_field(name="for", value=f"{days} days", inline=True)
        else:
            embed.description = "not married."

        if data.get('times_divorced', 0) > 0:
            embed.set_footer(text=f"divorced {data['times_divorced']} time(s)")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="marry_status", description="Check your own marriage status")
    async def marry_status(self, interaction: discord.Interaction):
        self.bot.increment_command('marry_status')
        # Delegate to /marriage logic
        data = self.get_user(interaction.user.id)
        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        if data.get('married_to'):
            try:
                spouse = await self.bot.fetch_user(int(data['married_to']))
                spouse_name = spouse.mention
            except Exception:
                spouse_name = "unknown"
            try:
                since = datetime.fromisoformat(data['married_since'])
                days = (datetime.utcnow() - since).days
            except Exception:
                days = 0
            embed.add_field(name="married to", value=spouse_name, inline=True)
            embed.add_field(name="for", value=f"{days} days", inline=True)
        else:
            embed.description = "not married."
        if data.get('times_divorced', 0) > 0:
            embed.set_footer(text=f"divorced {data['times_divorced']} time(s)")
        await interaction.response.send_message(embed=embed)

    # ==================== Legacy commands (kept for backward compat) ====================

    @app_commands.command(name="spouse", description="Check your or someone's marriage status (legacy)")
    async def spouse(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('spouse')
        target = user or interaction.user
        data = self.get_user(target.id)
        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(
            name=target.display_name,
            icon_url=target.avatar.url if target.avatar else None
        )
        if data.get('married_to'):
            try:
                spouse = await self.bot.fetch_user(int(data['married_to']))
                spouse_name = spouse.mention
            except Exception:
                spouse_name = "unknown"
            try:
                since = datetime.fromisoformat(data['married_since'])
                days = (datetime.utcnow() - since).days
            except Exception:
                days = 0
            embed.add_field(name="married to", value=spouse_name, inline=True)
            embed.add_field(name="for", value=f"{days} days", inline=True)
        else:
            embed.description = "not married."
        if data.get('times_divorced', 0) > 0:
            embed.set_footer(text=f"divorced {data['times_divorced']} time(s)")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Marriage(bot))
