/* Does the target kernel provide the getrandom system call?
 *
 * Section VI-E offers one mechanism for F5: built against recent glibc or kernel headers,
 * the vendored PQClean random source draws only from getrandom, which the Bebop's Linux 3.4
 * kernel lacks, and on failure returns an error without writing the buffers.  The manuscript
 * records that the toolchain of the evaluated build was not archived, so that cause remains a
 * candidate.  Running this on the aircraft's own CPU decides it.
 *
 * Build (on a Linux PC with an ARM cross-compiler):
 *     arm-linux-gnueabihf-gcc -O2 -static -o probe_getrandom probe_getrandom.c
 * Run on the target:
 *     ./probe_getrandom
 *
 * It prints three lines and nothing else.  No key material is produced or printed: of the
 * bytes the random source returns it reports only whether they are all zero.
 */
#include <errno.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <unistd.h>

int main(void) {
    struct utsname u;
    unsigned char buf[16];
    size_t i;
    int all_zero;

    if (uname(&u) == 0) {
        printf("kernel      : %s %s (%s)\n", u.sysname, u.release, u.machine);
    } else {
        printf("kernel      : uname failed, errno %d (%s)\n", errno, strerror(errno));
    }

#ifdef SYS_getrandom
    memset(buf, 0, sizeof buf);
    errno = 0;
    {
        long r = syscall(SYS_getrandom, buf, sizeof buf, 0);
        if (r == (long)sizeof buf) {
            all_zero = 1;
            for (i = 0; i < sizeof buf; i++) {
                if (buf[i] != 0) {
                    all_zero = 0;
                }
            }
            printf("getrandom   : available, %ld bytes, all-zero=%s\n", r, all_zero ? "yes" : "no");
        } else {
            printf("getrandom   : UNAVAILABLE, returned %ld, errno %d (%s)\n",
                   r, errno, strerror(errno));
        }
    }
#else
    printf("getrandom   : SYS_getrandom is not defined by this toolchain\n");
#endif

    memset(buf, 0, sizeof buf);
    errno = 0;
    {
        FILE *f = fopen("/dev/urandom", "rb");
        if (f == NULL) {
            printf("/dev/urandom: NOT readable, errno %d (%s)\n", errno, strerror(errno));
        } else {
            size_t n = fread(buf, 1, sizeof buf, f);
            fclose(f);
            all_zero = 1;
            for (i = 0; i < sizeof buf; i++) {
                if (buf[i] != 0) {
                    all_zero = 0;
                }
            }
            printf("/dev/urandom: readable, %lu bytes, all-zero=%s\n",
                   (unsigned long)n, all_zero ? "yes" : "no");
        }
    }
    return 0;
}
