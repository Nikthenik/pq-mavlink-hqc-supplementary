#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Statistics of Table VI broken down by stress run (R1-R5).

The 100 completed handshakes come from five runs on one bench and one day, so they are not
100 independent samples. This script checks whether the aggregate distribution hides
differences between runs: if the per-run medians agree, the aggregate describes the
configuration; if not, results must be reported per run.

Same definitions as tabla_reproducible.py:
  FC window  = first HQC_HELLO_ACK -> first HQC_STATUS
  CT stream  = first CT_CHUNK -> last CT_CHUNK

Usage:
    python por_corrida.py [capture_directory]
"""
import os
import sys

from extraer_sesiones import eventos_hqc, segmentar, pct
from tabla_reproducible import R, HELLO_ACK, CT_CHUNK, STATUS, CT_FRAGS, ts_de


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")
    print("%-22s %9s %11s %11s %11s %11s" % (
        "corrida", "compl.", "ventana p50", "ventana max", "CT p50", "retx p50"))
    medianas = []
    for n in R:
        raf = segmentar(eventos_hqc(os.path.join(d, n + ".pcapng")), 2.0)
        comp = [r for r in raf if any(e[1] == STATUS for e in r)]
        ven, ct, retx = [], [], []
        for r in comp:
            h, s = ts_de(r, HELLO_ACK, "primero"), ts_de(r, STATUS, "primero")
            if h is not None and s is not None and s > h:
                ven.append(s - h)
            a, b = ts_de(r, CT_CHUNK, "primero"), ts_de(r, CT_CHUNK, "ultimo")
            if a is not None and b is not None and b > a:
                ct.append(b - a)
            retx.append(sum(1 for e in r if e[1] == CT_CHUNK) / float(CT_FRAGS))
        medianas.append(pct(ven, .5))
        print("%-22s %4d/%-4d %11.3f %11.3f %11.3f %11.2f" % (
            n, len(comp), len(raf), pct(ven, .5), max(ven), pct(ct, .5), pct(retx, .5)))
    print()
    print("rango de medianas de la ventana FC entre corridas: %.3f - %.3f s" % (
        min(medianas), max(medianas)))


if __name__ == "__main__":
    main()
