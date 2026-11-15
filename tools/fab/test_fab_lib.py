"""Unit tests for tools/fab (no solver, no slicer): rays, keep-out, checks and coupon.
//tools/fab:lib_test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.fab import checks, coupon, keepout, rays  # noqa: E402


@pytest.fixture(scope="module")
def tray():
    """60 x 40 x 20 open tray, 3 mm walls, 2 mm floor, a 10 mm post at the centre."""
    from build123d import Align, Box, Cylinder, Pos

    mn = (Align.CENTER, Align.CENTER, Align.MIN)
    t = Box(60, 40, 20, align=mn) - Pos(0, 0, 2) * Box(54, 34, 20, align=mn)
    return t + Pos(0, 0, 2) * Cylinder(5, 8, align=mn)


def test_rays(tray):
    assert rays.thickness(tray, (-100, 10, 10), (1, 0, 0)) == pytest.approx(3.0, abs=1e-3)
    assert rays.thickness(tray, (-100, 10, 10), (1, 0, 0), index=1) == pytest.approx(3.0, abs=1e-3)
    assert rays.gaps(tray, (-100, 10, 10), (1, 0, 0)) == [pytest.approx(54.0, abs=1e-3)]
    assert rays.first_hit_z(tray, 0, 0) == pytest.approx(10.0, abs=1e-3)
    assert rays.first_hit_z(tray, 15, 0) == pytest.approx(2.0, abs=1e-3)
    with pytest.raises(AssertionError):
        rays.thickness(tray, (-100, 100, 10), (1, 0, 0))


def test_keepout():
    pieces = [keepout.Piece("bar", "rect", (-10, 10, -2, 2), 15.0),
              keepout.Piece("head", "circle", (20, 0, 3), 12.0),
              keepout.Piece("low", "circle", (0, 0, 5), 4.0)]
    rep = keepout.report([(0, 10), (20, 10)], r=4.0, z0=8.0, pieces=pieces, opening=(30, 20))
    assert rep["bar"] == {"xy_clear": 4.0}  # (0, 10) is 8 from the bar edge
    assert rep["head"] == {"xy_clear": 3.0}  # (20, 10): 10 - 3 - 4
    assert rep["low"] == {"z_clear": 4.0}
    assert rep["opening"] == {"xy_clear": 6.0}  # 30 - 20 - 4
    assert keepout.violations(rep, 1.0) == []
    v = keepout.violations(rep, 3.5, what="the connector bodies")
    assert v == ["head clears the connector bodies by 3.00 mm (< 3.5)"]
    assert keepout.rect_gap(0, 0, -1, 1, -1, 1) == 0.0


def test_checks():
    c = checks.Checks()
    assert c.need({"a_mm": 1}, "a_mm") and c
    c.require(2 > 1, "never")
    c.require(1 > 2, "rib %.1f too thick", 3.0)
    c.need({}, "wall_mm")
    c.extend(["x"], prefix="keepout: ")
    assert not c
    with pytest.raises(ValueError, match=r"rib 3.0 too thick; params missing: \['wall_mm'\]; keepout: x"):
        c.raise_if_any()
    checks.Checks().raise_if_any()


def test_coupon_section(tray):
    sec = coupon.section(tray, lo=(10, -25, -1), hi=(35, 25, 30))
    bb = sec.bounding_box()
    assert bb.min.Z == pytest.approx(0.0, abs=1e-6) and bb.size.X == pytest.approx(20.0, abs=1e-3)
    # same wall as the part at the same point
    assert rays.thickness(sec, (100, 10, 10), (-1, 0, 0)) == rays.thickness(tray, (100, 10, 10), (-1, 0, 0))
    with pytest.raises(ValueError, match="solids"):
        coupon.section(tray, lo=(-35, -25, 3), hi=(35, 25, 30))  # two walls apart
    with pytest.raises(ValueError, match="empty"):
        coupon.section(tray, lo=(0, 0, 0), hi=(0, 1, 1))


def test_package_lists_every_module():
    doc = (ROOT / "tools" / "fab" / "__init__.py").read_text()
    mods = sorted(p.stem for p in (ROOT / "tools" / "fab").glob("*.py")
                  if not p.stem.startswith(("test_", "_")))
    for m in mods:
        assert f"  {m} " in doc, m
    json.dumps(mods)
