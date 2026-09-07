#!/usr/bin/env python3
"""
scripts/generate_docs_commands.py — PHASE M PART 2.

Parses COMMANDS.md (the hand-maintained command reference) into
dashboard/lib/docs-commands-data.ts — the structured dataset behind
/docs/commands (category filter, per-command cards, client-side
search).

Parser rules (matched to COMMANDS.md conventions):
  ## <Category>            → category (the 10 command categories; the
                             meta sections — TOC, mention intents,
                             prefix commands, reactions, template
                             variables, permission matrix, cooldown
                             summary — are skipped)
  ### /name — group *(perm)* 🆕 *New...*  → command entry
  plain lines             → description paragraph
  - **Permissions:** X · **Cooldown:** Y  → permission / cooldown
  - Parameters: ... / indented sub-bullets → params
  - Example usage / Example / Example response → examples
  **/sub**                → subcommand entry (owns the lines after it)

Re-run whenever COMMANDS.md changes. Never edits COMMANDS.md itself.
"""
import argparse
import os
import re
import sys

META_SECTIONS = {
    "table of contents",
    "@mention natural-language intents",
    "prefix commands",
    "reactions & buttons",
    "template variables reference",
    "permission matrix",
    "cooldown summary",
}


def parse(text: str) -> list:
    categories = []
    cur_cat = None
    cur_cmd = None
    cur_sub = None

    def close_sub():
        nonlocal cur_sub
        cur_sub = None

    def close_cmd():
        nonlocal cur_cmd
        close_sub()
        cur_cmd = None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped or stripped == "---":
            i += 1
            continue

        if stripped.startswith("## "):
            close_cmd()
            title = stripped[3:].strip()
            if title.lower() in META_SECTIONS:
                cur_cat = None
            else:
                cur_cat = {"category": title, "commands": []}
                categories.append(cur_cat)
            i += 1
            continue

        if stripped.startswith("### ") and cur_cat is not None:
            close_cmd()
            heading = stripped[4:].strip()
            # split off "— group", "*(perm)*", "🆕 *New in Phase 2*"
            is_group = "— group" in heading or "- group" in heading
            perm = ""
            m = re.search(r"\*\(([^)]+)\)\*", heading)
            if m:
                perm = m.group(1)
            is_new = "🆕" in heading
            # name: everything before the first "—", "(", or 🆕 marker
            name = re.split(r"\s*[—-]\s*group", heading)[0]
            name = re.split(r"\s*\(", name)[0].strip()
            name = re.split(r"🆕", name)[0].strip()
            name = re.sub(r"[*🆕]", "", name).strip()
            cur_cmd = {
                "name": name,
                "isGroup": is_group,
                "permission": perm,
                "isNew": is_new,
                "description": [],
                "params": [],
                "examples": [],
                "subcommands": [],
                "other": [],
            }
            cur_cat["commands"].append(cur_cmd)
            i += 1
            continue

        # bold subcommand heading **/sub**
        m = re.match(r"^\*\*(.+?)\*\*\s*$", stripped)
        if m and cur_cmd is not None and stripped.startswith("**/"):
            close_sub()
            cur_sub = {"name": m.group(1).strip(), "body": []}
            cur_cmd["subcommands"].append(cur_sub)
            i += 1
            continue

        if cur_cmd is None:
            i += 1
            continue

        target_sub = cur_sub is not None
        store_sub = cur_sub["body"] if target_sub else None

        # permissions / cooldown combined bullet
        pm = re.match(r"^-\s*\*\*Permissions?:?\*\*:?\s*(.+)$", stripped)
        if pm and not target_sub:
            blob = pm.group(1)
            for part in blob.split("·"):
                part = part.strip()
                km = re.match(r"\*\*(.+?)\*\*:?\s*(.*)$", part)
                if km:
                    key = km.group(1).strip().rstrip(":").lower()
                    val = km.group(2).strip()
                    if "perm" in key:
                        cur_cmd["permission"] = val or cur_cmd["permission"]
                    elif "cool" in key:
                        cur_cmd.setdefault("cooldown", val)
            i += 1
            continue

        cm = re.match(r"^-\s*\*\*Cooldown\*\*:?\s*(.+)$", stripped)
        if cm and not target_sub:
            cur_cmd["cooldown"] = cm.group(1).strip()
            i += 1
            continue

        # parameters bullet (+ its indented sub-bullets)
        if stripped.startswith("- Parameters:") and not target_sub:
            rest = stripped[len("- Parameters:"):].strip()
            if rest:
                cur_cmd["params"].append(rest)
            i += 1
            # consume following indented sub-bullets ("  - `x` (...)")
            while i < len(lines):
                nxt = lines[i]
                sm = re.match(r"^\s+-\s+(.+)$", nxt)
                if sm and nxt.startswith("  "):
                    cur_cmd["params"].append(sm.group(1).strip())
                    i += 1
                else:
                    break
            continue

        # examples
        if re.match(r"^-\s*(Example usage|Example|Example response)\s*[:•]?", stripped):
            label_m = re.match(r"^-\s*(Example usage|Example|Example response)\s*[:•]?\s*(.*)$",
                               stripped)
            label = label_m.group(1)
            rest = label_m.group(2).strip()
            # consume continuation lines (indented, not new bullets)
            while i + 1 < len(lines):
                nxt = lines[i + 1]
                if nxt.strip() and not re.match(r"^\s*[-#*\n]", nxt) and nxt.startswith(("  ", "\t")):
                    rest = (rest + " " + nxt.strip()).strip()
                    i += 1
                else:
                    break
            prefix = "" if label in ("Example", "Example usage") else \
                ("response: " if "response" in label else "")
            if rest:
                (store_sub if target_sub else cur_cmd["examples"]).append(
                    prefix + rest)
            i += 1
            continue

        # plain description lines / any other bullets
        if not stripped.startswith("#"):
            if store_sub is not None:
                # description lines before the sub's first bullet
                store_sub.append(stripped)
            elif stripped.startswith("- "):
                cur_cmd["other"].append(stripped[2:].strip())
            else:
                cur_cmd["description"].append(stripped)
        i += 1

    # post-process: subcommand bodies — first non-bullet lines are the
    # description; keep the rest raw for rendering
    for cat in categories:
        for cmd in cat["commands"]:
            cmd["description"] = " ".join(cmd["description"]).strip()
            for sub in cmd["subcommands"]:
                desc_lines = []
                body_rest = []
                seen_bullet = False
                for ln in sub["body"]:
                    if ln.startswith("- ") or ln.startswith("**"):
                        seen_bullet = True
                    if not seen_bullet:
                        desc_lines.append(ln)
                    else:
                        body_rest.append(ln)
                sub["description"] = " ".join(desc_lines).strip()
                sub["body"] = body_rest
    return categories


