#!/usr/bin/env python3
"""Build a single self-contained HTML file from the portfolio.

The output has the CSS and JavaScript inlined and the fonts embedded as
base64, so it opens correctly from a file:// path with no server and no
network. This is what gets copied to the Desktop.

Usage: python3 build/opencode-bundle.py [--out ~/Desktop/portfolio/portfolio.html]
"""

from __future__ import annotations

import argparse
import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def data_uri(path: Path) -> str:
    mime = {
        ".woff2": "font/woff2",
        ".svg": "image/svg+xml",
        ".png": "image/png",
    }.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path.home() / "Desktop/portfolio/portfolio.html"))
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    html = (ROOT / "index.html").read_text(encoding="utf-8")

    # ── inline the stylesheet, with the fonts as data URIs ────────────────
    css = (ASSETS / "css/site.css").read_text(encoding="utf-8")
    for name in ("spectral-400", "spectral-600", "plexmono-400", "plexmono-500"):
        woff = ASSETS / "fonts" / f"{name}.woff2"
        if woff.exists():
            css = css.replace(f'url("../fonts/{name}.woff2")', f'url("{data_uri(woff)}")')
    html = html.replace(
        '<link rel="stylesheet" href="assets/css/site.css">',
        "<style>\n" + css + "\n</style>",
    )

    # ── inline the script ─────────────────────────────────────────────────
    js = (ASSETS / "js/site.js").read_text(encoding="utf-8")
    html = html.replace(
        '<script src="assets/js/site.js" type="module"></script>',
        "<script>\n" + js + "\n</script>",
    )

    # ── inline the favicon ───────────────────────────────────────────────
    icon = ASSETS / "favicon.svg"
    if icon.exists():
        html = html.replace(
            '<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">',
            f'<link rel="icon" href="{data_uri(icon)}" type="image/svg+xml">',
        )

    # ── drop the preload links: the fonts are inlined as data URIs ───────
    # A preload pointing at a file that no longer exists is only a warning,
    # but removing it keeps the console clean.
    html = re.sub(r'<link rel="preload"[^>]*>\s*', "", html)

    # ── inline the manifest, so the figures survive offline ───────────────
    manifest = (ASSETS / "manifest.json").read_text(encoding="utf-8")
    # A file:// page cannot fetch() a sibling file in some browsers, so the
    # manifest is embedded and the fetch is redirected to read it from here.
    html = html.replace(
        '<script src="assets/js/site.js" type="module"></script>',
        "<script>\n" + js + "\n</script>",
    )
    html = html.replace(
        "</body>",
        "<script id=\"embedded-manifest\" type=\"application/json\">\n"
        + manifest.replace("</", "<\\/")
        + "\n</script>\n</body>",
    )

    # Point the loader at the embedded copy when the page is a local file.
    html = html.replace(
        'const res = await fetch("assets/manifest.json", { cache: "no-cache" });',
        '''const embedded = document.getElementById("embedded-manifest");
    if (embedded && location.protocol === "file:") {
      return JSON.parse(embedded.textContent);
    }
    const res = await fetch("assets/manifest.json", { cache: "no-cache" });''',
    )

    if args.title:
        html = re.sub(r"<title>.*?</title>", f"<title>{args.title}</title>", html, count=1, flags=re.S)

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    size = out.stat().st_size
    print(f"wrote {out}")
    print(f"  {size:,} bytes — self-contained, opens from file://")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
