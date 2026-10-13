# Handshake transcript and key schedule, as the evaluated flight-controller firmware computes them

Everything below is read from `libraries/GCS_MAVLink/GCS_KEMTLS.cpp` of the evaluated commit
(`cdcp2/ardupilot_post_quantum_kem` at b402392); line numbers refer to that file. It describes what the
flight controller (FC) does. The ground-station (GCS) software was not archived, so what the GCS computes
is known only from the frames it sent and from the fact that the FC accepted its `HQC_FINISH` tags: the
GCS must have derived the same transcript hash and the same finished key in the 100 completed stress
attempts and the bidirectional session.

## Transcript hash (TH)

TH is a 32-byte SHA-256 chaining value. It starts as 32 zero bytes (`HqcSession::reset()`, line 513) and
is updated as `TH <- SHA256(TH || record)` (`th_update`, line 42; a zero-length record hashes TH alone).
Every record begins with the MAVLink message identifier of the message it summarizes, as a little-endian
32-bit integer, followed by the `session_id` as a little-endian 64-bit integer. Integers wider than one
byte are little-endian throughout.

Records, in the order in which the FC absorbs them during a successful handshake:

| Order | Record | Bytes hashed (after `tag || session_id`) | Where |
|---|---|---|---|
| 1 | `HQC_HELLO` (tag 61000) | `pk_len` (u32), `version`, `suite_id`, `flags`, `aead_offer` (u8 each); then `handshake_salt` (16 B); then `rc` (32 B) | `th_add_hello`, line 82; called at line 586 |
| 2 | Static-key ciphertext summary (tag 61003) | `kind` = 1 (static), `ct_len` (u32); then `SHA256(ct_s)` (32 B) | `th_add_ct_summary`, line 142; called at line 696, right after the FC encapsulates to `pk_s` |
| 3 | `HQC_HELLO_ACK` (tag 61001) | `mtu` (u16), `window`, `required_alg`, `accept`, `status` (u8 each), `ct_e_len`, `ct_s_len` (u32 each); then `rs` (32 B) | `th_add_hello_ack`, line 111; called at line 711 |
| 4 | Ephemeral public-key summary (tag 61002) | `pk_len` (u32); then `SHA256(pk_e)` (32 B) | `th_add_pk_summary`, line 131; called at line 779, once all fragments of `pk_e` have arrived |
| 5 | Ephemeral-key ciphertext summary (tag 61003) | `kind` = 0 (ephemeral), `ct_len` (u32); then `SHA256(ct_e)` (32 B) | `th_add_ct_summary`; called at line 787 |
| 6 | `HQC_FINISH` (tag 61005) | `role`, `tag_len` (u8 each); then the 32-byte tag | `th_add_finish`, line 57; called at line 927, **after** the tag has been verified against the TH of records 1 to 5 |

Notes on what is and is not bound:

- The cipher the FC requires (`required_alg`) and the transport parameters it announces (`mtu`, `window`,
  `ct_e_len`, `ct_s_len`) are bound through record 3, so a downgrade of the negotiated cipher changes
  the transcript. The GCS's offer (`aead_offer`) is bound through record 1.
- Fragments are not hashed individually. Records 2, 4, and 5 hash the digest of each reassembled object,
  so the transcript binds the objects' content and lengths, not the order or timing of fragments.
- `rc` (32 bytes) is supplied by the GCS in `HQC_HELLO`; the FC copies it (line 576) and hashes it, and
  uses it for nothing else.
- `rs` (32 bytes) is computed by the FC as `SHA256(session_id (8 B, LE) || handshake_salt (16 B) ||
  SHA256(pk_s))` (line 690). It is a digest of values the GCS already knows, not a nonce: the FC
  contributes no randomness of its own to the transcript (manuscript, Section V-D).
- On an abort or a rejected `HQC_FINISH`, the FC absorbs an abort record (`th_add_abort`, line 94) before
  resetting the session. Its tag field is 61006, the identifier of `HQC_STATUS`, not of `HQC_ABORT`
  (61008); the record is `status`, `detail` (u8 each) and `value` (u32). This matters only for a transcript
  that ends in failure.

## Key schedule

With `ss_e` and `ss_s` the two shared secrets (64 bytes each), `salt` the 16-byte handshake salt and
`session_id` the 64-bit session identifier (`verify_finish_and_derive`, lines 295 to 350; signing key at
line 937):

```
ikm     = ss_e || ss_s                                   (128 B)
salt32  = SHA256(salt || session_id as little-endian u64)
PRK     = HKDF-Extract(salt32, ikm) = HMAC-SHA256(key = salt32, msg = ikm)
expand(label, L) = first L bytes of HMAC-SHA256(key = PRK, msg = "ardupilot-hqc-v1:" || label || 0x01)
                   (a single HKDF-Expand block; L <= 32; no context bytes are used)
finished_key = expand("finished", 32)
tag          = HMAC-SHA256(key = finished_key, msg = TH after record 5)
ms           = expand("ms", 32)
k_tx, k_rx   = expand("key:tx", 16), expand("key:rx", 16)            AES-128-CTR keys
iv_tx, iv_rx = expand("iv:tx", 12),  expand("iv:rx", 12)             per-session IVs (manuscript, F1)
k_chacha_tx, k_chacha_rx = expand("chacha:key:tx", 32), expand("chacha:key:rx", 32)
k_sign       = expand("sign", 32)                                    MAVLink 2 signing key
```

"tx" and "rx" are from the FC's point of view. The FC compares the `HQC_FINISH` tag with the expected one
in constant time (an OR over the XOR of all 32 bytes, lines 322 to 324) before deriving the traffic keys;
on a mismatch it sends `HQC_STATUS` with `HQC_KEX_REJECTED`, detail 31, and resets the session (lines 917
to 921). The expected input sizes are checked before verification: `role` must be 1 and `tag_len` 32
(lines 898 and 899), and both ciphertexts must have been fully acknowledged (line 909).

## What the captures confirm

The FC accepted the GCS's `HQC_FINISH` in every completed attempt, so the GCS computed the same TH over
records 1 to 5 and the same `finished_key`. Whether the GCS verified anything about the FC is not
observable: the handshake authenticates the GCS to the FC, not the FC to the GCS (manuscript,
Sections V-D and V-E).
