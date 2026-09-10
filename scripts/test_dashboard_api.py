"""
test_dashboard_api.py — Backend verification for the Aurelia dashboard API.

Boots the Flask app WITHOUT the real bot/Discord/Supabase:
  * utils.dashboard_api's imported auth functions are monkeypatched to a
    fake Discord user (id 698142490775257119 = volc, manage_guild on the
    test guild).
  * keep_alive.bot_ref is replaced with a fake bot carrying one fake guild.
  * No SUPABASE_URL in env -> every db call exercises the JSON fallback.

Two modes:
  python scripts/test_dashboard_api.py          -> assert suite (exit code)
  python scripts/test_dashboard_api.py --serve  -> live server on :8081 for curl

Run from the repo root (the script chdirs itself).
"""
import json
import os
import sys
import types
from datetime import datetime, timezone

import discord

REPO = "/home/z/my-project/miles-discord-bot"
os.chdir(REPO)
sys.path.insert(0, REPO)

# ── Fake Discord surfaces ───────────────────────────────────────────
GUILD_ID = "111222333444555666"
USER_ID = "698142490775257119"


class FakeRole:
    def __init__(self, rid, name, color=0, position=1, default=False,
                 managed=False):
        self.id, self.name, self.position = int(rid), name, position
        self.color = types.SimpleNamespace(value=color)
        self._default, self._managed = default, managed

    def is_default(self):
        return self._default

    @property
    def managed(self):
        return self._managed


class FakeChannel:
    """Channel stand-in whose `.type` is a REAL discord.ChannelType
    member — the PHASE O.2 lesson: the old harness set `.type` to a
    plain int, so the boosters PATCH validator's int(channel.type)
    worked in tests while raising TypeError on every real guild
    object in production. Real discord.py 2.x channels carry enum
    members (`_EnumValue_ChannelType`); this harness now models that
    faithfully, including unknown-future enum-like values via
    `ctype=future(99)`."""

    def __init__(self, cid, name, ctype=None, category=None, position=0,
                 can_send=True):
        self.id, self.name, self.position = int(cid), name, position
        # default: a real text-channel enum member, exactly like
        # discord.TextChannel.type in discord.py 2.7.1
        self.type = discord.ChannelType.text if ctype is None else ctype
        self.category_id = category
        self.can_send = can_send

    def permissions_for(self, member):
        # gateway-fallback path of the channel serializer calls this —
        # the fake bot can see every fake channel; can_send models
        # Send Messages overwrites (False = the locked channel case)
        return discord.Permissions(
            view_channel=True, send_messages=self.can_send)


class FakeMember:
    def __init__(self, uid, name, status="online"):
        self.id, self.display_name, self.status = int(uid), name, status


class FakeGuild:
    def __init__(self):
        self.id, self.name = int(GUILD_ID), "veloura lounge"
        # REGRESSION (live round 2): real discord.py 2.x Guild.icon is an
        # Optional[Asset] — Assets are NOT JSON serializable, and a bare
        # `guild.icon` in the /overview response 500'd EVERY call in
        # production while this suite's old plain-string mock passed.
        # The fake now carries a REAL discord.Asset (animated hash, to
        # cover the a_ gif path) so the serializer fix is enforced.
        import discord
        self.icon = discord.Asset._from_guild_icon(
            None, int(GUILD_ID), "a_1c2e3a4e5f6fakegif")
        self.member_count = 42
        self.premium_subscription_count = 2
        self.me = types.SimpleNamespace(
            joined_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            guild_permissions=types.SimpleNamespace(
                manage_roles=True, manage_channels=True,
                moderate_members=True, send_messages=True, embed_links=True,
            ),
            # _live_guild_roles gateway fallback reads me.top_role.position
            # (roles at/above the bot are filtered out of every picker)
            top_role=types.SimpleNamespace(position=10),
            # _perms_from_overwrites reads me.roles (REST channel path)
            roles=[FakeRole("200", "@everyone", default=True, position=0),
                   FakeRole("201", "veloura", 0xFFC0CB, position=3)],
        )
        self.owner_id = int(USER_ID)
        self.members = [FakeMember(USER_ID, "volc"),
                        FakeMember("999", "sleepy")]
        self.channels = [
            # REAL discord.py ChannelType enum members — the production
            # representation (see FakeChannel docstring)
            FakeChannel("100", "general", discord.ChannelType.text),
            FakeChannel("101", "announcements", discord.ChannelType.news),
            FakeChannel("102", "vc-lounge", discord.ChannelType.voice),
            FakeChannel("103", "boosting", discord.ChannelType.text),
            FakeChannel("104", "forum-board", discord.ChannelType.forum),
            FakeChannel("105", "media-gallery", discord.ChannelType.media),
            FakeChannel("106", "stage", discord.ChannelType.stage_voice),
            FakeChannel("107", "archive", discord.ChannelType.category),
            # unknown/future channel type: a value discord.py 2.7.1 does
            # not know yet — must fail SAFE (rejected), never accepted
            # nor a 500
            FakeChannel("108", "future-channel",
                        types.SimpleNamespace(value=99)),
            # text channel the bot CANNOT send in (Send Messages denied)
            FakeChannel("109", "locked", discord.ChannelType.text,
                        can_send=False),
        ]
        self.roles = [
            FakeRole("200", "@everyone", default=True, position=0),
            FakeRole("201", "veloura", 0xFFC0CB, position=3),
            FakeRole("202", "midnight", 0x1A1D29, position=2),
            # PHASE O — a Discord-native style MANAGED role (integration):
            # must never appear in pickers nor be accepted as booster role
            FakeRole("203", "Server Booster", 0xFF73FA, position=4,
                     managed=True),
            # a role ABOVE the bot's top role (bot top = 10): unmanageable
            FakeRole("204", "above-bot", 0xFF0000, position=11),
        ]

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

    def get_member(self, uid):
        for m in self.members:
            if str(m.id) == str(uid):
                return m
        return None


