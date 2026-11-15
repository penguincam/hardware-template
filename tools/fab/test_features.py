"""Numeric proof of tools/fab/features.py: bbox, volume against closed-form values,
ray-measured walls and openings, and no overlap between bodies that must only touch.
//tools/fab:features_test."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.fab import checks, features as F, rays  # noqa: E402

C = F.constants()
TOL = 0.02


def bbox(part):
    bb = part.bounding_box()
    return [round(v, 3) for v in (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z)]


def overlap(a, b) -> float:
    inter = a & b
    return sum(s.volume for s in inter.solids()) if inter is not None else 0.0


# ---------------------------------------------------------------- bosses

def test_pilot_boss_from_the_proven_6_32_pilot():
    pilot = F.self_tap_pilot("n6_32", C)
    assert pilot["pilot"] == 2.6 and "Coupon-proven" in pilot["source"]
    od, h, depth = 11.0, 20.0, 12.0
    f = F.pilot_boss(od, h, pilot["pilot"], depth, relief_d=7.5, relief_depth=1.0, tip_d=2.6, tip_depth=4.0)
    boss = F.apply(F.rrect_prism(30, 30, 0, -2, 0), f)  # boss on a 2 mm floor
    assert bbox(boss) == pytest.approx([-15, -15, -2, 15, 15, 20], abs=TOL)
    # bore floor: relief 1 + pilot 12 + tip 4 below the top
    assert rays.first_hit_z(boss, 0, 0, 50) == pytest.approx(20 - 1 - 12 - 4, abs=TOL)
    # pilot wall at mid-bore and relief wall at the top
    assert rays.thickness(boss, (-50, 0, 12), (1, 0, 0)) == pytest.approx((od - 2.6) / 2, abs=TOL)
    assert rays.thickness(boss, (-50, 0, 19.5), (1, 0, 0)) == pytest.approx((od - 7.5) / 2, abs=TOL)
    # volume: floor + boss annulus, closed form
    v = 30 * 30 * 2 + math.pi / 4 * (od ** 2 * h - 7.5 ** 2 * 1.0 - 2.6 ** 2 * 16.0)
    assert boss.volume == pytest.approx(v, rel=1e-4)
    assert F.pilot_boss_errors(od, h, 2.6, 12, relief_d=7.5, relief_depth=1, tip_d=2.6, tip_depth=4) == []


def test_pilot_boss_errors_catch_thin_walls_and_deep_bores():
    e = F.pilot_boss_errors(6.0, 10.0, 4.0, 9.0, relief_d=5.5, relief_depth=1.5, min_floor=1.0)
    assert any("round the 4.0 bore" in m for m in e)
    assert any("round the 5.5 relief" in m for m in e)
    assert any("past height" in m for m in e)
    c = checks.Checks()
    c.extend(e, prefix="boss: ")
    with pytest.raises(ValueError, match="boss: boss wall"):
        c.raise_if_any()


def test_insert_boss_uses_the_insert_table():
    m3 = C["inserts"]["m3"]
    f = F.insert_boss("m3", 10.0, C)
    assert bbox(f.add)[3] == pytest.approx(m3["boss_od"] / 2, abs=TOL)
    body = F.apply(F.rrect_prism(20, 20, 0, -2, 0), f)
    assert rays.first_hit_z(body, 0, 0, 50) == pytest.approx(10 - m3["depth"], abs=TOL)


# ---------------------------------------------------------------- glands and teardrops

def test_teardrop_profile_and_cap():
    r = 5.0
    assert F.teardrop_profile(r) == pytest.approx((r * math.sqrt(2), 0.0))
    top, half = F.teardrop_profile(r, cap=0.6)
    assert top == pytest.approx(5.6) and half == pytest.approx(r * math.sqrt(2) - 5.6)


@pytest.mark.parametrize("key", ["pg9", "pg11", "m20"])
def test_gland_hole_through_a_standing_wall(key):
    g = F.gland(key, C)
    wall_t, zc = 3.0, 20.0
    wall = F.rrect_prism(40, wall_t, 0, 0, 40)
    wall = F._b().Pos(0, wall_t / 2, 0) * wall  # wall occupies y in [0, wall_t]
    holed = F._part(wall - F.gland_hole(key, wall_t, cap=0.6, corner_r=0.5, z=zc, consts=C))
    # horizontal opening across the axis is the catalogue hole
    gaps = rays.gaps(holed, (-50, wall_t / 2, zc), (1, 0, 0))
    assert gaps == [pytest.approx(g["hole"], abs=TOL)]
    # the opening's top is the capped tip, r + 0.6 above the axis
    top = F.teardrop_profile(g["hole"] / 2, 0.6)[0]
    assert rays.first_hit_z(holed, 0, wall_t / 2, zc + top - 0.05) == pytest.approx(zc - g["hole"] / 2, abs=TOL)
    assert rays.thickness(holed, (0, wall_t / 2, 100), (0, 0, -1)) == pytest.approx(40 - (zc + top), abs=0.05)


def test_gland_hole_override_and_vertical():
    cut = F.gland_hole("pg9", 2.0, hole_d=16.0, horizontal=False, consts=C)
    assert bbox(cut)[3] - bbox(cut)[0] == pytest.approx(16.0, abs=TOL)


def test_gland_errors_clamp_range_and_squeeze_allowance():
    assert F.gland_errors("pg9", 6.0, consts=C) == []
    assert F.gland_errors("pg9", 8.8, consts=C)  # over clamp_max 8
    assert F.gland_errors("pg9", 8.8, squeeze_ok=1.0, consts=C) == []  # coupon-backed squeeze allowance
    assert any("will not seal" in m for m in F.gland_errors("pg11", 3.0, consts=C))
    with pytest.raises(KeyError):
        F.gland("pg99", C)


# ---------------------------------------------------------------- gaskets

def test_gasket_groove_and_bead_fit_without_overlap():
    w, d, r, rim_w, top = 100.0, 80.0, 6.0, 6.0, 30.0
    inset, gw, bw, depth, proud = 3.0, 2.0, 1.2, 1.5, 0.6
    rim = F.rrect_prism(w, d, r, 0, top) - F.rrect_prism(w - 2 * rim_w, d - 2 * rim_w, max(r - rim_w, 0.5), -1, top + 1)
    grooved = F._part(rim - F.gasket_groove(w, d, r, inset, gw, depth, top))
    bead = F.gasket_bead(w, d, r, inset, bw, depth, proud, top)
    assert overlap(grooved, bead) == pytest.approx(0.0, abs=1e-3)
    # on the straight -Y side: groove width and depth, bead width and height
    y = -d / 2 + inset
    assert rays.gaps(grooved, (-5, -d / 2 - 5, top - depth / 2), (0, 1, 0))[0] == pytest.approx(gw, abs=TOL)
    assert rays.first_hit_z(grooved, 0, y + gw / 2 - 0.05, top + 5) == pytest.approx(top - depth, abs=TOL)
    assert rays.thickness(bead, (0, -d / 2 - 5, top), (0, 1, 0)) == pytest.approx(bw, abs=TOL)
    bb = bbox(bead)
    assert bb[5] - bb[2] == pytest.approx(depth + proud, abs=TOL)
    flat = F.gasket_bead(w, d, r, inset, bw, depth, proud, top, flat=True)
    assert bbox(flat)[2] == pytest.approx(0.0, abs=TOL)
    assert flat.volume == pytest.approx(bead.volume, rel=1e-6)
    assert F.gasket_errors(gw, bw, depth, proud, rim_w=rim_w, inset=inset) == []


def test_gasket_errors():
    e = F.gasket_errors(1.0, 1.0, 1.0, 0.0, rim_w=3.0, inset=0.6)
    assert any("not wider than the bead" in m for m in e)
    assert any("not proud" in m for m in e)
    assert any("of rim" in m for m in e)
    assert any("under 2 lines" in m for m in F.gasket_errors(2.0, 0.6, 1.0, 0.5))


# ---------------------------------------------------------------- strain saddle

def test_strain_saddle_grips_the_cable_and_parts_do_not_collide():
    cable, width, axis_z = 8.8, 20.0, 12.0
    s = F.strain_saddle(cable, width, axis_z, liner_t=1.2, squeeze=0.4, gap=2.0)
    g = s.dims
    assert g["r_liner_in"] == pytest.approx(cable / 2 - 0.4)
    # bodies touch at most: base, bar and both liners never overlap
    bodies = [s.base, s.bar, *s.liners]
    for i, a in enumerate(bodies):
        for bb in bodies[i + 1:]:
            assert overlap(a, bb) == pytest.approx(0.0, abs=1e-3)
    # the liners' bore is smaller than the cable by the squeeze: vertical gap along the axis
    lin = F._part(s.liners[0] + s.liners[1])
    gap = rays.gaps(lin, (0, 0, 100), (0, 0, -1))
    assert gap == [pytest.approx(2 * g["r_liner_in"], abs=TOL)]
    # base top, bar top, insert bore depth (M3 default 6.7)
    assert rays.first_hit_z(s.base, g["pillar_x"] + 3.0, 0, 50) == pytest.approx(axis_z - 1.0, abs=TOL)
    assert rays.first_hit_z(s.base, g["pillar_x"], 0, 50) == pytest.approx(axis_z - 1.0 - 6.7, abs=TOL)
    assert bbox(s.bar)[5] == pytest.approx(axis_z + 1.0 + 6.0, abs=TOL)
    # clearance holes in the bar line up with the insert bores
    assert rays.gaps(s.bar, (g["pillar_x"], 0, 100), (0, 0, -1)) == []  # straight through
    # liner in print orientation stands on an end, length = width
    lb = bbox(s.liner_print)
    assert lb[5] - lb[2] == pytest.approx(width, abs=TOL)
    assert F.saddle_errors(cable, axis_z=axis_z) == []


def test_saddle_errors():
    e = F.saddle_errors(8.8, liner_t=0.6, squeeze=0.5, gap=0.0, axis_z=6.0)
    assert any("under 2 lines" in m for m in e)
    assert any("over a third" in m for m in e)
    assert any("gap must be positive" in m for m in e)
    assert any("insert bores" in m for m in e)


# ---------------------------------------------------------------- skins and keys

def test_dovetail_cutter_widths():
    depth, mouth, base = 1.2, 1.6, 2.6
    k = F.dovetail_cutter(depth, mouth, base, 10.0)
    assert rays.thickness(k, (-10, 0, -0.001), (1, 0, 0)) == pytest.approx(mouth, abs=TOL)
    assert rays.thickness(k, (-10, 0, -depth + 0.001), (1, 0, 0)) == pytest.approx(base, abs=TOL)
    assert F.dovetail_errors(depth, mouth, base) == []
    assert any("undercut" in m for m in F.dovetail_errors(1.2, 1.6, 1.8))
    assert any("must exceed" in m for m in F.dovetail_errors(1.2, 1.6, 1.6))
    assert any("2 lines" in m for m in F.dovetail_errors(1.2, 0.6, 1.6))


def test_skinned_bar_core_and_skin_fill_the_envelope():
    L, w, h, t, foot = 60.0, 16.0, 10.0, 1.6, 0.6
    s = F.skinned_bar(L, w, h, t, foot_h=foot)
    assert len(s.dims["keys_x"]) == 6
    assert overlap(s.core, s.skin) == pytest.approx(0.0, abs=1e-3)
    assert s.core.volume + s.skin.volume == pytest.approx(s.dims["envelope_volume"], rel=1e-5)
    # skin thickness on top (between keys) and at the side, and none on the bed
    x_between = (s.dims["keys_x"][0] + s.dims["keys_x"][1]) / 2
    assert rays.thickness(s.skin, (x_between, 0, 50), (0, 0, -1)) == pytest.approx(t, abs=TOL)
    assert rays.thickness(s.skin, (x_between, -50, h / 2), (0, 1, 0)) == pytest.approx(t, abs=TOL)
    assert bbox(s.skin)[2] == pytest.approx(foot, abs=TOL)
    assert bbox(s.core)[2] == pytest.approx(0.0, abs=TOL)
    # over a key the skin reaches down into the dovetail
    assert rays.thickness(s.skin, (s.dims["keys_x"][0], 0, 50), (0, 0, -1)) == pytest.approx(t + 1.2, abs=TOL)
    assert F.skin_errors(t, foot, core_h=h, key_depth=1.2) == []
    assert any("skin_min" in m for m in F.skin_errors(0.8, foot))
    assert any("layer 1" in m for m in F.skin_errors(t, 0.1))
    assert any("core floor" in m for m in F.skin_errors(t, foot, core_h=2.0, key_depth=1.2))


# ---------------------------------------------------------------- PCB bay (board_outline.json)

OUTLINE = ROOT / "tools" / "fab" / "testdata" / "board_outline.json"


def test_board_outline_fixture_has_the_documented_shape():
    """The fixture carries every field the board_* builders read, holes and connectors sit on
    the board, and the bbox matches the outline."""
    o = F.board_outline(OUTLINE)
    for k in ("outline_mm", "thickness_mm", "holes", "connectors", "keepouts",
              "max_component_height_top_mm", "max_component_height_bottom_mm"):
        assert k in o, k
    x0, y0, x1, y1 = F.board_bbox(o)
    assert (x0, y0, x1, y1) == (0, 0, 52, 40)
    for item in o["holes"] + o["connectors"]:
        assert x0 <= item["x_mm"] <= x1 and y0 <= item["y_mm"] <= y1, item
    assert F.board_outline(OUTLINE, "head") is not None
    with pytest.raises(KeyError, match="no variant"):
        F.board_outline(OUTLINE, "stage0")


def test_board_mount_bosses_under_every_hole():
    o = F.board_outline(OUTLINE)
    standoff, od, pilot, depth = 4.0, 5.0, 2.2, 3.5
    f = F.board_mount(o, standoff, od, pilot, depth)
    floor = F.rrect_prism(70, 60, 0, -2, 0)
    body = F.apply(_pos(floor, 26, 20, 0), f)
    bb = bbox(body)
    assert bb[2] == pytest.approx(-2, abs=TOL) and bb[5] == pytest.approx(standoff, abs=TOL)
    for h in o["holes"]:
        # boss top at the seat, pilot bore depth below it, full wall round the pilot
        assert rays.first_hit_z(body, h["x_mm"] + od / 2 - 0.3, h["y_mm"], 50) == pytest.approx(standoff, abs=TOL)
        assert rays.first_hit_z(body, h["x_mm"], h["y_mm"], 50) == pytest.approx(standoff - depth, abs=TOL)
    v = 70 * 60 * 2 + len(o["holes"]) * math.pi / 4 * (od ** 2 * standoff - pilot ** 2 * depth)
    assert body.volume == pytest.approx(v, rel=1e-4)
    assert F.board_seat_z(o, standoff) == pytest.approx(
        {"seat": 4.0, "top": 5.6, "top_env": 15.6, "bottom_env": 2.5})


def test_board_envelope_and_plug_envelopes_follow_the_outline():
    o = F.board_outline(OUTLINE)
    env = F.board_envelope(o, 4.0, clear=0.5)
    assert bbox(env) == pytest.approx([-0.5, -0.5, 2.0, 52.5, 40.5, 16.1], abs=TOL)
    plugs = dict(F.plug_envelopes(o, 4.0, 15.0, clear=0.5))
    assert sorted(plugs) == ["J1", "J2"]
    # J1 mates -X from the W edge: 15 long beyond x = 0, 9 + 1 wide about y = 20, from the
    # board top (seat 4 + 1.6) to 9.9 above it, grown by 0.5
    assert bbox(plugs["J1"]) == pytest.approx([-15, 15.0, 5.1, 0, 25.0, 16.0], abs=TOL)
    # J2 mates -Y from the S edge about x = 30
    assert bbox(plugs["J2"]) == pytest.approx([25.75, -15, 5.1, 34.25, 0, 12.1], abs=TOL)
    assert F.plug_envelopes(o, 4.0, 15.0, skip=("J1", "J2")) == []
    bad = dict(o, connectors=[dict(o["connectors"][0], mate_dir="+Z")])
    with pytest.raises(ValueError, match="mate_dir"):
        F.plug_envelopes(bad, 4.0, 15.0)
    ko = dict(F.keepout_boxes(o, 0, 20, grow=1.0))
    assert bbox(ko["antenna"]) == pytest.approx([11, 27, 0, 31, 41, 20], abs=TOL)


def test_board_errors():
    o = F.board_outline(OUTLINE)
    assert F.board_errors(o, standoff_h=4.0, boss_od=5.0, bore_d=2.2, bay=(54, 42, 17)) == []
    ins = C["inserts"]["m2_5"]  # a heat-set M2.5 boss is wider than the 5 mm pad
    e = F.board_errors(o, standoff_h=1.0, boss_od=ins["boss_od"], bore_d=ins["hole"], bay=(52, 40, 10))
    assert any("presses on copper" in m for m in e)
    assert any("not narrower than hole" in m for m in e)
    assert any("does not clear bottom components" in m for m in e)
    assert {m.split()[2] for m in e if m.startswith("board bay")} == {"W", "D", "H"}
    bad = dict(o, connectors=[dict(o["connectors"][0], mate_dir="up")])
    assert any("mate_dir" in m for m in F.board_errors(bad, standoff_h=4.0, boss_od=5.0, bore_d=2.2))


def _pos(part, x, y, z):
    import build123d as b

    return F._part(b.Pos(x, y, z) * part)


def test_features_listed_in_package_doc():
    import tools.fab as pkg

    assert "features" in pkg.__doc__
