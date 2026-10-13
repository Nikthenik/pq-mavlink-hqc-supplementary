#!/bin/bash
# Builds the AP_KEM self-test against each HQC-128 tree, with the random source either
# working or forced to fail, and checks the verdict in each case:
#
#   reference tree, working random source          -> ACCEPT
#   fork tree before cd7be51, working source       -> ACCEPT
#   evaluated tree b402392, working source         -> REJECT  (detects F6)
#   reference tree, random source that fails       -> REJECT  (detects F5)
#
# The trees are the ones described in ../kem_selfcheck/README.md.  Nothing secret is printed:
# each case reports only ACCEPT or REJECT.
#
# Usage:  P=$(pwd) H=/path/to/hqc_equiv bash check_selftest.sh
set -u
P=${P:-$(cd "$(dirname "$0")" && pwd)}          # this directory
H=${H:-/mnt/d/Tesis/_compilar_rev/hqc_equiv}    # trees: up/, base/, vend/, common/
C=$H/common
NS=-DPQCLEAN_NAMESPACE=PQCLEAN_HQC128_CLEAN
T=$(mktemp -d)
failures=0

run_case() {        # $1 = tree, $2 = label, $3 = extra flags, $4 = expected verdict
    local tree=$1 label=$2 flags=$3 expected=$4
    local d="$T/$tree${flags:+_ff}"
    rm -rf "$d"; mkdir -p "$d/inc/vendor/pqclean/crypto_kem/hqc-128/clean"
    cp "$H/$tree"/clean/*.h "$d/inc/vendor/pqclean/crypto_kem/hqc-128/clean/"
    local INC="-I $H/$tree/clean -I $C -I $P -I $d/inc"
    local objs="" f o
    for f in "$H/$tree"/clean/*.c "$C"/aes.c "$C"/sha2.c "$C"/fips202.c \
             "$C"/nistseedexpander.c "$C"/sp800-185.c "$P"/ap_kem_rng.c "$P"/selftest_main.c; do
        o="$d/$(basename "$f" .c).o"
        if ! cc -O2 -std=gnu11 $NS $flags $INC -c "$f" -o "$o" 2>"$d/err"; then
            printf "  %-46s build failed (%s)\n" "$label" "$(basename "$f")"; sed -n 1,3p "$d/err"
            failures=$((failures + 1)); return
        fi
        objs="$objs $o"
    done
    if ! g++ -O2 -std=gnu++17 $NS $flags $INC -c "$P/ap_kem.cpp" -o "$d/ap_kem.o" 2>"$d/err"; then
        printf "  %-46s build failed (ap_kem.cpp)\n" "$label"; sed -n 1,3p "$d/err"
        failures=$((failures + 1)); return
    fi
    if ! g++ -O2 $objs "$d/ap_kem.o" -o "$d/selftest" 2>"$d/err"; then
        printf "  %-46s link failed\n" "$label"; sed -n 1,3p "$d/err"
        failures=$((failures + 1)); return
    fi
    local got
    got=$("$d/selftest")
    if [ "$got" = "$expected" ]; then
        printf "  %-46s %-6s (expected %s)  ok\n" "$label" "$got" "$expected"
    else
        printf "  %-46s %-6s (expected %s)  MISMATCH\n" "$label" "$got" "$expected"
        failures=$((failures + 1))
    fi
}

echo "AP_KEM self-test, run on the first handshake (detects F5 and F6)"
run_case up   "reference tree (upstream PQClean)"          ""                          ACCEPT
run_case base "fork tree before cd7be51"                   ""                          ACCEPT
run_case vend "evaluated tree b402392 (F6)"                ""                          REJECT
run_case up   "reference tree, random source down (F5)"    "-DAP_KEM_RNG_FORCE_FAIL"   REJECT
rm -rf "$T"
echo "cases whose verdict differs from the expected one: $failures"
[ "$failures" -eq 0 ]
