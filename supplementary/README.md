# Supplementary material — Post-Quantum Key Establishment over MAVLink: Measured Cost and Integration Pitfalls of HQC on a Small UAV

These scripts regenerate every measured figure in Sections VI and VII of the manuscript,
including Tables V and VI and Fig. 3: those from the raw packet captures, and
the F6 figures from standalone tests of the vendored KEM (`kem_selfcheck/`), and the
microcontroller encapsulation benchmarks of Section VII-E (`microcontroller_encaps/`). The
packet-capture scripts use only the Python standard library (Python 3.8 or later) and read the
`.pcapng` files directly; no Wireshark or third-party package is needed.

## Data

The firmware and the captures are public:

```
git clone https://github.com/cdcp2/ardupilot_post_quantum_kem
cd ardupilot_post_quantum_kem
git checkout b402392      # "Added data files from captures": the evaluated snapshot
git submodule update --init --recursive   # optional: the MAVLink dialect and cipher headers
```

The captures are in `captures/`; the scripts need nothing else. The MAVLink dialect
(`hqc.xml`) and the payload-cipher headers cited in Section VI live in nested submodules,
which the last command fetches at the commits b402392 records. The scripts rely on these captures
(`inventario_capturas.py`, `extraer_sesiones.py`, and `firma_por_sentido.py` scan all of them):

| Capture | Content |
|---|---|
| `fc_20251113_180441` … `fc_20251113_191218` | Stress runs R1–R5, recorded on the ground station, FC→GCS direction |
| `clear_fc_20251114_153259` | The only complete handshake captured in both directions (`clear_fc_20251114_155529` contains it again) |
| `previous_pcaps/fc_20251112_142951`, `fc_20251112_154826` | Two earlier stress runs of 12 November 2025, not used in the paper; `corridas_no_usadas.py` summarizes them with the criteria of Table VI |
| `gcs_*`, `plain_gcs_*` | Ground-station side, where the proxy has already removed the payload encryption: R1–R5 (`gcs_20251113_180441` … `gcs_20251113_191218`), the ten-minute runs of 14 November (`gcs_20251114_164939`, `gcs_20251114_171039`, `gcs_aesctr20251114_183415`, `gcs_chacha20251114_182011`), and shorter sessions; `plain_gcs_20251114_153259` and `plain_gcs_20251114_155529` repeat the FC frames of `gcs_20251114_164939`. `bateria_soc.py` reads the battery telemetry from them |
| `fc_20251114_164939`, `fc_20251114_171039` | Wi-Fi side (FC→GCS) of two of the ten-minute runs of 14 November; `bateria_soc.py` reads from them the cipher the FC selected, whether the handshake completed, and whether the FC's later heartbeats are readable in the clear |

`previous_pcaps/` also holds CSV and JSON exports that no script reads. The battery exports from
the Wi-Fi captures of 12 November (`fc_batt.csv`, `fc_142951_clean.csv`, `fc_batt.json`,
`fc_batt_142951.json`, and `fc_batt_154826.json`) decode frames of the encrypted sessions as if
they were cleartext, which gives impossible values (for example `current_battery` 1144 and
23790, `battery_remaining` -52); `fc_batt_streamed.csv` and the three `gcs_batt*.json` files are
empty.

## Running

Every script takes the capture directory as its argument (`figura_linea_tiempo.py` also
takes the path of the data file it writes), for example:

```
python tabla_reproducible.py path/to/ardupilot_post_quantum_kem/captures
```

The files in `outputs/` are the outputs we obtained. Some code comments and output labels
are in Spanish; the table below gives, for each figure in the paper, the script and the
output label that contains it.

## Where each figure comes from

