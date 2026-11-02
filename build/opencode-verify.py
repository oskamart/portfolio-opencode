#!/usr/bin/env python3
"""Verify the portfolio: links, anchors, assets, accessible names, and that
every figure on the page resolves to a real measurement.

The last check is the important one. A figure that renders "—" is a claim the
page could not back up.

Usage: python3 build/opencode-verify.py [--url http://127.0.0.1:8080/]
"""

from __future__ import annotations

import argparse
import html.parser
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = {
    "index.html",
    "assets/css/site.css",
    "assets/js/site.js",
    "assets/manifest.json",
    "assets/favicon.svg",
    "assets/fonts/spectral-400.woff2",
    "assets/fonts/spectral-600.woff2",
    "assets/fonts/plexmono-400.woff2",
    "assets/fonts/plexmono-500.woff2",
}

# Every measurement the page asks for must exist in the manifest.
REQUIRED_METRICS = [
    "totals.local_code_loc",
    "totals.files",
    "totals.commits",
    "generated",
    "taa_core.loc",
    "taa_core.designs",
    "dependencies.uvmstack.code_loc",
    "systems.cern_app.code_loc",
    "systems.cern_app.files",
    "systems.haelo.code_loc",
    "systems.odenflow.code_loc",
    "systems.odenflow.commits",
    "systems.oden_colibri.files",
    "systems.oden_colibri_vk.files",
    "systems.oden_colibri_ab.files",
    "systems.oden_hwbench_runtime.files",
    "systems.oden_oden_ide.files",
    "systems.oden_oden_ide_dev.files",
    "systems.oden_oquip2.files",
    "systems.oden_verification_methods.files",
    "systems.oden_self_improvement.files",
    "systems.oden_papers.files",
    "systems.phisix.code_loc",
]


class Collector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[str] = []
        self.assets: list[str] = []
        self.imgs_without_alt: list[str] = []
        self.interactive: list[tuple[str, str, bool]] = []
        self.metrics: list[str] = []
        self.lang: str | None = None
        self.title: str | None = None
        self._in_title = False
        self._stack: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)

        if tag == "html":
            self.lang = a.get("lang")
        if tag == "title":
            self._in_title = True

        if "id" in a and a["id"]:
            self.ids.append(a["id"])

        if "data-metric" in a:
            self.metrics.append(a["data-metric"])

        if tag == "a" and "href" in a:
            self.links.append(a["href"])
            self.interactive.append(
                (f"a[href={a['href']}]", a.get("aria-label") or a.get("title") or "", False)
            )
        if tag == "link" and a.get("href"):
            self.assets.append(a["href"])
        if tag == "script" and a.get("src"):
            self.assets.append(a["src"])
        if tag == "img":
            if a.get("src"):
                self.assets.append(a["src"])
            if "alt" not in a:
                self.imgs_without_alt.append(a.get("src", "?"))
        if tag == "button":
            self.interactive.append(
                (f"button[{a.get('id', '?')}]", a.get("aria-label") or a.get("title") or "", False)
            )
        if tag in ("input", "select", "textarea"):
            self.interactive.append((tag, a.get("aria-label", ""), False))

        if tag not in ("br", "hr", "img", "meta", "link", "input", "source"):
            self._stack.append((tag, []))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                _, chunks = self._stack.pop(i)
                text = "".join(chunks).strip()
                if text and self._stack:
                    ptag, pchunks = self._stack[-1]
                    self._stack[-1] = (ptag, pchunks + [text])
                if tag in ("a", "button") and text:
                    for j in range(len(self.interactive) - 1, -1, -1):
                        kind, label, has_text = self.interactive[j]
                        if kind.startswith(tag) and not label and not has_text:
                            self.interactive[j] = (kind, label, True)
                            break
                break

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data
        for i in range(len(self._stack)):
            tag, chunks = self._stack[i]
            self._stack[i] = (tag, chunks + [data])


