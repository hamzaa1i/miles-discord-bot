#!/usr/bin/env python3
"""
scripts/test_phase_o.py — PHASE O regression suite (server booster system).

ALL DISCORD EVENTS ARE MOCKED. No real boost is ever performed, no
premium_since on a real account is ever mutated, no achievement is
awarded, no live Discord API call happens. Members/guilds/channels/
roles are fakes with AsyncMock send/add_roles/remove_roles recorders.

The 40 required Phase O regressions (numbered like the phase spec):

  EVT 1   non-booster → booster          → announcement triggers ONCE
  EVT 2   booster → booster (unrelated)  → nothing
  EVT 3   booster → non-booster          → configured role removed
  EVT 4   unrelated member update        → nothing
  EVT 5   new boost                      → sent to configured channel
  EVT 6   disabled system                → nothing sent
  EVT 7   missing channel                → fails safely
  EVT 8   deleted channel                → fails safely
  EVT 9   inaccessible channel (403)     → fails safely
  ROLE 10 configured role                → added on boost
  ROLE 11 managed role                   → rejected (never assigned)
  ROLE 12 role above bot                 → rejected/fails safely
  ROLE 13 unboost                        → role removed when enabled
  ROLE 14 unboost, flag off              → role kept
  ACH 15  first_boost achievement        → still independent (achievements
          cog owns it; boosters never writes achievement rows)
  DM 16   /toggledms off                 → public announcement NOT suppressed
  MSG 17  variables                      → replaced correctly
  MSG 18  literal \\n                    → real newline
  MSG 19  braces / user content          → cannot crash templates
  MODE 20 text mode                      → content only
  MODE 21 embed mode                     → embed only
  MODE 22 hybrid mode                    → split at --- (+ no-sep fallback)
  MODE 23 image                          → embed image set
  MODE 24 avatar thumbnail               → embed thumbnail set
  CFG 25  invalid image URL              → rejected
  CFG 26  invalid color                  → rejected
  CMD 27  /boosters show                 → reflects stored config
  CMD 28  /boosters test                 → real boost state untouched
  CMD 29  /boosters reset                → resets ONLY the booster module
  DUP 30  duplicate member update        → no duplicate announcement
  MIL 31  milestone                      → posts once
  MIL 32  same milestone after restart   → no repost (persisted state)
  DASH 33-36 (dashboard auth / manage-guild / csrf / managed role in the
        picker) live in scripts/test_dashboard_api.py — the canonical
        dashboard API suite — which this file runs as a subprocess
        (REG 40 also re-runs the Phase N.1 suite for achievements).
  DB 37   JSON fallback                  → settings persist + round-trip
  DB 38   Supabase path                  → column-sanitized, ISO updated_at
  CNT 39  command count                  → 74 top-level < Discord 100 limit
  REG 40  Phase N.1 suite                → still green (achievements incl.)

Run:  python3 scripts/test_phase_o.py
"""
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)

# JSON fallback mode (never touch a real Supabase project)
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)
os.environ.setdefault("DISCORD_TOKEN", "test-token")

import logging  # noqa: E402
logging.basicConfig(level=logging.CRITICAL)

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


# ─── fakes (zero Discord traffic) ───────────────────────────────────

BOOSTED_AT = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeAsset:
    def __init__(self, url):
        self.url = url


class FakeRole:
    def __init__(self, rid, name, position=1, managed=False, default=False):
        self.id = int(rid)
        self.name = name
        self.position = position
        self.mention = f"<@&{self.id}>"
        self._managed = managed
        self._default = default

    @property
    def managed(self):
        return self._managed

    def is_default(self):
        return self._default

    def __repr__(self):
        return f"<FakeRole {self.name} pos={self.position}>"


class FakeChannel:
    def __init__(self, cid, name="boosting", fail=None):
        self.id = int(cid)
        self.name = name
        self.mention = f"<#{self.id}>"
        self.fail = fail  # None | exception instance raised on send
        self.send = AsyncMock(side_effect=self._send)

    async def _send(self, content=None, embed=None):
        if self.fail:
            raise self.fail
        return MagicMock(id=1)


class FakeMember:
    def __init__(self, uid, name, guild, premium_since=None, roles=None,
                 bot=False):
        self.id = int(uid)
        self.name = name
        self.display_name = name.capitalize()
        self.mention = f"<@{self.id}>"
        self.guild = guild
        self.bot = bot
        self.premium_since = premium_since
        self.display_avatar = FakeAsset(f"https://cdn.test/avatar-{uid}.png")
        self.roles = list(roles or [])
        self.add_roles_calls = []
        self.remove_roles_calls = []

    async def add_roles(self, role, reason=None):
        self.add_roles_calls.append((role, reason))
        if role not in self.roles:
            self.roles.append(role)

    async def remove_roles(self, role, reason=None):
        self.remove_roles_calls.append((role, reason))
        self.roles = [r for r in self.roles if r.id != role.id]


