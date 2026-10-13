#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Battery telemetry the FC reports over MAVLink (manuscript, Section VII-F; response letter, objection 4).

Reads SYS_STATUS (message 1) from the FC (sysid 1) in the ground-station captures, where the proxy has
already removed the payload encryption, and prints, per capture:
  - the state of charge (battery_remaining, whole percentage points) at the first and last valid
    sample (MAVLink uses -1 for "not sent");
  - the set of values of current_battery (-1 is MAVLink's "not sent by the autopilot");
  - whether the capture repeats, frame for frame, the FC frames of a capture listed before it
    (repeats are shown but counted once).
Then it prints the largest current_battery value, how many samples carry -1, and the
state-of-charge fall in each distinct ten-minute run.

Last, for each ten-minute run, it reads the capture of the Wi-Fi link with the same name (fc_*), if
there is one, and prints the cipher the FC selected in HQC_HELLO_ACK, how many of those handshakes
completed (an HQC_STATUS with status HQC_KEX_OK and the same session_id, the criterion of Section
VII-B), and how many of the FC's HEARTBEAT frames after the first HQC_HELLO_ACK are readable in the
clear. The withdrawn idle-battery table of the original submission labeled three of these runs
cleartext, AES-CTR, and ChaCha20 (WITHDRAWN_LABELS below, identified by their state of charge:
34 > 24, 69 > 61, 81 > 72).

Only gcs_*.pcapng and plain_gcs_*.pcapng in the capture directory are read for the battery (not
previous_pcaps/): in the fc_* captures the payloads of an active session are encrypted.

Usage:
    python bateria_soc.py [capture_directory]
"""
import glob
import hashlib
import os
import struct
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
from inventario_capturas import read_pcapng, decode          # noqa: E402

MSG_HEARTBEAT, MSG_SYS_STATUS, MSG_HQC_HELLO_ACK, MSG_HQC_STATUS = 0, 1, 61001, 61006
SYSID_FC = 1
# SYS_STATUS wire layout (MAVLink orders fields by size): three uint32, then load, voltage_battery,
# current_battery (int16, offset 16), drop_rate_comm, errors_comm, errors_count1..4, and
# battery_remaining (int8, offset 30). MAVLink 2 trims trailing zero bytes, so payloads are padded.
OFF_CURRENT, OFF_REMAINING, LEN_SYS_STATUS = 16, 30, 31
# HQC_HELLO_ACK: session_id (uint64, offset 0), ct_e_len and ct_s_len (uint32), mtu (uint16), then
# window, required_alg (offset 19), accept, status and rs[32] (uint8). Cipher values as in
# select_aead() of libraries/GCS_MAVLink/GCS_KEMTLS.cpp at b402392.
OFF_REQUIRED_ALG, LEN_HELLO_ACK = 19, 54
CIPHER = {0: "none", 1: "ChaCha20", 2: "AES-CTR"}
# HQC_STATUS: session_id (uint64, offset 0), value (uint32), status (uint8, offset 12), detail (uint8).
OFF_STATUS, LEN_HQC_STATUS, HQC_KEX_OK = 12, 14, 0
# HEARTBEAT: custom_mode (uint32), then type, autopilot (offset 5), base_mode, system_status and
# mavlink_version (offset 8). In the clear, ArduPilot sends autopilot 3 and mavlink_version 3.
OFF_AUTOPILOT, OFF_VERSION, LEN_HEARTBEAT, AUTOPILOT_ARDUPILOT = 5, 8, 9, 3
WITHDRAWN_LABELS = {
    "gcs_20251114_171039.pcapng": "cleartext",
    "gcs_aesctr20251114_183415.pcapng": "AES-CTR",
    "gcs_chacha20251114_182011.pcapng": "ChaCha20",
}


def frames(buf):
    """MAVLink 1 and 2 frames in a UDP payload -> (sysid, msgid, payload)."""
    i, n = 0, len(buf)
    while i < n:
        if buf[i] == 0xFD and i + 12 <= n:
            ln = buf[i + 1]
            total = 12 + ln + (13 if buf[i + 2] & 0x01 else 0)
            if i + total > n:
                break
            yield buf[i + 5], buf[i + 7] | buf[i + 8] << 8 | buf[i + 9] << 16, bytes(buf[i + 10:i + 10 + ln])
            i += total
        elif buf[i] == 0xFE and i + 8 <= n:
            ln = buf[i + 1]
            if i + 8 + ln > n:
                break
            yield buf[i + 3], buf[i + 5], bytes(buf[i + 6:i + 6 + ln])
            i += 8 + ln
        else:
            i += 1


def fc_frames(path):
    """(time, msgid, payload) of every frame the FC (sysid 1) sends in a capture."""
    for t, lt, data in read_pcapng(path):
        d = decode(lt, data)
        if not d or d[0] != "UDP":
            continue
        for sysid, msgid, pl in frames(d[5]):
            if sysid == SYSID_FC:
                yield t, msgid, pl


def pad(pl, n):
    return pl + bytes(max(0, n - len(pl)))


def battery(path):
    """SoC samples, current_battery values, sample times, how many samples carry
    current_battery = -1, and a digest of all the FC's frames in the capture."""
    soc, cur, ts, minus_one = [], set(), [], 0
    digest = hashlib.sha256()
    for t, msgid, pl in fc_frames(path):
        digest.update(repr((round(t, 6), msgid, pl)).encode())
        if msgid != MSG_SYS_STATUS:
            continue
        pl = pad(pl, LEN_SYS_STATUS)
        c = struct.unpack_from("<h", pl, OFF_CURRENT)[0]
        cur.add(c)
        minus_one += c == -1
        soc.append(struct.unpack_from("<b", pl, OFF_REMAINING)[0])
        ts.append(t)
    return soc, cur, ts, minus_one, digest.hexdigest()


def wifi_side(path):
    """Ciphers the FC selected in HQC_HELLO_ACK; how many of those handshakes completed; and the FC's
    HEARTBEAT frames after the first HQC_HELLO_ACK: how many, and how many are readable in the clear."""
    ciphers, sessions, completed, after, clear = [], set(), set(), 0, 0
    for t, msgid, pl in fc_frames(path):
        if msgid == MSG_HQC_HELLO_ACK:
            pl = pad(pl, LEN_HELLO_ACK)
            ciphers.append(pl[OFF_REQUIRED_ALG])
            sessions.add(struct.unpack_from("<Q", pl, 0)[0])
        elif msgid == MSG_HQC_STATUS:
            pl = pad(pl, LEN_HQC_STATUS)
            sid = struct.unpack_from("<Q", pl, 0)[0]
            if pl[OFF_STATUS] == HQC_KEX_OK and sid in sessions:
                completed.add(sid)
        elif msgid == MSG_HEARTBEAT and sessions:
            pl = pad(pl, LEN_HEARTBEAT)
            after += 1
            if pl[OFF_AUTOPILOT] == AUTOPILOT_ARDUPILOT and 1 <= pl[OFF_VERSION] <= 3:
                clear += 1
    return ciphers, len(completed), after, clear


def main():
    cap = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(
        _AQUI, "..", "..", "..", "02_repo", "cdcp2-ardupilot_post_quantum_kem-b402392", "captures"))
    files = sorted(glob.glob(os.path.join(cap, "gcs_*.pcapng")) + glob.glob(os.path.join(cap, "plain_gcs_*.pcapng")))
    print("SYS_STATUS from the FC (sysid 1), ground-station captures")
    print("%-36s %6s %8s %12s %6s  %s" % ("capture", "frames", "minutes", "SoC first>last", "fall", "current_battery values"))
    first_with = {}
    values, minus_one, falls, ten_minute = set(), 0, [], []
    for path in files:
        soc, cur, ts, m1, digest = battery(path)
        if not soc:
            continue
        name = os.path.basename(path)
        repeats = first_with.get(digest)
        first_with.setdefault(digest, name)
        valid = [s for s in soc if s >= 0]
        minutes = (ts[-1] - ts[0]) / 60.0
        fall = valid[0] - valid[-1] if valid else None
        print("%-36s %6d %8.1f %8d > %-3d %6s  %s%s" % (
            name, len(soc), minutes, valid[0] if valid else -1, valid[-1] if valid else -1, fall,
            sorted(cur), "  (same FC frames as %s)" % repeats if repeats else ""))
        if repeats:
            continue
        values |= cur
        minus_one += m1
        if minutes >= 9.5 and fall is not None:
            falls.append(fall)
            ten_minute.append(name)
    print()
    print("largest current_battery value in any sample: %d" % max(values))
    print("samples with current_battery = -1 (not sent by the autopilot): %d" % minus_one)
    print("state-of-charge fall in the %d distinct ten-minute runs: %s points" % (
        len(falls), ", ".join(str(c) for c in falls)))
    print()
    print("Ten-minute runs: label in the withdrawn idle-battery table, and the capture of the Wi-Fi link")
    for name in ten_minute:
        label = WITHDRAWN_LABELS.get(name, "not in that table")
        fc = os.path.join(cap, "fc_" + name[len("gcs_"):])
        if not os.path.exists(fc):
            print("  %-34s %-18s no capture of the Wi-Fi link" % (name, label))
            continue
        ciphers, completed, after, clear = wifi_side(fc)
        print("  %-34s %-18s %s: cipher selected in HQC_HELLO_ACK %s; completed handshakes (HQC_STATUS "
              "HQC_KEX_OK, same session_id) %d; FC HEARTBEAT frames after the first HQC_HELLO_ACK %d, "
              "readable in the clear %d" % (name, label, os.path.basename(fc),
                                            ", ".join(CIPHER.get(c, str(c)) for c in ciphers) or "(none sent)",
                                            completed, after, clear))


if __name__ == "__main__":
    main()