class FakeBot:
    def __init__(self):
        self.guilds = [fake_guild, FakeGuild()]
        # second guild: id 777 — bot is present but user lacks manage_guild
        self.guilds[1].id = 777
        self.guilds[1].name = "no perms here"

    def is_ready(self):
        return True

    def get_guild(self, gid):
        for gu in self.guilds:
            if gu.id == int(gid):
                return gu
        return None


fake_guild = FakeGuild()

# ── Patch auth before importing the blueprint module ───────────────
import utils.dashboard_auth as dauth  # noqa: E402

FAKE_USER = {
    "id": USER_ID, "username": "volc", "global_name": "volc",
    "avatar": "abc123",
}
FAKE_GUILDS = [
    {"id": GUILD_ID, "name": "veloura lounge", "icon": None,
     "owner": False, "permissions": str(1 << 5)},          # manage_guild
    {"id": "777", "name": "not manage", "icon": None,
     "owner": False, "permissions": "0"},                  # no perms
    {"id": "888", "name": "no bot here", "icon": None,
     "owner": True, "permissions": "8"},
]
dauth.verify_discord_token = lambda token: (
    FAKE_USER if token == "good-token" else None)
dauth.get_user_guilds = lambda token: (
    FAKE_GUILDS if token == "good-token" else None)
dauth.verify_guild_permission = (
    lambda token, gid, perm=None: token == "good-token" and str(gid) == GUILD_ID)
# require_guild_api checks permissions via verify_guild_permission_detailed
# (imported INTO the blueprint module at import time — patch the dapi copy).
# Mimics the real reason codes: ok / no_permission / auth.
def _fake_verify_detailed(token, gid, perm=None):
    if token != "good-token":
        return False, dauth.VERIFY_AUTH
    if str(gid) == GUILD_ID:
        return True, dauth.VERIFY_OK
    if str(gid) == "777":
        return False, dauth.VERIFY_NO_PERMISSION
    return False, dauth.VERIFY_NOT_FOUND

dauth.verify_guild_permission_detailed = _fake_verify_detailed

import keep_alive  # noqa: E402
fake_bot = FakeBot()
keep_alive.bot_ref = fake_bot

# ── Build the app ───────────────────────────────────────────────────
from flask import Flask  # noqa: E402
import utils.dashboard_api as dapi  # noqa: E402

# re-point the names imported INTO the blueprint module
dapi.verify_discord_token = dauth.verify_discord_token
dapi.get_user_guilds = dauth.get_user_guilds
dapi.verify_guild_permission = dauth.verify_guild_permission
dapi.verify_guild_permission_detailed = _fake_verify_detailed

app = Flask(__name__)
dapi.init_dashboard_api(app)