class FakeGuild:
    def __init__(self, gid, name="veloura lounge", boost_count=0,
                 tier=0, channels=None, roles=None, icon=True):
        self.id = int(gid)
        self.name = name
        self.member_count = 42
        self.premium_subscription_count = boost_count
        self.premium_tier = tier
        self.icon = FakeAsset(f"https://cdn.test/icon-{gid}.png") if icon else None
        self.channels = list(channels or [])
        self.roles = list(roles or [])
        bot_role = FakeRole(900, "aurelia-bot", position=10)
        self.me = MagicMock()
        self.me.top_role = bot_role
        self.me.guild_permissions = MagicMock(manage_roles=True)

    def get_channel(self, cid):
        for c in self.channels:
            if c.id == int(cid):
                return c
        return None

    def get_role(self, rid):
        for r in self.roles:
            if r.id == int(rid):
                return r
        return None


class FakeBot:
    def __init__(self):
        self.command_counts = {}

    def increment_command(self, name):
        self.command_counts[name] = self.command_counts.get(name, 0) + 1

    def get_cog(self, name):
        return None


class FakeInteraction:
    def __init__(self, guild, user):
        self.guild = guild
        self.user = user
        self.response = MagicMock()
        self.response.send_message = AsyncMock()
        self.response.edit_message = AsyncMock()
        self.followup = MagicMock()
        self.followup.send = AsyncMock()


# ─── fake Supabase (records boundary payloads; zero network) ────────

class FakeSBQuery:
    def __init__(self, recorder, table, op):
        self.rec = recorder
        self.table = table
        self.op = op
        self.filters = {}
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        self.op = "insert"
        return self

    def select(self, _cols):
        self.op = "select"
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def update(self, payload):
        self.payload = payload
        self.op = "update"
        return self

    def execute(self):
        self.rec.calls.append({
            "table": self.table, "op": self.op,
            "filters": dict(self.filters), "payload": self.payload,
        })
        resp = MagicMock()
        if self.op == "insert" and self.payload:
            resp.data = [dict(self.payload)]
        elif self.op == "insert":
            resp.data = [{}]
        else:
            resp.data = self.rec.rows
        return resp


class FakeSupabase:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def table(self, name):
        return FakeSBQuery(self, name, "select")


# ─── fixtures / helpers ─────────────────────────────────────────────

import utils.db as _db  # noqa: E402
from utils.db import (  # noqa: E402
    get_booster_settings_async, set_booster_settings_async,
    BOOSTER_DEFAULT_MESSAGE,
)
from cogs.boosters import (  # noqa: E402
    Boosters, BoosterResetView, parse_hex_color, parse_milestone_counts,
)

TEST_GUILD_BASE = 910000000  # ids far away from anything real
BOOSTER_JSON = "data/booster_settings.json"
LOG_JSON = "data/log_settings.json"
DM_JSON = "data/dm_prefs.json"
ACH_JSON = "data/user_achievements.json"


def _clean_test_rows():
    """Remove every test guild row this suite writes (leave real rows)."""
    for path in (BOOSTER_JSON, LOG_JSON, ACH_JSON):
        try:
            if not os.path.exists(path):
                continue
            data = json.load(open(path))
            changed = False
            for k in [k for k in data if k.isdigit()
                      and int(k) >= TEST_GUILD_BASE]:
                data.pop(k)
                changed = True
            if changed:
                json.dump(data, open(path, "w"), indent=2)
        except Exception:
            pass
    try:
        if os.path.exists(DM_JSON):
            data = json.load(open(DM_JSON))
            if data.pop(str(91000111), None) is not None:
                json.dump(data, open(DM_JSON, "w"), indent=2)
    except Exception:
        pass


