#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Where the CT_CHUNK retransmissions come from (manuscript, Section VII-D).

What the code says (GCS_KEMTLS.cpp):
  - pump_tx(), on every scheduler iteration: at most ONE timer-driven retransmission when
    now - t_last_tx >= 300 ms * 2^tries (capped at 4 s), with t_last_tx = now when it is
    sent; t_last_tx is per session, so two timer-driven retransmissions are at least
    300 ms apart.
  - handle_hqc_ct_ack(), on every CT_ACK: walks the fragments from index 0 and sends the
    unacknowledged ones (usually still in flight) before new ones, up to the window. It
    does not update t_last_tx.
  - kick_acks(): only after 1.5 s without traffic.

Prediction: in a transfer of about 0.53 s the timer explains at most 2 re-sends. If there
are dozens, they come from the CT_ACK handler, and in the bidirectional trace each re-send
must closely follow a CT_ACK.

HQC_CT_CHUNK layout (inferred and validated, not assumed): the dialect XML is not in the
repository. The MAVLink 2 wire order follows from the field types of the generated send
call (session_id u64, ct_kind u8, offset u32, count u16, data u8[220]):
    session_id [0:8]  offset [8:12]  count [12:14]  ct_kind [14]  data [15:]
MAVLink 2 trims trailing zeros of the payload, so it is zero-padded before reading. The
layout is accepted only if ALL offsets are multiples of 220 in [0, 4400], ct_kind is in
{0, 1}, and every completed handshake covers 21 distinct offsets per kind.

Usage:
    python retransmisiones_ct.py [capture_directory]
