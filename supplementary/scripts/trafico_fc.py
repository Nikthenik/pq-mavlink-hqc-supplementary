#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Composition of the traffic the FC emits in R1-R5 (manuscript, Section VII-D).

Two figures: the share of HQC messages among the frames the FC emits, and the STATUSTEXT
(msgid 253) rate inside and outside the handshakes, which the evaluated firmware raises
with a diagnostic send_text() for every HQC message it receives (GCS_Common.cpp). Uses the
SAME handshake windows and the same filter (UDP from the FC) as contencion_canal.py, so
that all rates of Section VII-D come from one definition.

Usage:
    python trafico_fc.py [capture_directory]
"""
import os
import sys

from extraer_sesiones import segmentar
from contencion_canal import tramas_fc, R, HQC_LO, HQC_HI

STATUSTEXT = 253


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")
    total = hqc = 0
    st_dentro = st_fuera = 0
    t_dentro = t_fuera = 0.0
    for n in R:
        tr = tramas_fc(os.path.join(d, n + ".pcapng"))
        if not tr:
            continue
        total += len(tr)
        hqc_ev = [(t, m, 0, "") for t, m in tr if HQC_LO <= m <= HQC_HI]
        hqc += len(hqc_ev)
        ventanas = [(min(e[0] for e in r), max(e[0] for e in r)) for r in segmentar(hqc_ev, 2.0)]

        def dentro(t):
            return any(a <= t <= b for a, b in ventanas)

        for t, m in tr:
            if m == STATUSTEXT:
                if dentro(t):
                    st_dentro += 1
                else:
                    st_fuera += 1
        dur_hs = sum(b - a for a, b in ventanas)
        t_dentro += dur_hs
        t_fuera += (tr[-1][0] - tr[0][0]) - dur_hs

    print("=" * 96)
    print("TRAFICO QUE EMITE EL FC -- R1-R5 (mismas ventanas que contencion_canal.py)")
    print("=" * 96)
    print("  Tramas del FC                  %d" % total)
    print("  de ellas, mensajes HQC         %d   (%.1f %%)" % (hqc, 100.0 * hqc / total))
    print("  STATUSTEXT fuera de handshakes %d en %.0f s   -> %.2f /s" % (st_fuera, t_fuera, st_fuera / t_fuera))
    print("  STATUSTEXT dentro de handshakes %d en %.1f s  -> %.1f /s" % (st_dentro, t_dentro, st_dentro / t_dentro))


if __name__ == "__main__":
    main()