async def make_fixture(gid, *, enabled=True, channel=True, auto_role=False,
                       role=None, member_roles=None, boost_count=0,
                       remove_role_on_unboost=True, milestone_enabled=True,
                       milestone_last=None, milestone_counts=None,
                       log_channel=None):
    """Build (cog, guild, member, channel, role) + persisted settings."""
    bot = FakeBot()
    cog = Boosters(bot)
    channel_obj = FakeChannel(910222) if channel else None
    role_obj = role or FakeRole(910333, "booster", position=2)
    channels = ([channel_obj] if channel_obj else [])
    if log_channel is not None:
        channels.append(log_channel)
    guild = FakeGuild(
        gid, boost_count=boost_count, channels=channels,
        roles=[role_obj, FakeRole(900, "aurelia-bot", position=10)],
    )
    member = FakeMember(91000111, "diva", guild,
                        premium_since=None,
                        roles=list(member_roles or []))
    payload = {
        "enabled": enabled,
        "channel_id": str(channel_obj.id) if channel_obj else None,
        "booster_role_id": str(role_obj.id) if (auto_role or role is not None) else None,
        "auto_role": auto_role,
        "remove_role_on_unboost": remove_role_on_unboost,
        "milestone_enabled": milestone_enabled,
    }
    if milestone_last is not None:
        payload["milestone_last"] = milestone_last
    if milestone_counts is not None:
        payload["milestone_counts"] = milestone_counts
    await set_booster_settings_async(gid, payload)
    return cog, guild, member, channel_obj, role_obj


async def fire_boost(cog, guild, count=None, uid=91000111, name="diva",
                     roles=None):
    """Fire on_member_update as a non-booster → booster transition.
    Returns the `after` member (whose role recorders the cog acted on)."""
    if count is not None:
        guild.premium_subscription_count = count
    before = FakeMember(uid, name, guild, premium_since=None,
                        roles=list(roles or []))
    after = FakeMember(uid, name, guild, premium_since=BOOSTED_AT,
                       roles=list(roles or []))
    await cog.on_member_update(before, after)
    return after


async def fire_unboost(cog, guild, count=None, uid=91000111, name="diva",
                       roles=None):
    """Fire on_member_update as a booster → non-booster transition.
    Returns the `after` member (whose role recorders the cog acted on)."""
    if count is not None:
        guild.premium_subscription_count = count
    before = FakeMember(uid, name, guild, premium_since=BOOSTED_AT,
                        roles=list(roles or []))
    after = FakeMember(uid, name, guild, premium_since=None,
                       roles=list(roles or []))
    await cog.on_member_update(before, after)
    return after


# ═══ EVT 1–9: detection + announcement delivery ═════════════════════

async def test_events():
    print("\n── boost detection & announcement delivery ──")
    gid = TEST_GUILD_BASE + 1

    # EVT 1 + 5 + 30 — triggers exactly once, to the configured channel
    cog, guild, member, channel, role = await make_fixture(gid)
    after = await fire_boost(cog, guild, count=1)
    check("EVT-1  non-booster → booster announcement sent ONCE",
          channel.send.call_count == 1,
          f"calls={channel.send.call_count}")
    kwargs = channel.send.call_args.kwargs
    check("EVT-5  sent to the CONFIGURED channel with the rendered embed",
          kwargs.get("embed") is not None
          and "a new star is shining brighter" in kwargs["embed"].description
          and member.mention in kwargs["embed"].description)
    # duplicate delivery of the same member update within the window
    await fire_boost(cog, guild, count=1)
    check("EVT-30 duplicate member update → no duplicate announcement",
          channel.send.call_count == 1,
          f"calls={channel.send.call_count}")

    # EVT 2 — booster → booster unrelated update (nickname changed)
    cog2, guild2, member2, channel2, _ = await make_fixture(gid + 1)
    b = FakeMember(91000111, "oldnick", guild2, premium_since=BOOSTED_AT)
    a = FakeMember(91000111, "newnick", guild2, premium_since=BOOSTED_AT)
    await cog2.on_member_update(b, a)
    check("EVT-2  booster → booster unrelated update → nothing",
          channel2.send.call_count == 0)

    # EVT 4 — plain unrelated member update
    b2 = FakeMember(91000112, "x", guild2, premium_since=None)
    a2 = FakeMember(91000112, "y", guild2, premium_since=None)
    await cog2.on_member_update(b2, a2)
    check("EVT-4  unrelated member update → nothing",
          channel2.send.call_count == 0)

    # EVT 6 — disabled system sends nothing
    cog3, guild3, member3, channel3, role3 = await make_fixture(
        gid + 2, enabled=False, auto_role=True)
    after3 = await fire_boost(cog3, guild3, count=1)
    check("EVT-6  disabled system → no announcement, no role grant",
          channel3.send.call_count == 0
          and not after3.add_roles_calls)

    # EVT 7 — missing channel fails safely
    cog4, guild4, member4, _, role4 = await make_fixture(gid + 3, channel=False)
    try:
        await fire_boost(cog4, guild4, count=1)
        check("EVT-7  missing channel → no crash, nothing sent", True)
    except Exception as e:
        check("EVT-7  missing channel → no crash, nothing sent", False,
              f"raised {type(e).__name__}: {e}")

    # EVT 8 — deleted channel (id points nowhere) fails safely
    cog5, guild5, member5, _, role5 = await make_fixture(gid + 4)
    await set_booster_settings_async(gid + 4, {"channel_id": "918888"})
    try:
        await fire_boost(cog5, guild5, count=1)
        check("EVT-8  deleted channel → no crash, nothing sent", True)
    except Exception as e:
        check("EVT-8  deleted channel → no crash, nothing sent", False,
              f"raised {type(e).__name__}: {e}")

    # EVT 9 — inaccessible channel (Forbidden) fails safely
    import discord
    forbidden = FakeChannel(
        910999, fail=discord.Forbidden(MagicMock(), MagicMock()))
    cog6, guild6, member6, _, role6 = await make_fixture(gid + 5)
    guild6.channels = [forbidden]
    await set_booster_settings_async(gid + 5,
                                     {"channel_id": str(forbidden.id)})
    try:
        await fire_boost(cog6, guild6, count=1)
        check("EVT-9  inaccessible channel (403) → no crash, failed "
              "gracefully", True)
    except Exception as e:
        check("EVT-9  inaccessible channel (403) → no crash", False,
              f"raised {type(e).__name__}: {e}")