| Paper | Figure | Script | Output label |
|---|---|---|---|
| Table VI, A | 100 of 105 attempts complete (95.2%), no `HQC_ABORT` | `tabla_reproducible.py` | `completados (terminan en HQC_STATUS)`, `con HQC_ABORT` |
| Table VI, A | Ciphertext stream: mean 0.528 s, p50 0.527, p95 0.539, 0.474–0.717 | `tabla_reproducible.py` | `CT stream (s)` |
| Table VI, A | Ciphertext goodput: 0.135 Mb/s | `tabla_reproducible.py` | `CT goodput (Mbps)` |
| Table VI, A | FC window `HELLO_ACK`→`STATUS`: p50 0.551 s, max 0.760 s | `tabla_reproducible.py` | `Ventana FC: HELLO_ACK -> STATUS (s)` |
| Table VI, A | Transmissions per ciphertext fragment: 2.53 | `tabla_reproducible.py` | `Factor de retransmision CT (envios/42)` |
| Table VI, A | Interval between `PK_ACK`: p50 10.00 ms (n = 1,000) | `ritmo_fc.py` | `Intervalo entre PK_ACK consecutivos` |
| Table VI, A | Last `PK_ACK`→next `CT_CHUNK` interval: p50 19.78 ms (n = 100) | `ritmo_fc.py` | `Ultimo PK_ACK -> siguiente CT_CHUNK (contiene encap pk_e)` |
| VII-B | Completion criterion: each of the 100 completed attempts contains exactly one `HQC_STATUS`, with status `HQC_KEX_OK` and the session identifier of its `HQC_HELLO_ACK`; no attempt has an error status or `HQC_ABORT` | `verificar_status.py` | all lines |
| VII-C, VII-D | 95% confidence intervals: completion rate 89.2–98.4% (Clopper–Pearson); median FC window 0.550–0.551 s, median ciphertext stream 0.523–0.529 s, median `PK_ACK`→`CT_CHUNK` interval 19.12–19.95 ms (order statistics) | `intervalos_confianza.py` | all lines |
| Table VI, B | Total 0.605 s; `HELLO`→`HELLO_ACK` 54.7 ms; public key 117.6 ms; ciphertexts 520.0 ms; last `CT_ACK`→`FINISH` 2.0 ms; `FINISH`→`STATUS` 136.7 ms | `tabla_reproducible.py` | block `BLOQUE B` |
| Table VI, note | First ciphertext fragment 0.65 ms after `HELLO_ACK` | `ritmo_fc.py` | `HELLO_ACK -> primer CT_CHUNK` |
| Fig. 3 | Timeline of the bidirectional session: 604.9 ms, 97 `CT_CHUNK` of which 55 duplicates, 42 `CT_ACK`, 11 `PK_CHUNK` and 11 `PK_ACK` | `figura_linea_tiempo.py` | per-lane counts; writes `timeline_{gcs,fc,dup}.dat` |
| VII-B | 104 of 105 attempts carry exactly 11 `PK_ACK` | `tabla_reproducible.py` | `intercambio de pk completo (11 PK_ACK)` |
| VII-B | 42 `CT_ACK` in the bidirectional session | `retransmisiones_ct.py` | `CT_ACK recibidos` |
| VII-C | Per-run medians of the FC window 0.550–0.551 s; failures per run 0, 0, 1, 1, 3 | `por_corrida.py` | table and last line |
| VII-D | 55–72 duplicate `CT_CHUNK` per handshake; at most 2 timer-driven retransmissions; all 55 duplicates within 300 ms of the previous copy | `retransmisiones_ct.py` | both blocks |
| VII-D | Heartbeat intervals during handshakes ≤ 1.11 s (max 1.103 s) | `contencion_canal.py` | `Intervalo HEARTBEAT con un handshake en medio` |
| VII-D | 2.29 non-handshake frames/s outside handshakes (4,069 in 1,776 s, restarts included) | `contencion_canal.py` | `Tasa de tramas no-HQC del FC fuera de handshakes` |
| VII-D | `STATUSTEXT` 24.4/s inside handshakes (the rate outside them mixes start-up messages and handshake diagnostics, so it is no baseline) | `trafico_fc.py` | all lines |
| VI-B | All 9,239 signed frames carry link ID 0; six unsigned `COMMAND_LONG` after activation (requests for `BATTERY_STATUS` or `SYS_STATUS`), each answered in order 16–47 ms later by a `COMMAND_ACK` followed by the requested message | `firma_por_sentido.py` | sections (1) and (2) |
| VI-A | 964 encrypted `HEARTBEAT` frames after activation take 256 distinct ciphertexts, one per sequence number | `ciphertext_check.py` | block `Data-plane keystream` |
| VI-E, Table V | F5: the 16-byte salt is zero in all 211 captured ciphertexts; `ct_s` is identical in all 106 sessions; the 105 `ct_e` are distinct | `ciphertext_check.py` | blocks `ct_s` and `ct_e` |
| VII-C | The five incomplete attempts are followed by the next attempt 4.5–15.2 s later (FC timeout 20 s), so `HQC_ABORT` was never exercised | `bytes_and_retries.py` | block `Incomplete attempts` |
| VII-D | 26,490 B of handshake frames on the wire (14,124 B without duplicated fragments): 4.60 s / 2.45 s at 57,600 baud; objects alone 1.93 s (HQC-128) / 0.41 s (ML-KEM-512) | `bytes_and_retries.py` | first block |
| VII-D, Table VI note | 54 GCS datagrams after `HQC_HELLO_ACK` (11 `PK_CHUNK`, 42 `CT_ACK`, `HQC_FINISH`); 22 `CT_CHUNK` after `HQC_FINISH` | `figura_linea_tiempo.py` | per-lane counts |
| VII-B | The autopilot restarted before each attempt: 101 FC source ports for 105 attempts, each starting at sequence 0 or 1; the four retries that followed a failure reuse the port; at least seven completed handshakes begin before "ArduPilot Ready" (readable only before activation) | `reinicios_y_fallos.py` | blocks `Restarts` and `Start-up` |
| VII-C, VII-E | The maxima 0.760 s, 0.717 s, and 35.25 ms come from one attempt that began during start-up; without it, or without all seven listed, 0.619 s, 0.589 s, and 30.99 ms | `reinicios_y_fallos.py` | block `Maxima` |
| VII-C | In the five incomplete attempts the FC emits no `HQC_STATUS` and signs no frame before the next attempt (it signs after every completed one); four stop after the full ciphertext transfer (11 `PK_ACK`, 97 `CT_CHUNK`), one during the public-key transfer (9 `PK_ACK`) | `reinicios_y_fallos.py` | blocks `Completed attempts…` and `Incomplete attempts` |
| VI-F, Table V | F6: the vendored KEM fails PQClean's HQC-128 known-answer test (the pre-optimization tree reproduces the published hash) | `kem_selfcheck/README.md` (PQClean `hqckat.c`) | `kem_selfcheck/salida_kat.txt` |
| VI-F, Table V | F6: the vendored KEM fails to decapsulate ~7% of its own ciphertexts (715 of 10,000), against 0 for the validated trees | `kem_selfcheck/selfcheck.c` | `kem_selfcheck/salida_selfcheck.txt` |
| VI-F, VII-D, VII-E | F6: the vendored KEM encapsulates ~26 times faster than validated code on a PC (0.105 vs 2.7 ms) | `kem_selfcheck/bench.c` | `kem_selfcheck/salida_bench.txt` |
| VI-G | The corrections for F2–F6, as a patch against commit b402392, and the self-test run on the first handshake: it accepts the reference tree and the fork's tree before cd7be51, and rejects the vendored tree (F6) and a random source that fails (F5) | `corrections/check_selftest.sh` | `corrections/selftest_output.txt` |
| IV-B | The nine messages of the MAVLink dialect, with their identifiers, direction and fields | -- | `dialect_messages.md` |
| VII-E | PQClean HQC-128 reference encapsulation on two microcontrollers: 1.11 s median on a Raspberry Pi Pico (Cortex-M0+, 125 MHz) and 0.97 s on an ESP32 (Xtensa LX6, 160 MHz), 500 runs each; the vendored variant (F6) takes 57 ms on the Pico; on-board self-consistency, 0 of 100 failures with the reference and 7–8 of 100 with the variant | `microcontroller_encaps/{pico,esp32}/main.c`, `main_selfcheck.c` | `microcontroller_encaps/{pico,esp32}/validation/*.log`, `captura_serie_*.log` |
| VII-F; response letter | The Bebop reports no battery current (`current_battery` is 0 or -1, never above zero); its reported state of charge falls 8–10 whole points in each of the four distinct ten-minute runs (10, 8, and 9 in the three runs the withdrawn idle-battery table labeled cleartext, AES-CTR, and ChaCha20); in the run labeled cleartext the handshake completed with ChaCha20, and none of the FC's 948 later heartbeats is readable in the clear | `bateria_soc.py` | `outputs/salida_bateria.txt` |
| -- (response letter) | The two earlier stress runs of 12 November, not used in the paper: 62 completed in 64 attempts (an `HQC_STATUS` of `HQC_KEX_OK` with the session identifier of its `HQC_HELLO_ACK`), median FC window 0.550 s (p95 0.570 s), one window of 1.518 s | `corridas_no_usadas.py` | `outputs/salida_corridas_no_usadas.txt` |

