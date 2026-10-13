#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
95% confidence intervals for the main figures of Table VI, block A.

- Completion rate (100 of 105): exact Clopper-Pearson interval.
- Medians (FC window, ciphertext stream, PK_ACK -> CT_CHUNK interval): distribution-free
  interval from order statistics (the population median lies between the order statistics
  of ranks j and k with binomial probability >= 0.95).

Assumption, stated in the paper: the completed handshakes are treated as exchangeable.
They come from five runs of one bench setup on one day, so the per-run medians are also
reported (por_corrida.py). The 1000 PK_ACK intervals are clustered within 100 handshakes:
no interval is given for them.

Usage:
    python intervalos_confianza.py [capture_directory]
"""
import math
import os
import sys

from extraer_sesiones import eventos_hqc, segmentar
from tabla_reproducible import R, HELLO_ACK, STATUS, CT_CHUNK, PK_ACK, ts_de


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def clopper_pearson(x, n, alfa=0.05):
    def biseccion(f, lo, hi):
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    # inferior: P(X >= x | p) = alfa/2  <=>  1 - F(x-1; p) = alfa/2
    lo = 0.0 if x == 0 else biseccion(lambda p: 1 - binom_cdf(x - 1, n, p) >= alfa / 2, 0.0, 1.0)
    # superior: P(X <= x | p) = alfa/2
    hi = 1.0 if x == n else biseccion(lambda p: binom_cdf(x, n, p) <= alfa / 2, 0.0, 1.0)
    return lo, hi


def ic_mediana(xs, conf=0.95):
    """Intervalo por estadisticos de orden: el mas corto y centrado con cobertura >= conf."""
    s = sorted(xs)
    n = len(s)
    mejor = None
    for j in range(1, n + 1):
        k = n + 1 - j                              # simetrico: rangos j y n+1-j
        if k <= j:
            break
        # P(X_(j) <= mediana <= X_(k)) = P(j <= B <= k-1), B ~ Bin(n, 1/2)
        cob = binom_cdf(k - 1, n, 0.5) - binom_cdf(j - 1, n, 0.5)
        if cob >= conf:
            mejor = (j, k, cob)
    j, k, cob = mejor
    return s[j - 1], s[k - 1], j, k, cob


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "../../02_repo/cdcp2-ardupilot_post_quantum_kem-b402392/captures")
    raf = []
    for n in R:
        raf.extend(segmentar(eventos_hqc(os.path.join(d, n + ".pcapng")), 2.0))
    comp = [r for r in raf if any(e[1] == STATUS for e in r)]

    lo, hi = clopper_pearson(len(comp), len(raf))
    print("Finalizacion %d/%d = %.1f %%  IC95 Clopper-Pearson [%.1f %%, %.1f %%]"
          % (len(comp), len(raf), 100.0 * len(comp) / len(raf), 100 * lo, 100 * hi))

    ventana, ct, encap = [], [], []
    for r in comp:
        h, s = ts_de(r, HELLO_ACK, "primero"), ts_de(r, STATUS, "primero")
        if h is not None and s is not None:
            ventana.append(s - h)
        cts = [e[0] for e in r if e[1] == CT_CHUNK and e[0] is not None]
        if len(cts) > 1:
            ct.append(max(cts) - min(cts))
        pk_ult = ts_de(r, PK_ACK, "ultimo")
        if pk_ult is not None:
            sig = [e[0] for e in r if e[1] == CT_CHUNK and e[0] is not None and e[0] > pk_ult]
            if sig:
                encap.append((min(sig) - pk_ult) * 1000.0)

    for nombre, xs, fmt in [("Ventana FC HELLO_ACK->STATUS (s)", ventana, "%.3f"),
                            ("Flujo de ciphertext (s)", ct, "%.3f"),
                            ("Ultimo PK_ACK -> siguiente CT_CHUNK (ms)", encap, "%.2f")]:
        a, b, j, k, cob = ic_mediana(xs)
        med = sorted(xs)[len(xs) // 2 - 1:len(xs) // 2 + 1]
        print(("%-42s n=%d  mediana " + fmt + "  IC95 [" + fmt + ", " + fmt + "]  (rangos %d y %d, cobertura %.4f)")
              % (nombre, len(xs), sum(med) / len(med), a, b, j, k, cob))


if __name__ == "__main__":
    main()
