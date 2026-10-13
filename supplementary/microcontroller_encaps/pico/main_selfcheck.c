// Self-consistency check of the KEM on the board (RP2040): key pair + encapsulation + decapsulation,
// N times. Counts the decapsulations that do not return the encapsulated secret, and times the
// encapsulation as a by-product. A correct KEM gives 0 failures (HQC-128's decryption-failure rate is
// below 2^-128); the fork's hand-optimized variant (commit cd7be51, finding F6) fails about 7 %
// (715 of 10 000 on a PC: ../../kem_selfcheck/salida_selfcheck.txt). It is ../../kem_selfcheck/selfcheck.c
// run on the target.
//
// Build it in place of main.c (-DHQC_MAIN=main_selfcheck.c) with -DARBOL=<commit>, so that the log
// records the tree. With the reference tree each iteration takes a few seconds on the Pico; N = 100 is
// about five minutes. Serial output labels are in Spanish.

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "pico/stdlib.h"

#include "api.h"

#ifndef N_MUESTRAS
#define N_MUESTRAS 100
#endif
#ifndef ARBOL
#define ARBOL "no indicado: compilar con -DARBOL=\"\\\"<commit>\\\"\""
#endif

static uint8_t pk[PQCLEAN_HQC128_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_HQC128_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t ct[PQCLEAN_HQC128_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t ss_enc[PQCLEAN_HQC128_CLEAN_CRYPTO_BYTES];
static uint8_t ss_dec[PQCLEAN_HQC128_CLEAN_CRYPTO_BYTES];

static uint64_t enc_us[N_MUESTRAS];
static uint64_t ordenadas[N_MUESTRAS];

static int comparar_u64(const void *a, const void *b) {
    uint64_t va = *(const uint64_t *)a;
    uint64_t vb = *(const uint64_t *)b;
    if (va < vb) return -1;
    if (va > vb) return 1;
    return 0;
}

static void parar(void) { while (1) { tight_loop_contents(); } }

int main(void) {
    stdio_init_all();
    uint32_t espera_ms = 0;
    while (!stdio_usb_connected() && espera_ms < 15000) {
        sleep_ms(200);
        espera_ms += 200;
    }
    sleep_ms(500);

    printf("=== selfcheck_pico -- HQC-128 (PQClean) en RP2040 ===\n");
    printf("arbol del KEM compilado: %s\n", ARBOL);
    printf("PQCLEAN_HQC128_CLEAN_CRYPTO_PUBLICKEYBYTES = %d\n", PQCLEAN_HQC128_CLEAN_CRYPTO_PUBLICKEYBYTES);
    printf("PQCLEAN_HQC128_CLEAN_CRYPTO_CIPHERTEXTBYTES = %d\n", PQCLEAN_HQC128_CLEAN_CRYPTO_CIPHERTEXTBYTES);
    printf("N_MUESTRAS = %d\n\n", N_MUESTRAS);

    int fallos_ss = 0;   // la descapsulacion devolvio otro secreto
    int fallos_rc = 0;   // crypto_kem_dec devolvio distinto de 0
    for (int i = 0; i < N_MUESTRAS; i++) {
        int rc = PQCLEAN_HQC128_CLEAN_crypto_kem_keypair(pk, sk);
        if (rc != 0) { printf("ERROR: crypto_kem_keypair devolvio %d en la muestra %d\n", rc, i); parar(); }

        uint64_t t0 = time_us_64();
        rc = PQCLEAN_HQC128_CLEAN_crypto_kem_enc(ct, ss_enc, pk);
        uint64_t t1 = time_us_64();
        if (rc != 0) { printf("ERROR: crypto_kem_enc devolvio %d en la muestra %d\n", rc, i); parar(); }
        enc_us[i] = t1 - t0;

        rc = PQCLEAN_HQC128_CLEAN_crypto_kem_dec(ss_dec, ct, sk);
        if (rc != 0) fallos_rc++;
        if (memcmp(ss_enc, ss_dec, sizeof ss_enc) != 0) fallos_ss++;

        if ((i % 10) == 0) {
            printf("  [%d/%d] enc %llu us, fallos hasta ahora: %d\n", i, N_MUESTRAS,
                   (unsigned long long)enc_us[i], fallos_ss);
        }
    }

    memcpy(ordenadas, enc_us, sizeof(enc_us));
    qsort(ordenadas, N_MUESTRAS, sizeof(uint64_t), comparar_u64);

    printf("\n=== Resultado ===\n");
    printf("descapsulaciones que NO devolvieron el secreto encapsulado: %d de %d\n", fallos_ss, N_MUESTRAS);
    printf("crypto_kem_dec devolvio distinto de 0: %d de %d\n", fallos_rc, N_MUESTRAS);
    printf("encapsulacion: mediana %llu us, p95 %llu us, min %llu us, max %llu us\n",
           (unsigned long long)ordenadas[N_MUESTRAS / 2],
           (unsigned long long)ordenadas[(N_MUESTRAS * 95) / 100],
           (unsigned long long)ordenadas[0],
           (unsigned long long)ordenadas[N_MUESTRAS - 1]);
    printf("\n=== FIN ===\n");
    parar();
}