# PHASE O.2 — synthetic internal-error route (registered BEFORE any
# request is dispatched; Flask locks setup after the first request).
# Raises the exact production TypeError so the suite can prove the
# require_api wrapper sanitizes unexpected exceptions (Part 7).
@app.route("/api/dashboard/__boom__")
@dapi.require_api
def _synthetic_boom():
    raise TypeError("int() argument must be a string, a bytes-like object "
                    "or a real number, not '_EnumValue_ChannelType'")

SERVE = "--serve" in sys.argv
if SERVE:
    app.run(host="127.0.0.1", port=8081, threaded=True)
    sys.exit(0)

# ── Assertion suite (Flask test client) ────────────────────────────
client = app.test_client()
PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {extra}")


H = {"Authorization": "Bearer good-token"}

print("== auth ==")
r = client.get("/api/dashboard/user")
check("401 without token", r.status_code == 401)
r = client.get("/api/dashboard/user", headers={"Authorization": "Bearer nope"})
check("401 with bad token", r.status_code == 401)

r = client.get("/api/dashboard/user", headers=H)
body = r.get_json()
check("200 /user", r.status_code == 200)
check("/user shape", body["user"]["id"] == USER_ID
      and body["user"]["avatar"].startswith("https://cdn.discordapp.com"))
check("/user filters to manageable+bot guilds",
      [g["id"] for g in body["guilds"]] == [GUILD_ID],
      str(body["guilds"]))

print("== csrf ==")
r = client.get("/api/dashboard/csrf", headers=H)
csrf = r.get_json()["csrf_token"]
check("csrf issued", bool(csrf))
HC = {**H, "X-CSRF-Token": csrf, "Content-Type": "application/json"}

print("== guild guard ==")
r = client.get("/api/dashboard/guild/777/overview", headers=H)
check("403 guild without manage perms", r.status_code == 403)
r = client.get("/api/dashboard/guild/999999/overview", headers=H)
check("404 guild bot not in", r.status_code == 404)

print("== overview ==")
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/overview", headers=H)
ov = r.get_json()
check("200 overview", r.status_code == 200, str(ov)[:200])
check("overview fields", ov.get("name") == "veloura lounge"
      and ov.get("member_count") == 42 and ov.get("boost_count") == 2
      and str(ov.get("bot_joined_at", "")).startswith("2024-01-15")
      and "welcome" in ov.get("active_features", {})
      and "commands_used_7d" in ov.get("stats", {}), str(ov)[:200])
check("overview icon = raw Asset hash (a_ gif path), not the Asset object",
      ov.get("icon") == "a_1c2e3a4e5f6fakegif",
      f"got: {ov.get('icon')!r}")

print("== settings GET/PATCH ==")
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/settings/welcome", headers=H)
s = r.get_json()["settings"]
check("welcome defaults merged", s["embed_mode"] == "embed"
      and s["welcome_color"] == "#FFC0CB" and "message" in s)

r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/welcome",
                 headers=HC, json={"enabled": True})
check("PATCH without csrf 403 first?",
      True)  # placeholder ordering; real check below
# actually test no-csrf rejection
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/welcome",
                 headers={**H, "Content-Type": "application/json"},
                 json={"enabled": True})
check("PATCH rejected without CSRF", r.status_code == 403)

r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/welcome",
                 headers=HC, json={"enabled": True})
check("PATCH ok with csrf", r.status_code == 200
      and r.get_json()["settings"]["enabled"] is True)

r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/welcome",
                 headers=HC, json={"enabled": "yes"})
check("PATCH type validation 400", r.status_code == 400)

r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/welcome",
                 headers=HC, json={"bogus_field": 1})
check("PATCH unknown field 400 + allowed list",
      r.status_code == 400 and "allowed" in r.get_json())

r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/leveling",
                 headers=HC, json={"rewards": {"5": "201"}})
check("PATCH rewards ok", r.status_code == 200)
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/leveling",
                 headers=HC, json={"rewards": {"five": "201"}})
check("PATCH bad rewards 400", r.status_code == 400)

r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/custom_commands",
                 headers=HC, json={"commands": [
                     {"trigger": "hey", "response": "hello {user}"}]})
check("PATCH custom commands ok", r.status_code == 200)
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/custom_commands",
                 headers=HC, json={"commands": [{"trigger": "x"}]})
check("PATCH bad custom command 400", r.status_code == 400)

