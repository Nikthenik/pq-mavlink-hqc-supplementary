#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Reproducible version of Table VI from the raw captures.

Separates what can be stated with a large n from what has n = 1, and never mixes the two
in one row:
  - the five stress runs R1-R5 (fc_*): 105 attempts, 105 distinct bursts; they capture only
    the FC->GCS direction (HELLO_ACK, PK_ACK, CT_CHUNK, STATUS), so HELLO, PK_CHUNK, CT_ACK
    and FINISH are not visible in them;
  - clear_fc_20251114_153259: the only capture with both directions of a complete handshake
    (clear_fc_20251114_155529 contains the same handshake again, same first timestamp to
    the microsecond; clear_fc_20251113_* contain no HQC message).

The capturing host is the GCS, on the Bebop's Wi-Fi.

Usage:
    python tabla_reproducible.py [capture_directory]
"""
import collections
import os
import sys

from extraer_sesiones import eventos_hqc, segmentar, media, pct

HELLO, HELLO_ACK, PK_CHUNK, CT_CHUNK, CT_ACK, FINISH, STATUS, PK_ACK, ABORT = range(61000, 61009)
CT_FRAGS = 42                    # 2 x ceil(4433 / 220)
CT_GOODPUT_BITS = 2 * 4433 * 8   # dos ciphertexts de HQC-128
R = ["fc_20251113_180441", "fc_20251113_182734", "fc_20251113_184155",
     "fc_20251113_190020", "fc_20251113_191218"]
BIDIR = "clear_fc_20251114_153259"


def ts_de(r, msgid, cual):
    xs = [e[0] for e in r if e[1] == msgid and e[0] is not None]
    if not xs:
        return None
    return min(xs) if cual == "primero" else max(xs)


def resumen(nombre, xs, fmt="%.3f"):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "%-44s   sin datos" % nombre
    f = lambda v: fmt % v
    return "%-44s n=%-4d media %s  p50 %s  p95 %s  min %s  max %s" % (
        nombre, len(xs), f(media(xs)), f(pct(xs, .5)), f(pct(xs, .95)), f(min(xs)), f(max(xs)))


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")

    # ---------------------------------------------------------- bloque n grande
    raf = []
    for n in R:
        for r in segmentar(eventos_hqc(os.path.join(d, n + ".pcapng")), 2.0):
            raf.append(r)
    comp = [r for r in raf if any(e[1] == STATUS for e in r)]

    print("=" * 100)
    print("BLOQUE A  --  corridas de estres R1-R5, sentido FC->GCS")
    print("=" * 100)
    print("intentos (rafagas unicas)             %d" % len(raf))
    print("completados (terminan en HQC_STATUS)  %d   (%.1f %%)" % (len(comp), 100.0 * len(comp) / len(raf)))
    print("con HQC_ABORT                          %d" % sum(1 for r in raf if any(e[1] == ABORT for e in r)))
    print("intercambio de pk completo (11 PK_ACK) %d" % sum(1 for r in raf if sum(1 for e in r if e[1] == PK_ACK) == 11))
    print()
    print("Sobre los %d completados:" % len(comp))

    ct = []
    ventana_fc = []
    retx = []
    for r in comp:
        a, b = ts_de(r, CT_CHUNK, "primero"), ts_de(r, CT_CHUNK, "ultimo")
        if a is not None and b is not None and b > a:
            ct.append(b - a)
        h, s = ts_de(r, HELLO_ACK, "primero"), ts_de(r, STATUS, "primero")
        if h is not None and s is not None and s > h:
            ventana_fc.append(s - h)
        retx.append(sum(1 for e in r if e[1] == CT_CHUNK) / float(CT_FRAGS))

    print(resumen("  CT stream (s)", ct))
    print(resumen("  CT goodput (Mbps)", [CT_GOODPUT_BITS / x / 1e6 for x in ct]))
    print(resumen("  Ventana FC: HELLO_ACK -> STATUS (s)", ventana_fc))
    print(resumen("  Factor de retransmision CT (envios/42)", retx, "%.2f"))

    # ---------------------------------------------------------- bloque n = 1
    print()
    print("=" * 100)
    print("BLOQUE B  --  el UNICO handshake completo con las dos direcciones visibles (n = 1)")
    print("=" * 100)
    r = segmentar(eventos_hqc(os.path.join(d, BIDIR + ".pcapng")), 2.0)[0]
    t = [e[0] for e in r if e[0] is not None]

    def dif(a, b):
        return (b - a) if (a is not None and b is not None and b >= a) else None

    fases = [
        ("Total (primer HQC -> ultimo HQC)", max(t) - min(t)),
        ("HELLO -> HELLO_ACK", dif(ts_de(r, HELLO, "primero"), ts_de(r, HELLO_ACK, "primero"))),
        ("PK: primer PK_CHUNK -> ultimo PK_ACK", dif(ts_de(r, PK_CHUNK, "primero"), ts_de(r, PK_ACK, "ultimo"))),
        ("CT: primer CT_CHUNK -> ultimo CT_CHUNK", dif(ts_de(r, CT_CHUNK, "primero"), ts_de(r, CT_CHUNK, "ultimo"))),
        ("ultimo CT_ACK -> FINISH", dif(ts_de(r, CT_ACK, "ultimo"), ts_de(r, FINISH, "primero"))),
        ("FINISH -> STATUS", dif(ts_de(r, FINISH, "primero"), ts_de(r, STATUS, "primero"))),
    ]
    for nombre, v in fases:
        print("  %-44s %s" % (nombre, ("%.4f s" % v) if v is not None else "no medible"))
    n_ct = sum(1 for e in r if e[1] == CT_CHUNK)
    print("  %-44s %d envios / %d fragmentos = %.2fx" % ("CT_CHUNK", n_ct, CT_FRAGS, n_ct / float(CT_FRAGS)))
    print()
    print("Este bloque es una traza ilustrativa, no una estadistica: n = 1.")


if __name__ == "__main__":
    main()
