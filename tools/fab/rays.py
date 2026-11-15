"""Ray measurements through a build123d B-rep (numbers, not pictures).

Measure walls, lands, bosses and coupon bands at named points with rays and
compare with the params, so a geometry bug and a param change both show up.

    from tools.fab import rays
    assert rays.thickness(box, (0, -200, 20), (0, 1, 0)) == pytest.approx(p["wall_mm"], abs=0.02)
    assert rays.first_hit_z(box, x, y) == pytest.approx(boss_top, abs=0.02)

build123d is imported lazily so the module loads without it.
"""

from __future__ import annotations


def hits(shape, origin, direction) -> list[float]:
    """Sorted distances along the ray to every surface crossing (>= 0)."""
    from build123d import Axis, Vector

    o, d = Vector(*origin), Vector(*direction).normalized()
    ts = sorted(round((q - o).dot(d), 4) for q, _n in shape.find_intersection_points(Axis(o, d)))
    return [t for t in ts if t > -1e-6]


def thickness(shape, origin, direction, index: int = 0) -> float:
    """Material thickness at the index-th entry along the ray (first wall = 0)."""
    t = hits(shape, origin, direction)
    if len(t) < 2 * index + 2:
        raise AssertionError(f"ray from {origin} along {direction} crossed {len(t)} faces: {t}")
    return t[2 * index + 1] - t[2 * index]


def gaps(shape, origin, direction) -> list[float]:
    """Empty spans between consecutive solid entries along the ray."""
    t = hits(shape, origin, direction)
    return [t[i + 1] - t[i] for i in range(1, len(t) - 1, 2)]


def first_hit_z(shape, x: float, y: float, z_from: float = 1000.0) -> float:
    """Z of the first surface met looking down at (x, y) from z_from."""
    t = hits(shape, (x, y, z_from), (0, 0, -1))
    if not t:
        raise AssertionError(f"no surface below ({x}, {y}) from z {z_from}")
    return z_from - t[0]