r = client.get(f"/api/dashboard/guild/{GUILD_ID}/settings/autorole", headers=H)
check("autorole JSON-only module works",
      r.status_code == 200 and "role_id" in r.get_json()["settings"])
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/autorole",
                 headers=HC, json={"role_id": "201"})
check("autorole PATCH persists to json",
      r.status_code == 200
      and r.get_json()["settings"]["role_id"] == "201")

r = client.get(f"/api/dashboard/guild/{GUILD_ID}/settings/giveaways", headers=H)
check("data-only module returns note", r.status_code == 200
      and r.get_json().get("data_endpoint", "").endswith("/module/giveaways/data"))

print("== settings persist (JSON fallback) ==")
data = json.load(open("data/welcome_settings.json"))
check("welcome written to JSON", data.get(GUILD_ID, {}).get("enabled") is True,
      str(data.get(GUILD_ID))[:120])
data = json.load(open("data/leveling_settings.json"))
check("rewards written to JSON",
      data.get(GUILD_ID, {}).get("rewards") == {"5": "201"},
      str(data.get(GUILD_ID))[:120])

print("== boosters module (PHASE O) ==")
from utils.dashboard_actions import dashboard_action_queue  # noqa: E402
# start from a clean slate so this section is re-run safe
try:
    _bs = json.load(open("data/booster_settings.json"))
    if _bs.pop(GUILD_ID, None) is not None:
        json.dump(_bs, open("data/booster_settings.json", "w"), indent=2)
except Exception:
    pass
try:
    dapi._db.cache.invalidate_sync(f"gs:booster_settings:{GUILD_ID}")
except Exception:
    pass
# DASH-33 — auth required
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters")
check("boosters settings need auth (401)", r.status_code == 401)
# DASH-34 — manage-guild required
g777 = client.get("/api/dashboard/guild/777/settings/boosters", headers=H)
check("boosters settings need manage_guild (403)",
      g777.status_code == 403)
# DASH-35 — CSRF required on mutation
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers={**H, "Content-Type": "application/json"},
                 json={"enabled": True})
check("boosters PATCH rejected without CSRF (403)", r.status_code == 403)

# defaults merged (template straight from utils/db.py)
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters", headers=H)
s = r.get_json()["settings"]
check("boosters defaults merged", r.status_code == 200
      and s["embed_mode"] == "embed" and s["color"] == "#FFC0CB"
      and s["milestone_counts"] == [2, 7, 14]
      and s["thumbnail_mode"] == "member"
      and s["remove_role_on_unboost"] is True
      and "a new star is shining brighter" in (s["message"] or ""),
      str(s)[:200])

# valid PATCH persists + milestone baseline pinned to current count (2)
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC,
                 json={"enabled": True, "channel_id": "100",
                       "booster_role_id": "201", "auto_role": True,
                       "milestone_counts": [2, 7, 14, 25]})
check("boosters PATCH ok (channel + role + milestones)",
      r.status_code == 200
      and r.get_json()["settings"]["channel_id"] == "100"
      and r.get_json()["settings"]["booster_role_id"] == "201"
      and r.get_json()["settings"]["milestone_counts"] == [2, 7, 14, 25],
      str(r.get_json())[:200])
check("milestone baseline pinned to current boost count on enable",
      r.get_json()["settings"]["milestone_last"] == 2,
      str(r.get_json()["settings"].get("milestone_last")))

# DASH-36 — managed role rejected server-side
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"booster_role_id": "203"})
check("boosters PATCH managed role → 400",
      r.status_code == 400 and "managed" in r.get_json().get("error", ""),
      str(r.get_json()))
# role above the bot rejected
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"booster_role_id": "204"})
check("boosters PATCH role above bot → 400",
      r.status_code == 400 and "top role" in r.get_json().get("error", ""),
      str(r.get_json()))
# value validation
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"embed_mode": "bogus"})
check("boosters PATCH bad embed_mode → 400", r.status_code == 400)
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"color": "pink!"})
check("boosters PATCH bad color → 400", r.status_code == 400)
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"image_url": "ftp://x"})
check("boosters PATCH bad image_url → 400", r.status_code == 400)
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"milestone_counts": [0, 2]})
check("boosters PATCH bad milestone list → 400", r.status_code == 400)
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"enabled": "yes"})
check("boosters PATCH wrong type → 400", r.status_code == 400)

