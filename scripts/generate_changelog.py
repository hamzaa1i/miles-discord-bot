#!/usr/bin/env python3
"""
scripts/generate_changelog.py — PHASE M PART 5 (maintained through N).

Generates, from git history:
  1. CHANGELOG.md              (repo root — human-readable release notes)
  2. dashboard/lib/changelog-data.ts (typed data for /changelog page)

One source of truth, two artifacts. Re-run after any release; existing
non-v1.0.0 version blocks in CHANGELOG.md are PRESERVED so manual
entries for future versions (v1.1.0 …) are never wiped.

PHASE N: V1_UNTIL pins the v1.0.0 commit range so re-running this
script after later releases never rewrites the launch notes (Part 27:
"do not rewrite previous release notes") — post-1.0 commits belong to
their own version blocks (added by hand, like v1.1.0).

Usage:
    python scripts/generate_changelog.py [--repo /path/to/repo]
"""
import argparse
import os
import re
import subprocess
import sys

# ─── PHASE N — v1.0.0 commit cutoff ──────────────────────────────
# The launch release shipped at 28734dd (Phase M). Everything after
# that belongs to v1.1.0+ blocks, never to the v1.0.0 entry.
V1_UNTIL = "28734dd"

# ─── curated launch copy (v1.0.0) ──────────────────────────────────
V1_HIGHLIGHTS = [
    "public launch — 45 cogs, 167 commands, 34 dashboard modules",
    "ai chat with persistent memory + personality",
    "full veloura web dashboard with live previews",
    "gentle moderation: warnings, ai automod, thresholds",
    "engagement core: leveling, daily rewards, qotd, starboard",
    "privacy-first: /privacy export + delete everywhere",
]
V1_SUMMARY = (
    "the launch release — everything aurelia is today. five build phases, "
    "two live-test repair rounds and a full web dashboard later, she's "
    "ready for your server ♡"
)

CATEGORY_BY_PREFIX = {
    "feat": "feature",
    "fix": "fix",
    "docs": "improvement",
    "chore": "improvement",
    "style": "improvement",
    "refactor": "improvement",
    "perf": "improvement",
    "test": "improvement",
}


