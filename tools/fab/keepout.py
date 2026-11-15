"""Keep-out clearance for rigid hardware hanging into a printed enclosure.

Used on an earlier enclosure for four connector bodies behind a wall plate
versus a strain-relief bar, screw heads, bosses and a gland pad. Numbers
only, no CAD booleans: each keep-out body is a
vertical cylinder of radius r occupying z >= z0 (it hangs down from a plate
at the top), and each piece is a footprint that rises from the floor to
z_top. A piece whose top stays below z0 is judged on Z, anything taller on
its XY gap. A rounded corner is ignored (conservative).

    pieces = [keepout.Piece("saddle_bar", "rect", (x0, x1, y0, y1), z_top),
              keepout.Piece("m3_head", "circle", (x, y, r), z_top)]
    rep = keepout.report(centers, r, z0, pieces, opening=(half_x, half_y))
    errs = keepout.violations(rep, clear=1.0)        # [] when clear

Pair it with a CAD collision test (cylinders & solids volume == 0) so the
numbers and the B-rep agree, and with a test that a deliberately bad layout
is caught (the check is live).
"""

from __future__ import annotations

import math
from typing import NamedTuple


class Piece(NamedTuple):
    name: str
    kind: str  # "rect": shape (x0, x1, y0, y1); "circle": shape (x, y, r)
    shape: tuple
    z_top: float


def rect_gap(cx: float, cy: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """Distance from a point to an axis-aligned rectangle (0 inside)."""
    return math.hypot(max(x0 - cx, 0.0, cx - x1), max(y0 - cy, 0.0, cy - y1))


def piece_gap(cx: float, cy: float, piece) -> float:
    """Distance from a point to a piece footprint (negative inside a circle)."""
    _name, kind, shape, _top = piece
    if kind == "rect":
        return rect_gap(cx, cy, *shape)
    if kind == "circle":
        return math.hypot(cx - shape[0], cy - shape[1]) - shape[2]
    raise ValueError(f"unknown piece kind {kind!r}")


def report(centers, r: float, z0: float, pieces, opening: tuple[float, float] | None = None) -> dict:
    """Clearance (mm) from the keep-out cylinders to each piece, negative = collision.

    centers: [(x, y)] cylinder axes; r: radius; z0: lowest Z the bodies reach.
    opening: optional (half_x, half_y) of a centred rectangular opening the
    cylinders must pass through (a rim lip), reported as "opening".
    """
    rep = {}
    for pc in pieces:
        name, _kind, _shape, top = pc
        if top <= z0:
            rep[name] = {"z_clear": round(z0 - top, 3)}
            continue
        rep[name] = {"xy_clear": round(min(piece_gap(cx, cy, pc) - r for cx, cy in centers), 3)}
    if opening is not None:
        ox, oy = opening
        rep["opening"] = {"xy_clear": round(min(min(ox - abs(x), oy - abs(y)) - r for x, y in centers), 3)}
    return rep


def violations(rep: dict, clear: float, what: str = "the keep-out bodies") -> list[str]:
    """Messages for every entry under `clear` (use in a part's check())."""
    out = []
    for name, v in rep.items():
        c = v.get("xy_clear", v.get("z_clear"))
        if c < clear - 1e-9:
            out.append("%s clears %s by %.2f mm (< %.1f)" % (name, what, c, clear))
    return out
