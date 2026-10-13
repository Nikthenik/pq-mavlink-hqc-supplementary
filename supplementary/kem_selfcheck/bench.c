/* Relative timing of an HQC-128 tree on this PC: median wall time of keypair, encaps and
 * decaps over N runs, with the tree's real random source. Used only to compare the
 * validated tree with the evaluated variant on the same machine (x86, not the Bebop). */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "api.h"

static double now_us(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e6 + t.tv_nsec / 1e3; }
static int cmp(const void *a, const void *b) { double x = *(const double *)a, y = *(const double *)b; return (x > y) - (x < y); }

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 300;
    static uint8_t pk[PQCLEAN_HQC128_CLEAN_CRYPTO_PUBLICKEYBYTES], sk[PQCLEAN_HQC128_CLEAN_CRYPTO_SECRETKEYBYTES];
    static uint8_t ct[PQCLEAN_HQC128_CLEAN_CRYPTO_CIPHERTEXTBYTES];
    uint8_t ss[PQCLEAN_HQC128_CLEAN_CRYPTO_BYTES], ss2[PQCLEAN_HQC128_CLEAN_CRYPTO_BYTES];
    double *kg = malloc(n * sizeof(double)), *en = malloc(n * sizeof(double)), *de = malloc(n * sizeof(double));
    for (int i = 0; i < n; i++) {
        double t0 = now_us(); PQCLEAN_HQC128_CLEAN_crypto_kem_keypair(pk, sk);
        double t1 = now_us(); PQCLEAN_HQC128_CLEAN_crypto_kem_enc(ct, ss, pk);
        double t2 = now_us(); PQCLEAN_HQC128_CLEAN_crypto_kem_dec(ss2, ct, sk);
        double t3 = now_us();
        kg[i] = t1 - t0; en[i] = t2 - t1; de[i] = t3 - t2;
    }
    qsort(kg, n, sizeof(double), cmp); qsort(en, n, sizeof(double), cmp); qsort(de, n, sizeof(double), cmp);
    printf("median over %d runs (us): keypair %.1f  encaps %.1f  decaps %.1f\n", n, kg[n / 2], en[n / 2], de[n / 2]);
    return 0;
}
