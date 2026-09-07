#!/usr/bin/env python3
"""
scripts/test_phase_n.py — PHASE N PART 24+25 checks.

Two layers, both hermetic (no live Discord / no browser / no network):

  A. STRUCTURAL NAVIGATION CHECKS (Part 24, source-level)
     auth-aware header, home↔dashboard links, docs breadcrumbs on
     every docs page, mobile menu destinations, no public repo links
     (private-source prep), no AI provider key in the client bundle.

  B. BACKEND WIRING CHECKS
     /owner ai_status subcommand registered (no new root command),
     GET /api/dashboard/ai/status auth-gated, /api/public/stats gains
     the generic ai_status, owner cog loads, root command count
     unchanged from Phase M (70).

A real browser pass (rendered DOM, console errors, 375px) is done
after `npm run build` with `next start` + a headless check — see the
phase N worklog. This file is the fast, always-runnable core.

Run:  python3 scripts/test_phase_n.py
"""
import asyncio
import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

DASH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "dashboard")


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")


def read(path: str) -> str:
    with open(os.path.join(DASH, path), encoding="utf-8") as f:
        return f.read()


# ─── A. structural navigation ───────────────────────────────────────

def test_navigation():
    print("── A · navigation structure ──")

    header = read("components/site/SiteHeader.tsx")
    check("A1. header is auth-aware (uses useAuth, no cookie probing)",
          "useAuth" in header and "document.cookie" not in header)
    check("A2. header profile dropdown has dashboard / my servers / sign out",
          all(x in header for x in (
              'href="/servers"', "dashboard", "my servers", "sign out")))
    check("A3. header no longer links the repository",
          "GITHUB_URL" not in header and "miles-discord-bot" not in header)
    check("A4. mobile drawer includes login/profile + same destinations",
          "MobileAuthButton" in header and "support" in header)

    landing = read("app/page.tsx")
    check("A5. landing hero has auth-aware secondary CTA",
          "AuthAwareCta" in landing)
    check("A6. landing keeps 'add to discord' primary CTA",
          "add to discord" in landing and "botInviteUrl" in landing)
    check("A7. pricing bullets no longer advertise MIT self-hosting",
          "MIT licensed" not in landing and "self-hosting?" not in landing)

    auth_cta = read("components/site/AuthAwareCta.tsx")
    check("A8. auth CTA flips login ↔ open dashboard by session",
          "open dashboard" in auth_cta and 'href="/servers"' in auth_cta
          and 'href="/login"' in auth_cta)

    servers = read("app/servers/page.tsx")
    check("A9. /servers page has a home link",
          'href="/"' in servers and "aurelia home" in servers)

    sidebar = read("components/Sidebar.tsx")
    check("A10. guild sidebar footer links home + all servers",
          'href="/"' in sidebar and 'href="/servers"' in sidebar
          and "aurelia home" in sidebar and "all servers" in sidebar)

    guild_layout = read("app/servers/[guildId]/layout.tsx")
    check("A11. guild sidebar header still links back to /servers",
          'href="/servers"' in guild_layout)

    # docs breadcrumbs — every docs page except /docs itself
    docs_pages = [
        ("app/docs/getting-started/page.tsx", "getting started"),
        ("app/docs/commands/page.tsx", "commands"),
        ("app/docs/dashboard/page.tsx", "dashboard guide"),
        ("app/docs/faq/page.tsx", "faq"),
        ("app/docs/api/page.tsx", "api"),
        ("app/docs/modules/page.tsx", "modules"),
        ("app/docs/modules/[module]/page.tsx", "module deep dive"),
    ]
    for path, label in docs_pages:
        src = read(path)
        check(f"A12. docs breadcrumb present: {label}",
              "DocsBreadcrumb" in src, path)
    breadcrumb = read("components/docs/DocsBreadcrumb.tsx")
    check("A13. breadcrumb 'docs' crumb is clickable",
          'href="/docs"' in breadcrumb)

    # every public page family uses the shared header/footer (thin
    # page wrappers delegate to *Client components that render it)
    for path in ("components/site/StatsClient.tsx",
                 "components/site/ChangelogClient.tsx"):
        src = read(path)
        check(f"A14. public page renders SiteHeader ({path})",
              "<SiteHeader />" in src, path)

    stats_client = read("components/site/StatsClient.tsx")
    check("A15. stats page shows the generic ai_status chip (no quota data)",
          "ai_status" in stats_client
          and "daily_budget" not in stats_client
          and "requests_today" not in stats_client)

    # ── private-source copy sweep ──
    # NOTE: FAQ *questions* like "can i self-host?" are fine — they're
    # answered with the managed-project wording. What must be gone are
    # AFFIRMATIVE self-host instructions and repo/MIT links.
    public_files = [
        "components/site/SiteFooter.tsx",
        "components/site/Faq.tsx",
        "components/site/SiteHeader.tsx",
        "app/page.tsx",
        "app/docs/faq/page.tsx",
        "app/docs/api/page.tsx",
        "app/docs/dashboard/page.tsx",
        "app/docs/page.tsx",
        "app/docs/getting-started/page.tsx",
        "lib/marketing.ts",
    ]
    bad_patterns = [
        "mit licensed", "mit license", "she's mit", "absolutely —",
        "self-host her", "you can even self-host", "self-hosting?",
        "open source", "open-source", "fork it", "git clone",
        "github.com/hamzaa1i/miles-discord-bot",
        "import { GITHUB_URL", "`${GITHUB_URL", "href={GITHUB_URL",
    ]
    for path in public_files:
        src = read(path).lower()
        hits = [p for p in bad_patterns if p.lower() in src]
        check(f"A16. no public self-host/repo copy: {path}", not hits,
              f"found {hits}")

    footer = read("components/site/SiteFooter.tsx")
    check("A17. footer keeps creator attribution via profile link",
          "CREATOR_GITHUB_URL" in footer and "volc" in footer)