# ═══ ROLE 10–14: booster role management ════════════════════════════

async def test_roles():
    print("\n── booster role management (hierarchy-safe) ──")
    gid = TEST_GUILD_BASE + 20

    # ROLE 10 — configured role added on boost
    cog, guild, member, channel, role = await make_fixture(
        gid, auto_role=True)
    after = await fire_boost(cog, guild, count=1)
    check("ROLE-10 auto_role on + valid role → role granted",
          len(after.add_roles_calls) == 1
          and after.add_roles_calls[0][0].id == role.id)

    # ROLE 11 — managed role rejected (never assigned)
    managed = FakeRole(910444, "Server Booster (native)", position=2,
                       managed=True)
    cog2, guild2, member2, channel2, _ = await make_fixture(
        gid + 1, auto_role=True, role=managed)
    after2 = await fire_boost(cog2, guild2, count=1)
    check("ROLE-11 managed/integration role → never assigned",
          not after2.add_roles_calls)

    # ROLE 12 — role above the bot rejected / fails safely
    above = FakeRole(910555, "admin-ish", position=12)
    cog3, guild3, member3, channel3, _ = await make_fixture(
        gid + 2, auto_role=True, role=above)
    after3 = await fire_boost(cog3, guild3, count=1)
    check("ROLE-12 role above bot top role → never assigned, no crash",
          not after3.add_roles_calls)

    # ROLE 13 + EVT 3 — unboost removes configured role
    cog4, guild4, member4, channel4, role4 = await make_fixture(
        gid + 3, auto_role=True)
    after_u = await fire_unboost(cog4, guild4, count=0,
                                 roles=[role4])
    check("EVT-3/ROLE-13 unboost with remove flag on → role removed",
          any(c[0].id == role4.id for c in after_u.remove_roles_calls))

    # ROLE 14 — unboost keeps role when the flag is off
    cog5, guild5, member5, channel5, role5 = await make_fixture(
        gid + 4, remove_role_on_unboost=False)
    after_u2 = await fire_unboost(cog5, guild5, count=0, roles=[role5])
    check("ROLE-14 remove-on-unboost off → role kept",
          not after_u2.remove_roles_calls)


# ═══ ACH 15 + DM 16: coexistence with achievements & /toggledms ════

async def test_achievements_and_dms():
    print("\n── achievements independence & /toggledms ──")
    gid = TEST_GUILD_BASE + 40

    # ACH 15 — boosters cog never unlocks achievements; the
    # achievements cog still owns first_boost via its own listener
    cog, guild, member, channel, role = await make_fixture(gid)
    await fire_boost(cog, guild, count=1)
    ach_rows = []
    if os.path.exists(ACH_JSON):
        data = json.load(open(ACH_JSON))
        ach_rows = [r for rows in data.values()
                    if isinstance(rows, list) for r in rows
                    if isinstance(r, dict)
                    and str(r.get("user_id")) == str(member.id)]
    ach_src = open("cogs/achievements.py", encoding="utf-8").read()
    check("ACH-15 first_boost stays independent: boosters wrote no "
          "achievement rows AND achievements.py still owns the listener",
          not ach_rows
          and "first_boost" in ach_src
          and 'if before.premium_subscriber or not after.premium_subscriber:'
          in ach_src)

    # DM 16 — /toggledms off does NOT suppress the PUBLIC announcement
    _db.set_user_allows_passive_dms(member.id, False)
    try:
        cog2, guild2, member2, channel2, _ = await make_fixture(gid + 1)
        await fire_boost(cog2, guild2, count=1, uid=member.id)
        check("DM-16  /toggledms off → public boost announcement still "
              "sent (it is a channel message, not a DM)",
              channel2.send.call_count == 1,
              f"calls={channel2.send.call_count}")
    finally:
        _db.set_user_allows_passive_dms(member.id, True)


