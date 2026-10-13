// randombytes() for the ESP32 through esp_fill_random(), the chip's hardware random-number generator,
// for this benchmark only (randombytes_pico.c uses a software PRNG because the RP2040 has no dedicated
// TRNG). It is not the firmware's random source, whose failure the manuscript documents as finding
// F5, and does not replace it.

#include <stdint.h>
#include <stddef.h>
#include "esp_random.h"
#include "randombytes.h" // renombra a PQCLEAN_randombytes via macro, igual que llaman hqc.c/kem.c

int randombytes(uint8_t *output, size_t n) {
    esp_fill_random(output, n);
    return 0;
}
