#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The two earlier stress runs in captures/previous_pcaps/ (12 November 2025), which the paper does
not use, summarized with the same criteria as Block A of Table VI (tabla_reproducible.py).

The paper's data are the five stress runs R1-R5 of 13 November 2025 and one bidirectional session
of 14 November (Section VII-B). The public snapshot b402392 also holds, in previous_pcaps/, two
runs of 12 November (fc_20251112_142951, fc_20251112_154826), captured the same way (ground station,
FC->GCS direction). The paper does not use them; the response letter summarizes them, and this
script reports them, so that the choice of data can be checked:
  - attempts: bursts of HQC messages separated by more than 2 s, as in tabla_reproducible.py;
  - completed attempts: bursts with an HQC_STATUS whose status is HQC_KEX_OK (0) and whose
    session_id is that of the burst's first HQC_HELLO_ACK, decoded from the payloads as in
    verificar_status.py (the criterion of Section VII-B); the script also counts the bursts that
    merely contain an HQC_STATUS, to show whether the two criteria differ;
  - the FC's window, first HQC_HELLO_ACK -> first HQC_STATUS, over the completed attempts.

Usage:
    python corridas_no_usadas.py [capture_directory]
"""
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
import tabla_reproducible as T                               # noqa: E402
import verificar_status as V                                 # noqa: E402

CORRIDAS = ["previous_pcaps/fc_20251112_142951", "previous_pcaps/fc_20251112_154826"]
HQC_KEX_OK = 0


def kex_ok(rafaga, con_carga):
    """True if the burst has an HQC_STATUS with status HQC_KEX_OK and the session_id of its first
    HQC_HELLO_ACK. `con_carga` holds the capture's HELLO_ACK, STATUS and ABORT frames with payload."""
    t0, t1 = rafaga[0][0], rafaga[-1][0]
    ev = [e for e in con_carga if t0 <= e[0] <= t1]
    ha = [e for e in ev if e[1] == V.HELLO_ACK]
    if not ha:
        return False
    sid = V.campo(ha[0][4], 0, 8)
    return any(e[1] == V.STATUS and V.campo(e[4], 12, 13)[0] == HQC_KEX_OK and V.campo(e[4], 0, 8) == sid
               for e in ev)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(
        _AQUI, "..", "..", "..", "02_repo", "cdcp2-ardupilot_post_quantum_kem-b402392", "captures"))
    print("Earlier stress runs not used in the paper (12 November 2025), same criteria as Table VI, Block A")
    total_raf, total_status, total_comp, todas_ventanas = 0, 0, 0, []
    for n in CORRIDAS:
        ruta = os.path.join(d, n + ".pcapng")
        raf = T.segmentar(T.eventos_hqc(ruta), 2.0)
        con_carga = V.eventos(ruta)
        con_status = [r for r in raf if any(e[1] == T.STATUS for e in r)]
        comp = [r for r in con_status if kex_ok(r, con_carga)]
        ventanas = []
        for r in comp:
            h, s = T.ts_de(r, T.HELLO_ACK, "primero"), T.ts_de(r, T.STATUS, "primero")
            if h is not None and s is not None and s > h:
                ventanas.append(s - h)
        total_raf += len(raf)
        total_status += len(con_status)
        total_comp += len(comp)
        todas_ventanas += ventanas
        print()
        print("%s: %d attempts, %d with an HQC_STATUS, %d completed (HQC_KEX_OK with the session_id of "
              "their HQC_HELLO_ACK)" % (os.path.basename(n), len(raf), len(con_status), len(comp)))
        print(T.resumen("  FC window HELLO_ACK -> STATUS (s)", ventanas))
    print()
    print("Both runs: %d attempts, %d with an HQC_STATUS, %d completed" % (total_raf, total_status, total_comp))
    print(T.resumen("  FC window HELLO_ACK -> STATUS (s)", todas_ventanas))


if __name__ == "__main__":
    main()