## Handshake transcript and key schedule

`transcript_and_key_schedule.md` lists, from the FC source at b402392, the records the transcript hash
binds (in order, with their byte layouts), the HKDF labels of every derived key, and what the captures
confirm about the GCS side.

## Corrections

`corrections/` holds the patch that implements the corrections for F2–F6 (not F1, which changes the wire format; of F3 it covers the session, arming, and rate conditions; the patched firmware accepts no `HQC_HELLO` while a session is active, so rekeying needs a restart) against commit
b402392 (`corrections.patch`, applied with `git apply` in a `--recursive` clone) and the
self-test run on the first handshake that detects the two defects which void key establishment. F6 also needs
one file restored from the commit before the optimization:

```
git checkout cd7be51~1 -- libraries/AP_KEM/vendor/pqclean/crypto_kem/hqc-128/clean/hqc.c
```

`check_selftest.sh` builds the self-test against each HQC-128 tree, with the random source
working or forced to fail, and checks the verdict; `selftest_output.txt` is the run we
obtained. The patched firmware builds for the software-in-the-loop target; it was not run on
the aircraft, and no figure in the manuscript was re-measured with it.

`probe_getrandom.c` reports whether a target kernel provides the `getrandom` system call and
whether `/dev/urandom` is readable. Section VI-E gives the absence of `getrandom` on the
Bebop's Linux 3.4 as a candidate mechanism for F5 and records that the toolchain of the
evaluated build was not archived; running this on the aircraft's own CPU decides it. It
prints three lines and no key material: of the bytes the random source returns it reports
only whether they are all zero.

