/*
 * Offline check of the self-test added to AP_KEM (findings F5 and F6).
 *
 * Prints one line: whether ap_kem_selftest() accepts the KEM tree it was linked against.
 * A correct tree with a working random source must be accepted; the vendored tree (whose ring
 * arithmetic is not functionally correct) and a failing random source must both be rejected.
 * Nothing secret is printed: the program reports only the verdict.
 */
#include <stdio.h>
#include <stdbool.h>

bool ap_kem_selftest(void);

int main(void) {
    printf("%s\n", ap_kem_selftest() ? "ACCEPT" : "REJECT");
    return 0;
}
