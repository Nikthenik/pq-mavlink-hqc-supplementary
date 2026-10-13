#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Timing behavior of the flight controller during the handshake, n = 100, on the real
hardware (Parrot Bebop 1, Cortex-A9); manuscript, Sections VII-B and VII-D.

The stress runs R1-R5 only see the FC->GCS direction, but that direction contains
everything the FC emits: HELLO_ACK, PK_ACK, CT_CHUNK and STATUS. All of them are generated
by the FC and travel the same path, so the constant part of the network delay cancels when
two of them are subtracted; the difference contains what the FC did between them, the wait
for its next input cycle, and the variation of the network delay (the paper reports the
medians as estimates, not bounds).

    PK_ACK -> next PK_ACK          pace at which the FC processes ephemeral-key fragments:
                                   one datagram per 10 ms cycle of the Linux HAL serial
                                   thread in the evaluated version
    last PK_ACK -> next CT_CHUNK   interval that contains the FC's encapsulation to pk_e
                                   and its transcript update
    CT_CHUNK bursts                pace at which the FC emits ciphertext

What R1-R5 cannot show: HELLO -> HELLO_ACK, because HELLO goes from the GCS to the FC. It
exists only in the single bidirectional handshake (n = 1), which this script also prints.

Usage:
    python ritmo_fc.py [capture_directory]
"""
import os
import sys

from extraer_sesiones import eventos_hqc, segmentar, media, pct

HELLO, HELLO_ACK, PK_CHUNK, CT_CHUNK, CT_ACK, FINISH, STATUS, PK_ACK = (
    61000, 61001, 61002, 61003, 61004, 61005, 61006, 61007)
R = ["fc_20251113_180441", "fc_20251113_182734", "fc_20251113_184155",
     "fc_20251113_190020", "fc_20251113_191218"]
GRUPO = 0.004   # dos CT_CHUNK a menos de 4 ms pertenecen a la misma rafaga de emision


def linea(nombre, xs, escala=1e3, unidad="ms"):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "  %-50s sin datos" % nombre
    return "  %-50s n=%-5d media %6.2f  p50 %6.2f  p95 %6.2f  min %6.2f  max %6.2f %s" % (
        nombre, len(xs), escala * media(xs), escala * pct(xs, .5), escala * pct(xs, .95),
        escala * min(xs), escala * max(xs), unidad)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")

    pk_inter, encap_pke, ct_inter, n_ok = [], [], [], 0
    for n in R:
        for r in segmentar(eventos_hqc(os.path.join(d, n + ".pcapng")), 2.0):
            if not any(e[1] == STATUS for e in r):
                continue
            n_ok += 1
            pk = sorted(e[0] for e in r if e[1] == PK_ACK and e[0] is not None)
            ct = sorted(e[0] for e in r if e[1] == CT_CHUNK and e[0] is not None)
            if len(pk) >= 2:
                pk_inter += [b - a for a, b in zip(pk, pk[1:])]
            if pk:
                despues = [t for t in ct if t > pk[-1]]
                if despues:
                    encap_pke.append(despues[0] - pk[-1])
            # inicio de cada rafaga de emision de CT, a partir del final del intercambio de pk
            if pk:
                cola = [t for t in ct if t > pk[-1]]
                inicios = [t for i, t in enumerate(cola) if i == 0 or t - cola[i - 1] > GRUPO]
                ct_inter += [b - a for a, b in zip(inicios, inicios[1:])]

    print("=" * 112)
    print("RITMO DEL FLIGHT CONTROLLER  --  R1-R5, %d handshakes completados, Parrot Bebop (Cortex-A9)" % n_ok)
    print("=" * 112)
    print(linea("Intervalo entre PK_ACK consecutivos", pk_inter))
    print(linea("Ultimo PK_ACK -> siguiente CT_CHUNK (contiene encap pk_e)", encap_pke))
    print(linea("Intervalo entre rafagas de emision de CT_CHUNK", ct_inter))
    if pk_inter:
        print("\n  Frecuencia implicita del procesado de fragmentos: %.0f Hz (1 / mediana del intervalo PK_ACK)"
              % (1.0 / pct(pk_inter, .5)))

    # ---------------------------------------------------------- el unico completo y bidireccional
    b = segmentar(eventos_hqc(os.path.join(d, "clear_fc_20251114_153259.pcapng")), 2.0)[0]

    def t(m, f):
        xs = [e[0] for e in b if e[1] == m and e[0] is not None]
        return f(xs) if xs else None

    print("\n" + "=" * 112)
    print("UNICO HANDSHAKE COMPLETO BIDIRECCIONAL (n = 1)")
    print("=" * 112)
    h, ha = t(HELLO, min), t(HELLO_ACK, min)
    c0 = t(CT_CHUNK, min)
    print("  HELLO (GCS->FC) -> HELLO_ACK (FC->GCS)              %.2f ms" % (1e3 * (ha - h)))
    print("  HELLO_ACK -> primer CT_CHUNK                        %.2f ms" % (1e3 * (c0 - ha)))
    print("  -> el FC ya tenia ct_s calculado al responder al HELLO: HELLO->HELLO_ACK")
    print("     contiene la encapsulacion a la clave estatica pk_s, no solo la red.")
    ca = t(CT_ACK, max)
    fi = t(FINISH, min)
    print("  ultimo CT_ACK (GCS) -> FINISH (GCS)                 %.2f ms   <- computo de la GCS (x86)" % (1e3 * (fi - ca)))


if __name__ == "__main__":
    main()
