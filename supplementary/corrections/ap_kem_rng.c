/*
 * AP_KEM random source: fail closed.
 *
 * Finding F5 of the audit: the KEM code calls randombytes() and discards its result, so a
 * platform source that returns nothing yields a deterministic encapsulation and the handshake
 * completes without an error.  Two changes fix that here:
 *
 *   1. Fallback.  getrandom() does not exist before Linux 3.17, and the evaluation platform
 *      runs 3.4.  When it is unavailable or short, this implementation reads /dev/urandom
 *      instead of giving up.
 *   2. Fail closed.  Any failure that remains is recorded in a sticky flag.  ap_kem.cpp reads
 *      and clears that flag around every KEM call and reports failure to its caller, so the
 *      handshake can be declined instead of proceeding with predictable material.
 *
 * Defining PQCLEAN_randombytes here replaces the vendored common/randombytes.c, which the
 * build must therefore exclude (see wscript).
 */
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <unistd.h>
#if defined(__linux__)
#include <sys/syscall.h>
#endif

#include "ap_kem_rng.h"

static volatile int ap_kem_rng_error;

static int urandom_bytes(uint8_t *out, size_t n)
{
#ifdef AP_KEM_RNG_FORCE_FAIL
    (void)out;
    (void)n;
    return -1;                       /* only for the offline check in the supplementary material */
#else
    int fd;
    do {
        fd = open("/dev/urandom", O_RDONLY);
    } while (fd < 0 && errno == EINTR);
    if (fd < 0) {
        return -1;
    }
    while (n > 0) {
        const ssize_t r = read(fd, out, n);
        if (r < 0) {
            if (errno == EINTR) {
                continue;
            }
            close(fd);
            return -1;
        }
        if (r == 0) {
            close(fd);
            return -1;
        }
        out += (size_t)r;
        n -= (size_t)r;
    }
    close(fd);
    return 0;
#endif
}

int PQCLEAN_randombytes(uint8_t *out, size_t n)
{
    size_t done = 0;

#if defined(__linux__) && defined(SYS_getrandom) && !defined(AP_KEM_RNG_FORCE_FAIL)
    while (done < n) {
        const long r = syscall(SYS_getrandom, out + done, n - done, 0);
        if (r < 0) {
            if (errno == EINTR) {
                continue;
            }
            break;                   /* ENOSYS on pre-3.17 kernels: use /dev/urandom below */
        }
        done += (size_t)r;
    }
#endif

    if (done < n && urandom_bytes(out + done, n - done) != 0) {
        ap_kem_rng_error = 1;
        return -1;
    }
    return 0;
}

int ap_kem_rng_failed_and_clear(void)
{
    const int e = ap_kem_rng_error;
    ap_kem_rng_error = 0;
    return e;
}
