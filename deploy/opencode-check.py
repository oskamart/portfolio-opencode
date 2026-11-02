#!/usr/bin/env python3
"""Report where opencode.osys.one currently points and whether it is serving.

Usage: python3 deploy/opencode-check.py
"""

from __future__ import annotations

import socket
import ssl
import sys
import urllib.error
import urllib.request

DOMAIN = "opencode.osys.one"
GH_PAGES_IPS = {"185.199.108.153", "185.199.109.153",
                "185.199.110.153", "185.199.111.153"}


def resolve(host: str) -> set[str]:
    out = set()
    try:
        for info in socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM):
            out.add(info[4][0])
    except socket.gaierror:
        pass
    return out


def main() -> int:
    print("── opencode.osys.one ────────────────────────────────────────")
    ips = resolve(DOMAIN)
    if not ips:
        print(f"  ✗ {DOMAIN} does not resolve yet")
        print("    the CNAME record at the registrar has not propagated")
        return 1

    print(f"  resolves to: {', '.join(sorted(ips))}")
    if ips & GH_PAGES_IPS:
        print("  ✓ points at GitHub Pages")
    else:
        print("  ✗ not pointing at GitHub Pages yet")

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((DOMAIN, 443), timeout=12) as sock:
            with ctx.wrap_socket(sock, server_hostname=DOMAIN) as tls:
                cert = tls.getpeercert()
        cn = dict(x[0] for x in cert.get("subject", [])).get("commonName", "")
        print(f"  ✓ certificate CN: {cn}")
    except Exception as exc:
        print(f"  ✗ TLS: {exc}")

    try:
        req = urllib.request.Request(f"https://{DOMAIN}/",
                                     headers={"User-Agent": "portfolio-check"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(4096).decode("utf-8", "replace")
            print(f"  ✓ HTTP {resp.status}")
            if "Oskar" in body:
                print("  ✓ this portfolio is being served")
    except urllib.error.HTTPError as exc:
        print(f"  ✗ HTTP {exc.code}")
    except Exception as exc:
        print(f"  ✗ HTTP: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
