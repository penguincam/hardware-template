"""Numeric checks of the example sealed box: every check() rule fires, and walls, floor,
groove, gland hole, insert bores and lid holes measure as the params say (rays, not
pictures). Bazel: //mods/example/sealed_box:sealed_box_test. Needs build123d."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from tools.fab import features as F, rays  # noqa: E402

_spec = importlib.util.spec_from_file_location("sealed_box", HERE / "CAD" / "sealed_box.py")
SB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SB)
P = json.loads((HERE / "params.json").read_text())
TOL = 0.02


@pytest.fixture(scope="module")
def body():
    return SB.build(P)


@pytest.fixture(scope="module")
def lid():
    return SB.build_lid(P)


def test_params_pass_check():
    SB.check(P)


@pytest.mark.parametrize("change,needle", [
    ({"wall_mm": 3.0}, "gasket: groove leaves"),
    ({"bead_proud_mm": 0.0}, "not proud"),
    ({"pillar_od_mm": 6.0}, "pillar: boss wall"),
    ({"pillar_ear_mm": 4.5}, "loose from the wall"),
    ({"lid_hole_mm": 6.0}, "of lid round it"),
    ({"cable_od_mm": 9.0}, "outside the gland clamp range"),
    ({"gland_z_mm": 10.0}, "within 1 mm of the floor"),
    ({"gland_z_mm": 36.0}, "within 2 mm of the groove floor"),
    ({"floor_mm": 1.0}, "floor 1.00 under"),
    ({"lid_t_mm": 2.0}, "lid 2.00 under"),
])
def test_each_rule_fires(change, needle):
    with pytest.raises(ValueError, match=needle):
        SB.check({**P, **change})


def test_missing_param_is_reported():
    with pytest.raises(ValueError, match="params missing"):
        SB.check({k: v for k, v in P.items() if k != "wall_mm"})


def test_body_is_one_valid_solid_on_the_bed(body):
    d = SB.dims(P)
    assert body.is_valid and len(body.solids()) == 1
    bb = body.bounding_box()
    assert bb.min.Z == pytest.approx(0.0, abs=TOL) and bb.max.Z == pytest.approx(d["H"], abs=TOL)


def test_walls_floor_and_groove(body):
    d = SB.dims(P)
    # Front wall above the gland, and the floor at the centre.
    assert rays.thickness(body, (0, -200, 30), (0, 1, 0)) == pytest.approx(P["wall_mm"], abs=TOL)
    assert rays.first_hit_z(body, 0, 0, 100) == pytest.approx(P["floor_mm"], abs=TOL)
    # Groove floor on the back rim, centred gasket_inset_mm in from the outer face.
    y = d["D"] / 2 - P["gasket_inset_mm"]
    assert rays.first_hit_z(body, 0, y, d["H"] + 5) == pytest.approx(d["H"] - P["groove_depth_mm"], abs=TOL)
    # Groove width across the back rim, measured just under the rim top.
    gaps = rays.gaps(body, (0, d["D"] / 2 + 5, d["H"] - P["groove_depth_mm"] / 2), (0, -1, 0))
    assert gaps[0] == pytest.approx(P["groove_w_mm"], abs=TOL)


def test_gland_hole_width_and_height(body):
    d = SB.dims(P)
    y = -d["D"] / 2 + P["wall_mm"] / 2  # inside the front wall
    # Across X at the hole axis the only opening is the gland hole.
    assert rays.gaps(body, (-200, y, P["gland_z_mm"]), (1, 0, 0)) == [pytest.approx(P["gland_hole_mm"], abs=TOL)]
    top, _ = F.teardrop_profile(P["gland_hole_mm"] / 2, P["gland_cap_mm"])
    # Looking down inside the wall from just under the capped tip: the hole bottom.
    z0 = P["gland_z_mm"] + top - 0.05
    assert rays.first_hit_z(body, 0, y, z0) == pytest.approx(P["gland_z_mm"] - P["gland_hole_mm"] / 2, abs=TOL)


def test_pillar_insert_bores(body):
    d = SB.dims(P)
    for x, y in d["pillars"]:
        assert rays.first_hit_z(body, x, y, d["H"] + 5) == pytest.approx(d["H"] - P["insert_depth_mm"], abs=TOL)


def test_lid_holes_line_up_with_the_pillars(lid):
    d = SB.dims(P)
    assert lid.is_valid and len(lid.solids()) == 1
    bb = lid.bounding_box()
    assert bb.min.Z == pytest.approx(0.0, abs=TOL) and bb.max.Z == pytest.approx(P["lid_t_mm"], abs=TOL)
    for x, y in d["pillars"]:
        assert rays.hits(lid, (x, y, 50), (0, 0, -1)) == []
    assert rays.thickness(lid, (0, 0, 50), (0, 0, -1)) == pytest.approx(P["lid_t_mm"], abs=TOL)


def test_gasket_fits_the_groove_and_stands_proud(body):
    d = SB.dims(P)
    flat = SB.build_gasket(P)
    bb = flat.bounding_box()
    assert bb.min.Z == pytest.approx(0.0, abs=TOL)
    assert bb.max.Z - bb.min.Z == pytest.approx(P["groove_depth_mm"] + P["bead_proud_mm"], abs=TOL)
    seated = F.gasket_bead(d["W"], d["D"], d["R"], P["gasket_inset_mm"], P["bead_w_mm"], P["groove_depth_mm"],
                           P["bead_proud_mm"], d["H"])
    inter = body & seated
    overlap = sum(s.volume for s in inter.solids()) if inter is not None else 0.0
    assert overlap == pytest.approx(0.0, abs=1e-3)
    assert seated.volume == pytest.approx(flat.volume, rel=1e-6)
