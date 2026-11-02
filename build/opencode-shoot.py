#!/usr/bin/env python3
"""Capture the portfolio with headless Chromium.

Screenshots land in shots/opencode/ so another agent's captures are never
overwritten.

Usage: python3 build/opencode-shoot.py [--url ...] [--width 1440] [--height 900]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CHROME = os.path.expanduser(
    "~/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell"
)
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8094/")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--name", default="viewport")
    ap.add_argument("--out", default="shots/opencode")
    args = ap.parse_args()

    if not os.path.exists(CHROME):
        print(f"chromium not found at {CHROME}")
        return 1

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="oc-shoot-")
    shot = out / f"{args.name}.png"
    cmd = [
        CHROME,
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--virtual-time-budget=3500",
        f"--user-data-dir={os.path.join(tmp, 'profile')}",
        f"--window-size={args.width},{args.height}",
        f"--screenshot={shot}",
        args.url,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print("chromium timed out")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if shot.exists():
        print(f"wrote {shot} ({shot.stat().st_size:,} bytes)")
        return 0
    print("screenshot failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
