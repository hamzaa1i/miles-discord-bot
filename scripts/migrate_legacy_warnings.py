#!/usr/bin/env python3
"""scripts/migrate_legacy_warnings.py — one-shot legacy warnings migration.

Before the B1 fix, /mod warnings add wrote to data/moderation.json (legacy
Database store) while list/clear read from utils.db (Supabase "warnings"
table / data/warnings.json fallback). This script imports any legacy
warnings into the unified store so nothing is lost.

Safety:
  - Idempotent: existing warnings are fetched first and skipped, matched on
    (reason, moderator name, timestamp) so re-running never duplicates.
  - Non-destructive: the legacy file is never deleted by this script. The
    caller (main.py on_ready one-time check) renames it to
    data/moderation_migrated.json after a successful run.

Usage:
    python scripts/migrate_legacy_warnings.py            # from repo root
    python scripts/migrate_legacy_warnings.py --dry-run  # report only
"""
import argparse
import json
import logging
import os
import sys

# Allow running from repo root OR from scripts/ — normalise sys.path so
# `utils.db` resolves to the repo's utils package in both cases.
# NOTE: no logging.basicConfig() at module level — this module is imported
# by main.py at runtime, and reconfiguring root logging there is a side
# effect. CLI logging is configured in main() instead.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)  # utils.db uses relative "data/..." paths

logger = logging.getLogger("migrate_warnings")

LEGACY_PATH = os.path.join(REPO_ROOT, "data", "moderation.json")
MIGRATED_PATH = os.path.join(REPO_ROOT, "data", "moderation_migrated.json")

# Legacy rows written by utils.database stores may be missing keys; these
# defaults keep the unified payload shape consistent with utils.db.add_warning
# callers (moderation.py / ai_chat.py).
LEGACY_TYPE = "legacy"
LEGACY_TS_DEFAULT = "unknown"


def _load_legacy() -> dict:
    """Return the legacy moderation.json contents, or {} if absent/invalid."""
    if not os.path.exists(LEGACY_PATH):
        return {}
    try:
        with open(LEGACY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"could not read {LEGACY_PATH}: {e}")
        return {}


def legacy_warnings_exist() -> bool:
    """True if the legacy file exists AND contains at least one warning.

    Used by main.py's one-time startup check. After migration the legacy
    file is renamed, but ensure_data_files()/log_action() may recreate an
    empty moderation.json — those must NOT re-trigger the migration.
    """
    legacy = _load_legacy()
    for guild_data in legacy.values():
        if not isinstance(guild_data, dict):
            continue
        warnings_map = guild_data.get("warnings")
        if isinstance(warnings_map, dict):
            for user_warnings in warnings_map.values():
                if isinstance(user_warnings, list) and user_warnings:
                    return True
    return False


def migrate_legacy_warnings(dry_run: bool = False) -> dict:
    """Import legacy warnings into the unified utils.db store.

    Returns a summary dict: {"guilds": n, "imported": n, "skipped": n}.
    """
    from utils.db import get_warnings, add_warning, init_db, using_supabase

    init_db()
    logger.info(f"database: {'Supabase' if using_supabase() else 'JSON fallback'}")

    legacy = _load_legacy()
    if not legacy:
        logger.info("no legacy moderation.json data to migrate")
        return {"guilds": 0, "imported": 0, "skipped": 0}

    summary = {"guilds": 0, "imported": 0, "skipped": 0}

    for guild_id_raw, guild_data in legacy.items():
        if not isinstance(guild_data, dict):
            continue
        warnings_map = guild_data.get("warnings")
        if not isinstance(warnings_map, dict) or not warnings_map:
            continue

        try:
            guild_id = int(guild_id_raw)
        except (TypeError, ValueError):
            logger.warning(f"skipping non-numeric guild key {guild_id_raw!r}")
            continue

        guild_touched = False
        for user_id_raw, user_warnings in warnings_map.items():
            if not isinstance(user_warnings, list):
                continue
            try:
                user_id = int(user_id_raw)
            except (TypeError, ValueError):
                logger.warning(f"guild {guild_id}: skipping non-numeric user key {user_id_raw!r}")
                continue

            # De-dup: fetch what's already in the unified store for this user.
            try:
                existing = get_warnings(guild_id, user_id)
            except Exception as e:
                logger.error(f"guild {guild_id} user {user_id}: get_warnings failed ({e}); skipping")
                continue
            existing_keys = set()
            for w in existing:
                if isinstance(w, dict):
                    existing_keys.add((
                        str(w.get("reason", "")),
                        str(w.get("mod_name") or w.get("moderator") or ""),
                        str(w.get("timestamp", "")),
                    ))

            for w in user_warnings:
                if not isinstance(w, dict):
                    continue
                reason = str(w.get("reason", "no reason provided"))
                moderator = str(w.get("moderator", "unknown"))
                timestamp = str(w.get("timestamp", LEGACY_TS_DEFAULT))
                key = (reason, moderator, timestamp)
                if key in existing_keys:
                    summary["skipped"] += 1
                    continue

                payload = {
                    "type": LEGACY_TYPE,
                    "reason": reason,
                    # utils.db.add_warning rows use mod_id/mod_name; legacy
                    # rows only kept the display name, so synthesise mod_name.
                    "mod_id": None,
                    "mod_name": moderator,
                    "timestamp": timestamp,
                }
                if dry_run:
                    logger.info(f"[dry-run] would import guild={guild_id} user={user_id} reason={reason[:50]!r}")
                else:
                    try:
                        add_warning(guild_id, user_id, payload)
                    except Exception as e:
                        logger.error(f"guild {guild_id} user {user_id}: add_warning failed ({e}); aborting this user")
                        break
                existing_keys.add(key)
                summary["imported"] += 1
                guild_touched = True

        if guild_touched:
            summary["guilds"] += 1

    logger.info(
        f"migration {'(dry-run) ' if dry_run else ''}complete: "
        f"{summary['imported']} imported, {summary['skipped']} duplicates skipped, "
        f"{summary['guilds']} guild(s) touched"
    )
    return summary


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Migrate legacy moderation.json warnings into utils.db")
    parser.add_argument("--dry-run", action="store_true", help="report what would be imported without writing")
    args = parser.parse_args()

    if not os.path.exists(LEGACY_PATH):
        print(f"no legacy file at {LEGACY_PATH} — nothing to migrate.")
        return 0

    summary = migrate_legacy_warnings(dry_run=args.dry_run)
    print(f"done: {summary['imported']} imported, {summary['skipped']} skipped (duplicates)")
    if not args.dry_run and summary["imported"] >= 0:
        print(f"note: legacy file left in place. main.py renames it to moderation_migrated.json "
              f"after its one-time startup migration, or you can do so manually.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
