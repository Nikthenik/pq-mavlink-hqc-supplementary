#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAVLink 2 signing policy on the Bebop's link, per direction (manuscript, Section VI-B, F2).

The FC->GCS traffic is much larger than the GCS->FC traffic, so an unsigned direction
disappears in an aggregate signing coverage. This script separates coverage by
(IP direction, sysid) and checks whether the FC processes commands that reach it unsigned
once the session is active.

Why it matters: MAVLink 2 signing only protects if the receiver requires signatures. In
ArduPilot, GCS_Signing.cpp accepts unsigned frames on channel 0 unconditionally ("assumed
to be secure channel. This is USB on ChibiOS boards"); on the Bebop, channel 0 is the
Wi-Fi UDP link.

How a processed unsigned command is recognized: GCS_Common.cpp dispatches only frames with
MAVLINK_FRAMING_OK, so a frame that fails the signature check never reaches
packetReceived() and produces no COMMAND_ACK. Section (2) pairs the k-th COMMAND_LONG
after activation with the k-th COMMAND_ACK the FC emits after activation (1:1, in order)
and prints the message id of the frame that follows the acknowledgment: for
MAV_CMD_REQUEST_MESSAGE it is the requested message (BATTERY_STATUS or SYS_STATUS), whose
id travels in the clear in the MAVLink header even though the payload is encrypted.

Usage:
    python firma_por_sentido.py [capture_directory]
"""
import os
import sys
import glob
import struct
import collections

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_AQUI, "..", "energy_reanalysis"))

from inventario_capturas import read_pcapng, decode          # noqa: E402

HQC_LO, HQC_HI = 61000, 61008
SYSID_FC, SYSID_GCS = 1, 255
MSG_REQUEST_DATA_STREAM, MSG_COMMAND_LONG, MSG_COMMAND_ACK = 66, 76, 77


def frames(buf):
    """Tramas MAVLink 2 con payload y bloque de firma."""
    i, n = 0, len(buf)
    while i < n:
        if buf[i] != 0xFD:
            i += 1
            continue
        if i + 12 > n:
            break
        ln = buf[i + 1]
        firmada = bool(buf[i + 2] & 0x01)
        total = 12 + ln + (13 if firmada else 0)
        if i + total > n:
            break
        f = {
            "sysid": buf[i + 5],
            "msgid": buf[i + 7] | buf[i + 8] << 8 | buf[i + 9] << 16,
            "firmada": firmada,
            "pl": bytes(buf[i + 10:i + 10 + ln]),
        }
        if firmada:
            f["link_id"] = buf[i + 12 + ln]
        yield f
        i += total


def eventos(path):
    """-> lista de (ts, 'src->dst', frame) en orden de captura. Solo UDP."""
    ev = []
    for ts, lt, data in read_pcapng(path):
        d = decode(lt, data)
        if not d:
            continue
        proto, src, _sp, dst, _dp, payload = d
        if not payload or proto == "TCP":
            continue
        for fr in frames(payload):
            ev.append((ts, "%s->%s" % (src, dst), fr))
    return ev


def param1_de_command_long(pl):
    """param1 (float) of COMMAND_LONG: the requested message id in MAV_CMD_REQUEST_MESSAGE."""
    p = bytes(pl) + bytes(33)
    return struct.unpack("<f", p[0:4])[0]


def cmd_de_command_long(pl):
    # COMMAND_LONG: 7 floats (28 B), luego command uint16. MAVLink 2 trunca ceros finales.
    return struct.unpack("<H", (pl + b"\0" * 33)[28:30])[0]


def cmd_de_command_ack(pl):
    p = pl + b"\0" * 3
    return struct.unpack("<H", p[0:2])[0], p[2]


def main():
    cap = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(
        _AQUI, "..", "..", "02_repo",
        "cdcp2-ardupilot_post_quantum_kem-b402392", "captures"))
    files = sorted(glob.glob(os.path.join(cap, "*.pcapng")))
    files += sorted(glob.glob(os.path.join(cap, "previous_pcaps", "*.pcapng")))

    print("=" * 92)
    print(" Politica de firma MAVLink 2 en el enlace del Bebop, por sentido")
    print("=" * 92)

    # ------------------------------------------ (1) cobertura por sentido y sysid
    print("\n## (1) Cobertura de firma por sentido, sin dialecto HQC, desde la 1a trama firmada\n")
    tot = collections.defaultdict(lambda: [0, 0])
    links = collections.Counter()
    for f in files:
        ev = eventos(f)
        firm = [t for t, _s, fr in ev if fr["firmada"]]
        if not firm:
            continue
        t0 = min(firm)
        por = collections.defaultdict(lambda: [0, 0])
        for t, sen, fr in ev:
            if fr["firmada"]:
                links[fr["link_id"]] += 1
            if t < t0 or HQC_LO <= fr["msgid"] <= HQC_HI:
                continue
            k = (sen, fr["sysid"])
            por[k][0 if fr["firmada"] else 1] += 1
            tot[k][0 if fr["firmada"] else 1] += 1
        print("   %s" % os.path.basename(f))
        for (sen, sid), (s, u) in sorted(por.items()):
            print("      %-32s sysid %-4d firmadas %6d  sin firma %6d  %5.1f%%"
                  % (sen, sid, s, u, 100.0 * s / (s + u)))
    print("\n   TOTAL")
    for (sen, sid), (s, u) in sorted(tot.items()):
        print("      %-32s sysid %-4d firmadas %6d  sin firma %6d  %5.1f%%"
              % (sen, sid, s, u, 100.0 * s / (s + u)))
    print("\n   link_id de todas las tramas firmadas: %s" % dict(links))
    print("   (GCS_Signing.cpp asigna link_id = numero de canal: link_id 0 == canal 0)")

    # ---------------- (2) ¿procesa el FC comandos SIN firma con la sesion activa?
    print("\n## (2) Comandos del GCS sin firma y respuesta del FC (capturas bidireccionales)\n")
    for f in files:
        if not os.path.basename(f).startswith("clear_fc_"):
            continue
        ev = eventos(f)
        firm = [t for t, _s, fr in ev if fr["firmada"]]
        if not firm:
            continue
        t0 = min(firm)
        base = ev[0][0]
        print("   %s   (firma activa desde t = %.2f s)" % (os.path.basename(f), t0 - base))
        for i, (t, _sen, fr) in enumerate(ev):
            if fr["sysid"] != SYSID_GCS or fr["msgid"] not in (MSG_COMMAND_LONG,
                                                                  MSG_REQUEST_DATA_STREAM):
                continue
            fase = "SESION ACTIVA" if t >= t0 else "antes        "
            firma = "firmado  " if fr["firmada"] else "sin firma"
            if fr["msgid"] == MSG_REQUEST_DATA_STREAM:
                print("      %s t=%8.2f  %s REQUEST_DATA_STREAM" % (fase, t - base, firma))
                continue
            cmd, p1 = cmd_de_command_long(fr["pl"]), param1_de_command_long(fr["pl"])
            # 1:1 pairing in order: the k-th command after activation is answered by the
            # k-th COMMAND_ACK the FC emits after activation (ACKs are encrypted after
            # activation, so their contents are not read; the message ids are in the clear).
            ack = None
            if t >= t0:
                k = sum(1 for t3, _s3, f3 in ev[:i] if t3 >= t0 and f3["sysid"] == SYSID_GCS
                        and f3["msgid"] == MSG_COMMAND_LONG)
                acks = [(t2, f2) for t2, _s2, f2 in ev if t2 >= t0 and f2["sysid"] == SYSID_FC
                        and f2["msgid"] == MSG_COMMAND_ACK]
                ack = acks[k] if k < len(acks) else None
            else:
                for t2, _s2, f2 in ev[i + 1:]:
                    if t2 - t > 1.0:
                        break
                    if f2["sysid"] == SYSID_FC and f2["msgid"] == MSG_COMMAND_ACK:
                        ack = (t2, f2)
                        break
            if ack is None:
                resp = "no COMMAND_ACK"
            else:
                t2, f2 = ack
                nxt = [f3["msgid"] for t3, _s3, f3 in ev if f3["sysid"] == SYSID_FC and t3 > t2][:1]
                resp = "COMMAND_ACK %s +%.1f ms, followed by msgid %s" % (
                    "signed" if f2["firmada"] else "unsigned", (t2 - t) * 1000, nxt[0] if nxt else "-")
            what = " (MAV_CMD_REQUEST_MESSAGE for msgid %d)" % int(p1) if cmd == 512 else ""
            print("      %s t=%8.2f  %s COMMAND_LONG cmd=%-4d%s -> %s"
                  % (fase, t - base, firma, cmd, what, resp))

    # ------------------ (3) patron por sesion en una corrida de estres (R1)
    print("\n## (3) Corrida de estres R1: rachas firmado/sin firma FC->GCS tras activarse\n")
    f = os.path.join(cap, "fc_20251113_180441.pcapng")
    if os.path.exists(f):
        ev = [(t, fr) for t, sen, fr in eventos(f)
              if sen.endswith("->192.168.42.2") and not HQC_LO <= fr["msgid"] <= HQC_HI]
        t0 = min(t for t, fr in ev if fr["firmada"])
        ev = [(t, fr) for t, fr in ev if t >= t0]
        rachas, cur, n = [], None, 0
        for _t, fr in ev:
            if fr["firmada"] != cur:
                if cur is not None:
                    rachas.append((cur, n))
                cur, n = fr["firmada"], 0
            n += 1
        rachas.append((cur, n))
        sinf = collections.Counter(fr["msgid"] for _t, fr in ev if not fr["firmada"])
        print("      rachas: %d   primeras 12: %s" % (
            len(rachas), " ".join("%s%d" % ("F" if a else "c", b) for a, b in rachas[:12])))
        print("      sin firma, por msgid: %s" % dict(sinf.most_common(6)))
        print("      (R1 tiene 18 handshakes: una pareja de rachas por sesion)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