# role pickers never list managed roles (gateway fallback path)
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/resources", headers=H)
res = r.get_json()
check("role picker filters managed + above-bot roles (DASH-36)",
      [ro["name"] for ro in res["roles"]] == ["veloura", "midnight"],
      str([ro["name"] for ro in res["roles"]]))

# boosters actions queue correctly
r = client.post(f"/api/dashboard/guild/{GUILD_ID}/action/booster_test",
                headers=HC, json={})
check("booster_test action queued", r.status_code == 200
      and r.get_json()["queued"] is True)
r = client.post(f"/api/dashboard/guild/{GUILD_ID}/action/booster_reset",
                headers=HC, json={})
check("booster_reset action queued", r.status_code == 200
      and r.get_json()["queued"] is True)
_qtypes = []
while dashboard_action_queue.qsize():
    item = dashboard_action_queue.get_nowait()
    _qtypes.append(item["type"])
check("booster action payloads well-formed",
      _qtypes == ["booster_test", "booster_reset"], str(_qtypes))

# persisted to the JSON fallback store
bdata = json.load(open("data/booster_settings.json")).get(GUILD_ID, {})
check("boosters written to JSON fallback",
      bdata.get("channel_id") == "100"
      and bdata.get("booster_role_id") == "201"
      and bdata.get("milestone_counts") == [2, 7, 14, 25]
      and bdata.get("milestone_last") == 2,
      str(bdata)[:200])

print("== PHASE O.2 — real discord.py ChannelType regression ==")
# ── 1. the harness now models production: real enum members ─────────
_real_ch = fake_guild.get_channel(100)
check("FakeChannel.type is a REAL ChannelType enum member",
      type(_real_ch.type).__name__ == "_EnumValue_ChannelType"
      and _real_ch.type is discord.ChannelType.text
      and _real_ch.type.value == 0
      and isinstance(_real_ch.type.value, int),
      f"type={type(_real_ch.type).__name__} value={getattr(_real_ch.type, 'value', None)!r}")

# ── 2. PROOF the old implementation raises the exact production error ─
# This is the verbatim old expression from _validate_boosters_targets
# (pre-O.2):   ctype = int(getattr(channel, "type", 0) or 0)
_old_expr_raised = None
try:
    int(getattr(_real_ch, "type", 0) or 0)      # ← the OLD code
except TypeError as e:
    _old_expr_raised = str(e)
check("OLD int(channel.type) raises the production TypeError",
      _old_expr_raised is not None
      and "_EnumValue_ChannelType" in _old_expr_raised,
      f"raised: {_old_expr_raised!r}")

# ── 3. the central normalizer handles every real representation ─────
check("shared _channel_type_int normalizes real enums to JSON-safe ints",
      dapi._channel_type_int(discord.ChannelType.text, default=None) == 0
      and dapi._channel_type_int(discord.ChannelType.news, default=None) == 5
      and dapi._channel_type_int(discord.ChannelType.voice, default=None) == 2
      and dapi._channel_type_int(discord.ChannelType.category, default=None) == 4
      and dapi._channel_type_int(discord.ChannelType.forum, default=None) == 15
      and dapi._channel_type_int(discord.ChannelType.media, default=None) == 16
      and dapi._channel_type_int("5") == 5
      and dapi._channel_type_int(None, default=None) is None)

# ── 4. the exact production flow: PATCH a real-enum channel → 200 ───
# (with the OLD code this was the 500 "internal error (TypeError: …)")
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"channel_id": "103"})
check("BOOSTERS SAVE with real ChannelType.text channel → 200",
      r.status_code == 200
      and r.get_json()["settings"]["channel_id"] == "103",
      str(r.get_json())[:200])
check("no internal-error/TypeError text in the save response",
      "error" not in r.get_json(), str(r.get_json())[:120])

# ── 5. valid announcement channel types are accepted ────────────────
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"channel_id": "101"})
check("announcement (news, type 5) channel accepted → 200",
      r.status_code == 200
      and r.get_json()["settings"]["channel_id"] == "101")
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"channel_id": "104"})
check("forum channel (type 15) accepted → 200 (intentional)",
      r.status_code == 200)
r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"channel_id": "105"})
check("media channel (type 16) accepted → 200 (intentional)",
      r.status_code == 200)