def ts_escape(s: str) -> str:
    return (s.replace("\\", "\\\\").replace("'", "\\'")
             .replace("`", "\\`"))


def ts_str(s: str) -> str:
    return f"'{ts_escape(s)}'"


def main() -> int:
    ap = argparse.ArgumentParser()
    default_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--repo", default=default_repo)
    args = ap.parse_args()

    src = os.path.join(args.repo, "COMMANDS.md")
    dst = os.path.join(args.repo, "dashboard", "lib", "docs-commands-data.ts")

    with open(src, "r", encoding="utf-8") as f:
        text = f.read()
    cats = parse(text)
    if not cats:
        print("parse produced no categories", file=sys.stderr)
        return 1

    out = [
        "/**",
        " * lib/docs-commands-data.ts — the /docs/commands dataset.",
        " *",
        " * AUTO-GENERATED by scripts/generate_docs_commands.py from",
        " * COMMANDS.md — do not edit by hand. Re-run the script when",
        " * COMMANDS.md changes.",
        " */",
        "",
        "export interface DocsSubcommand {",
        "  name: string;",
        "  description: string;",
        "  body: string[];",
        "}",
        "",
        "export interface DocsCommand {",
        "  name: string;",
        "  isGroup: boolean;",
        "  permission: string;",
        "  cooldown?: string;",
        "  isNew: boolean;",
        "  description: string;",
        "  params: string[];",
        "  examples: string[];",
        "  other: string[];",
        "  subcommands: DocsSubcommand[];",
        "}",
        "",
        "export interface DocsCategory {",
        "  category: string;",
        "  commands: DocsCommand[];",
        "}",
        "",
        "export const DOCS_COMMANDS: DocsCategory[] = [",
    ]
    total = 0
    for cat in cats:
        out.append("  {")
        out.append(f"    category: {ts_str(cat['category'])},")
        out.append("    commands: [")
        for cmd in cat["commands"]:
            total += 1
            out.append("      {")
            out.append(f"        name: {ts_str(cmd['name'])},")
            out.append(f"        isGroup: {str(cmd['isGroup']).lower()},")
            out.append(f"        permission: {ts_str(cmd['permission'])},")
            if cmd.get("cooldown"):
                out.append(f"        cooldown: {ts_str(cmd['cooldown'])},")
            out.append(f"        isNew: {str(cmd['isNew']).lower()},")
            out.append(f"        description: {ts_str(cmd['description'])},")
            out.append(f"        params: [{', '.join(ts_str(p) for p in cmd['params'])}],")
            out.append(f"        examples: [{', '.join(ts_str(e) for e in cmd['examples'])}],")
            out.append(f"        other: [{', '.join(ts_str(o) for o in cmd['other'])}],")
            if cmd["subcommands"]:
                out.append("        subcommands: [")
                for sub in cmd["subcommands"]:
                    out.append("          {")
                    out.append(f"            name: {ts_str(sub['name'])},")
                    out.append(f"            description: {ts_str(sub['description'])},")
                    out.append(f"            body: [{', '.join(ts_str(b) for b in sub['body'])}],")
                    out.append("          },")
                out.append("        ],")
            else:
                out.append("        subcommands: [],")
            out.append("      },")
        out.append("    ],")
        out.append("  },")
    out.append("];")
    out.append("")
    out.append(f"export const DOCS_COMMAND_COUNT = {total};")
    out.append("")

    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"wrote {dst}: {len(cats)} categories, {total} commands")
    return 0


if __name__ == "__main__":
    sys.exit(main())
