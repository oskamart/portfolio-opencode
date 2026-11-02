#!/usr/bin/env python3
"""Point opencode.osys.one at GitHub Pages through the GoDaddy DNS API.

The portfolio is already published to GitHub Pages with CNAME =
opencode.osys.one. This script adds the one DNS record that is missing:

    opencode.osys.one.  CNAME  oskamart.github.io

The apex osys.one and the shared kit are not touched: the apex A records
still point at the AWS Global Accelerator address, and the shared kit's
Pages site keeps the osys.one CNAME.

Credentials: a GoDaddy API key and secret in the environment:

    export GODADDY_API_KEY=...
    export GODADDY_API_SECRET=...

Create them at https://developer.godaddy.com/ (Account -> API keys).

Usage:
    python3 deploy/opencode-dns.py            # show the plan
    python3 deploy/opencode-dns.py --apply    # make the change
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DOMAIN = "osys.one"
HOST = "opencode"
TARGET = "oskamart.github.io"
API = "https://api.godaddy.com/v1"


def api(method: str, path: str, body=None):
    key = os.environ.get("GODADDY_API_KEY")
    secret = os.environ.get("GODADDY_API_SECRET")
    if not key or not secret:
        sys.exit(
            "Set GODADDY_API_KEY and GODADDY_API_SECRET.\n"
            "Create a key at https://developer.godaddy.com/ -> Account -> API keys."
        )
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method)
    req.add_header("Authorization", f"sso-key {key}:{secret}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except urllib.error.URLError as exc:
        sys.exit(f"GoDaddy API unreachable: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    status, records = api("GET", f"/domains/{DOMAIN}/records")
    if status != 200:
        sys.exit(f"cannot read records: {status} {records}")

    print("── current records for osys.one ──────────────────────────────")
    for rec in records:
        print(f"  {rec['type']:6s} {rec.get('name',''):22s} {rec['value'][:60]}")

    existing = [
        r for r in records
        if r["type"] == "CNAME" and r.get("name") == HOST
    ]
    if existing:
        print(f"\n  {HOST}.{DOMAIN} already points at {existing[0]['value']}")
    else:
        print(f"\n── plan ─────────────────────────────────────────────────────")
        print(f"  add CNAME {HOST} -> {TARGET}")

    print("\n  The apex records are not touched, and neither is the shared")
    print("  kit's Pages site, which keeps the osys.one CNAME.")

    if not args.apply:
        print("\nDry run. Re-run with --apply to make the change.")
        return 0

    if not args.yes:
        reply = input("\nApply? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("aborted")
            return 1

    if existing:
        payload = [{"type": "CNAME", "name": HOST, "value": TARGET, "ttl": 3600}]
    else:
        payload = [{"type": "CNAME", "name": HOST, "value": TARGET, "ttl": 3600}]

    code, body = api("PATCH", f"/domains/{DOMAIN}/records/{HOST}/CNAME", payload[0])
    if code == 204:
        print("\n✓ record written")
        print("  DNS changes take a few minutes to propagate.")
        return 0

    # Some accounts reject a PATCH on a name that does not exist yet; fall
    # back to appending the record to the zone.
    code, body = api("PUT", f"/domains/{DOMAIN}/records", payload)
    if code in (200, 201, 204):
        print("\n✓ record written")
        print("  DNS changes take a few minutes to propagate.")
        return 0

    print(f"\n✗ GoDaddy returned {code}: {body}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
