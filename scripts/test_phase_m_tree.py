#!/usr/bin/env python3
"""scripts/test_phase_m_tree.py — full-tree load check for PHASE M.

Loads EVERY active cog (the main.py loader semantics) into a real
discord.py tree, verifies:
  * all cogs load (47 expected after PHASE O added cogs/boosters.py)
  * /setup exists with manage_guild gating
  * /help still registers (the cog was edited)
  * root command count sanity (74 expected after PHASE O /boosters)
  * help.py home embed renders with and without SUPPORT_SERVER_URL
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")


async def main():
    import discord
    from discord.ext import commands

    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    cogs_dir = "cogs"
    loaded = 0
    failed = []
    for filename in sorted(os.listdir(cogs_dir)):
        if (filename.endswith(".py")
                and not filename.endswith("_disabled.py")
                and filename != "__init__.py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                loaded += 1
            except Exception as e:
                failed.append((filename, f"{type(e).__name__}: {e}"))
    check(f"all cogs load ({loaded})", loaded >= 47 and not failed,
          f"failed: {failed}")
    check("booster cog counted", loaded == 47, f"got {loaded}")

    cmds = {c.name: c for c in bot.tree.get_commands()}
    check("/setup in tree", "setup" in cmds)
    check("/help in tree", "help" in cmds)
    check("/boosters in tree (PHASE O)", "boosters" in cmds)
    boosters_group = cmds.get("boosters")
    check("/boosters has exactly 4 subcommands",
          boosters_group is not None
          and len(getattr(boosters_group, "commands", [])) == 4,
          f"got {len(getattr(boosters_group, 'commands', []))}")
    # cogs-only tree: main.py's 3 hybrid roots (ping/uptime/botinfo) are
    # NOT loaded here, so 71 here + 3 = 74 canonical top-level
    check("root count is 71 in the cogs-only tree (74 canonical with "
          "main.py hybrids)", len(cmds) == 71, f"got {len(cmds)}")

    # /setup permission gating
    sp = cmds.get("setup")
    check("/setup default_permissions manage_guild",
          sp and sp.default_permissions and sp.default_permissions.manage_guild)

    # help.py home embed with + without support url
    from cogs.help import HelpView
    from cogs import help as help_mod
    view = HelpView(bot, 1)
    e1 = view.build_home_embed()
    base_desc = e1.description
    help_mod.SUPPORT_SERVER_URL = "https://discord.gg/test"
    e2 = view.build_home_embed()
    check("help footer/desc gains support link when env set",
          "support server" in e2.description
          and "discord.gg/test" in e2.description)
    help_mod.SUPPORT_SERVER_URL = ""
    e3 = view.build_home_embed()
    check("help desc identical when env unset (old behavior)",
          e3.description == base_desc)

    await bot.close()
    print(f"\n{PASS} passed · {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