"""
import os
import sys

from inventario_capturas import read_pcapng, decode
from extraer_sesiones import media, pct

HELLO, HELLO_ACK, PK_CHUNK, CT_CHUNK, CT_ACK, FINISH, STATUS, PK_ACK, ABORT = range(61000, 61009)
MTU, CT_BYTES = 220, 4433
FRAGS_POR_CT = -(-CT_BYTES // MTU)            # 21
R = ["fc_20251113_180441", "fc_20251113_182734", "fc_20251113_184155",
     "fc_20251113_190020", "fc_20251113_191218"]
BIDIR = "clear_fc_20251114_153259"
RTO_BASE = 0.300
MARGEN = 0.100


def frames_con_payload(buf):
    """(msgid, payload) de cada trama MAVLink 2 del buffer."""
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
    """-> [(ts, msgid, payload)] de los mensajes HQC transportados por UDP."""
    ev = []
    for ts, lt, data in read_pcapng(path):
        d = decode(lt, data)
        if not d or ts is None:
            continue
        proto, _, _, _, _, payload = d
        if proto != "UDP" or not payload:
            continue
        for msgid, p in frames_con_payload(payload):
            if HELLO <= msgid <= ABORT:
                ev.append((ts, msgid, p))
    ev.sort(key=lambda e: e[0])
    return ev


def rafagas(ev, gap=2.0):
    out, cur, last = [], [], None
    for e in ev:
        if last is not None and e[0] - last > gap:
            out.append(cur)
            cur = []
        cur.append(e)
        last = e[0]
    if cur:
        out.append(cur)
    return out


def chunk(p):
    p = p + bytes(max(0, 15 - len(p)))       # MAVLink 2 recorta ceros finales
    return p[14], int.from_bytes(p[8:12], "little")


def analizar(r):
    """Transmisiones de CT_CHUNK de un handshake, con la validacion del formato."""
    tx = [(ts, chunk(p)) for ts, m, p in r if m == CT_CHUNK]
    for _, (kind, off) in tx:
        if kind not in (0, 1) or off % MTU or off > (FRAGS_POR_CT - 1) * MTU:
            raise SystemExit("FORMATO RECHAZADO: kind=%d offset=%d" % (kind, off))
    return tx


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")

    # ------------------------------------------------ corridas R1-R5 (FC->GCS)
    reenvios, cotas, dur = [], [], []
    for n in R:
        for r in rafagas(eventos(os.path.join(d, n + ".pcapng"))):
            if not any(m == STATUS for _, m, _ in r):
                continue
            tx = analizar(r)
            for k in (0, 1):
                if len({off for _, (kk, off) in tx if kk == k}) != FRAGS_POR_CT:
                    raise SystemExit("FORMATO RECHAZADO: un handshake completado no cubre 21 offsets")
            # on_hello_start precede a HELLO_ACK por la carga de pk_s y la encapsulacion
            # (54,7 ms en la traza bidireccional); se adelanta t0 100 ms para que la
            # cota nunca quede por debajo de la real.
            t0 = min(ts for ts, m, _ in r if m == HELLO_ACK) - MARGEN
            t1 = max(ts for ts, _ in tx)
            reenvios.append(len(tx) - 2 * FRAGS_POR_CT)
            cotas.append(int((t1 - t0) // RTO_BASE))              # reenvios posibles por temporizador
            dur.append(t1 - t0)

    print("=" * 96)
    print("R1-R5: handshakes completados, formato de CT_CHUNK validado en todos")
    print("=" * 96)
    print("handshakes                                   %d" % len(reenvios))
    print("reenvios de CT_CHUNK por handshake           min %d  p50 %.0f  max %d  (media %.1f)" % (
        min(reenvios), pct(reenvios, .5), max(reenvios), media(reenvios)))
    print("cota de reenvios por temporizador            min %d  max %d" % (min(cotas), max(cotas)))
    print("  (floor((ultimo CT_CHUNK - (HELLO_ACK - 100 ms)) / 300 ms): el temporizador")
    print("   exige 300 ms desde t_last_tx y lo reinicia al disparar)")
    exceso = [a - b for a, b in zip(reenvios, cotas)]
    print("reenvios que el temporizador NO puede explicar  min %d  max %d" % (min(exceso), max(exceso)))
    print("fraccion minima atribuible al manejador de CT_ACK  %.1f %%" % (
        100.0 * min(1 - b / a for a, b in zip(reenvios, cotas) if a)))

    # ------------------------------------------------ traza bidireccional
    print()
    print("=" * 96)
    print("Traza bidireccional (n = 1): retardo de cada reenvio respecto al CT_ACK previo")
    print("=" * 96)
    hs = [r for r in rafagas(eventos(os.path.join(d, BIDIR + ".pcapng")))
          if any(m == STATUS for _, m, _ in r)]
    if len(hs) != 1:
        raise SystemExit("se esperaba un unico handshake completado, hay %d" % len(hs))
    r = hs[0]
    visto, lag_ack, lag_mismo = {}, [], []
    ultimo_ack = None
    n_ack = 0
    for ts, m, p in r:
        if m == CT_ACK:
            ultimo_ack = ts
            n_ack += 1
        elif m == CT_CHUNK:
            key = chunk(p)
            if key in visto:
                lag_mismo.append(ts - visto[key])
                if ultimo_ack is not None:
                    lag_ack.append(ts - ultimo_ack)
            visto[key] = ts
    n_tx = sum(1 for _, m, _ in r if m == CT_CHUNK)
    ms = lambda xs, q: 1000 * pct(xs, q)
    print("CT_CHUNK enviados %d, fragmentos %d, reenvios %d, CT_ACK recibidos %d" % (
        n_tx, len(visto), len(lag_mismo), n_ack))
    print("reenvio - CT_ACK previo (ms)         p50 %.2f  p95 %.2f  max %.2f" % (
        ms(lag_ack, .5), ms(lag_ack, .95), 1000 * max(lag_ack)))
    print("reenvio - envio previo del mismo (ms) p50 %.1f  p95 %.1f  max %.1f" % (
        ms(lag_mismo, .5), ms(lag_mismo, .95), 1000 * max(lag_mismo)))
    print("reenvios a menos de 300 ms del envio previo del mismo fragmento: %d de %d" % (
        sum(1 for x in lag_mismo if x < RTO_BASE), len(lag_mismo)))


if __name__ == "__main__":
    main()
