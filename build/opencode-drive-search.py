#!/usr/bin/env python3
"""Search the Proton Drive backup index for a file, and report where it is.

The Proton Drive CLI needs the desktop session's keyring, which is not
reachable from an agent sandbox. The backup app, however, keeps a local index
of every file it has uploaded — the same files that live in the Drive — so the
index can be searched directly.

Usage:
    python3 build/opencode-drive-search.py <substring> [--limit 40]
    python3 build/opencode-drive-search.py --list-roots
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

ENTRIES = Path.home() / ".local/share/origo-backup/cache/entries"

# Skip the trees that are not the user's work.
NOISE = (
    "node_modules", "/.git/", "site-packages", "__pycache__", "/.cache/",
    "/vendor/", "texmf-dist", "texlive", "/flatpak/", "/.local/share/containers",
    "/.mozilla/", "/.config/BraveSoftware", "/.npm/",
)


def newest_index() -> Path | None:
    if not ENTRIES.exists():
        return None
    files = sorted(ENTRIES.glob("*.sqlite"))
    return files[-1] if files else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("needle", nargs="?", default="")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--list-roots", action="store_true")
    ap.add_argument("--include-vendored", action="store_true")
    args = ap.parse_args()

    index = newest_index()
    if index is None:
        print(f"No backup index under {ENTRIES}")
        print("The backup app has not run here yet.")
        return 1

    print(f"index: {index}")
    con = sqlite3.connect(f"file:{index}?mode=ro", uri=True)

    if args.list_roots:
        print("\n── top level ──────────────────────────────────────────────")
        seen = {}
        for (path,) in con.execute("select path from entries where type='file'"):
            ps = path.decode("utf-8", "replace")
            parts = ps.split("/")
            if len(parts) > 1:
                seen[parts[1]] = seen.get(parts[1], 0) + 1
        for name, n in sorted(seen.items(), key=lambda x: -x[1])[:30]:
            print(f"  {n:>8}  {name}")
        con.close()
        return 0

    if not args.needle:
        ap.error("give a substring to search for, or --list-roots")

    needle = args.needle.lower()
    hits = []
    for path, size in con.execute(
        "select path, size from entries where type='file'"
    ):
        ps = path.decode("utf-8", "replace")
        if needle not in ps.lower():
            continue
        if not args.include_vendored and any(n in ps for n in NOISE):
            continue
        hits.append((int(size or 0), ps))

    con.close()
    print(f"\n── {len(hits)} match(es) for {args.needle!r} ─────────────────────")
    for size, ps in sorted(hits, key=lambda x: -x[0])[: args.limit]:
        print(f"  {size:>10}  {ps}")
    if len(hits) > args.limit:
        print(f"  … and {len(hits) - args.limit} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
