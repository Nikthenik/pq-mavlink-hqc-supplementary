# F6 — Functional correctness of the vendored KEM (Section VI-F)

Three checks of the HQC-128 tree that the evaluated firmware links (commit b402392), each
against the tree the same fork used before the commit "optimizations for pqclean HQC-128
applied" (cd7be51) and, for the first two, against upstream PQClean. None reads a key or recovers plaintext; they test whether the KEM
computes what HQC-128 specifies, and how fast.

| Check | Validated (fork tree before cd7be51) | Evaluated (b402392) | Output |
|---|---|---|---|
| PQClean known-answer test (SHA-256 of the KAT file) | `74290ad7…` = published hash | `8ad33c20…` ≠ published hash | `salida_kat.txt` |
| Self-consistency: decapsulation returns the encapsulated secret | 0 failures of 10,000 (also upstream) | 715 failures of 10,000 (~7%) | `salida_selfcheck.txt` |
| Median time on a PC (Intel Core i7-12700K) | encaps 2.7 ms | encaps 0.105 ms (~26× faster) | `salida_bench.txt` |

The evaluated tree replaces the reference polynomial product with a hand-optimized
sparse-index routine used in key generation, encapsulation, and decapsulation. It fails the
published known-answer test, fails to decapsulate about 7% of its own honestly generated
ciphertexts (HQC-128's designed failure rate is below 2^-128), and encapsulates about 26 times
faster than the validated code, which made its computation cost look negligible. The
self-consistency test draws on the system's random source, so its failure count varies from run
to run; the manuscript reports the recorded run. The fork's own tree
before that commit reproduces the published known-answer hash exactly, so rebuilding from it
is the correction.

## Reproducing

Run from this directory; the KEM sources are in the firmware's main tree, so no submodule is
needed.

```
S=$(pwd)                                  # this directory
git clone https://github.com/cdcp2/ardupilot_post_quantum_kem
cd ardupilot_post_quantum_kem
git checkout b402392                     # evaluated tree
V=libraries/AP_KEM/vendor/pqclean
H=$V/crypto_kem/hqc-128/clean
C=$V/common
CF="$C/aes.c $C/sha2.c $C/fips202.c $C/nistseedexpander.c $C/sp800-185.c"

# 1. self-consistency and timing (real random source)
cc -O2 -std=gnu11 -DPQCLEAN_NAMESPACE=PQCLEAN_HQC128_CLEAN -I $H -I $C \
   $H/*.c $C/randombytes.c $CF $S/selfcheck.c -o selfcheck && ./selfcheck 10000
cc -O2 -std=gnu11 -DPQCLEAN_NAMESPACE=PQCLEAN_HQC128_CLEAN -I $H -I $C \
   $H/*.c $C/randombytes.c $CF $S/bench.c -o bench && ./bench 300

# 2. known-answer test, with PQClean's own harness and HQC KAT generator: first download
#    test/crypto_kem/hqckat.c and test/common/hqckatrng.c from github.com/PQClean/PQClean
#    into the current directory
cc -O3 -std=c99 -DPQCLEAN_NAMESPACE=PQCLEAN_HQC128_CLEAN -I $H -I $C \
   hqckat.c hqckatrng.c $CF $H/*.c -o kat && ./kat | sha256sum
# compare with nistkat-sha256 in PQClean crypto_kem/hqc-128/META.yml
```

Repeat with `git checkout cd7be51~1` (the tree before the optimization) for the validated
figures; it prints the published hash and zero self-consistency failures.

The same self-consistency test was run on two microcontrollers (`../microcontroller_encaps/`):
0 of 100 failures with the tree before cd7be51, 7 to 8 of 100 with the tree of b402392.
