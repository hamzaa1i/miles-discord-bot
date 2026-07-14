"""
cogs/marriage.py — marriage system with proposals, divorce, and economy bonus.

Data in data/marriages.json:
    {"user_id": {"partner_id": null, "married_at": null, "proposals_sent": [], "proposals_received": [], "last_proposal_time": null}}
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import time
from utils.database import Database


class ProposalView(discord.ui.View):
    def __init__(self, proposer: discord.Member, target: discord.Member, cog):
        super().__init__(timeout=300)  # 5 minutes
        self.proposer = proposer
        self.target = target
        self.cog = cog
        self.decided = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            try:
                await interaction.response.send_message("this isn't your proposal.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return False
        return True

    @discord.ui.button(label="Accept", emoji="✅", style=discord.ButtonStyle.success, row=0)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.decided = True
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        await self.cog._accept_proposal(interaction, self.proposer, self.target)

    @discord.ui.button(label="Decline", emoji="❌", style=discord.ButtonStyle.danger, row=0)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.decided = True
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        await self.cog._decline_proposal(interaction, self.proposer, self.target)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if not self.decided and hasattr(self, 'message'):
            try:
                await self.message.edit(
                    embed=discord.Embed(description=f"proposal from {self.proposer.mention} to {self.target.mention} expired.", color=0x1a1a2e),
                    view=self
                )
            except Exception:
                pass


class DivorceConfirmView(discord.ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=30)
        self.user = user
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            try:
                await interaction.response.send_message("this isn't your divorce.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return False
        return True

    @discord.ui.button(label="Yes, divorce", emoji="💔", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        self.stop()

    @discord.ui.button(label="No, keep it", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        self.stop()


class Marriage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/marriages.json')

    def get_user(self, user_id: int) -> dict:
        return self.db.get(str(user_id), {
            'partner_id': None,
            'married_at': None,
            'proposals_sent': [],
            'proposals_received': [],
            'last_proposal_time': None,
        })

    def save_user(self, user_id: int, data: dict):
        self.db.set(str(user_id), data)

    @app_commands.command(name="marry", description="Propose to someone")
    async def marry(self, interaction: discord.Interaction, user: discord.Member):
        self.bot.increment_command('marry')
        if user.id == interaction.user.id:
            await interaction.response.send_message("can't marry yourself.", ephemeral=True)
            return
        if user.id == interaction.client.user.id:
            await interaction.response.send_message("can't marry me. i'm taken.", ephemeral=True)
            return

        proposer_data = self.get_user(interaction.user.id)
        target_data = self.get_user(user.id)

        if proposer_data.get('partner_id'):
            await interaction.response.send_message("you're already married. divorce first.", ephemeral=True)
            return
        if target_data.get('partner_id'):
            await interaction.response.send_message(f"{user.mention} is already married.", ephemeral=True)
            return

        # Check 30 min cooldown after rejection
        if proposer_data.get('last_proposal_time'):
            elapsed = time.time() - float(proposer_data['last_proposal_time'])
            if elapsed < 1800:  # 30 min
                remaining = int(1800 - elapsed)
                await interaction.response.send_message(f"you were rejected recently. wait {remaining // 60}m {remaining % 60}s.", ephemeral=True)
                return

        # Check pending proposal
        if str(user.id) in proposer_data.get('proposals_sent', []):
            await interaction.response.send_message("you already have a pending proposal to them.", ephemeral=True)
            return

        await interaction.response.defer()

        # Record proposal
        proposer_data.setdefault('proposals_sent', []).append(str(user.id))
        proposer_data['last_proposal_time'] = str(time.time())
        self.save_user(interaction.user.id, proposer_data)

        target_data.setdefault('proposals_received', []).append(str(interaction.user.id))
        self.save_user(user.id, target_data)

        embed = discord.Embed(
            title="💍 Marriage Proposal",
            description=f"{interaction.user.mention} is proposing to {user.mention}!\n\n{user.mention}, click **Accept** or **Decline** within 5 minutes.",
            color=discord.Color.pink()
        )
        if interaction.user.avatar:
            embed.set_thumbnail(url=interaction.user.avatar.url)

        view = ProposalView(interaction.user, user, self)
        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response() if not interaction.is_followup() else None

    async def _accept_proposal(self, interaction, proposer, target):
        proposer_data = self.get_user(proposer.id)
        target_data = self.get_user(target.id)

        if proposer_data.get('partner_id') or target_data.get('partner_id'):
            await interaction.followup.send("someone is already married.", ephemeral=True)
            return

        now = datetime.utcnow().isoformat()
        proposer_data['partner_id'] = str(target.id)
        proposer_data['married_at'] = now
        target_data['partner_id'] = str(proposer.id)
        target_data['married_at'] = now

        # Remove from pending proposals
        if str(target.id) in proposer_data.get('proposals_sent', []):
            proposer_data['proposals_sent'].remove(str(target.id))
        if str(proposer.id) in target_data.get('proposals_received', []):
            target_data['proposals_received'].remove(str(proposer.id))

        self.save_user(proposer.id, proposer_data)
        self.save_user(target.id, target_data)

        embed = discord.Embed(
            title="❤️ Married!",
            description=f"{proposer.mention} and {target.mention} are now married!",
            color=discord.Color.pink()
        )
        embed.set_footer(text="congrats. or condolences.")
        await interaction.followup.send(embed=embed)

    async def _decline_proposal(self, interaction, proposer, target):
        proposer_data = self.get_user(proposer.id)
        target_data = self.get_user(target.id)

        if str(target.id) in proposer_data.get('proposals_sent', []):
            proposer_data['proposals_sent'].remove(str(target.id))
        if str(proposer.id) in target_data.get('proposals_received', []):
            target_data['proposals_received'].remove(str(proposer.id))

        proposer_data['last_proposal_time'] = str(time.time())
        self.save_user(proposer.id, proposer_data)
        self.save_user(target.id, target_data)

        embed = discord.Embed(
            description=f"💔 {target.mention} declined {proposer.mention}'s proposal. 30 min cooldown.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="divorce", description="End your marriage")
    async def divorce(self, interaction: discord.Interaction):
        self.bot.increment_command('divorce')
        data = self.get_user(interaction.user.id)
        if not data.get('partner_id'):
            await interaction.response.send_message("you're not married.", ephemeral=True)
            return

        partner_id = int(data['partner_id'])
        try:
            partner = await self.bot.fetch_user(partner_id)
            partner_name = partner.mention
        except Exception:
            partner_name = "your ex"

        view = DivorceConfirmView(interaction.user)
        embed = discord.Embed(
            description=f"are you sure you want to divorce {partner_name}?",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        await view.wait()

        if not view.confirmed:
            try:
                await interaction.followup.send("divorce cancelled.", ephemeral=True)
            except Exception:
                pass
            return

        # Remove marriage
        data['partner_id'] = None
        data['married_at'] = None
        self.save_user(interaction.user.id, data)

        partner_data = self.get_user(partner_id)
        partner_data['partner_id'] = None
        partner_data['married_at'] = None
        self.save_user(partner_id, partner_data)

        embed = discord.Embed(
            description=f"💔 {interaction.user.mention} divorced {partner_name}.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

        # DM the ex
        try:
            await partner.send(f"you got divorced by {interaction.user.mention}.")
        except Exception:
            pass

    proposal = app_commands.Group(name="proposal", description="Proposal management")

    @proposal.command(name="cancel", description="Cancel your outgoing proposal")
    async def proposal_cancel(self, interaction: discord.Interaction):
        self.bot.increment_command('proposal_cancel')
        data = self.get_user(interaction.user.id)
        sent = data.get('proposals_sent', [])
        if not sent:
            await interaction.response.send_message("you have no pending proposals.", ephemeral=True)
            return
        # Cancel the most recent
        target_id = sent[-1]
        data['proposals_sent'] = sent[:-1]
        self.save_user(interaction.user.id, data)
        # Remove from target's received
        target_data = self.get_user(int(target_id))
        if str(interaction.user.id) in target_data.get('proposals_received', []):
            target_data['proposals_received'].remove(str(interaction.user.id))
            self.save_user(int(target_id), target_data)
        await interaction.response.send_message("✅ proposal cancelled.")

    @proposal.command(name="list", description="Show all pending proposals you've received")
    async def proposal_list(self, interaction: discord.Interaction):
        self.bot.increment_command('proposal_list')
        data = self.get_user(interaction.user.id)
        received = data.get('proposals_received', [])
        if not received:
            await interaction.response.send_message("no pending proposals.", ephemeral=True)
            return
        embed = discord.Embed(title="💌 Pending Propals", color=discord.Color.pink())
        for uid in received[:10]:
            try:
                user = await self.bot.fetch_user(int(uid))
                name = user.mention
            except Exception:
                name = f"User {uid}"
            embed.add_field(name="Proposal from", value=name, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="marriage", description="Check marriage status")
    async def marriage(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('marriage')
        await interaction.response.defer()
        target = user or interaction.user
        data = self.get_user(target.id)
        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(name=target.display_name, icon_url=target.avatar.url if target.avatar else None)
        if data.get('partner_id'):
            try:
                partner = await self.bot.fetch_user(int(data['partner_id']))
                partner_name = partner.mention
            except Exception:
                partner_name = "unknown"
            try:
                since = datetime.fromisoformat(data['married_at'])
                days = (datetime.utcnow() - since).days
            except Exception:
                days = 0
            embed.add_field(name="married to", value=partner_name, inline=True)
            embed.add_field(name="for", value=f"{days} days", inline=True)
        else:
            embed.description = "not married. living the free life."
        await interaction.followup.send(embed=embed)



async def setup(bot):
    await bot.add_cog(Marriage(bot))