def git_log(repo: str, until: str | None = None) -> list:
    cmd = ["git", "log", "--pretty=format:%h|%ad|%s", "--date=short"]
    if until:
        # plain sha = this commit AND all its ancestors
        cmd.append(until)
    out = subprocess.run(
        cmd, cwd=repo, capture_output=True, text=True, check=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        h, d, s = line.split("|", 2)
        rows.append((h, d, s.strip()))
    return rows


def categorize(subject: str) -> str:
    m = re.match(r"^(\w+)(\([^)]*\))?!?:\s*(.+)$", subject)
    prefix = m.group(1).lower() if m else ""
    body = m.group(3) if m else subject
    if "breaking" in subject.lower():
        return "breaking"
    return CATEGORY_BY_PREFIX.get(prefix, "improvement"), body


def strip_prefix(subject: str) -> str:
    m = re.match(r"^\w+(\([^)]*\))?!?:\s*(.+)$", subject)
    return m.group(2) if m else subject


def build_v1_block(commits: list, date: str) -> str:
    cats = {"feature": [], "fix": [], "improvement": [], "breaking": []}
    for h, d, s in commits:
        cat, _ = categorize(s)
        cats[cat].append(f"{strip_prefix(s)} (`{h}`)")

    lines = [f"## [v1.0.0] — {date}", ""]
    lines.append("> highlights: " + " · ".join(V1_HIGHLIGHTS))
    lines.append("")
    lines.append(V1_SUMMARY)
    lines.append("")
    for label, key in (("features", "feature"), ("fixes", "fix"),
                       ("improvements", "improvement"),
                       ("breaking changes", "breaking")):
        items = cats[key]
        if not items:
            continue
        lines.append(f"### {label}")
        for it in items:
            lines.append(f"- {it}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def preserve_other_versions(text: str) -> list:
    """Raw text of every `## [vX]` block that is NOT v1.0.0."""
    blocks = re.split(r"\n(?=## \[)", text)
    return [b.strip() + "\n" for b in blocks
            if b.strip().startswith("## [") and "## [v1.0.0]" not in b]


HEADER = """# changelog

every change to aurelia, newest first ✦

generated from git history by `scripts/generate_changelog.py` — the
api mirror lives at `GET /api/changelog`, the rss feed at
`/changelog.rss`, and the pretty page at [/changelog](/changelog).
"""

# ─── minimal parser (mirrors utils/public_api._parse_changelog) ────
CAT_MAP = {
    "features": "feature", "feature": "feature",
    "fixes": "fix", "fix": "fix",
    "improvements": "improvement", "improvement": "improvement",
    "breaking changes": "breaking", "breaking": "breaking",
}


def parse_markdown(text: str) -> list:
    versions = []
    cur = None
    cat = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("## ["):
            inner = line[4:]
            pieces = inner.split("]", 1)
            cur = {"version": pieces[0].strip(),
                   "date": (pieces[1].replace("—", "").replace("--", "").strip()
                            if len(pieces) > 1 else ""),
                   "highlights": [], "summary": "",
                   "categories": {"feature": [], "fix": [],
                                  "improvement": [], "breaking": []}}
            versions.append(cur)
            cat = None
            continue
        if cur is None:
            continue
        if line.startswith("### "):
            cat = CAT_MAP.get(line[4:].strip().lower())
            continue
        if line.startswith("> highlights:"):
            cur["highlights"] = [p.strip() for p in
                                 line.split(":", 1)[1].split("·") if p.strip()]
            continue
        if line.startswith("- ") and cat:
            item = line[2:].strip()
            if item:
                cur["categories"][cat].append(item)
            continue
        if not cat and not cur["summary"] and not line.startswith("#") \
                and len(line) > 20:
            cur["summary"] = line
    return versions


def ts_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def write_ts(versions: list, path: str) -> None:
    out = [
        "/**",
        " * lib/changelog-data.ts — release notes for the /changelog page.",
        " *",
        " * AUTO-GENERATED by scripts/generate_changelog.py from git",
        " * history + CHANGELOG.md. Do not edit by hand — re-run the",
        " * script instead. The backend mirror is GET /api/changelog.",
        " */",
        "",
        "export interface ChangelogEntry {",
        "  version: string;",
        "  date: string;",
        "  highlights: string[];",
        "  summary: string;",
        "  categories: {",
        "    feature: string[];",
        "    fix: string[];",
        "    improvement: string[];",
        "    breaking: string[];",
        "  };",
        "}",
        "",
        "export const CHANGELOG: ChangelogEntry[] = [",
    ]
    for v in versions:
        out.append("  {")
        out.append(f"    version: '{ts_escape(v['version'])}',")
        out.append(f"    date: '{ts_escape(v['date'])}',")
        out.append(f"    highlights: [{', '.join(chr(39) + ts_escape(h) + chr(39) for h in v['highlights'])}],")
        out.append(f"    summary: '{ts_escape(v['summary'])}',")
        out.append("    categories: {")
        for key in ("feature", "fix", "improvement", "breaking"):
            items = ", ".join(f"'{ts_escape(i)}'" for i in v["categories"][key])
            out.append(f"      {key}: [{items}],")
        out.append("    },")
        out.append("  },")
    out.append("];")
    out.append("")
    out.append("export const LATEST_VERSION: string ="
               " CHANGELOG[0]?.version ?? 'v1.0.0';")
    out.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    repo = args.repo

    commits = git_log(repo, until=V1_UNTIL)
    if not commits:
        # cutoff not present in this clone — fall back to full history
        commits = git_log(repo)
    if not commits:
        print("no git history found", file=sys.stderr)
        return 1
    launch_date = commits[0][1]  # HEAD commit date

    md_path = os.path.join(repo, "CHANGELOG.md")
    existing = ""
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            existing = f.read()

    v1 = build_v1_block(commits, launch_date)
    preserved = preserve_other_versions(existing)

    doc = HEADER + "\n\n" + "\n".join(preserved) + v1 + "\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"wrote {md_path} ({len(preserved)} preserved + v1.0.0 with "
          f"{len(commits)} commits)")

    versions = parse_markdown(doc)
    ts_path = os.path.join(repo, "dashboard", "lib", "changelog-data.ts")
    write_ts(versions, ts_path)
    print(f"wrote {ts_path} ({len(versions)} versions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