def dig(obj, path):
    """Resolve a dotted path against nested dicts; None if any step is missing."""
    cur = obj
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080/")
    ap.add_argument("--no-serve-check", action="store_true")
    args = ap.parse_args()

    errors: list[str] = []
    notes: list[str] = []

    # ── files ─────────────────────────────────────────────────────────────
    for rel in sorted(REQUIRED):
        if not (ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    if not errors:
        notes.append(f"all {len(REQUIRED)} required files present")

    doc = Collector()
    doc.feed((ROOT / "index.html").read_text(encoding="utf-8"))

    if not doc.lang:
        errors.append("<html> has no lang attribute")
    if not (doc.title or "").strip():
        errors.append("<title> is empty")
    else:
        notes.append(f"title: {(doc.title or '').strip()[:60]}")

    for d in sorted({i for i in doc.ids if doc.ids.count(i) > 1}):
        errors.append(f"duplicate id: {d}")

    for href in doc.links:
        if href.startswith("#"):
            if href[1:] and href[1:] not in doc.ids:
                errors.append(f"anchor target missing: {href}")
        elif href.startswith(("http://", "https://", "mailto:", "tel:")):
            continue
        elif not (ROOT / href.split("#")[0]).exists():
            errors.append(f"link target missing: {href}")

    for src in doc.assets:
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        if not (ROOT / src.split("?")[0]).exists():
            errors.append(f"asset missing: {src}")

    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    for ref in re.findall(r'url\(["\']?([^"\')]+)["\']?\)', css):
        if ref.startswith(("data:", "http")):
            continue
        if not (ROOT / "assets/css" / ref).exists():
            errors.append(f"css asset missing: {ref}")

    for img in doc.imgs_without_alt:
        errors.append(f"<img> without alt: {img}")

    for kind, label, has_text in doc.interactive:
        if not label and not has_text:
            errors.append(f"unlabelled interactive element: {kind}")

    notes.append(
        f"{len(doc.links)} links, {len(doc.assets)} asset refs, "
        f"{len(doc.ids)} ids, {len(doc.interactive)} interactive elements checked"
    )

    # ── the manifest must back every figure on the page ──────────────────
    manifest_path = ROOT / "assets/manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"manifest.json invalid: {exc}")

    unknown = [m for m in doc.metrics if manifest and dig(manifest, m) is None]
    for m in sorted(set(unknown)):
        errors.append(f"page asks for a metric the manifest does not have: {m}")

    for m in REQUIRED_METRICS:
        if manifest and dig(manifest, m) is None:
            errors.append(f"required metric missing from the manifest: {m}")

    if manifest:
        notes.append(
            f"{len(manifest.get('systems', {}))} systems measured, "
            f"{manifest.get('totals', {}).get('local_code_loc', 0):,} local lines"
        )
        if manifest.get("taa_core", {}).get("identical_across_designs"):
            notes.append("shared AA engine verified byte-identical across designs")
        else:
            errors.append("the shared AA engine is no longer byte-identical across designs")

    # ── the served copy ───────────────────────────────────────────────────
    if not args.no_serve_check:
        for path in ("/", "/assets/manifest.json", "/assets/css/site.css", "/assets/js/site.js"):
            url = urljoin(args.url, path)
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    body = resp.read()
                    if resp.status != 200:
                        errors.append(f"{url} -> HTTP {resp.status}")
                    elif path.endswith(".json"):
                        json.loads(body)
                        notes.append("manifest.json serves and parses")
            except (urllib.error.URLError, OSError) as exc:
                errors.append(f"{url} unreachable: {exc}")

    print("── verification ─────────────────────────────────────────────")
    for n in notes:
        print(f"  ok   {n}")
    if errors:
        print()
        for e in errors:
            print(f"  FAIL {e}")
        print(f"\n{len(errors)} problem(s) found.")
        return 1
    print("\nno problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
