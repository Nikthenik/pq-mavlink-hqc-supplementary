# HQC-128 encapsulation on two microcontrollers (Section VII-E)

Standalone benchmarks of `PQCLEAN_HQC128_CLEAN_crypto_kem_enc()` on two boards, with no
handshake and no autopilot code: the operation the flight controller performs in this design
(the ground station generates the key pairs and decapsulates). Each build links the HQC-128
`clean` tree of the firmware's vendored PQClean copy, taken at one of two commits of the fork
<https://github.com/cdcp2/ardupilot_post_quantum_kem>:

- `cd7be51~1`: the tree before the commit "optimizations for pqclean HQC-128 applied", i.e. the
  unmodified PQClean reference (it reproduces the published known-answer hash; `../kem_selfcheck/`);
- `b402392`: the evaluated firmware's tree, which carries the hand-optimized variant of the ring
  arithmetic that fails the known-answer test (finding F6, Section VI-F).

Both boards ran the same code; nothing else about the firmware is involved.

## Results

Median wall-clock time of one encapsulation to a fixed public key, 500 runs per row, measured with
each board's hardware timer (1 µs resolution). The median is the firmware's `p50`, the 251st of the
500 sorted values; the mean of the 250th and 251st differs by at most 1 µs. Both boards run at their
SDK's default clock (125 MHz on the RP2040, 160 MHz on the ESP32); neither program changes it, and the
ESP32 logs that carry a boot banner print `cpu freq: 160000000 Hz`. "Optimized" means the compiler's release level:
`-O3` on the Pico (the Pico SDK's default) and `CONFIG_COMPILER_OPTIMIZATION_PERF` (`-O2`) on the
ESP32.

| Board | Core, clock | Tree | Build | Median | p95 | Log |
|---|---|---|---|---|---|---|
| Raspberry Pi Pico (RP2040) | Arm Cortex-M0+, 125 MHz, bare metal | `cd7be51~1` (reference) | optimized | **1 109 951 µs** | 1 109 982 µs | `pico/validation/benchmark_cd7be51-1_2026-10-06.log` |
| Raspberry Pi Pico (RP2040) | Arm Cortex-M0+, 125 MHz, bare metal | `b402392` (variant, F6) | optimized | **57 291 µs** | 57 578 µs | `pico/captura_serie_2026-09-21.log` |
| ESP32 | Xtensa LX6, 160 MHz, FreeRTOS task | `cd7be51~1` (reference) | optimized | **971 551 µs** | 971 559 µs | `esp32/validation/benchmark_cd7be51-1_PERF_2026-10-06.log` |
| ESP32 | Xtensa LX6, 160 MHz, FreeRTOS task | `b402392` (variant, F6) | optimized | **46 266 µs** | 46 454 µs | `esp32/validation/benchmark_b402392_PERF_2026-10-07.log` |
| ESP32 | Xtensa LX6, 160 MHz, FreeRTOS task | `cd7be51~1` (reference) | debug (archived) | 1 228 786 µs | 1 228 792 µs | `esp32/validation/benchmark_cd7be51-1_2026-10-06.log` |
| ESP32 | Xtensa LX6, 160 MHz, FreeRTOS task | `b402392` (variant, F6) | debug (archived) | 49 285 µs | 49 407 µs | `esp32/captura_serie_2026-09-22.log` |

The manuscript quotes the two optimized reference figures, 1.11 s and 0.97 s, and the variant's
57 ms on the Pico, where both trees were built with the same flags. The two ESP32 runs marked
"debug" were built before `sdkconfig.defaults` set an optimization level, so ESP-IDF used its
default debug level (about `-Og`); they are kept as a record and are not comparable with the
optimized runs. With the variant also rebuilt under `PERF` (7 Oct 2026), the ESP32 has a
matching pair: 46.27 ms (variant) against 971.55 ms (reference), a 21.0x ratio, close to the
Pico's 19.4x (57.3 ms against 1.11 s); the two boards agree once both trees are built the same
way. The manuscript quotes the Pico pair; the ESP32 pair is reported here.

At 125 MHz the reference encapsulation costs about 139 million cycles on the Cortex-M0+, and
about 155 million at 160 MHz on the LX6; pqm4 reports about 106 million cycles for the same
PQClean reference on a Cortex-M4 (`benchmarks.md`, NUCLEO-L4R5ZI, consulted 6 Oct 2026). Key
generation, timed once outside the loop and not a figure of the paper, took 551 ms on the Pico
with the reference tree.

### Self-consistency on the boards

`main_selfcheck.c` replaces the benchmark's `main.c`: for each of 100 runs it generates a key
pair, encapsulates, decapsulates, and compares the two shared secrets. It is the test of
`../kem_selfcheck/selfcheck.c`, run on the target.

| Board | Tree | Build | Decapsulations that did not return the encapsulated secret | Log |
|---|---|---|---|---|
| Pico | `b402392` (variant) | optimized | 8 of 100 | `pico/validation/selfcheck_b402392_2026-10-06.log` |
| Pico | `cd7be51~1` (reference) | optimized | 0 of 100 | `pico/validation/selfcheck_cd7be51-1_2026-10-06.log` |
| ESP32 | `b402392` (variant) | debug | 7 of 100 | `esp32/validation/selfcheck_b402392_2026-10-06.log` |
| ESP32 | `cd7be51~1` (reference) | debug | 0 of 100 | `esp32/validation/selfcheck_cd7be51-1_2026-10-06.log` |
| ESP32 | `cd7be51~1` (reference) | optimized | 0 of 100 | `esp32/validation/selfcheck_cd7be51-1_PERF_2026-10-06.log` |
| ESP32 | `cd7be51~1` (reference) | optimized | 0 of 100 | `esp32/validation/selfcheck_cd7be51-1_PERF_completo_2026-10-07.log` |

The self-check prints the commit it was built against (`-DARBOL`), and both programs print the
board banner and `N_MUESTRAS` first. Four of the five ESP32 logs of the reference tree begin after
those lines, because the serial monitor attached late: the PERF benchmark log starts at sample 50,
the PERF self-check log of 6 October at run 10, and the debug self-check log lacks one progress
line. The fifth (`..._PERF_completo_2026-10-07.log`, monitor attached before flashing) has the full
header, including `cpu freq: 160000000 Hz` and `arbol del KEM compilado: cd7be51~1`, and repeats
the 6 October self-check line for line. In each of them the run is identified by its build, by the
500 CSV rows of a benchmark or the progress lines and result of a self-check (the self-check writes
no CSV), and by the self-check timing, which matches the benchmark of the same tree and build to
within about 10 µs. The Pico logs are complete.

A note on provenance: the first captures (21 and 22 September 2026, `captura_serie_*.log`) were
taken as a benchmark of the reference, and only the self-check on the boards showed that they
had been built against `b402392`. They are kept here as the variant's figures. The lesson is the
manuscript's own (Section VIII-B): time a KEM only after it has passed a correctness test on the
same build.

## Files

Comments in the C sources and in `sdkconfig.defaults` were rewritten in English after the runs, and
references to material outside this supplement were removed; the code and the configuration values are
the ones that ran. Serial output labels remain in Spanish.

```
pico/main.c                 benchmark: one key pair, then 500 timed encapsulations; prints a summary and a CSV
pico/main_selfcheck.c       self-check: key pair + encapsulation + decapsulation, 100 times; counts failures
pico/randombytes_pico.c     randombytes() for the RP2040 via pico_rand (benchmark only; not the firmware's source)
pico/CMakeLists.txt         build file; PQCLEAN_VENDOR must point at the vendored PQClean copy (see below)
pico/pico_sdk_import.cmake  standard Pico SDK helper
pico/captura_serie_2026-09-21.log          variant benchmark (header, summary, CSV)
pico/validation/*.log                      reference benchmark and the two self-checks

esp32/main.c, main_selfcheck.c, randombytes_esp32.c   as above (randombytes via esp_fill_random())
esp32/CMakeLists.txt        project file; esp32/main_CMakeLists.txt goes in main/ as CMakeLists.txt
esp32/sdkconfig.defaults    optimization level PERF; main-task stack 64 KiB (the self-check overflowed
                            32 KiB during decapsulation); task watchdog disabled for this single-shot binary
esp32/captura_serie_2026-09-22.log         variant benchmark, debug build
esp32/validation/*.log                     reference and variant benchmarks (debug and PERF) and the four self-checks
```

## Reproducing

```
git clone https://github.com/cdcp2/ardupilot_post_quantum_kem
git -C ardupilot_post_quantum_kem checkout cd7be51~1      # reference; use b402392 for the variant
export PQCLEAN_VENDOR=$PWD/ardupilot_post_quantum_kem/libraries/AP_KEM/vendor/pqclean
```

The build files read `PQCLEAN_VENDOR` from the environment or from the CMake cache and add
`gf2x_sparse.c` and `vector_sparse.c` only when they exist (they do not before `cd7be51`). Two
more options select the program and label the log: `-DHQC_MAIN=main_selfcheck.c` builds the
self-check instead of the benchmark, and `-DARBOL=<commit>` writes the tree's commit into the
serial output.

- Pico: Raspberry Pi Pico SDK with `arm-none-eabi-gcc`; `cmake -B build -DARBOL=cd7be51~1 && cmake
  --build build`, flash the `.uf2` in BOOTSEL mode, read the USB-CDC serial port at 115200 baud.
- ESP32: ESP-IDF v5.3; `idf.py -DARBOL=cd7be51~1 build flash monitor`, with the `sdkconfig.defaults`
  of this folder (it sets the optimization level). Start the monitor before the board prints, or the
  header is lost.

The logs in this folder were produced with the earlier form of these build files, which pinned
`PQCLEAN_VENDOR` to a local checkout; the sources compiled were the same.

Neither benchmark measures energy, and neither involves the MAVLink handshake: they time the KEM
alone.
