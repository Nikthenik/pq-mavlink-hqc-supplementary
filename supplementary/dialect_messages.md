# Handshake messages of the MAVLink dialect

Reference for Section IV-B of the manuscript: the nine messages of the dialect, their
identifiers, direction and fields. The dialect file is `hqc.xml` in the firmware's MAVLink
submodule (`cdcp2/mavlink_hqc`, commit 7fd3abf, `message_definitions/v1.0/hqc.xml`).

| ID | Message | Direction | Purpose and key fields |
|---|---|---|---|
| 61000 | `HQC_HELLO` | GCS to FC | Opens a session, negotiates version, suite, and cipher, and seeds the transcript. Fields: `session_id`, `pk_len`, `version`, `suite_id`, `flags`, `aead_offer`, `handshake_salt[16]`, `rc[32]`. |
| 61001 | `HQC_HELLO_ACK` | FC to GCS | Accepts or rejects the offer and announces transport parameters and ciphertext sizes. Fields: `session_id`, `mtu`, `window`, `required_alg`, `accept`, `status`, `ct_e_len`, `ct_s_len`, `rs[32]`. |
| 61002 | `HQC_PK_CHUNK` | GCS to FC | Fragment of the ephemeral public key pk_e. Fields: `session_id`, `offset`, `count`, `data[220]`. |
| 61007 | `HQC_PK_ACK` | FC to GCS | Selective acknowledgment of pk_e fragments. Fields: `session_id`, `base`, `mask`. |
| 61003 | `HQC_CT_CHUNK` | FC to GCS | Fragment of a ciphertext, tagged ephemeral or static. Fields: `session_id`, `ct_kind`, `offset`, `count`, `data[220]`. |
| 61004 | `HQC_CT_ACK` | GCS to FC | Selective acknowledgment of ciphertext fragments. Fields: `session_id`, `ct_kind`, `base`, `mask`. |
| 61005 | `HQC_FINISH` | GCS to FC | MAC over the transcript hash that confirms the keys. Fields: `session_id`, `role`, `tag_len`, `tag[32]`. |
| 61006 | `HQC_STATUS` | both | Progress and error status. Fields: `session_id`, `value`, `status`, `detail`. |
| 61008 | `HQC_ABORT` | both | Abort with reason and optional offset. Fields: `session_id`, `status`, `detail`, `value`. |
