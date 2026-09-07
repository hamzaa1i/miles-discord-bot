"""
utils/command_counts.py — PHASE N.1 / PART 12 canonical command counting.

ONE definition of "how many commands does aurelia ship", used by:
  * main.py startup logs (cogs / top-level / total invokable paths)
  * /botinfo system card
  * the public /api/stats payload (landing + docs surfaces)
  * regression tests (scripts/test_phase_n1.py)

Counting semantics (matching Discord's model):
  top_level       every root entry in the command tree — standalone
                  commands AND groups (hybrid slash commands included).
                  This is the number against Discord's 100-per-guild
                  top-level limit.
  groups          root entries that own subcommands (not invokable by
                  themselves).
  standalone      root entries directly invokable.
  subcommands     child commands of groups (each its own invokable path).
  total_invokable standalone + subcommands = every slash path a user can
                  type. The group containers themselves are not counted.
  hybrid          hybrid commands usable via BOTH slash and text prefix
                  (reported separately; they are top_level too).

Static verification (no Discord connection required) parses the cogs/
directory + main.py the same way the live tree is built, so tests can
assert 73/169 without booting the bot. Runtime counting walks the real
`bot.tree` — the two must agree (a mismatch means a decorator was
missed, and the test fails loudly).
"""
import os
import re

COGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "cogs")
MAIN_PY = os.path.join(COGS_DIR, "..", "main.py")

# Discord's hard limit on top-level application commands per guild.
DISCORD_TOP_LEVEL_LIMIT = 100


def count_commands_static() -> dict:
    """Parse cogs/*.py + main.py and count the command surface.

    Mirrors how the cogs actually register commands:
      @app_commands.command(name="x")       → standalone root
      app_commands.Group(name="g")          → group root (+ subcommands)
      @<groupvar>.command(name="sub")       → subcommand
      @bot.hybrid_command(name="x")         → hybrid root
    """
    cogs = 0
    standalone = 0
    groups = 0
    subcommands = 0
    hybrid = 0

    for filename in sorted(os.listdir(COGS_DIR)):
        if not filename.endswith(".py"):
            continue
        if filename.endswith("_disabled.py") or filename == "__init__.py":
            continue
        cogs += 1
        with open(os.path.join(COGS_DIR, filename), "r", encoding="utf-8") as f:
            src = f.read()
        standalone += len(
            re.findall(r'@app_commands\.command\(\s*name="', src))
        groups += len(
            re.findall(r'app_commands\.Group\(\s*name="', src))
        subcommands += len([
            1 for var, _ in re.findall(
                r'@([a-zA-Z_]\w*)\.command\(\s*name="([^"]+)"', src)
            if var != "app_commands"
        ])

    if os.path.exists(MAIN_PY):
        with open(MAIN_PY, "r", encoding="utf-8") as f:
            main_src = f.read()
        hybrid = len(re.findall(
            r'@bot\.hybrid_command\(\s*name="', main_src))

    top_level = standalone + groups + hybrid
    return {
        "cogs": cogs,
        "standalone": standalone,
        "groups": groups,
        "subcommands": subcommands,
        "hybrid": hybrid,
        "top_level": top_level,
        "total_invokable": standalone + hybrid + subcommands,
        "discord_top_level_limit": DISCORD_TOP_LEVEL_LIMIT,
        "top_level_headroom": DISCORD_TOP_LEVEL_LIMIT - top_level,
    }


def count_commands_runtime(bot) -> dict:
    """Walk the LIVE command tree (what Discord actually sees after
    sync). Same semantics as count_commands_static()."""
    tree_cmds = list(bot.tree.get_commands())
    standalone = 0
    groups = 0
    subcommands = 0
    hybrid = 0
    for cmd in tree_cmds:
        subs = getattr(cmd, "commands", None)
        if subs is not None:  # a Group (or hybrid root with subcommands)
            if len(subs) == 0:
                # empty group still occupies a top-level slot
                groups += 1
                continue
            groups += 1
            subcommands += len(subs)
        else:
            standalone += 1
            # hybrid slash commands also answer to the text prefix
            if getattr(cmd, "__discord_app_commands_is_hybrid__", False):
                hybrid += 1
    top_level = standalone + groups
    return {
        "cogs": len(bot.cogs),
        "standalone": standalone,
        "groups": groups,
        "subcommands": subcommands,
        "hybrid": hybrid,
        "top_level": top_level,
        "total_invokable": standalone + subcommands,
        "discord_top_level_limit": DISCORD_TOP_LEVEL_LIMIT,
        "top_level_headroom": DISCORD_TOP_LEVEL_LIMIT - top_level,
    }


def format_command_summary(counts: dict) -> str:
    """One-line canonical summary for startup logs and /botinfo."""
    return (
        f"{counts['cogs']} cogs · "
        f"{counts['top_level']} top-level commands/groups "
        f"({counts['groups']} groups) · "
        f"{counts['total_invokable']} total invokable paths"
    )
