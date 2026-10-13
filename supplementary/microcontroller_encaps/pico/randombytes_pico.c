// randombytes() for the RP2040 through pico_rand (official SDK), for this benchmark only. It is not
// the firmware's random source, whose failure the manuscript documents as finding F5, and does not
// replace it.
// pico_rand seeds a 128-bit software PRNG from the ring oscillator, the timer and a bus counter:
// enough for timing a benchmark, not a validated entropy source for real use.

#include <string.h>
#include "pico/rand.h"
#include "randombytes.h"

int randombytes(uint8_t *output, size_t n) {
    size_t escrito = 0;
    while (escrito < n) {
        rng_128_t r;
        get_rand_128(&r);
        size_t quedan = n - escrito;
        size_t copiar = quedan < sizeof(r.r) ? quedan : sizeof(r.r);
        memcpy(output + escrito, r.r, copiar);
        escrito += copiar;
    }
    return 0;
}
