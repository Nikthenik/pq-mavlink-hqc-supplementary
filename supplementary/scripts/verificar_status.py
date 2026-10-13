#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Verifies the completion criterion: is every HQC_STATUS counted as "completed" the
activation status (HQC_KEX_OK), and not an error status? (manuscript, Section VII-B)

The firmware also emits HQC_STATUS on errors (GCS_KEMTLS.cpp: HQC_KEX_INTERNAL, BAD_SEQ,
BAD_LEN, REJECTED, IN_PROGRESS); only the call at activation sends
send_hqc_status(ch, session_id, value=0, HQC_KEX_OK, detail=0). tabla_reproducible.py
counts as completed any burst with an HQC_STATUS; this script decodes every one of them.

Payload layout (MAVLink 2 orders fields by size and trims trailing zeros):
    session_id uint64 [0:8] | value uint32 [8:12] | status uint8 [12] | detail uint8 [13]
Error calls carry detail != 0 (1-5, 10, 20-24, 31), except two not used on this path; the
activation call carries value = 0 and detail = 0. HELLO_ACK also starts with
session_id uint64 [0:8], which is compared with the one in STATUS.

Usage:
    python verificar_status.py [capture_directory]
"""
import collections
import os
import sys

from inventario_capturas import read_pcapng, decode
from extraer_sesiones import segmentar

HELLO_ACK, STATUS, ABORT = 61001, 61006, 61008
R = ["fc_20251113_180441", "fc_20251113_182734", "fc_20251113_184155",
     "fc_20251113_190020", "fc_20251113_191218"]
BIDIR = "clear_fc_20251114_153259"


def frames_con_payload(buf):
    """Genera (msgid, payload) de cada trama MAVLink 2 del buffer."""
    i, n = 0, len(buf)
    while i < n:
        if buf[i] == 0xFD and i + 12 <= n:
            plen = buf[i + 1]
            total = 12 + plen + (13 if buf[i + 2] & 0x01 else 0)
            if i + total > n:
                break
            msgid = buf[i + 7] | buf[i + 8] << 8 | buf[i + 9] << 16
            yield msgid, bytes(buf[i + 10:i + 10 + plen])
            i += total
        else:
            i += 1


def eventos(path):
    ev = []
    for ts, lt, data in read_pcapng(path):
        d = decode(lt, data)
        if not d or d[0] != "UDP" or not d[5]:
            continue
        for msgid, pay in frames_con_payload(d[5]):
            if msgid in (HELLO_ACK, STATUS, ABORT):
                ev.append((ts, msgid, len(pay), "%s->%s" % (d[1], d[3]), pay))
    ev.sort(key=lambda e: e[0])
    return ev


def campo(pay, a, b):
    """Lee pay[a:b] completando con ceros (MAVLink 2 recorta los ceros finales)."""
    x = pay[a:b]
    return x + bytes(b - a - len(x))


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")
    tot = collections.Counter()
    combos = collections.Counter()
    for nombre in R + [BIDIR]:
        for r in segmentar(eventos(os.path.join(d, nombre + ".pcapng")), 2.0):
            st = [e for e in r if e[1] == STATUS]
            ha = [e for e in r if e[1] == HELLO_ACK]
            tot["rafagas" if nombre in R else "rafagas_bidir"] += 1
            if not st:
                continue
            clave = "R" if nombre in R else "B"
            tot[clave + "_con_status"] += 1
            tot[clave + "_status_por_rafaga_%d" % len(st)] += 1
            sid_ha = campo(ha[0][4], 0, 8) if ha else None
            for k, e in enumerate(st):
                pay = e[4]
                value = int.from_bytes(campo(pay, 8, 12), "little")
                status, detail = campo(pay, 12, 14)
                combos[(status, detail, value)] += 1
                exito = value == 0 and detail == 0
                tot[clave + ("_ok" if exito else "_error")] += 1
                if k == 0 and exito:
                    tot[clave + "_primero_es_ok"] += 1
                if sid_ha is not None:
                    tot[clave + ("_sid_coincide" if campo(pay, 0, 8) == sid_ha else "_sid_distinto")] += 1
            if any(e[1] == ABORT for e in r):
                tot[clave + "_con_abort"] += 1

    print("Rafagas R1-R5:", tot["rafagas"], "| con HQC_STATUS:", tot["R_con_status"])
    for k in sorted(tot):
        if k.startswith("R_status_por_rafaga"):
            print("  %s: %d" % (k, tot[k]))
    print("HQC_STATUS de exito (value=0, detail=0):", tot["R_ok"], "| de error:", tot["R_error"])
    print("Primer HQC_STATUS de la rafaga es el de exito:", tot["R_primero_es_ok"])
    print("session_id igual al de HELLO_ACK:", tot["R_sid_coincide"], "| distinto:", tot["R_sid_distinto"])
    print("Rafagas con HQC_ABORT:", tot["R_con_abort"])
    print("Traza bidireccional: con STATUS", tot["B_con_status"], "| exito", tot["B_ok"],
          "| error", tot["B_error"], "| sid coincide", tot["B_sid_coincide"])
    print("Combinaciones (status, detail, value) observadas:")
    for (s, dt, v), n in sorted(combos.items()):
        print("  status=%d detail=%d value=%d  x%d" % (s, dt, v, n))


if __name__ == "__main__":
    main()
