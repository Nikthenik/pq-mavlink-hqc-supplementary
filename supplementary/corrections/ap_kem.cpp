#include "ap_kem.h"
#include "ap_kem_katvec.h"
#include "ap_kem_rng.h"

#include <stdlib.h>
#include <string.h>

/*
 * Every KEM call now reports a failure of the random source to its caller (finding F5): the
 * flag is cleared before the call and read after it, and the outputs are wiped when it is set.
 */
extern "C" bool ap_kem_keypair(uint8_t *pk, uint8_t *sk) {
    (void)ap_kem_rng_failed_and_clear();
    const bool ok = PQCLEAN_HQC128_CLEAN_crypto_kem_keypair(pk, sk) == 0;
    if (!ok || ap_kem_rng_failed_and_clear()) {
        memset(pk, 0, AP_KEM_PUBLICKEYBYTES);
        memset(sk, 0, AP_KEM_SECRETKEYBYTES);
        return false;
    }
    return true;
}

extern "C" bool ap_kem_enc(uint8_t *ct, uint8_t *ss, const uint8_t *pk) {
    (void)ap_kem_rng_failed_and_clear();
    const bool ok = PQCLEAN_HQC128_CLEAN_crypto_kem_enc(ct, ss, pk) == 0;
    if (!ok || ap_kem_rng_failed_and_clear()) {
        memset(ct, 0, AP_KEM_CIPHERTEXTBYTES);
        memset(ss, 0, AP_KEM_BYTES);
        return false;
    }
    return true;
}

extern "C" bool ap_kem_dec(uint8_t *ss, const uint8_t *ct, const uint8_t *sk) {
    /* Decapsulation draws no randomness; its result is returned unchanged. */
    return PQCLEAN_HQC128_CLEAN_crypto_kem_dec(ss, ct, sk) == 0;
}

/*
 * Self-test, run on the first handshake.  Two deterministic checks cover the defects that void key establishment:
 *
 *   F6  the KEM must reproduce a published known-answer vector.  A hand-optimized variant
 *       whose ring arithmetic does not compute HQC-128 fails this on the first vector, so one
 *       decapsulation settles it; a self-consistency round trip would not, because such a
 *       variant still agrees with itself on most draws.
 *   F5  two encapsulations to the same key must differ.  They are identical when the random
 *       source supplies nothing, which is what the evaluated firmware did in every measured
 *       handshake.
 *
 * Cost: one decapsulation, one key generation and two encapsulations, with about 11 kB
 * allocated transiently.  The handshake refuses to activate a session when it fails.
 */
extern "C" bool ap_kem_selftest(void) {
    uint8_t ss[AP_KEM_BYTES];
    if (!ap_kem_dec(ss, AP_KEM_KAT_CT, AP_KEM_KAT_SK) ||
        memcmp(ss, AP_KEM_KAT_SS, AP_KEM_BYTES) != 0) {          /* F6 */
        memset(ss, 0, sizeof(ss));
        return false;
    }
    memset(ss, 0, sizeof(ss));

    const size_t n = (size_t)AP_KEM_PUBLICKEYBYTES + AP_KEM_SECRETKEYBYTES +
                     2 * (size_t)AP_KEM_CIPHERTEXTBYTES;
    uint8_t *buf = (uint8_t *)calloc(1, n);
    if (buf == nullptr) {
        return false;
    }
    uint8_t *pk = buf;
    uint8_t *sk = pk + AP_KEM_PUBLICKEYBYTES;
    uint8_t *ct1 = sk + AP_KEM_SECRETKEYBYTES;
    uint8_t *ct2 = ct1 + AP_KEM_CIPHERTEXTBYTES;
    uint8_t ss1[AP_KEM_BYTES], ss2[AP_KEM_BYTES];

    const bool ok = ap_kem_keypair(pk, sk) &&
                    ap_kem_enc(ct1, ss1, pk) &&
                    ap_kem_enc(ct2, ss2, pk) &&
                    memcmp(ct1, ct2, AP_KEM_CIPHERTEXTBYTES) != 0;   /* F5 */

    memset(ss1, 0, sizeof(ss1));
    memset(ss2, 0, sizeof(ss2));
    memset(buf, 0, n);
    free(buf);
    return ok;
}