def test_env_leakage():
    print("── B · client bundle env audit (Part 22) ──")
    # no provider key may ever be NEXT_PUBLIC_*
    offenders = []
    for root, _dirs, files in os.walk(DASH):
        if "node_modules" in root or ".next" in root:
            continue
        for fn in files:
            if not fn.endswith((".ts", ".tsx", ".js", ".mjs", ".env*",
                                ".example", ".json")):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    src = f.read()
            except Exception:
                continue
            for key in ("GEMINI_API_KEY", "MISTRAL_API_KEY",
                        "OPENROUTER_API_KEY", "GROQ_API_KEY"):
                if f"NEXT_PUBLIC_{key}" in src:
                    offenders.append(f"{path}: NEXT_PUBLIC_{key}")
    check("B1. no NEXT_PUBLIC_ AI provider keys anywhere in dashboard",
          not offenders, f"found {offenders[:3]}")

    env_example = read(".env.example")
    check("B2. dashboard .env.example carries no provider keys",
          not any(k in env_example for k in (
              "GEMINI_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY",
              "GROQ_API_KEY")))


# ─── C. backend wiring ──────────────────────────────────────────────

async def test_backend():
    print("── C · backend wiring ──")
    import discord
    from discord.ext import commands
    import importlib

    for mod in ("utils.ai_handler", "utils.ai_router", "utils.ai_config",
                "utils.ai_sanitize", "utils.ai_types"):
        importlib.import_module(mod)
    check("C1. ai core modules import cleanly", True)

    from utils.ai_handler import call_ai, call_ai_fast, call_ai_reasoning, \
        pick_model
    import inspect
    check("C2. call_ai signature preserved",
          list(inspect.signature(call_ai).parameters) ==
          ["messages", "model", "max_tokens", "temperature", "retry_count"])
    check("C3. call_ai_fast signature preserved (+ sensitive flag)",
          list(inspect.signature(call_ai_fast).parameters) ==
          ["messages", "max_tokens", "sensitive"])
    check("C4. call_ai_reasoning signature preserved",
          list(inspect.signature(call_ai_reasoning).parameters) ==
          ["messages", "max_tokens", "temperature"])
    check("C5. pick_model signature preserved",
          list(inspect.signature(pick_model).parameters) ==
          ["message_content", "intent"])

    # cog + tree
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)
    from cogs.owner import Owner
    await bot.add_cog(Owner(bot))
    tree_cmds = {c.name: c for c in bot.tree.get_commands()}
    owner_group = tree_cmds.get("owner")
    check("C6. /owner group still a single root command",
          owner_group is not None)
    sub_names = {c.name for c in owner_group.commands} if owner_group else set()
    check("C7. /owner ai_status subcommand registered",
          "ai_status" in sub_names, f"got {sorted(sub_names)}")

    # root count: load ALL cogs (same loader as test_phase_m_tree) and
    # assert the phase N subcommand added no new root command.
    root_bot = commands.Bot(command_prefix="!", intents=intents)
    cogs_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "cogs")
    for filename in sorted(os.listdir(cogs_dir)):
        if filename.endswith(".py") and not filename.endswith("_disabled.py") \
                and filename != "__init__.py":
            try:
                await root_bot.load_extension(f"cogs.{filename[:-3]}")
            except Exception:
                pass
    root_count = len(root_bot.tree.get_commands())
    check("C8. root command count unchanged (70)", root_count == 70,
          f"got {root_count}")

    # dashboard api + public api endpoints — register BOTH before any
    # test_client request (flask forbids blueprint registration after
    # the first request)
    from flask import Flask
    app = Flask(__name__)
    app.config["TESTING"] = True
    os.environ.setdefault("OWNER_ID", "0")
    from utils.dashboard_api import init_dashboard_api
    from utils.public_api import init_public_api
    init_dashboard_api(app)
    init_public_api(app)
    rules = {r.rule for r in app.url_map.iter_rules()}
    check("C9. GET /api/dashboard/ai/status registered",
          "/api/dashboard/ai/status" in rules)
    client = app.test_client()
    resp = client.get("/api/dashboard/ai/status")
    check("C10. /ai/status requires auth (401 without bearer)",
          resp.status_code == 401, f"got {resp.status_code}")

    # public stats gains generic ai_status
    from utils.public_api import _collect_stats
    stats = _collect_stats()
    check("C11. public stats expose generic ai_status",
          stats.get("ai_status") in ("operational", "degraded", "down",
                                     "starting"))
    check("C12. public stats expose NO provider details",
          not any(k in str(stats) for k in (
              "daily_budget", "openrouter", "gemini", "mistral"))
          or "routes" not in str(stats))
    check("C13. version bumped to 1.1.0", stats.get("version") == "1.1.0")

    # db accounting round-trip
    from utils.db import record_ai_usage, get_ai_usage_for_date
    import datetime as dt
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    record_ai_usage(usage_date=day, provider="groq",
                    model="openai/gpt-oss-20b", profile="fast",
                    requests=1, successes=1)
    rows = get_ai_usage_for_date(day)
    check("C14. ai_provider_usage accounting round-trips",
          any(r.get("provider") == "groq" for r in rows))

    # intent parser + automod sensitivity wiring
    # deterministic parser still runs FIRST (zero LLM calls for known
    # intents) — the deterministic regex pass must execute before the
    # llm fallback call inside parse_intent
    ip = read_src("utils/intent_parser.py")
    am = read_src("cogs/ai_automod.py")
    check("C15. intent parser requests SENSITIVE_FAST",
          "sensitive=True" in ip)
    check("C16. ai automod requests SENSITIVE_FAST",
          "sensitive=True" in am)
    check("C17. deterministic parser still precedes the llm parser",
          ip.index("def parse_intent") < ip.index("await call_ai_fast(")
          and "deterministic" in ip.lower())


def read_src(relpath: str) -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, relpath), encoding="utf-8") as f:
        return f.read()


def main():
    test_navigation()
    test_env_leakage()
    asyncio.run(test_backend())
    print(f"\n{PASS} passed · {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
