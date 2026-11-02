#!/usr/bin/env python3
"""Serve the portfolio locally on 127.0.0.1.

Binds to loopback by default; pass --host 0.0.0.0 to expose on the LAN.
Prints the URL and opens a browser unless --no-browser is given.

Usage: python3 serve.py [--port 8080] [--host 127.0.0.1] [--no-browser]
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".woff2": "font/woff2",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }

    def end_headers(self):
        # The manifest must never be stale during local iteration.
        if self.path.endswith("manifest.json"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    handler = functools.partial(Handler, directory=str(ROOT))
    try:
        httpd = Server((args.host, args.port), handler)
    except OSError as exc:
        print(f"Cannot bind {args.host}:{args.port} — {exc}")
        return 1

    url = f"http://{args.host}:{httpd.server_address[1]}/"
    print(f"osys.one portfolio: {url}")
    print("Ctrl-C to stop.")

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
