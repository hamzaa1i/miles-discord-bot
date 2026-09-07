#!/usr/bin/env python3
"""
scripts/test_phase_n1.py — PHASE N.1 regression suite.

ALL AI PROVIDERS ARE MOCKED. This suite never contacts Gemini, Mistral,
OpenRouter or Groq — provider behavior is simulated with fakes and the
SDK classifiers are exercised with real exception objects raised
client-side (no network). No live quota is ever consumed (the ONLY live
diagnostic is scripts/test_ai_providers_live.py, env-gated, never run
by any test).

The 27 required Phase N.1 regressions:

  AI 1   exact GLM production leak       -> sanitized to EMPTY
  AI 2   meta-only provider output       -> router fails over
  AI 3   "we should probably use websockets…" -> PRESERVED (real prose)
  AI 4   HTTP 429                        -> RATE_LIMIT
  AI 5   HTTP 401                        -> AUTH
  AI 6   404 vs 400                      -> MODEL_UNAVAILABLE vs BAD_REQUEST
  AI 7   HTTP 200 + meta-only            -> SANITIZATION_EMPTY failure
  AI 8   configured != healthy           -> "unknown" until a real success
  AI 9   facade final guard              -> leaked meta never reaches a cog
  AI 10  casual replies                  -> unchanged (corpus E + friends)
  AI 11  Gemini request                  -> AFC disabled, no tools attached
  AI 12  Mistral adapter                 -> structural validation, mocked SDK

  CD 13  /recap cooldown                 -> exactly ONE ephemeral response
  CD 14  global handler / no local       -> exactly ONE response; 60s kept

  DM 15  achievements unlock with DMs off -> unlock saved, DM suppressed
  DM 16  achievements unlock with DMs on  -> DM sent
  DM 17  leveling dm-mode + onboarding    -> gated by shared preference
  DM 18  explicit DM flows                -> NOT gated (capsules, welcome test)
  DM 19  /toggledms semantics + wording  -> shared store, "passive DMs"

  CAP 20 Supabase capsule insert         -> ISO-8601 (22007 root cause)
  CAP 21 due query                       -> compares ISO, not epoch float
  CAP 22 Supabase rows                   -> normalized to epoch floats
  CAP 23 create -> not due               -> JSON fallback lifecycle
  CAP 24 not due -> due                  -> due query finds it
  CAP 25 due -> unlocked                 -> terminal state
  CAP 26 JSON fallback format            -> floats preserved

  CNT 27 canonical command counts        -> 46 cogs / 73 top-level / 169
         total invokable, consistent across every current surface

Run:  python3 scripts/test_phase_n1.py
"""
import asyncio
import json
import logging
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


# ═══ THE EXACT GLM LEAK THAT REACHED PRODUCTION (P0) ═════════════════
GLM_PRODUCTION_LEAK = (
    "We must not start two responses with same word; we only have one "
    "response now, okay. We must not mention creator unless asked. We "
    "must not say \"as an AI\". Should not mention we lack real-time "
    "data. Provide the answer. We must keep under maybe moderate "
    "length, but can be multiple paragraphs. No restriction on length "
    "for technical answer. Keep lowercase. Let's produce: \"yes volc\" "
    "then answer. We should include points: authentication (token, "
    "session), scaling (horizontal, stateless), latency (ws low, sse "
    "moderate, rest high), implementation complexity (ws high, sse "
    "medium, rest"
)

LEGIT_WEBSOCKETS_PROSE = (
    "we should probably use websockets here because they offer "
    "bidirectional communication."
)

# ─── fake provider machinery (zero network) ──────────────────────────
from utils.ai_types import AIResult, AIRequestError, AIFailureCategory
import utils.ai_config as cfg
import utils.ai_router as ar
from utils.ai_router import AIRouter, set_router
import utils.db as udb
import utils.ai_sanitize as san