# ── 6. non-sendable / non-text targets are REJECTED cleanly (400) ───
for cid, label in (("102", "voice"), ("106", "stage"),
                   ("107", "category"), ("108", "unknown/future type")):
    r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                     headers=HC, json={"channel_id": cid})
    err = r.get_json().get("error", "")
    check(f"{label} channel → clean 400, never a 500",
          r.status_code == 400 and "text channel" in err,
          f"{r.status_code}: {err[:120]}")

r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"channel_id": "109"})
err = r.get_json().get("error", "")
check("non-sendable channel → clean 400 with actionable message",
      r.status_code == 400 and "cannot send" in err,
      f"{r.status_code}: {err[:120]}")

r = client.patch(f"/api/dashboard/guild/{GUILD_ID}/settings/boosters",
                 headers=HC, json={"channel_id": "55555"})
check("unknown channel id → clean 400",
      r.status_code == 400
      and "not found" in r.get_json().get("error", ""))

# ── 7. listing never leaks raw enum objects into JSON ────────────────
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/resources", headers=H)
res = r.get_json()
check("all resource channel types serialize as plain ints",
      r.status_code == 200
      and len(res["channels"]) >= 10
      and all(isinstance(c["type"], int) and not isinstance(c["type"], bool)
              for c in res["channels"]),
      str([c["type"] for c in res.get("channels", [])])[:200])
check("locked channel flagged not-sendable for the pickers",
      any(c["name"] == "locked" and c["bot_can_send"] is False
          for c in res["channels"]))

# ── 8. sanitized internal errors (PHASE O.2 Part 7) ─────────────────
# route registered at app-init time above; raise the exact production
# exception shape and check what the wrapper actually returns
r = client.get("/api/dashboard/__boom__", headers=H)
_boom = r.get_json()
check("unexpected exceptions → sanitized 500 (no raw Python text)",
      r.status_code == 500
      and "TypeError" not in _boom.get("error", "")
      and "_EnumValue" not in _boom.get("error", "")
      and "int()" not in _boom.get("error", "")
      and "ref" in _boom.get("error", "")
      and "refresh" in _boom.get("error", ""),
      str(_boom))

print("== actions ==")
r = client.post(f"/api/dashboard/guild/{GUILD_ID}/action/qotd_post_now",
                headers=HC, json={})
check("action queued", r.status_code == 200 and r.get_json()["queued"] is True)
from utils.dashboard_actions import dashboard_action_queue
check("queue received action", dashboard_action_queue.qsize() == 1)
item = dashboard_action_queue.get_nowait()
check("action payload shape", item["type"] == "qotd_post_now"
      and item["guild_id"] == GUILD_ID and item["user_id"] == USER_ID)

r = client.post(f"/api/dashboard/guild/{GUILD_ID}/action/not_real",
                headers=HC, json={})
check("unknown action 404", r.status_code == 404)
r = client.post(f"/api/dashboard/guild/{GUILD_ID}/action/welcome_test",
                headers=HC, json={"type": "bogus"})
check("welcome_test bad type 400", r.status_code == 400)

print("== module data ==")
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/module/warnings/data?page=1",
               headers=H)
check("warnings data paginated", r.status_code == 200
      and "warnings" in r.get_json() and "total" in r.get_json())
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/module/custom_commands/data",
               headers=H)
check("custom_commands data", r.status_code == 200
      and r.get_json()["custom_commands"][0]["trigger"] == "hey")
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/module/giveaways/data", headers=H)
check("giveaways data", r.status_code == 200 and "active" in r.get_json())
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/module/level_rewards/data",
               headers=H)
check("level_rewards data", r.status_code == 200
      and r.get_json()["rewards"][0]["role_name"] == "veloura",
      str(r.get_json()))
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/module/qotd/data", headers=H)
check("qotd queue data (asyncio.run in thread)", r.status_code == 200)
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/module/stats/data", headers=H)
check("stats data", r.status_code == 200 and "series" in r.get_json())
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/module/nope/data", headers=H)
check("unknown data module 404", r.status_code == 404)

