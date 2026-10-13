#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Compara vector a vector los ficheros .rsp del KAT oficial de PQClean generados por cada arbol
HQC-128, y dice en cuantos de los 100 vectores publicados difiere el arbol vendido y en cuales.
Uso: python comparar_kat.py"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = r"D:\Tesis\_compilar_rev\hqc_equiv"


def leer(rsp):
    """-> [{campo: valor}] por vector."""
    txt = open(os.path.join(D, rsp), encoding="utf-8", errors="replace").read()
    out, cur = [], {}
    for lin in txt.splitlines():
        m = re.match(r"(\w+) = (.*)", lin.strip())
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if k == "count":
            if cur:
                out.append(cur)
            cur = {}
        cur[k] = v
    if cur:
        out.append(cur)
    return out


ref = leer("kat_up.rsp")
print("vectores en el KAT de referencia (PQClean original): %d" % len(ref))
for nombre, rsp in (("fork previo a cd7be51", "kat_base.rsp"), ("vendido b402392", "kat_vend.rsp")):
    otro = leer(rsp)
    if len(otro) != len(ref):
        print("%-24s %d vectores (distinto numero)" % (nombre, len(otro)))
        continue
    difs = {c: [] for c in ("pk", "sk", "ct", "ss")}
    for i, (a, b) in enumerate(zip(ref, otro)):
        for c in difs:
            if a.get(c) != b.get(c):
                difs[c].append(i)
    print("\n%s:" % nombre)
    for c in ("pk", "sk", "ct", "ss"):
        n = len(difs[c])
        print("   %-3s difiere en %3d de %d vectores%s" % (c, n, len(ref),
              ("  (primeros: %s)" % difs[c][:8]) if n else ""))
