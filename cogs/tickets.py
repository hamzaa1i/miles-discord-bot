import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.database import Database

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.secondary,
        emoji="🎫",
        custom_id="open_ticket"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        from utils.database import Database
        db = Database('data/tickets.json')
        config = db.get(str(interaction.guild.id), {})

        # Check if user already has open ticket
        existing = discord.utils.get(
            interaction.guild.channels,
            name=f"ticket-{interaction.user.name.lower()}"
        )
        if existing:
            await interaction.followup.send(
                f"you already have an open ticket: {existing.mention}",
                ephemeral=True
            )
            return

        category_id = config.get('category_id')
        category = None
        if category_id:
            category = interaction.guild.get_channel(int(category_id))

        # Get staff role
        staff_role_id = config.get('staff_role_id')
        staff_role = None
        if staff_role_id:
            staff_role = interaction.guild.get_role(int(staff_role_id))

        # Create ticket channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            ),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True
            )
        }

        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            )

        try:
            channel = await interaction.guild.create_text_channel(
                name=f"ticket-{interaction.user.name}",
                category=category,
                overwrites=overwrites,
                topic=f"Ticket by {interaction.user} | ID: {interaction.user.id}"
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "i don't have permission to create channels.",
                ephemeral=True
            )
            return

        # Save ticket
        tickets = config.get('tickets', {})
        tickets[str(channel.id)] = {
            'user_id': str(interaction.user.id),
            'opened_at': datetime.utcnow().isoformat(),
            'status': 'open'
        }
        config['tickets'] = tickets
        db.set(str(interaction.guild.id), config)

        # Send welcome message in ticket
        embed = discord.Embed(
            title="Support Ticket",
            description=(
                f"hey {interaction.user.mention}, what do you need help with?\n\n"
                f"staff will be here soon."
            ),
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Ticket by {interaction.user}")

        close_view = CloseTicketView()
        await channel.send(
            content=f"{interaction.user.mention}" + (f" {staff_role.mention}" if staff_role else ""),
            embed=embed,
            view=close_view
        )

        await interaction.followup.send(
            f"ticket opened: {channel.mention}",
            ephemeral=True
        )


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        embed = discord.Embed(
            description="closing ticket in 5 seconds...",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

        import asyncio
        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except:
            pass


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/tickets.json')
        bot.add_view(TicketView())
        bot.add_view(CloseTicketView())

    @app_commands.command(name="ticket_setup", description="Setup the ticket system")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        staff_role: discord.Role = None,
        category: discord.CategoryChannel = None
    ):
        config = self.db.get(str(interaction.guild.id), {})
        config['staff_role_id'] = str(staff_role.id) if staff_role else None
        config['category_id'] = str(category.id) if category else None
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            title="Support",
            description=(
                "click the button below to open a support ticket.\n"
                "a private channel will be created for you."
            ),
            color=0x1a1a2e
        )

        await channel.send(embed=embed, view=TicketView())

        confirm = discord.Embed(
            description=f"ticket system set up in {channel.mention}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)

    @app_commands.command(name="ticket_close", description="Close a ticket channel")
    async def ticket_close(self, interaction: discord.Interaction):
        if 'ticket-' not in interaction.channel.name:
            await interaction.response.send_message(
                "this isn't a ticket channel.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            description=f"closed by {interaction.user.mention}. deleting in 5s.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

        import asyncio
        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )
        except:
            pass

async def setup(bot):
    await bot.add_cog(Tickets(bot))