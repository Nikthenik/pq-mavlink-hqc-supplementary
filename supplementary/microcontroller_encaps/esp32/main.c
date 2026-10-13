// Benchmark of HQC-128 encapsulation (PQClean "clean" tree, PQCLEAN_HQC128_CLEAN_crypto_kem_enc())
// on an ESP32 (Xtensa LX6 at ESP-IDF's default 160 MHz, with cache, as a FreeRTOS task): the operation
// the flight controller performs in this design; the ground station generates the key pairs and
// decapsulates.
//
// Measures the wall-clock time of each encapsulation, in microseconds, with esp_timer_get_time()
// (hardware timer, 1 us resolution). One key pair is generated once, outside the timed loop, and
// reported for information only. Decapsulation is neither timed nor checked here: see main_selfcheck.c.
//
// Which HQC-128 tree is linked (the reference, cd7be51~1, or the hand-optimized variant of b402392,
// finding F6) is decided by PQCLEAN_VENDOR in main/CMakeLists.txt; the optimization level and the
// main-task stack come from sdkconfig.defaults. Serial output labels are in Spanish.

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"

#include "api.h"

#ifndef N_MUESTRAS
#define N_MUESTRAS 500
#endif

static uint8_t pk[PQCLEAN_HQC128_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_HQC128_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t ct[PQCLEAN_HQC128_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t ss[PQCLEAN_HQC128_CLEAN_CRYPTO_BYTES];

static int64_t muestras_us[N_MUESTRAS];

static int comparar_i64(const void *a, const void *b) {
    int64_t va = *(const int64_t *)a;
    int64_t vb = *(const int64_t *)b;
    if (va < vb) return -1;
    if (va > vb) return 1;
    return 0;
}

void app_main(void) {
    // margen para que `idf.py monitor` enganche desde el principio
    vTaskDelay(pdMS_TO_TICKS(1500));

    printf("=== hqc_encaps_esp32 -- HQC-128 (PQClean clean) en ESP32 (Xtensa LX6) ===\n");
    printf("PQCLEAN_HQC128_CLEAN_CRYPTO_PUBLICKEYBYTES = %d\n", PQCLEAN_HQC128_CLEAN_CRYPTO_PUBLICKEYBYTES);
    printf("PQCLEAN_HQC128_CLEAN_CRYPTO_CIPHERTEXTBYTES = %d\n", PQCLEAN_HQC128_CLEAN_CRYPTO_CIPHERTEXTBYTES);
    printf("N_MUESTRAS = %d\n\n", N_MUESTRAS);

    printf("Generando keypair (una sola vez, fuera del bucle de medicion)...\n");
    int64_t t0 = esp_timer_get_time();
    int rc = PQCLEAN_HQC128_CLEAN_crypto_kem_keypair(pk, sk);
    int64_t t1 = esp_timer_get_time();
    if (rc != 0) {
        printf("ERROR: crypto_kem_keypair devolvio %d\n", rc);
        while (1) { vTaskDelay(portMAX_DELAY); }
    }
    printf("keypair: %lld us (informativo, no es la metrica de interes -- el FC no genera "
           "pares efimeros en este diseno)\n\n", (long long)(t1 - t0));

    printf("Midiendo %d encapsulaciones...\n", N_MUESTRAS);
    for (int i = 0; i < N_MUESTRAS; i++) {
        int64_t inicio = esp_timer_get_time();
        rc = PQCLEAN_HQC128_CLEAN_crypto_kem_enc(ct, ss, pk);
        int64_t fin = esp_timer_get_time();
        if (rc != 0) {
            printf("ERROR: crypto_kem_enc devolvio %d en la muestra %d\n", rc, i);
            while (1) { vTaskDelay(portMAX_DELAY); }
        }
        muestras_us[i] = fin - inicio;
        if ((i % 50) == 0) {
            printf("  [%d/%d] %lld us\n", i, N_MUESTRAS, (long long)muestras_us[i]);
        }
    }

    int64_t ordenadas[N_MUESTRAS];
    memcpy(ordenadas, muestras_us, sizeof(muestras_us));
    qsort(ordenadas, N_MUESTRAS, sizeof(int64_t), comparar_i64);

    int64_t suma = 0;
    for (int i = 0; i < N_MUESTRAS; i++) suma += muestras_us[i];
    double media = (double)suma / N_MUESTRAS;
    int64_t p50 = ordenadas[N_MUESTRAS / 2];
    int64_t p95 = ordenadas[(N_MUESTRAS * 95) / 100];
    int64_t minimo = ordenadas[0];
    int64_t maximo = ordenadas[N_MUESTRAS - 1];

    printf("\n=== Resumen (microsegundos) ===\n");
    printf("media = %.1f\n", media);
    printf("p50   = %lld\n", (long long)p50);
    printf("p95   = %lld\n", (long long)p95);
    printf("min   = %lld\n", (long long)minimo);
    printf("max   = %lld\n", (long long)maximo);

    printf("\n=== Volcado CSV (todas las muestras, orden de captura) ===\n");
    printf("indice,us\n");
    for (int i = 0; i < N_MUESTRAS; i++) {
        printf("%d,%lld\n", i, (long long)muestras_us[i]);
    }

    printf("\n=== FIN ===\n");
    while (1) { vTaskDelay(portMAX_DELAY); }
}
