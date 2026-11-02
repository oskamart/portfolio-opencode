#!/usr/bin/env python3
"""Measure every project the portfolio documents, from every source tree.

This is the opencode agent's own manifest builder. It reads four places:

    ~/portfolio-osys-one/...        the Origo-side trees
    ~/oden-uvm-staging/...          the frozen engine and harness trees
    ~/backup index (Proton Drive)   the Oden-side trees, via the backup
                                     catalog the backup app keeps locally

Every figure the page shows comes from here, so nothing is typed by hand.

Usage: python3 build/opencode-manifest.py [--out assets/manifest.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()

# Local trees, measured directly.
#
# Note on UVMStack: the engine (uvm_engine) is Trishna Raj's work —
# git@github.com:trishinraj/uvm_engine — and is not counted here as the
# operator's own. It is measured separately under "dependencies" so the page
# can state its size honestly while crediting it to its author.
LOCAL = {
    "haelo": {
        "label": "Haelo",
        "root": "Desktop/haelo-proxy",
        "repo": None,
    },
    "odenflow": {
        "label": "Oden Flow",
        "root": "oden-uvm-staging/oden_flow",
        "repo": "oden-uvm-staging/oden_flow",
    },
    "cern_app": {
        "label": "CERN delivery (the desktop app)",
        "root": "Desktop/uvm-app-cern-classic/frontend/src",
        "repo": None,
    },
    "ardverium": {
        "label": "Ardverium",
        "root": "Desktop/ardverium-reworked",
        "repo": None,
    },
    "lorapilot": {
        "label": "LoRA pilot",
        "root": "lora-pilot/lorapilot",
        "repo": "lora-pilot",
    },
    "lorapilot_tests": {
        "label": "LoRA pilot tests",
        "root": "lora-pilot/tests",
        "repo": None,
    },
    "origobackup": {
        "label": "Origo Backup",
        "root": "backup-app",
        "repo": None,
    },
    "phisix": {
        "label": "phi6 / UniPhy",
        "root": "Documents/phi6",
        "repo": None,
    },
    "ssmfs": {
        "label": "SSMFS translation",
        "root": "Desktop/ssmfs-english",
        "repo": None,
    },
    "kpow": {
        "label": "K-Pow",
        "root": "Desktop/k-pow-codex",
        "repo": None,
    },
    "heat": {
        "label": "District heating",
        "root": "Desktop/district-heating-workbench",
        "repo": None,
    },
}

# Work that exists but is not the operator's own. Measured, credited, and
# kept out of the totals.
DEPENDENCIES = {
    "uvmstack": {
        "label": "UVMStack (AVA)",
        "author": "Trishna Raj",
        "url": "https://github.com/trishinraj/uvm_engine",
        "root": "oden-uvm-staging/uvm_engine-v2",
        "note": "The verification engine. Delivered to CERN and evaluated here; "
                "not the operator's own work.",
    },
}

# Oden-side trees. They live on the Oden VM, whose home was backed up to
# Proton Drive; the backup app keeps a local index of every file, so the
# trees can be measured without reaching the machine.
BACKUP_INDEX = HOME / ".local/share/origo-backup/cache/entries"

# prefix -> label, measured from the backup index rather than the filesystem.
REMOTE = {
    "root-1/ai/colibri": "Colibri inference server",
    "root-1/ai/colibri-vk": "Colibri (Vulkan)",
    "root-1/ai/colibri-ab": "Colibri (abliteration)",
    "root-1/ai/platform/oden-ide": "Oden IDE",
    "root-1/ai/platform/oden-ide-dev": "Oden IDE (dev)",
    "root-1/ai/platform/oden-model-hub": "Model hub",
    "root-1/ai/oquip2": "Oquip",
    "root-1/ai/uvm": "UVM trees",
    "root-1/ai/runtime": "Model runtime",
    "root-1/ai/hwbench-runtime": "HW-bench runtime",
    "root-1/ai/translations": "Translations",
    "root-1/ai/inspiration/verification-methods": "Verification methods",
    "root-1/ai/inspiration/self-improvement": "Self-improvement",
    "root-1/ai/inspiration/papers": "Papers",
    "root-1/ai/inspiration/handbooks": "Handbooks",
}

CODE_EXT = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".c", ".h", ".cc", ".cpp",
    ".hpp", ".cu", ".mm", ".css", ".html", ".sv", ".svh", ".v", ".vh", ".sh",
    ".rs", ".pyi", ".yaml", ".yml",
}
DOC_EXT = {".md", ".rst", ".txt", ".org"}

# Never counted: vendored trees, build output, caches.
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "__pycache__",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".eggs", "site-packages", ".next", ".cache", "coverage", ".output",
    "texmf-dist", "texlive", "flatpak", "containers",
}

# Build artefacts that live next to sources.
SKIP_EXT = {".o", ".a", ".so", ".map", ".mjs", ".tsbuildinfo", ".pyc"}


def count_tree(root: Path) -> dict:
    """Return {files, code_loc, doc_loc, bytes} for an authored tree."""
    files = code_loc = doc_loc = total = 0
    if not root.exists():
        return {"files": 0, "code_loc": 0, "doc_loc": 0, "bytes": 0}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in SKIP_EXT:
                continue
            if ext not in CODE_EXT and ext not in DOC_EXT:
                continue
            path = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(path)
                with open(path, "rb") as fh:
                    lines = sum(1 for _ in fh)
            except OSError:
                continue
            files += 1
            total += size
            if ext in CODE_EXT:
                code_loc += lines
            else:
                doc_loc += lines
    return {"files": files, "code_loc": code_loc, "doc_loc": doc_loc, "bytes": total}


def git_commits(repo: Path) -> int:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def find_backup_index() -> Path | None:
    """Newest backup index of the Oden tree, if the backup app has run."""
    entries = BACKUP_INDEX
    if not entries.exists():
        return None
    files = sorted(entries.glob("*.sqlite"))
    return files[-1] if files else None


def count_remote(index: Path, prefix: str) -> dict:
    """Measure a tree from the backup index (the Oden-side source of truth).

    The index stores paths and byte sizes, not line counts, so a remote tree
    is reported as file counts and bytes. Local trees are reported as lines.
    The distinction is kept in the manifest so the page cannot blur it.
    """
    if not index.exists():
        return {"files": 0, "code_files": 0, "doc_files": 0, "bytes": 0}

    con = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    files = code_files = doc_files = total = 0
    # The path column is a BLOB, so the LIKE pattern must be a BLOB too — a
    # text pattern silently matches nothing.
    like = (prefix + "/%").encode()
    try:
        rows = con.execute(
            "select path, size, type from entries where path like ? and type = 'file'",
            (like,),
        )
        for path, size, _t in rows:
            ps = path.decode("utf-8", "replace") if isinstance(path, bytes) else path
            if "/node_modules/" in ps or "/.git/" in ps:
                continue
            # splitext keeps the dot; rsplit does not, and the sets are dotted.
            ext = os.path.splitext(ps)[1].lower()
            if ext in SKIP_EXT:
                continue
            if ext not in CODE_EXT and ext not in DOC_EXT:
                continue
            files += 1
            total += int(size or 0)
            if ext in CODE_EXT:
                code_files += 1
            else:
                doc_files += 1
    finally:
        con.close()
    return {"files": files, "code_files": code_files, "doc_files": doc_files, "bytes": total}


def count_remote_loc(index: Path, prefix: str) -> int:
    """Line count for a remote tree — the index stores bytes, not lines.

    The byte count is what the index has, so this reports bytes and says so.
    """
    return count_remote(index, prefix)["bytes"]


def measure_taa_core() -> dict:
    """The shared temporal-AA core: one implementation, four designs."""
    import hashlib

    core = ["taa-glsl.js", "taa-runtime.js", "taa-three.js"]
    dirs = [
        "Desktop/ardverium-reworked/4-chip/js",
        "Desktop/ardverium-reworked/5-graph/js",
        "Desktop/ardverium-reworked/6-prism/dist/js",
        "Desktop/ardverium-reworked/7-silicon/dist/js",
    ]
    loc = 0
    per_file = {}
    for name in core:
        digests = {}
        lines = 0
        for rel in dirs:
            path = HOME / rel / name
            if not path.exists():
                continue
            digests[rel] = hashlib.md5(path.read_bytes()).hexdigest()
            with open(path, "rb") as fh:
                lines = sum(1 for _ in fh)
        unique = set(digests.values())
        per_file[name] = {
            "copies": len(digests),
            "identical": len(unique) == 1 and len(digests) > 1,
            "md5": next(iter(unique)) if len(unique) == 1 else None,
            "loc": lines,
        }
        loc += lines
    return {
        "loc": loc,
        "designs": len(dirs),
        "identical_across_designs": all(f["identical"] for f in per_file.values()),
        "files": per_file,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/manifest.json")
    args = ap.parse_args()

    systems = {}
    for key, spec in LOCAL.items():
        root = HOME / spec["root"]
        stats = count_tree(root)
        stats["commits"] = git_commits(HOME / spec["repo"]) if spec["repo"] else 0
        stats["source"] = "local"
        stats["label"] = spec["label"]
        systems[key] = stats

    # Work that is measured but not the operator's own.
    dependencies = {}
    for key, spec in DEPENDENCIES.items():
        stats = count_tree(HOME / spec["root"])
        stats["commits"] = git_commits(HOME / spec["root"])
        stats["label"] = spec["label"]
        stats["author"] = spec["author"]
        stats["url"] = spec["url"]
        stats["note"] = spec["note"]
        dependencies[key] = stats

    index = find_backup_index()
    if index:
        for prefix, label in REMOTE.items():
            key = "oden_" + prefix.split("/")[-1].replace("-", "_")
            stats = count_remote(index, prefix)
            stats["commits"] = 0
            stats["source"] = "oden-via-backup"
            stats["label"] = label
            systems[key] = stats

    # Lines are only known for the local trees; the Oden trees are counted in
    # files. Both are reported, and the total adds only what it can add.
    local_loc = sum(s["code_loc"] for s in systems.values() if s["source"] == "local")
    local_files = sum(s["files"] for s in systems.values() if s["source"] == "local")
    remote_files = sum(s["files"] for s in systems.values() if s["source"] != "local")
    totals = {
        "local_code_loc": local_loc,
        "local_files": local_files,
        "remote_files": remote_files,
        "files": local_files + remote_files,
        "commits": sum(s["commits"] for s in systems.values()),
        "bytes": sum(s["bytes"] for s in systems.values()),
    }

    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "build/opencode-manifest.py",
        "agent": "opencode",
        "backup_index": str(index) if index else None,
        "systems": systems,
        "dependencies": dependencies,
        "totals": totals,
        "taa_core": measure_taa_core(),
    }

    out = Path(args.out)
    if not out.is_absolute():
        out = Path(__file__).resolve().parent.parent / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {out}")
    print("  own work:")
    for key, stats in sorted(systems.items(), key=lambda x: -x[1]["files"]):
        tag = "  (Oden, via backup)" if stats["source"] != "local" else ""
        loc = stats.get("code_loc")
        size = f"{loc:>8,} loc  " if loc is not None else "          "
        print(f"    {key:24s} {size}{stats['files']:>6} files{tag}")
    print(f"    {'TOTAL (local lines)':24s} {totals['local_code_loc']:>8,} loc")
    print(f"    {'TOTAL (files, both hosts)':24s} {totals['files']:>8,} files")
    print("  measured, not mine:")
    for key, stats in dependencies.items():
        print(f"    {key:24s} {stats['code_loc']:>8,} loc  by {stats['author']}")
    print(f"  taa core: {manifest['taa_core']['loc']:,} LOC, "
          f"identical={manifest['taa_core']['identical_across_designs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
