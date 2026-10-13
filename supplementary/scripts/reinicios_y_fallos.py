#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Restarts between attempts, and what the five incomplete attempts show (Sections VII-B, VII-C).

For every attempt of the stress runs R1-R5 (segmented as in extraer_sesiones.py) the script
reports, from the frames the FC emits:

  1. Restarts. The FC's UDP source port and the MAVLink sequence number of its first frame from
     that port. A new port whose first frame has sequence 0 or 1 is a freshly started autopilot
     process.
  2. Start-up. Whether the FC's "ArduPilot Ready" STATUSTEXT, which ArduPilot sends when
     AP_Vehicle::setup() finishes, arrives after the attempt's HQC_HELLO_ACK. Until then the
     firmware processes received MAVLink from its start-up delay callback, at most every 20 ms
     (AP_Vehicle::scheduler_delay_callback), not from the 400 Hz main loop. The message is
     readable only before the session activates (afterwards STATUSTEXT payloads are
     encrypted), so the count is a lower bound.
  3. Incomplete attempts (no HQC_STATUS). For each: PK_ACK and CT_CHUNK counts, whether any
     HQC_STATUS was emitted (the FC sends one in reply to every HQC_FINISH it receives, valid or
     not: GCS_KEMTLS.cpp, handle_hqc_finish), and whether the FC signed any frame before the
     next attempt (it installs the signing key only after verifying HQC_FINISH).

It reads frame headers and the clear-text STATUSTEXT diagnostics only; it decrypts nothing.

Usage:
    python reinicios_y_fallos.py path/to/ardupilot_post_quantum_kem/captures
"""
import collections
import os
import sys

from inventario_capturas import read_pcapng, decode
from extraer_sesiones import eventos_hqc, segmentar

FC = "192.168.42.1"
RUNS = ["fc_20251113_180441", "fc_20251113_182734", "fc_20251113_184155",
        "fc_20251113_190020", "fc_20251113_191218"]
HELLO_ACK, CT_CHUNK, STATUS, PK_ACK = 61001, 61003, 61006, 61007


def fc_frames(path):
    """-> [(ts, source_port, seq, msgid, signed, statustext_or_None)] for MAVLink 2 frames the
    FC sends over UDP."""
    out = []
    for ts, lt, data in read_pcapng(path):
        d = decode(lt, data)
        if not d or d[0] != "UDP" or not d[5] or ts is None or d[1] != FC:
            continue
        buf, i = d[5], 0
        while i + 12 <= len(buf):
            if buf[i] != 0xFD:
                i += 1
                continue
            ln, inc, seq = buf[i + 1], buf[i + 2], buf[i + 4]
            msgid = buf[i + 7] | (buf[i + 8] << 8) | (buf[i + 9] << 16)
            end = i + 10 + ln + 2 + (13 if inc & 1 else 0)
            if end > len(buf):
                break
            text = None
            if msgid == 253 and ln >= 2:
                text = bytes(buf[i + 11:i + 10 + ln]).split(b"\0")[0].decode("latin-1")
            out.append((ts, d[2], seq, msgid, bool(inc & 1), text))
            i = end
    return out


def main():
    capdir = sys.argv[1] if len(sys.argv) > 1 else "."
    ports, first_seq_ok, early, incomplete, metrics = [], 0, [], [], []
    total = signed_after_complete = 0
    for run in RUNS:
        path = os.path.join(capdir, run + ".pcapng")
        attempts = segmentar(eventos_hqc(path), 2.0)
        frames = fc_frames(path)
        first_on_port = {}
        for f in frames:
            first_on_port.setdefault(f[1], f)
        first_seq_ok += sum(1 for f in first_on_port.values() if f[2] <= 1)
        for k, att in enumerate(attempts):
            total += 1
            t0, t1 = att[0][0], att[-1][0]
            t_ack = next(e[0] for e in att if e[1] == HELLO_ACK)
            inside = [f for f in frames if t0 <= f[0] <= t1]
            ports.append(((run, k + 1), tuple(sorted(set(f[1] for f in inside)))))
            complete = any(e[1] == STATUS for e in att)
            ready = [f[0] - t_ack for f in frames
                     if f[5] and "ArduPilot Ready" in f[5] and 0 < f[0] - t_ack < 2.0]
            if ready and complete:
                early.append((run, k + 1, min(ready)))
            nxt = attempts[k + 1][0][0] if k + 1 < len(attempts) else t1 + 5.0
            if complete:
                t_status = max(e[0] for e in att if e[1] == STATUS)
                signed_after_complete += any(f[4] for f in frames if t_status < f[0] < nxt - 0.2)
                ct = [e[0] for e in att if e[1] == CT_CHUNK]
                last_pk_ack = max(e[0] for e in att if e[1] == PK_ACK)
                next_ct = min(t for t in ct if t > last_pk_ack)
                metrics.append(((run, k + 1), next(e[0] for e in att if e[1] == STATUS) - t_ack,
                                max(ct) - min(ct), 1000 * (next_ct - last_pk_ack)))
            else:
                after = [f for f in frames if t1 + 0.2 <= f[0] < nxt - 0.2]
                n = collections.Counter(e[1] for e in att)
                incomplete.append((run, k + 1, t1 - t0, n.get(PK_ACK, 0), n.get(CT_CHUNK, 0),
                                   n.get(STATUS, 0), sum(f[4] for f in after), len(after)))
    shared = collections.Counter(p for _, p in ports)
    print("Restarts (R1-R5, %d attempts)" % total)
    print("  distinct FC source ports                  %d" % len(set(p for _, ps in ports for p in ps)))
    print("  attempts sharing a port with another       %d" % sum(n for p, n in shared.items() if n > 1))
    for (run, k), ps in ports:
        if shared[ps] > 1:
            print("    %s attempt %2d, port %s" % (run, k, ",".join(str(p) for p in ps)))
    print("  ports whose first FC frame has seq 0 or 1  %d" % first_seq_ok)
    print("Start-up: completed attempts whose clear-text 'ArduPilot Ready' follows HQC_HELLO_ACK "
          "(a lower bound): %d" % len(early))
    for run, k, dt in early:
        print("  %s attempt %2d: %.2f s after HQC_HELLO_ACK" % (run, k, dt))
    early_ids = set((run, k) for run, k, _ in early)
    print("Maxima of Table VI, Block A, and without the attempts listed under Start-up")
    for col, label in ((1, "FC window HELLO_ACK->STATUS (s)"), (2, "ciphertext stream (s)"),
                       (3, "last PK_ACK -> next CT_CHUNK (ms)")):
        top = max(metrics, key=lambda m: m[col])
        rest = max(m[col] for m in metrics if m[0] not in early_ids)
        print("  %-34s max %.3f (%s attempt %d); without those attempts %.3f"
              % (label, top[col], top[0][0], top[0][1], rest))
    print("Completed attempts followed by at least one signed FC frame: %d" % signed_after_complete)
    print("Incomplete attempts (no HQC_STATUS)")
    for run, k, dur, pk, ct, st, signed, nafter in incomplete:
        print("  %s attempt %2d: lasts %.2f s, PK_ACK %2d, CT_CHUNK %3d, HQC_STATUS %d, "
              "signed frames before the next attempt %d of %d" % (run, k, dur, pk, ct, st, signed, nafter))


if __name__ == "__main__":
    main()