# ═══ MSG 17–19 + MODE 20–24: rendering ══════════════════════════════

async def test_rendering():
    print("\n── template variables & embed modes ──")
    gid = TEST_GUILD_BASE + 60
    bot = FakeBot()
    cog = Boosters(bot)
    guild = FakeGuild(gid, name="veloura lounge", boost_count=7, tier=2)
    member = FakeMember(91000111, "diva", guild, premium_since=BOOSTED_AT)

    # MSG 17 — every variable replaced
    tpl = ("{user}|{user.name}|{user.display_name}|{user.id}|"
           "{user.avatar}|{server}|{server.id}|{server.icon}|"
           "{boostcount}|{boostlevel}")
    out = cog._replace_variables(tpl, member, guild)
    check("MSG-17 all template variables replaced",
          out == (f"{member.mention}|diva|Diva|{member.id}|"
                  f"https://cdn.test/avatar-{member.id}.png|"
                  f"veloura lounge|{guild.id}|"
                  f"https://cdn.test/icon-{guild.id}.png|7|2"),
          f"got {out!r}")

    # MSG 18 — literal \n becomes a newline
    out = cog._replace_variables("line one\\nline two", member, guild)
    check("MSG-18 literal \\n → real newline", out == "line one\nline two")

    # MSG 19 — braces/user content never crash rendering
    try:
        weird = "{user {server} } {unclosed 50% off} {{{{}}}}"
        out = cog._replace_variables(weird, member, guild)
        cfg = {"message": weird + " {user}", "embed_mode": "embed"}
        content, embed = cog._render_payload(cfg, member, guild)
        ok = embed is not None
    except Exception as e:
        ok = False
        out = f"raised {type(e).__name__}: {e}"
    check("MSG-19 unbalanced braces/user content → no crash", ok,
          str(out)[:120])

    # MODE 20 — text
    cfg = {"message": "ty {user} ♡", "embed_mode": "text"}
    content, embed = cog._render_payload(cfg, member, guild)
    check("MODE-20 text mode → content only, no embed",
          content is not None and "ty " in content and embed is None)

    # MODE 21 — embed (default styling + footer)
    cfg = {"message": "thank you {user}",
           "embed_mode": "embed",
           "color": "#FFC0CB",
           "thumbnail_mode": "member",
           "image_url": "https://cdn.test/banner.png",
           "footer": "{boostcount} boosts ♡"}
    content, embed = cog._render_payload(cfg, member, guild)
    d = embed.to_dict()
    check("MODE-21 embed mode → embed only with description/footer/color",
          content is None and embed is not None
          and f"thank you {member.mention}" == d["description"]
          and d["footer"]["text"] == "7 boosts ♡"
          and d["color"] == 0xFFC0CB)
    check("MODE-23 image url → embed image set",
          d.get("image", {}).get("url") == "https://cdn.test/banner.png")
    check("MODE-24 thumbnail member → avatar thumbnail",
          d.get("thumbnail", {}).get("url") == member.display_avatar.url)

    # MODE 22 — hybrid (split at ---) + no-separator fallback
    cfg = {"message": "look who boosted ♡\n---\nthank you {user}!",
           "embed_mode": "hybrid"}
    content, embed = cog._render_payload(cfg, member, guild)
    d = embed.to_dict()
    check("MODE-22 hybrid with --- → text before + embed after",
          content == "look who boosted ♡"
          and f"thank you {member.mention}!" == d["description"])
    cfg = {"message": "no separator here {user}", "embed_mode": "hybrid"}
    content, embed = cog._render_payload(cfg, member, guild)
    d = embed.to_dict()
    check("MODE-22b hybrid without --- → whole template becomes the "
          "embed (never duplicated)",
          content is None and "no separator here" in d["description"])

    # truncation sanity — Discord limits respected
    cfg = {"message": "x" * 9000, "embed_mode": "text"}
    content, embed = cog._render_payload(cfg, member, guild)
    cfg = {"message": "y" * 9000, "embed_mode": "embed"}
    _, embed2 = cog._render_payload(cfg, member, guild)
    check("MODE-21b Discord limits respected (2000/4096 caps)",
          len(content) <= 2000
          and len(embed2.to_dict()["description"]) <= 4096)


# ═══ CFG 25–26: config validation ═══════════════════════════════════

