"""Count all slash commands across active cogs.

For each cog, count:
- top-level @app_commands.command() → 1 each
- app_commands.Group() → 1 per group + 1 per subcommand (Discord counts
  the group itself only if it has subcommands; subcommands count individually)

Total = sum of (1 for each standalone command + 1 for each subcommand)
Groups themselves don't count against the 100-limit; their subcommands do.
"""
import os
import re

COGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cogs")
COGS_DIR = os.path.abspath(COGS_DIR)

# (cog_filename, [commands])
results = []
grand_total = 0

for filename in sorted(os.listdir(COGS_DIR)):
    if not filename.endswith(".py"):
        continue
    if filename.endswith("_disabled.py"):
        continue
    if filename == "__init__.py":
        continue
    path = os.path.join(COGS_DIR, filename)
    with open(path, "r") as f:
        src = f.read()

    # Find all groups: name="groupname"
    groups = re.findall(r'app_commands\.Group\(\s*name="([^"]+)"', src)

    # Find all subcommands of groups: @<varname>.command(name="...")
    # IMPORTANT: must NOT match "@app_commands.command" (which is top-level).
    # The variable name (e.g. "mod", "poll", "owner") is lowercase; the
    # module path "app_commands" contains an underscore.
    subcommands = re.findall(r'@([a-zA-Z_]\w*)\.command\(\s*name="([^"]+)"', src)
    # Filter: only keep those whose variable name is NOT "app_commands"
    subcommands = [name for var, name in subcommands if var != "app_commands"]

    # Find all top-level commands: @app_commands.command(name="...")
    top_level = re.findall(r'@app_commands\.command\(\s*name="([^"]+)"', src)

    count = len(top_level) + len(subcommands)
    results.append((filename, top_level, subcommands, groups, count))
    grand_total += count

print(f"\n{'='*70}")
print(f"SLASH COMMAND COUNT BY COG (active cogs only)")
print(f"{'='*70}")
print(f"{'Cog':<28} {'Top':<5} {'Sub':<5} {'Total':<6}")
print(f"{'-'*28} {'-'*5} {'-'*5} {'-'*6}")
for filename, top, sub, groups, count in results:
    print(f"{filename:<28} {len(top):<5} {len(sub):<5} {count:<6}")
print(f"{'-'*28} {'-'*5} {'-'*5} {'-'*6}")
print(f"{'TOTAL (cogs)':<28} {'':<5} {'':<5} {grand_total:<6}")

# Add main.py commands (hybrid commands count as slash commands too)
main_path = os.path.join(os.path.dirname(COGS_DIR), "main.py")
with open(main_path, "r") as f:
    main_src = f.read()
main_hybrid = re.findall(r'@bot\.hybrid_command\(\s*name="([^"]+)"', main_src)
print(f"\nmain.py hybrid commands: {len(main_hybrid)} → {main_hybrid}")
grand_total += len(main_hybrid)
print(f"\nGRAND TOTAL (cogs + main.py): {grand_total}")
print(f"Discord limit: 100")
print(f"Status: {'UNDER LIMIT' if grand_total < 100 else 'AT OR OVER LIMIT'}")