class FakeProvider:
    """Configurable fake: scripts responses/errors per call."""
    name = "fake"

    def __init__(self, name: str, key: str = "k"):
        self.name = name
        self._key = key
        self.calls = 0
        self.script = None
        self.default_text = f"reply from {name}"

    @property
    def configured(self):
        return bool(self._key)

    def model_ids(self):
        return {"chat": f"{self.name}-model"}

    async def generate(self, messages, model, max_tokens, temperature,
                       reasoning_level=None, timeout_seconds=30.0):
        self.calls += 1
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, AIRequestError):
                raise item
            if isinstance(item, AIResult):
                return item
            return AIResult(text=str(item), provider=self.name, model=model)
        return AIResult(text=self.default_text, provider=self.name,
                        model=model, input_tokens=10, output_tokens=20)

    async def close(self):
        pass


def build_router():
    """Fresh AIRouter with fakes; singleton swapped so the facade uses
    ONLY the fakes."""
    import importlib
    for k in ("GEMINI_API_KEY", "MISTRAL_API_KEY",
              "OPENROUTER_API_KEY", "GROQ_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update({"AI_ROUTER_ENABLED": "true"})
    importlib.reload(cfg)
    importlib.reload(ar)

    fakes = {
        "gemini": FakeProvider("gemini"),
        "mistral": FakeProvider("mistral"),
        "openrouter": FakeProvider("openrouter"),
        "groq": FakeProvider("groq"),
    }
    router = AIRouter(providers=fakes)
    router._keep_alive_metrics = False
    set_router(router)
    return router, fakes


# ─── fake Supabase (records boundary values; zero network) ──────────

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
        self.filters[col] = ("eq", val)
        return self

    def lte(self, col, val):
        self.filters[col] = ("lte", val)
        return self

    def order(self, _col, desc=False):
        return self

    def limit(self, _n):
        return self

    def update(self, payload):
        self.payload = payload
        self.op = "update"
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        self.rec.calls.append({
            "table": self.table, "op": self.op,
            "filters": dict(self.filters), "payload": self.payload,
        })
        resp = MagicMock()
        if self.op == "insert" and self.payload:
            resp.data = [dict(self.payload, id=9001)]
        elif self.op == "insert":
            resp.data = [{"id": 9001}]
        else:
            resp.data = self.rec.rows
        return resp


class FakeSupabase:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def table(self, name):
        return FakeSBQuery(self, name, "select")


# ═══ AI 1–12 ═══════════════════════════════════════════════════════

async def test_ai():
    print("\n── AI core: sanitizer · router · providers · facade ──")

    # AI-1 — the exact production leak sanitizes to EMPTY
    out = san.sanitize_output(GLM_PRODUCTION_LEAK)
    check("AI-1  exact GLM production leak → EMPTY (never reaches discord)",
          out == "" and san.is_empty_content(out),
          f"got {out[:80]!r}")

    # AI-3 — legitimate prose that MENTIONS the vocabulary survives
    out = san.sanitize_output(LEGIT_WEBSOCKETS_PROSE)
    check("AI-3  legit 'we should probably use websockets…' preserved",
          out.strip().lower() == LEGIT_WEBSOCKETS_PROSE.strip().lower(),
          f"got {out!r}")

    # AI-10 — casual replies and the rest of the corpus
    casual_1 = san.sanitize_output("let me think about that ♡")
    casual_2 = san.sanitize_output("hmm, let me pick — probably 7!")
    corpus_a = san.sanitize_output(
        "I need to craft a perfect reply. The rules say to be brief.\n\n"
        "sure, here's how redis pub/sub works: channels are simple."
    )
    corpus_f = san.sanitize_output(
        "<thinking>internal scratch pad never shown</thinking>\n\n"
        "the visible answer is 42."
    )
    corpus_g = san.sanitize_output(
        "We need to answer concisely. Here goes: recursion is when a "
        "function calls itself."
    )
    check("AI-10 casual replies unchanged (corpus E + friends)",
          casual_1.strip() == "let me think about that ♡"
          and "7" in casual_2
          and "redis pub/sub" in corpus_a
          and "recursion is when" in corpus_g
          and "42" in corpus_f
          and "internal scratch" not in corpus_f,
          f"a={corpus_a!r} f={corpus_f!r} g={corpus_g!r}")

    # AI-2 + AI-7 — router failover on meta-only output + accounting
    router, fakes = build_router()
    fakes["gemini"].script = [GLM_PRODUCTION_LEAK]
    fakes["mistral"].script = [AIResult(
        text="mistral answer: use a websocket for live updates",
        provider="mistral", model="m")]
    from utils.ai_types import AIProfile
    result = await router.route(
        [{"role": "user", "content": "ws or rest?"}], AIProfile.CHAT)
    gem_health = router._health["gemini"]
    check("AI-2  meta-only provider output → failover to next provider",
          result.provider == "mistral"
          and "mistral answer" in result.text
          and result.failed_over_from == ["gemini"])
    check("AI-7  HTTP 200 + meta-only = SANITIZATION_EMPTY FAILURE "
          "(counted, not green)",
          gem_health.total_successes == 0
          and gem_health.total_failures >= 1
          and gem_health.last_error_category == "sanitization_empty"
          and gem_health.last_error_status == 200
          and gem_health.state("true" and True) != "healthy")

    # AI-7b — raw EMPTY text is EMPTY_RESPONSE, distinct category
    router2, fakes2 = build_router()
    fakes2["gemini"].script = [AIResult(text="   ", provider="gemini",
                                        model="g")]
    fakes2["mistral"].script = ["mistral fallback ok"]
    res2 = await router2.route(
        [{"role": "user", "content": "hi"}], AIProfile.CHAT)
    check("AI-7b raw-empty output → EMPTY_RESPONSE (distinct category)",
          res2.provider == "mistral"
          and router2._health["gemini"].last_error_category
          == "empty_response")

    # AI-8 — configured != healthy
    router3, fakes3 = build_router()
    snap = router3.status_snapshot()
    states = {n: p["state"] for n, p in snap["providers"].items()}
    check("AI-8  configured-but-unverified providers are 'unknown', "
          "never 'healthy'",
          all(s == "unknown" for s in states.values())
          and snap["ai_status"] == "unknown", f"states={states}")
    await router3.route([{"role": "user", "content": "hi"}],
                        AIProfile.CHAT)
    snap = router3.status_snapshot()
    check("AI-8b one real success → that provider becomes 'healthy'",
          snap["providers"]["gemini"]["state"] == "healthy")

    # AI-9 — facade final output guard (defense in depth)
    router4, _ = build_router()

    class LeakyRouter:
        """Simulates a SANITIZER REGRESSION: route() returns the raw
        leak as already-'sanitized' text. The facade guard must catch
        it at the boundary so no cog ever receives it."""
        async def route(self, messages, profile, max_tokens=300,
                        temperature=0.9):
            return AIResult(text=GLM_PRODUCTION_LEAK,
                            provider="openrouter", model="z-ai/glm-5.2:free")

    set_router(LeakyRouter())
    import utils.ai_handler as ah
    import importlib as _il
    _il.reload(ah)
    from utils.ai_handler import call_ai_profile as _cap
    guarded = await _cap(
        [{"role": "user", "content": "ws or rest"}], AIProfile.CHAT)
    check("AI-9  facade final guard: leaked meta replaced by graceful "
          "fallback (never shown)",
          guarded == ah._EMPTY_CONTENT_FALLBACK
          and "We must not" not in guarded)

    # AI-4/5/6 — provider error classifiers against REAL SDK exceptions
    from ai_providers.gemini_provider import _classify_error as gcls
    from ai_providers.mistral_provider import _classify_error as mcls
    from ai_providers.groq_provider import _classify_error as qcls
    from ai_providers.openrouter_provider import _classify_error as ocls
    from google.genai import errors as gerrs

    e429 = gcls(gerrs.ClientError(429, "resource exhausted retry 30s"))
    e401 = gcls(gerrs.ClientError(401, "unauthenticated"))
    e404 = gcls(gerrs.ClientError(404, "model not found"))
    e400 = gcls(gerrs.ClientError(400, "invalid argument"))
    check("AI-4  HTTP 429 → RATE_LIMIT (+ retry hint, status 429)",
          e429.category == AIFailureCategory.RATE_LIMIT
          and e429.status_code == 429 and e429.retry_after == 30.0)
    check("AI-5  HTTP 401 → AUTH",
          e401.category == AIFailureCategory.AUTH
          and e401.status_code == 401)

    class FakeSDKError(Exception):
        """Mirrors mistralai.client.errors.sdkerror.SDKError shape
        (verified against mistralai 2.9.4: status_code attr + 'Status
        NNN. Body:' string)."""
        def __init__(self, code, body=""):
            self.status_code = code
            super().__init__(f"API error occurred: Status {code}. "
                             f"Body: {body}")

    m401 = mcls(FakeSDKError(401, '{"detail":"Invalid API Key"}'))
    m404 = mcls(FakeSDKError(404, '{"message":"model not found"}'))
    m400 = mcls(FakeSDKError(400, '{"message":"bad request shape"}'))
    o400 = ocls(400, '{"error":{"message":"temperature out of range"}}')
    o404 = ocls(404, '{"error":{"message":"model decommissioned"}}')
    q400 = qcls(Exception("400 invalid_request_error: messages[0] bad"))
    check("AI-6  404 → MODEL_UNAVAILABLE; 400 → BAD_REQUEST "
          "(all four adapters)",
          e404.category == AIFailureCategory.MODEL_UNAVAILABLE
          and m401.category == AIFailureCategory.AUTH
          and m404.category == AIFailureCategory.MODEL_UNAVAILABLE
          and m400.category == AIFailureCategory.BAD_REQUEST
          and o400.category == AIFailureCategory.BAD_REQUEST
          and o404.category == AIFailureCategory.MODEL_UNAVAILABLE
          and q400.category == AIFailureCategory.BAD_REQUEST,
          f"m400={m400.category} o400={o400.category} q400={q400.category}")

    # AI-11 — Gemini request: AFC explicitly disabled, no tools
    from ai_providers.gemini_provider import GeminiProvider
    gp = GeminiProvider(api_key="test-key")
    captured = {}

    class FakeAsyncModels:
        async def generate_content(self, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            resp = MagicMock()
            part = MagicMock(); part.text = "ok"
            cand = MagicMock(); cand.content.parts = [part]
            cand.finish_reason = "STOP"
            resp.candidates = [cand]
            resp.usage_metadata = None
            return resp

    class FakeClient:
        def __init__(self):
            self.aio = MagicMock()
            self.aio.models = FakeAsyncModels()

    gp._client = FakeClient()
    await gp.generate(
        messages=[{"role": "user", "content": "say ok"}],
        model="gemini-3.7-flash", max_tokens=32, temperature=0.0)
    conf = captured["config"]
    afc = getattr(conf, "automatic_function_calling", None)
    check("AI-11 Gemini config: automatic_function_calling.disable=True, "
          "no tools ever attached",
          afc is not None and afc.disable is True
          and getattr(conf, "tools", None) is None
          and getattr(conf, "tool_config", None) is None,
          f"afc={afc} tools={getattr(conf, 'tools', 'MISSING')}")

    # AI-12 — Mistral adapter structural validation (mocked SDK shape)
    from ai_providers.mistral_provider import MistralProvider
    mp = MistralProvider(api_key="test-key")
    check("AI-12a mistral v2 import line resolves (mistralai.client)",
          mp.configured is True)

    class FakeChat:
        async def complete_async(self, model, messages, temperature,
                                 max_tokens, **kw):
            captured["mistral_payload"] = {
                "model": model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens}
            msg = MagicMock(); msg.content = "mistral says hi"
            choice = MagicMock(); choice.message = msg
            choice.finish_reason = "stop"
            resp = MagicMock(); resp.choices = [choice]
            usage = MagicMock()
            usage.prompt_tokens = 5
            usage.completion_tokens = 4
            resp.usage = usage
            return resp

    class FakeMistralClient:
        def __init__(self):
            self.chat = FakeChat()

    mp._client = FakeMistralClient()
    mres = await mp.generate(
        messages=[{"role": "system", "content": "be brief"},
                  {"role": "user", "content": "hi"}],
        model="mistral-small-2603", max_tokens=32, temperature=0.2)
    payload = captured.get("mistral_payload", {})
    check("AI-12b mocked SDK response → text + tokens extracted, "
          "system/user/assistant roles pass through",
          mres.text == "mistral says hi"
          and mres.input_tokens == 5 and mres.output_tokens == 4
          and payload.get("messages") == [
              {"role": "system", "content": "be brief"},
              {"role": "user", "content": "hi"}])


# ═══ CD 13–14 — duplicate cooldown fix ═════════════════════════════

class FakeInteraction:
    """Minimal discord.Interaction double for error-handler tests.
    response.send_message flips is_done() like the real API wrapper."""
    def __init__(self, done=False):
        self._done = done
        self.response = MagicMock()
        self.response.is_done = lambda: self._done
        self.response.send_message = AsyncMock(
            side_effect=self._mark_done)
        self.followup = MagicMock()
        self.followup.send = AsyncMock()
        self.command = MagicMock()
        self.command.name = "recap"
        self.user = MagicMock()
        self.user.id = 42

    async def _mark_done(self, *a, **kw):
        self._done = True

    def total_sends(self):
        return (self.response.send_message.await_count
                + self.followup.send.await_count)


async def test_cooldown():
    print("\n── cooldown: exactly ONE response ──")
    import main as main_mod
    from discord import app_commands as _ac

    cooldown_err = _ac.CommandOnCooldown(60.0, 48.9)

    # Scenario A (the production bug): local handler already responded.
    itx = FakeInteraction(done=True)
    await main_mod.bot.tree.on_error(itx, cooldown_err)
    check("CD-13 local handler answered → global handler stays SILENT "
          "(one response total)",
          itx.total_sends() == 0)

    # Scenario B: no local handler → global handler answers exactly once.
    itx2 = FakeInteraction(done=False)
    await main_mod.bot.tree.on_error(itx2, cooldown_err)
    check("CD-14 no local handler → global handler sends exactly ONE "
          "cooldown message",
          itx2.total_sends() == 1
          and "Slow down" in str(
              itx2.response.send_message.call_args))

    # Scenario C: recap's local handler responds once; the follow-on
    # global call (discord.py always calls both) adds nothing.
    from cogs.recap import Recap
    recap_cog = Recap.__new__(Recap)      # no bot needed for the handler
    recap_cog.bot = MagicMock()
    itx3 = FakeInteraction(done=False)
    await recap_cog.recap_error(itx3, cooldown_err)
    first = itx3.total_sends()
    await main_mod.bot.tree.on_error(itx3, cooldown_err)
    check("CD-13b /recap local + global sequence → exactly ONE response "
          "(was TWO in production)",
          first == 1 and itx3.total_sends() == 1
          and "slow down" in str(
              itx3.response.send_message.call_args))

    # 60s cooldown kept
    src = open("cogs/recap.py", encoding="utf-8").read()
    check("CD-14b /recap cooldown stays 60s",
          "cooldown(1, 60.0" in src)


# ═══ DM 15–19 — passive DM gating ══════════════════════════════════

class FakeMember:
    def __init__(self, uid=555):
        self.id = uid
        self.display_name = "tester"
        self.mention = f"<@{uid}>"
        self.send = AsyncMock()
        self.roles = []
        self.add_roles = AsyncMock()


async def test_dm():
    print("\n── passive DMs: /toggledms governs, explicit flows survive ──")
    tmp = tempfile.mkdtemp(prefix="n1_dm_")
    dm_file = os.path.join(tmp, "dm_prefs.json")
    orig_dm_path = udb._DM_PREFS_JSON
    udb._DM_PREFS_JSON = dm_file

    try:
        # DM-19 — semantics of the shared preference
        check("DM-19 default is allow (no stored preference, no silent "
              "flips)",
              udb.user_allows_passive_dms(555) is True)
        udb.set_user_allows_passive_dms(555, False)
        check("DM-19b /toggledms off is stored and respected "
              "(shared file)",
              udb.user_allows_passive_dms(555) is False
              and json.load(open(dm_file))["555"]["dms_enabled"] is False)
        udb.set_user_allows_passive_dms(555, True)
        check("DM-19c /toggledms on restores DMs",
              udb.user_allows_passive_dms(555) is True)
        welcome_src = open("cogs/welcome.py", encoding="utf-8").read()
        check("DM-19d /toggledms wording says 'passive aurelia DMs'",
              "passive aurelia DMs are now" in welcome_src)

        # ── achievements ──
        from cogs.achievements import Achievements, LEVEL_ACHIEVEMENTS
        import cogs.achievements as ach_mod
        cog = Achievements.__new__(Achievements)
        cog.bot = MagicMock()
        member = FakeMember(555)

        unlock_calls = []

        async def fake_unlock(guild_id, user_id, key):
            unlock_calls.append((guild_id, user_id, key))
            return True

        orig_unlock = ach_mod._db.unlock_achievement_async
        ach_mod._db.unlock_achievement_async = fake_unlock
        try:
            key = next(iter(LEVEL_ACHIEVEMENTS.values()))
            guild = MagicMock(); guild.id = 100

            udb.set_user_allows_passive_dms(555, False)
            ok = await cog._try_unlock(guild, member, key)
            check("DM-15 DMs off: achievement STILL unlocks + saves, only "
                  "the DM is suppressed",
                  ok is True and unlock_calls
                  and member.send.await_count == 0)

            udb.set_user_allows_passive_dms(555, True)
            ok2 = await cog._try_unlock(guild, member, "confession")
            check("DM-16 DMs on: achievement DM is sent",
                  ok2 is True and member.send.await_count == 1)
        finally:
            ach_mod._db.unlock_achievement_async = orig_unlock

        # ── leveling dm mode ──
        from cogs.leveling import Leveling
        lcog = Leveling.__new__(Leveling)
        lcog.bot = MagicMock()
        lcog.bot.get_cog = lambda _n: None
        member2 = FakeMember(556)
        guild2 = MagicMock(); guild2.id = 200
        guild2.name = "srv"; guild2.member_count = 5
        guild2.get_role = lambda _r: None

        def cfg_off(gid):
            return {"level_up_channel_mode": "dm"}

        def cfg_on(gid):
            return {"level_up_channel_mode": "active"}

        udb.set_user_allows_passive_dms(556, False)
        lcog.get_config = cfg_off
        await lcog.announce_levelup(guild2, member2, 10)
        check("DM-17a leveling dm-mode with DMs off → NO DM "
              "(level-up itself unaffected)",
              member2.send.await_count == 0)

        udb.set_user_allows_passive_dms(556, True)
        await lcog.announce_levelup(guild2, member2, 11)
        check("DM-17b leveling dm-mode with DMs on → DM sent",
              member2.send.await_count == 1)

        # ── onboarding join panel ──
        from cogs.onboarding import Onboarding
        ocog = Onboarding.__new__(Onboarding)
        ocog.bot = MagicMock()

        async def fake_get_cfg(gid):
            return {"enabled": True, "roles": [{"role_id": 1,
                                                "label": "x"}]}

        ocog._get_config = fake_get_cfg

        def fake_panel(_cfg, member, _guild):
            return MagicMock(), MagicMock()

        ocog._build_panel = fake_panel
        member3 = FakeMember(557)
        udb.set_user_allows_passive_dms(557, False)
        await ocog.on_member_join(member3)
        check("DM-17c onboarding join panel with DMs off → NOT sent",
              member3.send.await_count == 0)

        # ── explicit flows stay ungated ──
        from cogs.capsules import Capsules
        ccog = Capsules.__new__(Capsules)
        ccog.bot = MagicMock()
        fake_user = FakeMember(558)
        ccog.bot.fetch_user = AsyncMock(return_value=fake_user)
        ccog.bot.get_guild = lambda _g: None
        row = {"id": 7, "user_id": "558", "guild_id": "100",
               "channel_id": None, "is_public": False,
               "message": "from the past ♡",
               "unlock_time": 1000.0, "unlocked": False,
               "created_at": "2026-01-01T00:00:00"}
        udb.set_user_allows_passive_dms(558, False)
        await ccog._deliver(row)
        check("DM-18a private time-capsule delivery is EXPLICIT → still "
              "DMs even with passive DMs off",
              fake_user.send.await_count == 1)

        welcome_src = open("cogs/welcome.py", encoding="utf-8").read()
        test_dm_block = welcome_src.split("if type_value == \"dm\":")[1][:800]
        check("DM-18b /welcome test type:dm path has NO passive-DM gate "
              "(explicit test)",
              "user_allows_passive_dms" not in test_dm_block)
    finally:
        udb._DM_PREFS_JSON = orig_dm_path
        set_router(None)


# ═══ CAP 20–26 — time capsule TIMESTAMPTZ boundary ═════════════════

async def test_capsules():
    print("\n── capsules: ISO-8601 at the Supabase boundary ──")
    import time as _t
    from utils import db as _db
    import importlib
    importlib.reload(_db)

    tmp = tempfile.mkdtemp(prefix="n1_cap_")
    cap_file = os.path.join(tmp, "time_capsules.json")
    orig_path = _db._TIME_CAPSULES_JSON
    _db._TIME_CAPSULES_JSON = cap_file
    orig_sb = _db.get_supabase

    try:
        # CAP-20 — Supabase insert carries an ISO-8601 unlock_time
        sb = FakeSupabase()
        _db.get_supabase = lambda: sb
        unlock = _t.time() + 3600.0
        cid = await _db.create_capsule_async(
            "100", "200", "555", "hello future", unlock, False)
        insert_payload = next(c["payload"] for c in sb.calls
                              if c["op"] == "insert")
        sent_time = insert_payload["unlock_time"]
        iso_ok = isinstance(sent_time, str) and "T" in sent_time \
            and sent_time.endswith("+00:00")
        check("CAP-20 Supabase insert sends ISO-8601 UTC (22007 root "
              "cause fixed — never an epoch float)",
              iso_ok and abs(
                  _db._capsule_epoch(sent_time) - unlock) < 0.01,
              f"sent {sent_time!r}")
        check("CAP-20b insert returns the Supabase row id",
              cid == 9001)

        # CAP-21 — the due query compares against an ISO string
        sb2 = FakeSupabase()
        _db.get_supabase = lambda: sb2
        await _db.get_due_capsules_async()
        lte = next(c["filters"]["unlock_time"][1] for c in sb2.calls
                   if "unlock_time" in c["filters"])
        check("CAP-21 due query .lte('unlock_time', ISO) — not a float",
              isinstance(lte, str) and "T" in lte,
              f"got {lte!r}")

        # CAP-22 — Supabase rows are normalized back to epoch floats
        iso_row = {
            "id": 61, "guild_id": "100", "channel_id": "200",
            "user_id": "555", "message": "iso row",
            "unlock_time": _db._capsule_iso(unlock), "is_public": False,
            "unlocked": False, "created_at": "2026-01-01T00:00:00",
        }
        sb3 = FakeSupabase(rows=[iso_row])
        _db.get_supabase = lambda: sb3
        rows = await _db.get_user_capsules_async("555", unlocked=False)
        check("CAP-22 Supabase ISO rows normalize to epoch floats for "
              "every consumer",
              rows and isinstance(rows[0]["unlock_time"], float)
              and abs(rows[0]["unlock_time"] - unlock) < 0.01)

        # CAP 23-26 — JSON fallback lifecycle (floats preserved)
        _db.get_supabase = lambda: None
        future = _t.time() + 86400.0
        cid2 = await _db.create_capsule_async(
            "100", "200", "556", "sealed ♡", future, False)
        raw = json.load(open(cap_file))
        check("CAP-26 JSON fallback keeps the legacy FLOAT format "
              "(existing rows keep working)",
              isinstance(raw[str(cid2)]["unlock_time"], float))
        due = await _db.get_due_capsules_async()
        check("CAP-23 create → NOT due (future unlock excluded from the "
              "due query)",
              all(d.get("id") != cid2 for d in due))

        raw[str(cid2)]["unlock_time"] = _t.time() - 60.0
        json.dump(raw, open(cap_file, "w"))
        due = await _db.get_due_capsules_async()
        check("CAP-24 not due → due (time passes → the loop finds it)",
              any(d.get("id") == cid2 for d in due))

        ok = await _db.mark_capsule_unlocked_async(cid2)
        due = await _db.get_due_capsules_async()
        unlocked = await _db.get_user_capsules_async(
            "556", unlocked=True)
        check("CAP-25 due → unlocked (terminal: never refires, shows in "
              "/capsule opened)",
              ok is True
              and all(d.get("id") != cid2 for d in due)
              and any(u.get("id") == cid2 for u in unlocked))
    finally:
        _db._TIME_CAPSULES_JSON = orig_path
        _db.get_supabase = orig_sb


# ═══ CNT 27 — canonical command counts ═════════════════════════════

def test_counts():
    print("\n── command counts: one canonical number everywhere ──")
    from utils.command_counts import count_commands_static
    c = count_commands_static()
    check("CNT-27 canonical: 46 cogs / 73 top-level / 169 invokable "
          "(Discord 100-limit respected)",
          c["cogs"] == 46 and c["top_level"] == 73
          and c["total_invokable"] == 169
          and c["top_level_headroom"] >= 0,
          f"got {c['cogs']}/{c['top_level']}/{c['total_invokable']}")

    marketing = open("dashboard/lib/marketing.ts",
                     encoding="utf-8").read()
    check("CNT-27b dashboard COMMAND_COUNT == 169 (was 168)",
          "COMMAND_COUNT = 169" in marketing)

    docs_data = open("dashboard/lib/docs-commands-data.ts",
                     encoding="utf-8").read()
    check("CNT-27c docs dataset count matches its own entries "
          "(documented roots)",
          "export const DOCS_COMMAND_COUNT = 72;" in docs_data)

    cmds_md = open("COMMANDS.md", encoding="utf-8").read()
    check("CNT-27d COMMANDS.md documents /toggledms and "
          "/invite_leaderboard (closing the root-entry gap)",
          "### /toggledms" in cmds_md
          and "### /invite_leaderboard" in cmds_md)

    main_src = open("main.py", encoding="utf-8").read()
    check("CNT-27e startup log + /botinfo use the canonical helper",
          "count_commands_runtime" in main_src
          and "format_command_summary" in main_src)
    pub_src = open("utils/public_api.py", encoding="utf-8").read()
    check("CNT-27f public /api/stats exposes command_counts",
          "command_counts" in pub_src and "count_commands_static" in pub_src)
    changelog = open("CHANGELOG.md", encoding="utf-8").read()
    check("CNT-27g Phase N.1 changelog entry exists (history NOT "
          "rewritten — new entry only)",
          "## [v1.1.1]" in changelog
          and "phase n.1" in changelog.lower()[:2500]
          and changelog.index("[v1.1.1]") < changelog.index("[v1.1.0]"))


# ═══ runner ════════════════════════════════════════════════════════

async def run_all():
    await test_ai()
    await test_cooldown()
    await test_dm()
    await test_capsules()
    test_counts()
    set_router(None)


def main():
    asyncio.run(run_all())
    print(f"\n{PASS} passed · {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