async def test_config_validation():
    print("\n── config validation ──")
    gid = TEST_GUILD_BASE + 80
    bot = FakeBot()
    cog = Boosters(bot)
    guild = FakeGuild(gid)
    user = FakeMember(91000111, "admin", guild)

    # CFG 25 — invalid image URL rejected
    itx = FakeInteraction(guild, user)
    await cog._set_image(itx, "ftp://example.com/x.png", None, None)
    msg = itx.response.send_message.call_args.args[0]
    check("CFG-25 invalid image URL → rejected with an error",
          "http" in msg and itx.response.send_message.call_args.kwargs.get(
              "ephemeral") is True, f"got {msg!r}")

    # CFG 26 — invalid color rejected
    itx2 = FakeInteraction(guild, user)
    await cog._set_color(itx2, "notacolor", None, None)
    msg2 = itx2.response.send_message.call_args.args[0]
    check("CFG-26 invalid color → rejected with an error",
          "invalid color" in msg2.lower(), f"got {msg2!r}")
    check("CFG-26b parse_hex_color basics",
          parse_hex_color("#FFC0CB") == 0xFFC0CB
          and parse_hex_color("FFC0CB") == 0xFFC0CB
          and parse_hex_color(None) is None
          and parse_hex_color("#12345") is None)


# ═══ CMD 27–29: /boosters show · test · reset ═══════════════════════

async def test_commands():
    print("\n── /boosters show · test · reset ──")
    gid = TEST_GUILD_BASE + 100
    chan = FakeChannel(910222, "boosting")
    role = FakeRole(910333, "booster", position=2)
    guild = FakeGuild(gid, name="veloura lounge", boost_count=7, tier=2,
                      channels=[chan], roles=[role])
    member = FakeMember(91000111, "admin", guild)
    bot = FakeBot()
    cog = Boosters(bot)
    await set_booster_settings_async(gid, {
        "enabled": True, "channel_id": str(chan.id),
        "message": "thank you {user} for boosting {server}!",
        "embed_mode": "hybrid", "color": "#FFB6C1",
        "booster_role_id": str(role.id), "auto_role": True,
        "milestone_enabled": True, "milestone_counts": [2, 7, 14],
        "milestone_last": 7,
    })
    itx = FakeInteraction(guild, member)

    # CMD 27 — /boosters show reflects the stored config
    await cog.boosters_show.callback(cog, itx)
    embed = itx.response.send_message.call_args.kwargs.get("embed")
    txt = embed.to_dict() if embed else {}
    blob = json.dumps(txt, default=str)
    check("CMD-27 /boosters show reflects stored config",
          embed is not None and "<#910222>" in blob
          and "<@&910333>" in blob and "hybrid" in blob
          and "2,7,14" in blob.replace(" ", ""),
          blob[:200])

    # CMD 28 — /boosters test: real boost state untouched
    member.premium_since = None  # caller is NOT boosting
    await cog.boosters_test.callback(cog, itx)
    check("CMD-28 /boosters test → announcement rendered once, caller "
          "unchanged, no role/milestone/achievement side effects",
          chan.send.call_count == 1
          and member.premium_since is None
          and not member.add_roles_calls
          and (await get_booster_settings_async(gid))["milestone_last"] == 7
          and bot.command_counts.get("boosters_test") == 1)

    # CMD 29 — /boosters reset resets ONLY the booster module
    log_chan = FakeChannel(910777, "logs")
    guild.channels.append(log_chan)
    _db.set_guild_setting(gid, "log_settings",
                          {"enabled": True, "channel_id": str(log_chan.id)})
    itx2 = FakeInteraction(guild, member)
    view = BoosterResetView(member.id, cog)
    await view.confirm.callback(itx2)
    after = await get_booster_settings_async(gid)
    check("CMD-29 /boosters reset → booster settings back to defaults "
          "(milestone baseline pinned to current count)",
          after["enabled"] is False and after["channel_id"] is None
          and after["message"] == BOOSTER_DEFAULT_MESSAGE
          and after["milestone_last"] == 7,  # guild boost count is 7
          f"got enabled={after['enabled']} last={after['milestone_last']}")
    log_cfg = _db.get_guild_setting(gid, "log_settings")
    check("CMD-29b reset touches ONLY boosters (log settings intact)",
          log_cfg.get("channel_id") == str(log_chan.id))
    check("CMD-29c reset removed no Discord roles / achievements",
          not member.remove_roles_calls
          and "booster" not in json.dumps(
              json.load(open(ACH_JSON)) if os.path.exists(ACH_JSON) else {}))


# ═══ MIL 31–32: milestones ══════════════════════════════════════════

