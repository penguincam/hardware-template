"""Compare a freshly built STL against the committed copy (cad_part_test).

Usage: stl_compare.py BUILT.stl COMMITTED.stl [--rel-tol 1e-3]
Checks: facet count > 0, closed-volume within rel-tol, bounding box within
0.01 mm. Byte equality is not required (OCCT tessellation may differ across
hosts); geometry drift is what fails. Stdlib only; ASCII and binary STL.
"""

import argparse
import struct
import sys


def read_stl(path):
    data = open(path, "rb").read()
    tris = []
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if 84 + 50 * n == len(data):
            for i in range(n):
                off = 84 + 50 * i + 12
                v = struct.unpack("<9f", data[off:off + 36])
                tris.append((v[0:3], v[3:6], v[6:9]))
            return tris
    verts = []
    for line in data.decode("ascii", "replace").splitlines():
        parts = line.split()
        if parts and parts[0] == "vertex":
            verts.append(tuple(float(x) for x in parts[1:4]))
    return [tuple(verts[i:i + 3]) for i in range(0, len(verts) - 2, 3)]


def stats(tris):
    vol = 0.0
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for a, b, c in tris:
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
        for p in (a, b, c):
            for k in range(3):
                lo[k] = min(lo[k], p[k])
                hi[k] = max(hi[k], p[k])
    return abs(vol), lo, hi


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("built")
    ap.add_argument("committed")
    ap.add_argument("--rel-tol", type=float, default=1e-3)
    a = ap.parse_args(argv)
    tb, tc = read_stl(a.built), read_stl(a.committed)
    if not tb or not tc:
        print(f"empty STL: built {len(tb)} facets, committed {len(tc)} facets")
        return 1
    vb, lob, hib = stats(tb)
    vc, loc, hic = stats(tc)
    fails = []
    if abs(vb - vc) > a.rel_tol * vc:
        fails.append(f"volume {vb:.3f} vs committed {vc:.3f} mm3")
    for k, ax in enumerate("xyz"):
        if abs(lob[k] - loc[k]) > 0.01 or abs(hib[k] - hic[k]) > 0.01:
            fails.append(f"bbox {ax} [{lob[k]:.3f},{hib[k]:.3f}] vs committed [{loc[k]:.3f},{hic[k]:.3f}]")
    print(f"built: {len(tb)} facets, {vb:.3f} mm3; committed: {len(tc)} facets, {vc:.3f} mm3")
    for f in fails:
        print("FAIL", f)
    if fails:
        print("geometry drifted: rebuild and commit STLs/ (bazelisk build, copy bazel-bin outputs)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
