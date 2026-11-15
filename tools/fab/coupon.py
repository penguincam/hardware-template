"""Fit coupons cut from the real part (print a coupon before the part).

A coupon is build(params) cut down to a window, for example a rear wall with
its gland land and teardrop hole, the floor and a saddle base with its insert
bores. Because it is the same solid, the coupon can never drift from the
part: print it (on an earlier box, about 1 h and 18 g instead of 7 h and
180 g), fit the real hardware (gland, locknut, inserts, cable), record the
result in the mod's docs/, then print the part.

    from tools.fab import coupon

    def build_fit_section(params):
        return coupon.section(build(params), lo=(-20, 30, -1), hi=(20, 60, 35))

In a cad_part (tools/bazel/defs.bzl) list "//tools/fab:lib" in data; the
exporter puts the staged tools/fab on the `tools` package path, so the plain
import above works there too (no file-path loader needed).

Test it against the part with rays at the same points (tools/fab/rays.py),
for example the land thickness and the pillar heights, so a section window
that misses a feature fails.
"""

from __future__ import annotations


def section(part, lo: tuple[float, float, float], hi: tuple[float, float, float], solids: int | None = 1,
            rest_on_bed: bool = True):
    """part & the box lo..hi, checked valid; lowered to Z = 0 when rest_on_bed.

    solids: expected solid count (None: any). A window that splits the part
    into islands is usually a mistake; pass the count when it is not."""
    from build123d import Box, Part, Pos

    size = [hi[k] - lo[k] for k in range(3)]
    if min(size) <= 0:
        raise ValueError(f"empty section window {lo}..{hi}")
    window = Pos(*[(lo[k] + hi[k]) / 2 for k in range(3)]) * Box(*size)
    cut = part & window
    cut = cut if isinstance(cut, Part) else Part(cut.wrapped)
    if not cut.is_valid or not cut.solids():
        raise ValueError("section window misses the part or gives an invalid solid")
    if solids is not None and len(cut.solids()) != solids:
        raise ValueError(f"section has {len(cut.solids())} solids, expected {solids}")
    if rest_on_bed:
        cut = Pos(0, 0, -cut.bounding_box().min.Z) * cut
    return cut