async def test_milestones():
    print("\n── milestones (once, persisted, churn-safe) ──")
    gid = TEST_GUILD_BASE + 120
    cog, guild, member, channel, role = await make_fixture(
        gid, boost_count=1, milestone_last=0)

    def milestone_sends():
        return [c for c in channel.send.call_args_list
                if c.kwargs.get("embed")
                and "reached" in (c.kwargs["embed"].description or "")]

    # MIL 31 — milestone posts once (boost count reaches 2)
    await fire_boost(cog, guild, count=2)
    sends = milestone_sends()
    check("MIL-31 crossing threshold 2 → milestone posted once",
          len(sends) == 1
          and "veloura lounge reached 2 boosts" in
          sends[0].kwargs["embed"].description,
          f"milestone_sends={len(sends)}")

    # a second member boosting at count 2 → threshold already marked
    await fire_boost(cog, guild, count=2, uid=91000113, name="nova")
    sends = milestone_sends()
    check("MIL-31b same threshold never reposted (high-water mark)",
          len(sends) == 1, f"milestone_sends={len(sends)}")

    # MIL 32 — restart-safe: a brand-new cog instance (fresh memory,
    # persisted state) does not repost the same milestone
    cog_restarted = Boosters(FakeBot())
    await fire_boost(cog_restarted, guild, count=2,
                     uid=91000114, name="stella")
    sends = milestone_sends()
    check("MIL-32 after restart (state reload) → no repost",
          len(sends) == 1, f"milestone_sends={len(sends)}")

    # churn: count drops to 1 then climbs back to 2 → still no repost
    await fire_unboost(cog_restarted, guild, count=1,
                       uid=91000115, name="comet")
    await fire_boost(cog_restarted, guild, count=2,
                     uid=91000116, name="luna")
    sends = milestone_sends()
    check("MIL-32b boost churn (drop below, climb back) → no repost",
          len(sends) == 1, f"milestone_sends={len(sends)}")

    # parse_milestone_counts sanity
    check("MIL-31c milestone list parsing",
          parse_milestone_counts("2, 7, 14") == [2, 7, 14]
          and parse_milestone_counts("5,10,20,25,50,100") == [5, 10, 20, 25, 50, 100]
          and parse_milestone_counts("x") is None
          and parse_milestone_counts("0") is None)


# ═══ LOG (part 12): private event logging ═══════════════════════════

async def test_logging():
    print("\n── private boost event logging ──")
    gid = TEST_GUILD_BASE + 140
    log_chan = FakeChannel(910888, "logs")
    cog, guild, member, channel, role = await make_fixture(
        gid, log_channel=log_chan, boost_count=1)
    _db.set_guild_setting(gid, "log_settings",
                          {"enabled": True, "channel_id": str(log_chan.id)})
    await fire_boost(cog, guild, count=2)
    log_embeds = [c for c in log_chan.send.call_args_list
                  if c.kwargs.get("embed")]
    check("LOG-12 new boost logged privately to the existing log channel",
          log_chan.send.call_count == 1 and log_embeds
          and "Boost Started" in log_embeds[0].kwargs["embed"].to_dict()["title"],
          f"calls={log_chan.send.call_count}")
    await fire_unboost(cog, guild, count=1)
    unboost_log = [c for c in log_chan.send.call_args_list
                   if c.kwargs.get("embed")
                   and "Boost Ended" in c.kwargs["embed"].to_dict()["title"]]
    check("LOG-12b unboost logged privately (no public goodbye message)",
          len(unboost_log) == 1 and channel.send.call_count == 2,
          f"logs={len(unboost_log)} announcements={channel.send.call_count}")


# ═══ DB 37–38: persistence layers ═══════════════════════════════════

