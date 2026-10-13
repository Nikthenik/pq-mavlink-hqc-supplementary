#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Does the handshake delay the FC's ordinary MAVLink traffic? (manuscript, Section VII-D)

The stress runs R1-R5 capture everything the FC emits, including its ordinary traffic
(HEARTBEAT and the rest), so the rate of that traffic can be compared inside and outside
the handshake windows.

Measures:
  - intervals between consecutive HEARTBEAT frames of the FC: those that contain a
    handshake against those that do not;
  - the rate of non-HQC frames from the FC inside the handshake windows against the rate
    outside them.

Limit: the FC emits little ordinary traffic in these captures (about 2.3 frames/s, mostly
HEARTBEAT at 1 Hz). This measures contention on the traffic that exists, not on a 50 Hz
command stream.

Usage:
    python contencion_canal.py [capture_directory]
"""
import collections
import os
import sys

from inventario_capturas import read_pcapng, decode, mav_frames
from extraer_sesiones import segmentar, media, pct

HQC_LO, HQC_HI, HEARTBEAT, STATUS = 61000, 61008, 0, 61006
R = ["fc_20251113_180441", "fc_20251113_182734", "fc_20251113_184155",
     "fc_20251113_190020", "fc_20251113_191218"]
FC = "192.168.42.1"


def tramas_fc(path):
    """-> [(ts, msgid)] de todo lo que emite el FC por UDP."""
    out = []
    for ts, lt, data in read_pcapng(path):
        d = decode(lt, data)
        if not d:
            continue
        proto, src, sp, dst, dp, payload = d
        if proto != "UDP" or src != FC or not payload:
            continue
        for _, _, msgid, _ in mav_frames(payload):
            out.append((ts, msgid))
    return sorted(out)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")
    hb_con, hb_sin = [], []
    n_dentro = n_fuera = 0
    t_dentro = t_fuera = 0.0
    for n in R:
        tr = tramas_fc(os.path.join(d, n + ".pcapng"))
        if not tr:
            continue
        hqc = [(t, m, 0, "") for t, m in tr if HQC_LO <= m <= HQC_HI]
        ventanas = []
        for r in segmentar(hqc, 2.0):
            ts = [e[0] for e in r]
            ventanas.append((min(ts), max(ts)))

        def dentro(t):
            return any(a <= t <= b for a, b in ventanas)

        ordinarias = [(t, m) for t, m in tr if not (HQC_LO <= m <= HQC_HI)]
        for t, m in ordinarias:
            if dentro(t):
                n_dentro += 1
            else:
                n_fuera += 1
        dur_total = tr[-1][0] - tr[0][0]
        dur_hs = sum(b - a for a, b in ventanas)
        t_dentro += dur_hs
        t_fuera += dur_total - dur_hs

        hb = [t for t, m in ordinarias if m == HEARTBEAT]
        for a, b in zip(hb, hb[1:]):
            solapa = any(not (vb < a or va > b) for va, vb in ventanas)
            (hb_con if solapa else hb_sin).append(b - a)

    def fila(nombre, xs):
        if not xs:
            return "  %-46s sin datos" % nombre
        return "  %-46s n=%-5d media %.3f  p50 %.3f  p95 %.3f  max %.3f s" % (
            nombre, len(xs), media(xs), pct(xs, .5), pct(xs, .95), max(xs))

    print("=" * 104)
    print("CONTENCION DEL CANAL DURANTE EL HANDSHAKE -- R1-R5, trafico que emite el FC")
    print("=" * 104)
    print(fila("Intervalo HEARTBEAT sin handshake en medio", hb_sin))
    print(fila("Intervalo HEARTBEAT con un handshake en medio", hb_con))
    if t_dentro and t_fuera:
        print()
        print("  Tasa de tramas no-HQC del FC fuera de handshakes : %.2f tramas/s  (%d en %.0f s)"
              % (n_fuera / t_fuera, n_fuera, t_fuera))
        print("  Tasa de tramas no-HQC del FC dentro de handshakes: %.2f tramas/s  (%d en %.1f s)"
              % (n_dentro / t_dentro, n_dentro, t_dentro))


if __name__ == "__main__":
    main()
