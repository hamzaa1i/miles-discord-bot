"""
cogs/owner.py — owner-only bot management commands.

All commands check OWNER_ID env var. If the user is not the owner,
they get "not your command." and the command returns early.

Every command defers(ephemeral=True) and uses followup.send().

Commands:
  /owner status       — bot stats (servers, users, cogs, commands, uptime, memory)
  /owner reload [cog] — reload a specific cog by name
  /owner sync         — force re-sync slash commands to all guilds
  /owner shutdown     — shut down the bot gracefully
  /owner eval [code]  — execute Python code and return result
  /owner dm [user_id] [message] — send a DM to any user by ID
  /owner announce [message]     — send a message to the first text channel of every server
  /owner createrole [name] [color] [admin] — create a role
  /owner giverole [role] [member] — give a role to a member
  /owner removerole [role] [member] — remove a role from a member
  /owner allroles [member] — give all assignable roles to a member
  /owner servers — list all servers the bot is in
  /owner say [message] [channel] — send a message as the bot
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
import asyncio
import traceback
from datetime import datetime, timezone
import io
import contextlib


OWNER_ID = int(os.getenv('OWNER_ID', '0'))


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.now(timezone.utc)

    def _check_owner(self, interaction: discord.Interaction) -> bool:
        """Returns True if the user is the owner, else sends rejection."""
        if interaction.user.id != OWNER_ID:
            return False
        return True

    owner = app_commands.Group(name="owner", description="Owner-only bot management")

    @owner.command(name="status", description="Show bot statistics (owner only)")
    async def owner_status(self, interaction: discord.Interaction):
        self.bot.increment_command('owner_status')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_mb = process.memory_info().rss / (1024 * 1024)
            cpu_percent = process.cpu_percent(interval=0.1)
            mem_str = f"{mem_mb:.1f} MB"
            cpu_str = f"{cpu_percent:.1f}%"
        except ImportError:
            mem_str = "psutil not installed"
            cpu_str = "n/a"

        now = datetime.now(timezone.utc)
        uptime_delta = now - self.start_time
        uptime_str = f"{uptime_delta.days}d {uptime_delta.seconds // 3600}h {(uptime_delta.seconds % 3600) // 60}m"

        total_members = sum(g.member_count for g in self.bot.guilds)
        cmd_count = len(self.bot.tree.get_commands())

        embed = discord.Embed(
            title="📊 Bot Status",
            color=0x1a1a2e,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Users", value=f"{total_members:,}", inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Cogs", value=str(len(self.bot.cogs)), inline=True)
        embed.add_field(name="Commands", value=str(cmd_count), inline=True)
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Memory", value=mem_str, inline=True)
        embed.add_field(name="CPU", value=cpu_str, inline=True)
        embed.add_field(name="Python", value=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", inline=True)
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Bot ID: {self.bot.user.id if self.bot.user else 'unknown'}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @owner.command(name="reload", description="Reload a specific cog by name (owner only)")
    @app_commands.describe(cog_name="Name of the cog to reload (e.g. 'ai_chat')")
    async def owner_reload(self, interaction: discord.Interaction, cog_name: str):
        self.bot.increment_command('owner_reload')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        try:
            await self.bot.reload_extension(f"cogs.{cog_name}")
            await interaction.followup.send(f"✅ reloaded `cogs.{cog_name}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ failed: `{e}`", ephemeral=True)

    @owner.command(name="sync", description="Force re-sync slash commands to all guilds (owner only)")
    async def owner_sync(self, interaction: discord.Interaction):
        self.bot.increment_command('owner_sync')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        results = []
        for guild in self.bot.guilds:
            try:
                self.bot.tree.copy_global_to(guild=guild)
                synced = await self.bot.tree.sync(guild=guild)
                results.append(f"✅ {guild.name}: {len(synced)} commands")
            except Exception as e:
                results.append(f"❌ {guild.name}: {e}")

        # Send in chunks if too long
        text = "\n".join(results)
        if len(text) > 1900:
            for i in range(0, len(text), 1900):
                await interaction.followup.send(text[i:i+1900], ephemeral=True)
        else:
            await interaction.followup.send(text, ephemeral=True)

    @owner.command(name="shutdown", description="Shut down the bot gracefully (owner only)")
    async def owner_shutdown(self, interaction: discord.Interaction):
        self.bot.increment_command('owner_shutdown')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        await interaction.followup.send(" shutting down...", ephemeral=True)
        print(f"[SHUTDOWN] requested by {interaction.user} ({interaction.user.id})")

        # Give the response time to send
        await asyncio.sleep(1)
        await self.bot.close()

    @owner.command(name="eval", description="Execute Python code and return result (owner only)")
    @app_commands.describe(code="Python code to execute")
    async def owner_eval(self, interaction: discord.Interaction, code: str):
        self.bot.increment_command('owner_eval')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        # Capture stdout/stderr
        stdout_capture = io.StringIO()
        result = None
        error = None

        # Build a safe-ish eval environment
        env = {
            'bot': self.bot,
            'interaction': interaction,
            'discord': discord,
            'os': os,
            'sys': sys,
            'asyncio': asyncio,
            'len': len,
            'str': str,
            'int': int,
            'list': list,
            'dict': dict,
            'print': print,
        }

        try:
            # Try exec first (for statements), then eval (for expressions)
            with contextlib.redirect_stdout(stdout_capture):
                try:
                    # Wrap in async function to allow await
                    exec_code = code.strip()
                    if exec_code.startswith('```'):
                        # Strip code fences
                        lines = exec_code.split('\n')
                        exec_code = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

                    # Check if it's an expression (single line) or statements
                    try:
                        compiled = compile(exec_code, '<eval>', 'eval')
                        result = eval(compiled, env)
                        if asyncio.iscoroutine(result):
                            result = await result
                    except SyntaxError:
                        # It's statements, use exec
                        compiled = compile(exec_code, '<eval>', 'exec')
                        exec(compiled, env)
                        result = "(executed)"
                except Exception as e:
                    error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

        stdout_text = stdout_capture.getvalue()
        result_text = ""
        if stdout_text:
            result_text += f"```\n{stdout_text[:1500]}\n```\n"
        if result is not None and result != "(executed)":
            result_text += f"**Result:** `{str(result)[:500]}`"
        if error:
            result_text += f"\n**Error:**\n```\n{error[:1500]}\n```"
        if not result_text:
            result_text = "(no output)"

        await interaction.followup.send(result_text, ephemeral=True)

    @owner.command(name="dm", description="Send a DM to any user by ID (owner only)")
    @app_commands.describe(user_id="The user ID to DM", message="The message to send")
    async def owner_dm(self, interaction: discord.Interaction, user_id: str, message: str):
        self.bot.increment_command('owner_dm')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        try:
            user_id_int = int(user_id)
        except ValueError:
            await interaction.followup.send("invalid user ID.", ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(user_id_int)
            embed = discord.Embed(
                description=message,
                color=0x1a1a2e,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"from the bot owner")
            await user.send(embed=embed)
            await interaction.followup.send(f"✅ sent to {user} ({user.id})", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("user not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("can't DM that user (DMs closed).", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @owner.command(name="announce", description="Send a message to the first text channel of every server (owner only)")
    @app_commands.describe(message="The announcement to send")
    async def owner_announce(self, interaction: discord.Interaction, message: str):
        self.bot.increment_command('owner_announce')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        success = 0
        fail = 0
        for guild in self.bot.guilds:
            try:
                # Find the first text channel where we can send
                channel = None
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break
                if not channel:
                    fail += 1
                    continue
                embed = discord.Embed(
                    title="📢 Announcement",
                    description=message,
                    color=0xfee75c,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text=f"cyn • bot owner announcement")
                await channel.send(embed=embed)
                success += 1
            except Exception:
                fail += 1

        await interaction.followup.send(
            f"announced to {success} servers. {fail} failed.",
            ephemeral=True
        )

    @owner.command(name="createrole", description="Create a role (owner only)")
    @app_commands.describe(
        name="Role name",
        color="Hex color (e.g. ff0000 or #ff0000)",
        admin="Give administrator permission"
    )
    async def owner_createrole(
        self,
        interaction: discord.Interaction,
        name: str,
        color: str = "000000",
        admin: bool = False
    ):
        self.bot.increment_command('owner_createrole')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        if not interaction.guild:
            await interaction.followup.send("this command only works in a server.", ephemeral=True)
            return

        try:
            c = discord.Color(int(color.replace('#', ''), 16))
        except Exception:
            c = discord.Color.default()

        perms = discord.Permissions.all() if admin else discord.Permissions()
        try:
            role = await interaction.guild.create_role(
                name=name, color=c, permissions=perms, reason="Owner command"
            )
            # Move role just below bot's top role
            pos = interaction.guild.me.top_role.position
            await role.edit(position=pos - 1)
            await interaction.user.add_roles(role, reason="Owner command")
            await interaction.followup.send(
                f"✅ created {role.mention} (admin={admin})",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission to create roles.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @owner.command(name="giverole", description="Give a role to a member (owner only)")
    @app_commands.describe(role="Role to give", member="Member to give the role to (defaults to you)")
    async def owner_giverole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        member: discord.Member = None
    ):
        self.bot.increment_command('owner_giverole')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        target = member or interaction.user
        try:
            await target.add_roles(role, reason="Owner command")
            await interaction.followup.send(
                f"✅ gave {role.mention} to {target.mention}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission.", ephemeral=True)

    @owner.command(name="removerole", description="Remove a role from a member (owner only)")
    @app_commands.describe(role="Role to remove", member="Member to remove the role from (defaults to you)")
    async def owner_removerole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        member: discord.Member = None
    ):
        self.bot.increment_command('owner_removerole')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        target = member or interaction.user
        try:
            await target.remove_roles(role, reason="Owner command")
            await interaction.followup.send(
                f"✅ removed {role.mention} from {target.mention}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission.", ephemeral=True)

    @owner.command(name="allroles", description="Give all assignable roles to a member (owner only)")
    @app_commands.describe(member="Member to give all roles to (defaults to you)")
    async def owner_allroles(self, interaction: discord.Interaction, member: discord.Member = None):
        self.bot.increment_command('owner_allroles')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        if not interaction.guild:
            await interaction.followup.send("this command only works in a server.", ephemeral=True)
            return

        target = member or interaction.user
        roles = [
            r for r in interaction.guild.roles
            if r.name != "@everyone"
            and not r.managed
            and r.position < interaction.guild.me.top_role.position
        ]
        try:
            await target.add_roles(*roles, reason="Owner command")
            await interaction.followup.send(
                f"✅ gave {len(roles)} roles to {target.mention}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @owner.command(name="servers", description="List all servers the bot is in (owner only)")
    async def owner_servers(self, interaction: discord.Interaction):
        self.bot.increment_command('owner_servers')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"servers ({len(self.bot.guilds)})",
            color=0x1a1a2e,
            timestamp=datetime.now(timezone.utc)
        )
        for g in self.bot.guilds[:25]:
            embed.add_field(
                name=g.name,
                value=f"`{g.id}` · {g.member_count} members",
                inline=True
            )
        if len(self.bot.guilds) > 25:
            embed.set_footer(text=f"+ {len(self.bot.guilds) - 25} more")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @owner.command(name="say", description="Send a message as the bot (owner only)")
    @app_commands.describe(message="Message to send", channel="Channel to send to (defaults to current)")
    async def owner_say(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel = None
    ):
        self.bot.increment_command('owner_say')
        await interaction.response.defer(ephemeral=True)
        if not self._check_owner(interaction):
            await interaction.followup.send("not your command.", ephemeral=True)
            return

        target = channel or interaction.channel
        try:
            await target.send(message)
            await interaction.followup.send("✅ sent.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("can't send to that channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Owner(bot))
