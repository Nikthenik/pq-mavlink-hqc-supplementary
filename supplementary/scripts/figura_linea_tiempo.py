#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Data for the handshake timeline figure (manuscript, Fig. 3).

Takes the one session captured in both directions (clear_fc_20251114_153259) and emits,
for every HQC frame and every STATUSTEXT of the FC during the handshake, the time in ms
since HQC_HELLO, the lane, and the class:
    0 = GCS -> FC
    1 = FC -> GCS, first transmission
    2 = FC -> GCS, duplicated CT_CHUNK (same kind and offset already sent)

Output: three plain-text tables ready for pgfplots, and a per-lane summary to check
against the manuscript (97 CT_CHUNK, 42 unique, 42 CT_ACK, 11 PK_CHUNK, 11 PK_ACK).

Usage:
    python figura_linea_tiempo.py [capture_directory] [output_file]
"""
import os
import sys
import collections

from inventario_capturas import read_pcapng, decode
from retransmisiones_ct import frames_con_payload, chunk

FC, GCS = "192.168.42.1", "192.168.42.2"
BIDIR = "clear_fc_20251114_153259"
HELLO, HELLO_ACK, PK_CHUNK, CT_CHUNK, CT_ACK, FINISH, STATUS, PK_ACK, ABORT = range(61000, 61009)
STATUSTEXT = 253

CARRIL = {HELLO: 1, HELLO_ACK: 2, PK_CHUNK: 3, PK_ACK: 4, CT_ACK: 7, FINISH: 8, STATUS: 9, STATUSTEXT: 10}
# CT_CHUNK: carril 5 para ct_s (kind 1, estatico) y 6 para ct_e (kind 0, efimero)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")
    salida = sys.argv[2] if len(sys.argv) > 2 else "timeline.dat"
    ev = []
    for ts, lt, data in read_pcapng(os.path.join(d, BIDIR + ".pcapng")):
        dd = decode(lt, data)
        if not dd or ts is None:
            continue
        proto, src, _, dst, _, payload = dd
        if proto != "UDP" or not payload or {src, dst} != {FC, GCS}:
            continue
        for msgid, p in frames_con_payload(payload):
            if HELLO <= msgid <= ABORT or (msgid == STATUSTEXT and src == FC):
                ev.append((ts, msgid, p, src))
    ev.sort(key=lambda e: e[0])

    # la sesion completada: del primer HELLO seguido de STATUS
    t_hello = next(ts for ts, m, _, _ in ev if m == HELLO)
    t_status = next(ts for ts, m, _, _ in ev if m == STATUS and ts > t_hello)
    ventana = [e for e in ev if t_hello - 1e-3 <= e[0] <= t_status + 1e-3]

    tablas = {0: [], 1: [], 2: []}
    visto = set()
    cuenta = collections.Counter()
    for ts, m, p, src in ventana:
        t = 1000.0 * (ts - t_hello)
        if m == CT_CHUNK:
            kind, off = chunk(p)
            carril = 5 if kind == 1 else 6
            clase = 2 if (kind, off) in visto else 1
            visto.add((kind, off))
        else:
            carril = CARRIL[m]
            clase = 0 if src == GCS else 1
        tablas[clase].append((t, carril))
        cuenta[(carril, clase)] += 1

    base = salida[:-4] if salida.endswith(".dat") else salida
    for clase, nombre in [(0, "gcs"), (1, "fc"), (2, "dup")]:
        with open("%s_%s.dat" % (base, nombre), "w") as f:
            f.write("t lane\n")
            for t, carril in tablas[clase]:
                f.write("%.2f %d\n" % (t, carril))

    nombres = {1: "HELLO", 2: "HELLO_ACK", 3: "PK_CHUNK", 4: "PK_ACK", 5: "CT_CHUNK ct_s",
               6: "CT_CHUNK ct_e", 7: "CT_ACK", 8: "FINISH", 9: "STATUS", 10: "STATUSTEXT"}
    print("sesion: %.1f ms de HELLO a STATUS" % (1000.0 * (t_status - t_hello)))
    for carril in range(1, 11):
        print("  %-14s  gcs %3d  fc %3d  dup %3d" % (
            nombres[carril], cuenta[(carril, 0)], cuenta[(carril, 1)], cuenta[(carril, 2)]))
    print("escrito", salida)


if __name__ == "__main__":
    main()