## Method notes

- **Handshakes** are separated by gaps of more than 2 s between HQC messages
  (`segmentar()` in `extraer_sesiones.py`). A handshake counts as complete when the FC
  emits `HQC_STATUS` with status `HQC_KEX_OK`; `verificar_status.py` (R1–R5 and the
  bidirectional session) and `corridas_no_usadas.py` (12 November) decode every `HQC_STATUS`
  and find no other status. The only other statuses in the public captures answer the rejected
  SITL attempt in `previous_pcaps/hqc_handshake_*`.
- **Parser validation.** Before extracting any timing, the scripts check a prediction made
  from the object sizes: 11 public-key fragments (2,249 B at a 220-byte MTU) and 42
  ciphertext fragments (2 × 4,433 B).
- **`HQC_CT_CHUNK` layout** (used by `retransmisiones_ct.py`): the dialect XML lives in the
  firmware's MAVLink submodule (fetched by the `git submodule` command above); the scripts avoid depending on
  a generated parser and instead infer the field layout from the generated send call,
  accepting it only if every offset is a multiple of 220 in [0, 4400], every kind is 0 or
  1, and every completed handshake covers 21 distinct offsets per ciphertext. All 100 do.
- **Timestamps** are capture timestamps on the ground-station host. An interval between two
  messages emitted by the FC needs no clock synchronization and cancels the constant part
  of the network delay, but not its variation; the paper therefore reports medians of
  these intervals as estimates of FC-side timing, not bounds on its computation.
- **Pacing.** The 10 ms step between consecutive `PK_ACK` is the period of the serial-port
  thread of ArduPilot's Linux HAL (100 Hz), whose UDP device returned one datagram per read
  in the evaluated version (ArduPilot commit 381357f, August 2026, changed this). The
  scripts do not model it; they only measure the intervals.
- **Ciphertext reassembly** (`ciphertext_check.py`) concatenates the `HQC_CT_CHUNK`
  fragments of each session by offset and checks the trailing 16 bytes (the HQC salt) and
  the number of distinct ciphertexts; it reads no key and decrypts nothing.
- **Confidence intervals** (`intervalos_confianza.py`) treat the completed handshakes as
  exchangeable. They come from five runs of one bench setup on one day; `por_corrida.py`
  gives the per-run medians that show how far that assumption holds.
