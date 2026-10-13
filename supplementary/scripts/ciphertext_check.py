#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Randomness check of the FC's encapsulations (manuscript, Section VI-E, finding F5).

An HQC-128 ciphertext is u (2209 B) || v (2208 B) || salt (16 B), where the salt is drawn
by the encapsulating party from its random source; a correct encapsulation therefore
yields a different ciphertext every time, even to the same public key. This script
reassembles every complete ciphertext carried by HQC_CT_CHUNK fragments in the stress
runs R1-R5 and in the bidirectional trace, and reports, for each kind (0 = ct_e, to the
ephemeral key; 1 = ct_s, to the pre-distributed static key):
  - how many complete ciphertexts were reassembled and in how many sessions;
  - how many of them are distinct;
  - the value of the trailing 16 bytes (the salt), and in how many ciphertexts it is zero.

Expected for a working random source: as many distinct ct_s as sessions, and 16 random
salt bytes in every ciphertext.

HQC_CT_CHUNK layout (see retransmisiones_ct.py): session_id u64 | offset u32 | count u16 |
kind u8 | data u8[count].

Usage:
    python ciphertext_check.py [capture_directory]
"""
import collections
import os
import struct
import sys

from inventario_capturas import read_pcapng, decode
from tabla_reproducible import R, BIDIR

CT_CHUNK = 61003
CT_BYTES = 4433                      # HQC-128 ciphertext
SALT_BYTES = 16


def fragments(path):
    """-> [(session_id, kind, offset, data)] of every HQC_CT_CHUNK sent over UDP."""
    out = []
    for ts, lt, data in read_pcapng(path):
        d = decode(lt, data)
        if not d or d[0] != "UDP" or not d[5]:
            continue
        buf, i, n = d[5], 0, len(d[5])
        while i < n:
            if buf[i] == 0xFD and i + 12 <= n:
                plen = buf[i + 1]
                total = 12 + plen + (13 if buf[i + 2] & 0x01 else 0)
                if i + total > n:
                    break
                msgid = buf[i + 7] | buf[i + 8] << 8 | buf[i + 9] << 16
                if msgid == CT_CHUNK:
                    p = bytes(buf[i + 10:i + 10 + plen]) + bytes(240)   # MAVLink 2 trims zeros
                    sid, off, cnt, kind = struct.unpack("<QIHB", p[:15])
                    out.append((sid, kind, off, p[15:15 + cnt]))
                i += total
            else:
                i += 1
    return out


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")
    parts = collections.defaultdict(dict)          # (capture, session, kind) -> {offset: data}
    for name in R + [BIDIR]:
        for sid, kind, off, data in fragments(os.path.join(d, name + ".pcapng")):
            parts[(name, sid, kind)][off] = data
    complete = {}
    for key, frags in parts.items():
        ct = b"".join(frags[o] for o in sorted(frags))
        if len(ct) == CT_BYTES:
            complete[key] = ct
    print("Captures: %s + %s" % (", ".join(R), BIDIR))
    print("Ciphertexts reassembled: %d complete of %d started" % (len(complete), len(parts)))
    for kind, label in ((1, "ct_s (to the static key pk_s)"), (0, "ct_e (to the ephemeral key pk_e)")):
        cts = [ct for k, ct in complete.items() if k[2] == kind]
        sessions = len(set((k[0], k[1]) for k in complete if k[2] == kind))
        salts = collections.Counter(ct[-SALT_BYTES:] for ct in cts)
        zero = salts.get(bytes(SALT_BYTES), 0)
        print("\n%s" % label)
        print("  complete ciphertexts : %d, in %d sessions" % (len(cts), sessions))
        print("  distinct ciphertexts : %d" % len(set(cts)))
        print("  distinct salts       : %d; salt == 0x00*16 in %d of %d" % (len(salts), zero, len(cts)))
        for s, n in salts.most_common(3):
            print("    salt %s  x%d" % (s.hex(), n))

    # ---------------------------------------------------------------- data plane (F1)
    # After activation the FC's HEARTBEAT payload is encrypted. With a nonce that depends
    # only on the 8-bit sequence number, frames with the same sequence number and the same
    # plaintext must repeat the same ciphertext; this counts distinct (seq, ciphertext)
    # pairs without reading any key or decrypting anything.
    print("\nData-plane keystream (bidirectional trace, FC HEARTBEAT frames after activation)")
    hb, t_act = [], None
    for ts, lt, data in read_pcapng(os.path.join(d, BIDIR + ".pcapng")):
        dd = decode(lt, data)
        if not dd or dd[0] != "UDP" or not dd[5] or dd[1] != "192.168.42.1":
            continue
        buf, i, n = dd[5], 0, len(dd[5])
        while i < n:
            if buf[i] == 0xFD and i + 12 <= n:
                plen = buf[i + 1]
                total = 12 + plen + (13 if buf[i + 2] & 0x01 else 0)
                if i + total > n:
                    break
                msgid = buf[i + 7] | buf[i + 8] << 8 | buf[i + 9] << 16
                if msgid == 61006 and t_act is None:          # HQC_STATUS: activation
                    t_act = ts
                if msgid == 0 and t_act is not None and ts > t_act:
                    hb.append((buf[i + 4], bytes(buf[i + 10:i + 10 + plen])))
                i += total
            else:
                i += 1
    per_seq = collections.defaultdict(set)
    for seq, payload in hb:
        per_seq[seq].add(payload)
    print("  encrypted HEARTBEAT frames : %d" % len(hb))
    print("  distinct sequence numbers  : %d" % len(per_seq))
    print("  distinct ciphertexts       : %d" % len(set(p for _, p in hb)))
    print("  sequence numbers with more than one ciphertext: %d" % sum(1 for v in per_seq.values() if len(v) > 1))


if __name__ == "__main__":
    main()
