#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Random source used by the vendored KEM (see ap_kem_rng.c). */
int PQCLEAN_randombytes(uint8_t *out, size_t n);

/* Non-zero if the random source has failed since the last call; clears the flag. */
int ap_kem_rng_failed_and_clear(void);

#ifdef __cplusplus
}
#endif
