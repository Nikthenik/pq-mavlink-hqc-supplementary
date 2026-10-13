#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Two checks for Sections VII-C and VII-D of the manuscript.

1. Bytes on the wire and serialization lower bounds. Sums the length of every MAVLink frame
   of the HQC dialect (message ids 61000-61008) in the one session captured in both
   directions, with and without the repeated HQC_CT_CHUNK fragments, and divides by the
   byte rate of a serial telemetry link at 57 600 baud, 8N1 (10 bits per byte, 5760 B/s):
   the default of ArduPilot's SERIAL1 port and the usual rate of telemetry radios. Also
   gives the handshake objects alone (public key + two ciphertexts) for HQC-128 and
   ML-KEM-512. These are lower bounds from byte counts, not measurements.

2. Why no HQC_ABORT appears in the five incomplete attempts: for each incomplete attempt in
   R1-R5, the time from its last message to the first message of the next attempt, against
   the FC's 20 s handshake timeout (HS_TIMEOUT_MS in GCS_KEMTLS.cpp).

Usage:
    python bytes_and_retries.py [capture_directory]
"""
import collections
import os
import sys

from inventario_capturas import read_pcapng, decode
from extraer_sesiones import segmentar
from tabla_reproducible import R, BIDIR, STATUS, CT_CHUNK

BAUD_BYTES = 57600 / 10.0
OBJECTS = (("HQC-128", 2249 + 2 * 4433), ("ML-KEM-512", 800 + 2 * 768))


def frames(path):
    """-> [(ts, msgid, frame_length, payload)] of every HQC frame sent over UDP."""
    ev = []
    for ts, lt, data in read_pcapng(path):
        d = decode(lt, data)
        if not d or d[0] != "UDP" or not d[5]:
            continue
        buf, i, n = d[5], 0, len(d[5])
        while i < n:
            if buf[i] == 0xFD and i + 12 <= n:
                plen = buf[i + 1]
                total = 12 + plen + (13 if buf[i + 2] & 0x01 else 0)
                if i + total > n:
                    break
                msgid = buf[i + 7] | buf[i + 8] << 8 | buf[i + 9] << 16
                if 61000 <= msgid <= 61008:
                    ev.append((ts, msgid, total, bytes(buf[i + 10:i + 10 + plen])))
                i += total
            else:
                i += 1
    ev.sort(key=lambda e: e[0])
    return ev


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")

    # ------------------------------------------------------------- 1. bytes on the wire
    ev = frames(os.path.join(d, BIDIR + ".pcapng"))
    total = sum(e[2] for e in ev)
    seen, unique = set(), 0
    for e in ev:
        if e[1] == CT_CHUNK:
            if e[3] in seen:                     # repeated fragment = identical payload
                continue
            seen.add(e[3])
        unique += e[2]
    print("Bidirectional session %s: %d HQC frames, %d B on the wire (with repeats)" % (BIDIR, len(ev), total))
    print("  without the repeated CT_CHUNK fragments: %d B" % unique)
    print("  at 57 600 baud 8N1 (5760 B/s): %.2f s with repeats, %.2f s without" % (total / BAUD_BYTES, unique / BAUD_BYTES))
    for name, size in OBJECTS:
        print("  objects alone %-10s %5d B -> %.2f s" % (name, size, size / BAUD_BYTES))
    per_type = collections.Counter()
    for e in ev:
        per_type[e[1]] += e[2]
    print("  bytes per message id:", dict(sorted(per_type.items())))

    # ------------------------------------------------------------- 2. incomplete attempts
    print("\nIncomplete attempts in R1-R5: gap until the next attempt (FC timeout: 20 s)")
    for name in R:
        bursts = segmentar([(t, m, l, "") for (t, m, l, _) in frames(os.path.join(d, name + ".pcapng"))], 2.0)
        for k, b in enumerate(bursts):
            if any(e[1] == STATUS for e in b):
                continue
            end = max(e[0] for e in b)
            nxt = bursts[k + 1][0][0] if k + 1 < len(bursts) else None
            print("  %s attempt %3d: lasts %.2f s; next attempt after %s" % (
                name, k + 1, end - b[0][0], "%.1f s" % (nxt - end) if nxt else "end of capture"))


if __name__ == "__main__":
    main()