async def test_db():
    print("\n── persistence: JSON fallback + Supabase boundary ──")
    gid = TEST_GUILD_BASE + 160

    # DB 37 — JSON fallback round-trip
    await set_booster_settings_async(gid, {
        "enabled": True, "channel_id": "910222",
        "message": "ty {user} ♡", "embed_mode": "hybrid",
        "color": "#FFB6C1", "milestone_counts": [2, 7, 14, 25],
    })
    stored = json.load(open(BOOSTER_JSON)).get(str(gid), {})
    got = await get_booster_settings_async(gid)
    check("DB-37  JSON fallback: settings persist + round-trip "
          "(milestone_counts as list, updated_at ISO)",
          stored.get("channel_id") == "910222"
          and got["enabled"] is True
          and got["milestone_counts"] == [2, 7, 14, 25]
          and isinstance(got["updated_at"], str)
          and "T" in got["updated_at"])

    # defaults fill on a guild that never configured anything
    fresh = await get_booster_settings_async(gid + 1)
    check("DB-37b defaults filled for unconfigured guild",
          fresh["enabled"] is False
          and fresh["embed_mode"] == "embed"
          and fresh["color"] == "#FFC0CB"
          and fresh["thumbnail_mode"] == "member"
          and fresh["milestone_counts"] == [2, 7, 14]
          and fresh["milestone_last"] == 0
          and fresh["remove_role_on_unboost"] is True)

    # DB 38 — Supabase path: column-sanitized payload + ISO updated_at
    sb = FakeSupabase(rows=[])
    orig_sb, orig_use = _db._supabase, _db._use_supabase
    _db._supabase = sb
    _db._use_supabase = True
    try:
        await set_booster_settings_async(gid + 2, {
            "enabled": True, "channel_id": "910222",
            "milestone_counts": [2, 7],
            "bogus_column": "should be stripped",
        })
        calls = [c for c in sb.calls if c["table"] == "booster_settings"
                 and c["op"] in ("insert", "update")]
        payload = calls[0]["payload"]
        allowed = _db._TABLE_COLUMNS["booster_settings"] | {"guild_id"}
        check("DB-38  Supabase: payload sanitized to known columns, "
              "updated_at is an ISO string (TIMESTAMPTZ-safe)",
              bool(calls) and set(payload.keys()) <= allowed
              and "bogus_column" not in payload
              and isinstance(payload.get("updated_at"), str)
              and datetime.fromisoformat(payload["updated_at"]) is not None,
              f"payload keys={sorted(payload.keys())}")

        # read path returns the stored row
        sb2 = FakeSupabase(rows=[{
            "guild_id": str(gid + 3), "enabled": True,
            "channel_id": "910222", "milestone_counts": [2, 7],
        }])
        _db._supabase = sb2
        got2 = await get_booster_settings_async(gid + 3)
        check("DB-38b Supabase: stored row read back with defaults filled",
              got2["enabled"] is True and got2["channel_id"] == "910222"
              and got2["milestone_counts"] == [2, 7]
              and got2["embed_mode"] == "embed")
    finally:
        _db._supabase = orig_sb
        _db._use_supabase = orig_use


# ═══ CNT 39: command counts ═════════════════════════════════════════

def test_counts():
    print("\n── command counts (canonical helper) ──")
    from utils.command_counts import count_commands_static
    c = count_commands_static()
    check("CNT-39 /boosters added exactly ONE root group: 74 top-level, "
          "173 total invokable — below Discord's 100 top-level limit",
          c["cogs"] == 47 and c["top_level"] == 74
          and c["total_invokable"] == 173
          and c["top_level_headroom"] == 26,
          f"got {c['cogs']}/{c['top_level']}/{c['total_invokable']}")
    boosters_md = open("COMMANDS.md", encoding="utf-8").read()
    check("CNT-39b COMMANDS.md documents /boosters + canonical counts",
          "### /boosters" in boosters_md and "74 top-level" in boosters_md
          and "173 total" in boosters_md)
    help_src = open("cogs/help.py", encoding="utf-8").read()
    check("CNT-39c /help lists the boosters commands",
          "/boosters config" in help_src and "/boosters test" in help_src)


# ═══ REG 40 (+ DASH 33–36 via the canonical dashboard suite) ════════

def test_regression_suites():
    print("\n── existing suites stay green ──")
    # REG 40 — the Phase N.1 suite covers achievements behavior (DM
    # gating, unlock independence) + the count surfaces; run it whole.
    r = subprocess.run(
        [sys.executable, "scripts/test_phase_n1.py"],
        cwd=REPO, capture_output=True, text=True, timeout=300)
    tail = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
    check("REG-40 Phase N.1 regression suite still green "
          "(achievements + counts)", r.returncode == 0, f"tail={tail!r}")
    # DASH 33-36 — the canonical dashboard API suite now includes the
    # boosters auth/CSRF/managed-role checks.
    r2 = subprocess.run(
        [sys.executable, "scripts/test_dashboard_api.py"],
        cwd=REPO, capture_output=True, text=True, timeout=300)
    tail2 = (r2.stdout or "").strip().splitlines()[-1] if r2.stdout else ""
    check("DASH-33..36 dashboard API suite green "
          "(auth · manage-guild · csrf · managed role)",
          r2.returncode == 0, f"tail={tail2!r}")


# ═══ runner ═════════════════════════════════════════════════════════

async def run_all():
    _clean_test_rows()
    try:
        await test_events()
        await test_roles()
        await test_achievements_and_dms()
        await test_rendering()
        await test_config_validation()
        await test_commands()
        await test_milestones()
        await test_logging()
        await test_db()
        test_counts()
        test_regression_suites()
    finally:
        _clean_test_rows()


def main():
    asyncio.run(run_all())
    print(f"\n{PASS} passed · {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
