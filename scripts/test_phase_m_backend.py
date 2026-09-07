#!/usr/bin/env python3
"""
scripts/test_phase_m_backend.py — PHASE M backend checks.

Validates (without a live Discord connection):
  1. cogs/setup_wizard.py loads into a real discord.py tree, /setup is
     manage_guild gated, the on_guild_join listener exists.
  2. utils/public_api.py registers on a Flask app; /api/public/stats,
     /api/changelog and /changelog.rss respond correctly with keep_alive
     + utils.db stubbed; rate limiting kicks in; the 60s cache works;
     history sampling writes the ring buffer.
  3. The changelog parser round-trips CHANGELOG.md (version / date /
     categories / highlights all present).
"""
import asyncio
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")


# ─── 1. cog load into a real tree ──────────────────────────────────
async def test_cog():
    import discord
    from discord.ext import commands

    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    from cogs.setup_wizard import SetupWizard, SetupWizardView, FEATURES
    await bot.add_cog(SetupWizard(bot))

    cog = bot.get_cog("SetupWizard")
    check("setup_wizard cog loads", cog is not None)

    tree_cmds = {c.name: c for c in bot.tree.get_commands()}
    check("/setup registered in tree", "setup" in tree_cmds)
    cmd = tree_cmds.get("setup")
    perms = getattr(cmd, "default_permissions", None)
    check("/setup gated manage_guild", perms is not None and
          perms.manage_guild)

    has_listener = any(l[0] == "on_guild_join"
                       for l in cog.__cog_listeners__)
    check("on_guild_join listener attached", has_listener)

    # feature defs sanity
    keys = {f.key for f in FEATURES}
    check("wizard covers the 8 spec features",
          {"welcome", "leveling", "logging", "ai", "qotd",
           "anniversary", "confessions", "daily"} <= keys,
          f"got {sorted(keys)}")
    tables = {f.table for f in FEATURES if f.table}
    check("wizard writes to existing settings tables",
          tables <= {"welcome_settings", "leveling_settings", "log_settings",
                     "proactive_settings", "qotd_settings",
                     "anniversary_settings", "confess_settings"},
          f"got {sorted(tables)}")

    # view state machine — walk a tiny synthetic flow
    guild = types.SimpleNamespace(id=1, get_channel=lambda cid: None)
    view = SetupWizardView(bot, guild, 42)
    check("wizard starts on the select step", view.step == "select")
    view.queue = [f for f in FEATURES if f.key in ("welcome", "daily")]
    view.index = 0
    view.step = "channel"  # welcome is first
    check("first queued step is the welcome channel picker",
          view._current_feature().key == "welcome")
    view._advance()
    check("advance moves to the informational daily step",
          view.step == "intro" and view._current_feature().key == "daily")
    view._advance()
    check("advance after last feature lands on summary",
          view.step == "summary")

    await bot.close()


# ─── 2. public api with stubs ──────────────────────────────────────
def test_public_api():
    import keep_alive
    import flask

    class FakeGuild:
        member_count = 100

        def __init__(self):
            self.id = 1

    class FakeBot:
        guilds = [FakeGuild()]
        latency = 0.05
        command_counts = {"level": 12, "daily": 9, "help": 30}

        def is_ready(self):
            return True

    keep_alive.bot_ref = FakeBot()
    from datetime import datetime
    keep_alive.start_time = datetime(2026, 9, 6)

    # stub utils.db BEFORE public_api imports it lazily
    import utils.db as db

    class FakeSB:
        class _Table:
            def __init__(self, table):
                self.table = table

            def select(self, *a, **k):
                if self.table == "command_usage":
                    # simulate the table being missing/unreachable so the
                    # in-memory fallback path is exercised
                    raise RuntimeError("relation does not exist")
                return self

            def eq(self, *a, **k):
                return self

            def gte(self, *a, **k):
                return self

            def execute(self):
                class R:
                    data = []
                    count = None
                return R()

        def table(self, name):
            return FakeSB._Table(name)

    db.get_supabase = lambda: FakeSB()

    from utils import public_api
    public_api._ALLOWED_ORIGINS.add("http://localhost:3000")

    # point history at a temp file
    import tempfile
    tmpdir = tempfile.mkdtemp()
    public_api.HISTORY_PATH = os.path.join(tmpdir, "history.json")
    public_api.HISTORY_DIR = tmpdir

    app = flask.Flask("t")
    public_api.init_public_api(app)
    public_api._sampler_started = False  # don't start the thread here

    client = app.test_client()

    r = client.get("/api/public/stats")
    body = r.get_json()
    check("GET /api/public/stats -> 200", r.status_code == 200)
    check("stats has servers", body.get("servers") == 1)
    check("stats has members", body.get("members") == 100)
    check("stats has version", body.get("version") == "1.0.0")
    check("stats has top_commands fallback",
          isinstance(body.get("top_commands"), list) and
          body["top_commands"][0]["command"] == "help")
    check("stats has fun_stats keys",
          set(body.get("fun_stats", {})) >= {"total_xp", "warnings_issued",
                                             "confessions_posted",
                                             "memories_stored",
                                             "daily_streaks_active"})
    check("stats has growth + latency_history arrays",
          isinstance(body.get("growth"), list) and
          isinstance(body.get("latency_history"), list))
    check("no user/guild ids leak in stats json",
          "user_id" not in json.dumps(body) and
          "guild_id" not in json.dumps(body))

    # cache: second call within 60s serves the same generated_at
    r2 = client.get("/api/public/stats")
    check("60s stats cache serves identical payload",
          r2.get_json().get("generated_at") == body.get("generated_at"))

    # changelog endpoints BEFORE the rate-limit hammering below (shared
    # per-IP limiter across all public routes)
    r = client.get("/api/changelog")
    body = r.get_json()
    check("GET /api/changelog -> 200", r.status_code == 200)
    versions = body.get("versions", [])
    check("changelog parses v1.0.0", any(
        v.get("version") == "v1.0.0" for v in versions))
    v100 = next((v for v in versions if v.get("version") == "v1.0.0"), {})
    check("changelog v1.0.0 has date",
          v100.get("date") == "2026-09-07", v100.get("date"))
    cats = v100.get("categories", {})
    check("changelog categories populated",
          len(cats.get("feature", [])) >= 5 and
          len(cats.get("fix", [])) >= 5 and
          len(cats.get("improvement", [])) >= 3)
    check("changelog highlights parsed",
          len(v100.get("highlights", [])) >= 4)

    r = client.get("/changelog.rss")
    check("GET /changelog.rss -> 200 xml", r.status_code == 200 and
          b"<rss" in r.data and b"<item>" in r.data)
    check("rss mimetype", "rss+xml" in r.headers.get("Content-Type", ""))

    # rate limit (60/min) — hammer past the limit
    limited = False
    for _ in range(80):
        rr = client.get("/api/public/stats")
        if rr.status_code == 429:
            limited = True
            break
    check("public rate limit engages (429)", limited)
    public_api._rl_map.clear()  # un-throttle for the history tests below

    # history sampling writes the ring buffer
    public_api._record_sample()
    hist = public_api._load_history()
    check("history sampler writes samples",
          len(hist) >= 1 and hist[-1].get("s") == 1)

    # growth series from history
    series = public_api._growth_series(hist)
    check("growth series builds from history", len(series) >= 1 and
          series[-1]["servers"] == 1)


async def main():
    print("── 1. setup_wizard cog ──")
    await test_cog()
    print("── 2. public api endpoints ──")
    test_public_api()
    print(f"\n{PASS} passed · {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
