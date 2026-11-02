#!/usr/bin/env python3
"""Decrypt Chromium/Brave cookies on Linux (v10/v11 scheme) with no dependencies.

Chromium on Linux stores the cookie key in the profile's "Local State" file,
encrypted with a hard-coded PBKDF2 passphrase ("peanuts"). Each cookie value
is prefixed "v10" or "v11" and sealed with AES-128-GCM.

This is a small, self-contained AES implementation plus the Chromium key
derivation, so it works in a sandbox with no pip and no cryptography module.

Usage: python3 decrypt_cookies.py <profile-dir> [host-filter]
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import sys
from pathlib import Path

# ── AES ────────────────────────────────────────────────────────────────────
SBOX = []
INV_SBOX = [0] * 256


def _build_sbox():
    p = q = 1
    sbox = [0] * 256
    while True:
        # multiply p by 3
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        # divide q by 3
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


SBOX = _build_sbox()
for i, v in enumerate(SBOX):
    INV_SBOX[v] = i

RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def xtime(a):
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x1B) & 0xFF
    return a


def gmul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        b >>= 1
        a = xtime(a)
    return r


def key_expansion(key: bytes):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[b] for b in temp]
            temp[0] ^= RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [SBOX[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
    return w, nr


def _add_round_key(state, w, rnd):
    for c in range(4):
        for r in range(4):
            state[r][c] ^= w[rnd * 4 + c][r]


def _sub_bytes(state, box):
    for r in range(4):
        for c in range(4):
            state[r][c] = box[state[r][c]]


def _shift_rows(state):
    for r in range(1, 4):
        state[r] = state[r][r:] + state[r][:r]


def _inv_shift_rows(state):
    for r in range(1, 4):
        state[r] = state[r][-r:] + state[r][:-r]


def _mix_columns(state):
    for c in range(4):
        a = [state[r][c] for r in range(4)]
        state[0][c] = gmul(a[0], 2) ^ gmul(a[1], 3) ^ a[2] ^ a[3]
        state[1][c] = a[0] ^ gmul(a[1], 2) ^ gmul(a[2], 3) ^ a[3]
        state[2][c] = a[0] ^ a[1] ^ gmul(a[2], 2) ^ gmul(a[3], 3)
        state[3][c] = gmul(a[0], 3) ^ a[1] ^ a[2] ^ gmul(a[3], 2)


def _inv_mix_columns(state):
    for c in range(4):
        a = [state[r][c] for r in range(4)]
        state[0][c] = gmul(a[0], 14) ^ gmul(a[1], 11) ^ gmul(a[2], 13) ^ gmul(a[3], 9)
        state[1][c] = gmul(a[0], 9) ^ gmul(a[1], 14) ^ gmul(a[2], 11) ^ gmul(a[3], 13)
        state[2][c] = gmul(a[0], 13) ^ gmul(a[1], 9) ^ gmul(a[2], 14) ^ gmul(a[3], 11)
        state[3][c] = gmul(a[0], 11) ^ gmul(a[1], 13) ^ gmul(a[2], 9) ^ gmul(a[3], 14)


def _encrypt_block(block: bytes, w, nr) -> bytes:
    state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    _add_round_key(state, w, 0)
    for rnd in range(1, nr + 1):
        _sub_bytes(state, SBOX)
        _shift_rows(state)
        if rnd != nr:
            _mix_columns(state)
        _add_round_key(state, w, rnd)
    return bytes(state[r][c] for c in range(4) for r in range(4))


def _decrypt_block(block: bytes, w, nr) -> bytes:
    state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    _add_round_key(state, w, nr)
    for rnd in range(nr - 1, -1, -1):
        _inv_shift_rows(state)
        _sub_bytes(state, INV_SBOX)
        _add_round_key(state, w, rnd)
        if rnd != 0:
            _inv_mix_columns(state)
    return bytes(state[r][c] for c in range(4) for r in range(4))


def _ghash_mul(x: bytes, y: bytes) -> bytes:
    """Multiply two 128-bit blocks in GF(2^128)."""
    z = 0
    v = int.from_bytes(y, "big")
    for i in range(128):
        if x[i // 8] & (0x80 >> (i % 8)):
            z ^= v
        if v & 1:
            v = (v >> 1) ^ (0xE1000000000000000000000000000000)
        else:
            v >>= 1
    return z.to_bytes(16, "big")


def _ghash(h: bytes, data: bytes) -> bytes:
    y = b"\x00" * 16
    for i in range(0, len(data), 16):
        block = data[i:i + 16]
        if len(block) < 16:
            block = block + b"\x00" * (16 - len(block))
        y = _ghash_mul(bytes(a ^ b for a, b in zip(y, block)), h)
    return y


def _ctr_inc(counter: bytes) -> bytes:
    prefix = counter[:12]
    c = int.from_bytes(counter[12:], "big")
    c = (c + 1) % (1 << 32)
    return prefix + c.to_bytes(4, "big")


def _pad16(data: bytes) -> bytes:
    """Zero-pad to a multiple of 16 bytes."""
    if len(data) % 16:
        return data + b"\x00" * (16 - len(data) % 16)
    return data


def aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes,
                    aad: bytes = b"") -> bytes:
    """Decrypt AES-GCM. `key` is 16/24/32 bytes; `nonce` is 12 bytes."""
    w, nr = key_expansion(key)
    h = _encrypt_block(b"\x00" * 16, w, nr)

    # CTR mode starts at J0 + 1.
    j0 = nonce + b"\x00\x00\x00\x01"
    counter = j0
    out = bytearray()
    for i in range(0, len(ciphertext), 16):
        counter = _ctr_inc(counter)
        stream = _encrypt_block(counter, w, nr)
        chunk = ciphertext[i:i + 16]
        out.extend(bytes(a ^ b for a, b in zip(chunk, stream)))

    # GHASH authenticates the CIPHERTEXT, not the plaintext.
    g = _ghash(h, _pad16(aad) + _pad16(ciphertext)
               + (len(aad) * 8).to_bytes(8, "big")
               + (len(ciphertext) * 8).to_bytes(8, "big"))

    expected = bytes(a ^ b for a, b in zip(_encrypt_block(j0, w, nr), g))
    if expected != tag:
        raise ValueError("GCM tag mismatch")
    return bytes(out)


# ── PBKDF2 (Chromium's "peanuts" derivation) ───────────────────────────────
def pbkdf2_sha1(password: bytes, salt: bytes, iterations: int, length: int) -> bytes:
    import hashlib
    import struct

    def h(pw, s, i):
        return hashlib.sha1(pw + s + struct.pack(">I", i)).digest()

    out = b""
    block = 1
    while len(out) < length:
        u = h(password, salt, block)
        result = u
        for _ in range(iterations - 1):
            u = h(password, u, 1)
            result = bytes(a ^ b for a, b in zip(result, u))
        out += result
        block += 1
    return out[:length]


# ── Chromium cookie decryption ──────────────────────────────────────────────
def load_key(profile: Path) -> bytes:
    # The "Local State" file sits at the browser root, not in the profile dir.
    candidates = [
        profile / "Local State",
        profile.parent / "Local State",
        profile.parent.parent / "Local State",
    ]
    state_path = next((c for c in candidates if c.exists()), None)
    if state_path is None:
        raise FileNotFoundError(f"no Local State in {[str(c) for c in candidates]}")
    state = json.loads(state_path.read_text())
    enc = state["os_crypt"]["encrypted_key"]
    raw = base64.b64decode(enc)
    if raw[:5] != b"DPEnc":
        raise ValueError(f"unexpected key prefix {raw[:5]!r}")
    iv = raw[5:21]
    wrapped = raw[21:]
    # v10/v11: the key is sealed with the fixed "peanuts" passphrase.
    key = pbkdf2_sha1(b"peanuts", iv, 1, 16)
    w, nr = key_expansion(key)
    # The wrapped key is AES-256-CBC with PKCS#7.
    from ctypes import Array  # noqa: F401  (keep import local)
    plain = _aes_cbc_decrypt(wrapped, key, iv)
    return plain[:16]


def _aes_cbc_decrypt(ct: bytes, key: bytes, iv: bytes) -> bytes:
    import struct
    w, nr = key_expansion(key)
    pad = ct[-1]
    out = bytearray()
    prev = iv
    for i in range(0, len(ct), 16):
        blk = ct[i:i + 16]
        dec = _decrypt_block(blk, w, nr)
        out.extend(bytes(a ^ b for a, b in zip(dec, prev)))
        prev = blk
    if pad and 1 <= pad <= 16:
        out = out[:-pad]
    return bytes(out)


def decrypt_value(enc: bytes, key: bytes) -> str:
    if not enc:
        return ""
    prefix = enc[:3]
    if prefix not in (b"v10", b"v11"):
        return ""
    nonce = enc[3:15]
    ct = enc[15:-16]
    tag = enc[-16:]
    plain = aes_gcm_decrypt(key, nonce, ct, tag)
    return plain[32:].decode("utf-8", "replace")  # strip the SHA-256 host hash


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    profile = Path(sys.argv[1]).expanduser()
    filt = sys.argv[2] if len(sys.argv) > 2 else ""

    key = load_key(profile)
    print(f"# key loaded for {profile}")

    cookies_db = profile / "Cookies"
    if not cookies_db.exists():
        cookies_db = profile / "Network" / "Cookies"

    import shutil
    import tempfile
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy(cookies_db, tmp)
    con = sqlite3.connect(tmp)

    for host, name, value, enc in con.execute(
        "select host_key, name, value, encrypted_value from cookies"
    ):
        if filt and filt not in host:
            continue
        plain = value
        if enc:
            try:
                plain = decrypt_value(bytes(enc), key)
            except Exception:
                plain = f"<undecryptable: {bytes(enc)[:3]!r}>"
        print(f"{host}\t{name}\t{plain}")

    con.close()
    os.unlink(tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