print("== polls data (new) ==")
# seed two polls: one live for this guild, one ended, one foreign guild
_polls = {
    "900": {"guild_id": GUILD_ID, "channel_id": "100", "question": "movie night?",
            "options": ["friday", "saturday"], "author_name": "volc",
            "end_time": 9999999999, "ended": False},
    "901": {"guild_id": GUILD_ID, "channel_id": "100", "question": "old poll",
            "options": ["a", "b"], "author_name": "volc",
            "end_time": None, "ended": True},
    "902": {"guild_id": "555555", "channel_id": "1", "question": "other server",
            "options": ["x"], "author_name": "someone",
            "end_time": None, "ended": False},
}
json.dump(_polls, open("data/polls.json", "w"))
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/module/polls/data", headers=H)
pdata = r.get_json()
check("polls data 200", r.status_code == 200, str(pdata)[:200])
check("polls data: only this guild's ACTIVE polls",
      [p["message_id"] for p in pdata.get("polls", [])] == ["900"],
      str(pdata)[:200])
check("polls row shape",
      pdata["polls"][0]["question"] == "movie night?"
      and pdata["polls"][0]["options"] == ["friday", "saturday"]
      and pdata["polls"][0]["author_name"] == "volc"
      and pdata["polls"][0]["channel_id"] == "100")

print("== delete data ==")
r = client.delete(f"/api/dashboard/guild/{GUILD_ID}/data/custom_commands/hey",
                  headers=HC)
check("delete custom command", r.status_code == 200)
r = client.delete(f"/api/dashboard/guild/{GUILD_ID}/data/custom_commands/hey",
                  headers=HC)
check("delete again -> 404", r.status_code == 404)
r = client.delete(f"/api/dashboard/guild/{GUILD_ID}/data/warnings/123",
                  headers=HC)
check("delete unknown warning 404", r.status_code == 404)

print("== resources ==")
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/resources", headers=H)
res = r.get_json()
check("resources channels", r.status_code == 200
      and any(c["name"] == "general" for c in res["channels"]))
check("resources roles skip @everyone+managed",
      [ro["name"] for ro in res["roles"]] == ["veloura", "midnight"])
check("resources bot perms", res["bot_permissions"]["manage_roles"] is True)

print("== audit ==")
r = client.get(f"/api/dashboard/guild/{GUILD_ID}/audit", headers=H)
check("audit entries recorded", r.status_code == 200
      and len(r.get_json()["entries"]) > 0,
      str(r.get_json())[:150])

print("== owner ==")
r = client.get("/api/dashboard/owner/logs", headers=H)
check("owner endpoint 403 when OWNER_ID unset", r.status_code == 403)
dapi.OWNER_ID = USER_ID
r = client.get("/api/dashboard/owner/logs?lines=5", headers=H)
check("owner logs with OWNER_ID", r.status_code == 200
      and isinstance(r.get_json()["lines"], list))
r = client.post("/api/dashboard/owner/reload_cog", headers=HC,
                json={"cog": "welcome"})
check("owner reload_cog queued", r.status_code == 200
      and dashboard_action_queue.qsize() == 1)
dashboard_action_queue.get_nowait()
r = client.post("/api/dashboard/owner/blacklist_add", headers=HC,
                json={"user_id": "123"})
check("owner blacklist queued", r.status_code == 200)
dashboard_action_queue.get_nowait()

print("== rate limit (150 reads / 60 mutations per min) ==")
dapi._rl_map.clear()
limited_at = None
for i in range(160):
    r = client.get("/api/dashboard/csrf", headers=H)
    if r.status_code == 429:
        limited_at = i
        break
check("GET rate limit kicks in <= 150/min",
      limited_at is not None and limited_at >= 145, f"hit at {limited_at}")

dapi._rl_map.clear()
limited_at = None
for i in range(70):
    r = client.post(f"/api/dashboard/guild/{GUILD_ID}/action/not_real",
                    headers=HC, json={})
    if r.status_code == 429:
        limited_at = i
        break
check("mutation rate limit kicks in <= 60/min",
      limited_at is not None and limited_at >= 55, f"hit at {limited_at}")

print("== CORS ==")
r = client.get("/api/dashboard/user", headers={**H, "Origin": "http://localhost:3000"})
check("CORS allows localhost dev origin",
      r.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000")
r = client.get("/api/dashboard/user", headers={**H, "Origin": "https://evil.example"})
check("CORS blocks unknown origin",
      "Access-Control-Allow-Origin" not in r.headers)

print("== oauth callback (no creds configured) ==")
r = client.get("/api/dashboard/oauth/callback?code=abc")
check("oauth callback without config -> 500 json", r.status_code == 500)

print()
print(f"RESULT: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
