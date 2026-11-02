#!/usr/bin/env python3
"""Extract text from a PDF without any third-party dependency.

Handles the two cases that matter here:
  * simple fonts, where the text is drawn with literal strings
  * Type0 / CID fonts, where the strings are hex CIDs that need the
    font's ToUnicode CMap to be decoded

Usage: python3 build/opencode-pdf-text.py <file.pdf> [--raw]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from pathlib import Path


def streams(data: bytes):
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        try:
            yield zlib.decompress(raw)
        except zlib.error:
            yield raw


def build_cmaps(data: bytes) -> dict[int, str]:
    """Decode every ToUnicode CMap in the file into one lookup."""
    mapping: dict[int, str] = {}
    for dec in streams(data):
        if b"beginbfchar" not in dec and b"beginbfrange" not in dec:
            continue
        for blk in re.findall(rb"beginbfchar(.*?)endbfchar", dec, re.S):
            for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
                try:
                    mapping[int(a, 16)] = bytes.fromhex(b.decode()).decode("utf-16-be", "replace")
                except ValueError:
                    pass
        for blk in re.findall(rb"beginbfrange(.*?)endbfrange", dec, re.S):
            for a, b, c in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
                lo, hi, dst = int(a, 16), int(b, 16), int(c, 16)
                for i in range(lo, min(hi, lo + 4096) + 1):
                    try:
                        mapping[i] = chr(dst + (i - lo))
                    except ValueError:
                        pass
    return mapping


def decode_hex(hexs: str, mapping: dict[int, str]) -> str:
    out = []
    for i in range(0, len(hexs) - 3, 4):
        cid = int(hexs[i:i + 4], 16)
        out.append(mapping.get(cid, ""))
    return "".join(out)


def decode_literal(raw: bytes) -> str:
    s = raw.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
    return s.decode("latin-1", "replace")


def extract(path: Path) -> list[list[str]]:
    data = path.read_bytes()
    mapping = build_cmaps(data)
    pages: list[list[str]] = []

    for dec in streams(data):
        if b"Tj" not in dec and b"TJ" not in dec:
            continue
        lines: list[str] = []
        for blk in re.findall(rb"BT(.*?)ET", dec, re.S):
            buf: list[str] = []
            for t in re.finditer(
                rb"<([0-9A-Fa-f]*)>\s*Tj|\((?:[^()\\]|\\.)*\)\s*Tj|\[(.*?)\]\s*TJ", blk, re.S
            ):
                if t.group(1) is not None:
                    buf.append(decode_hex(t.group(1).decode(), mapping))
                elif t.group(2) is not None:
                    parts = re.findall(rb"<([0-9A-Fa-f]+)>", t.group(2))
                    if parts:
                        buf.append(decode_hex("".join(p.decode() for p in parts), mapping))
                    else:
                        lits = re.findall(rb"\((?:[^()\\]|\\.)*\)", t.group(2))
                        buf.append("".join(decode_literal(l[1:-1]) for l in lits))
                else:
                    lit = t.group(0)
                    m = re.search(rb"\(((?:[^()\\]|\\.)*)\)", lit)
                    if m:
                        buf.append(decode_literal(m.group(1)))
            s = "".join(buf)
            if s.strip():
                lines.append(s)
        if lines:
            pages.append(lines)
    return pages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = Path(args.pdf).expanduser()
    pages = extract(path)

    if args.json:
        print(json.dumps(pages, ensure_ascii=False, indent=1))
        return 0

    for i, page in enumerate(pages, 1):
        print(f"===== page {i} =====")
        for line in page:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
