/* Research-integrity check: a correct KEM must decapsulate its own honestly generated
 * ciphertexts with overwhelming probability (HQC-128's designed decryption-failure rate
 * is below 2^-128). This links each HQC tree against its own real entropy source
 * (PQClean common/randombytes.c -> getrandom/urandom) and counts, over N honest runs,
 * how often crypto_kem_dec fails to return the encapsulated shared secret. No keys or
 * plaintext are recovered; this only measures functional self-consistency. */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include "api.h"

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 500;
    static uint8_t pk[PQCLEAN_HQC128_CLEAN_CRYPTO_PUBLICKEYBYTES];
    static uint8_t sk[PQCLEAN_HQC128_CLEAN_CRYPTO_SECRETKEYBYTES];
    static uint8_t ct[PQCLEAN_HQC128_CLEAN_CRYPTO_CIPHERTEXTBYTES];
    uint8_t ssA[PQCLEAN_HQC128_CLEAN_CRYPTO_BYTES], ssB[PQCLEAN_HQC128_CLEAN_CRYPTO_BYTES];
    int fail = 0;
    for (int i = 0; i < n; i++) {
        PQCLEAN_HQC128_CLEAN_crypto_kem_keypair(pk, sk);
        PQCLEAN_HQC128_CLEAN_crypto_kem_enc(ct, ssA, pk);
        PQCLEAN_HQC128_CLEAN_crypto_kem_dec(ssB, ct, sk);
        if (memcmp(ssA, ssB, sizeof ssA) != 0) fail++;
    }
    printf("self-consistency: %d decapsulation failures of %d honest runs\n", fail, n);
    return 0;
}
