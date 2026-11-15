"""pytest: dxf_lint generic checks and vendor rules (the example service profile and a shop profile)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import ezdxf
import pytest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location("dxf_lint", HERE / "dxf_lint.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


def _constants() -> Path:
    for p in [Path.cwd(), *HERE.parents]:
        c = p / "ssot" / "generated" / "constants.json"
        if c.is_file():
            return c
    raise FileNotFoundError("ssot/generated/constants.json")


CONSTANTS = _constants()
SVC = L.load_vendor(CONSTANTS, "example_service")
AL23 = L.find_sku(SVC, "AL-2.3")  # t 2.3 mm: hole floor max(0.8, 1.15) = 1.15, bridge 0.9, edge 0.7


def shop_vendor(bed=(300.0, 200.0), kerf=0.15) -> dict:
    """Mirror of ssot/constants/laser_vendors/shop.dhall for a repo's shop laser."""
    return {
        "slug": "my_shop", "name": "Shop CO2", "kind": "shop", "processes": ["laser_co2"],
        "formats": ["DXF", "SVG"], "units": ["mm"], "kerf_in_cad": True, "kerf_mm": kerf,
        "layers": ["CUT", "SCORE", "ENGRAVE"], "text_allowed": True, "one_part_per_file": False,
        "islands_allowed": True, "min_part_mm": {"x": 0.0, "y": 0.0},
        "max_part_mm": {"x": bed[0], "y": bed[1]}, "min_hole_factor_t": 0.0,
        "warn_hole_factor_t": 0.0, "warn_edge_factor_t": 0.0, "inside_corner_r_mm": 0.0,
        "finish_windows": [], "tap_drills": [], "skus": [], "source": "test",
    }


def make(tmp_path, w=80.0, h=50.0, holes=(), extra=None, name="p.dxf"):
    """A w x h plate at (5, 5) on CUT with circular holes [(x, y, d), ...] relative to its corner."""
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_lwpolyline([(5, 5), (5 + w, 5), (5 + w, 5 + h), (5, 5 + h)], close=True, dxfattribs={"layer": "CUT"})
    for x, y, d in holes:
        msp.add_circle((5 + x, 5 + y), d / 2.0, dxfattribs={"layer": "CUT"})
    if extra:
        extra(msp)
    p = tmp_path / name
    doc.saveas(p)
    return str(p)


def run(path, vendor=SVC, sku=AL23, bed=None):
    layers = {"CUT", "SCORE", "ENGRAVE"}
    return L.lint(path, layers, bed, vendor, sku)


def errs(rep, needle):
    return [e for e in rep["errors"] if needle in e]


def test_example_service_is_the_builtin_default():
    vendors = json.loads(CONSTANTS.read_text())["laser_vendors"]
    assert "example_service" in vendors
    assert SVC["kind"] == "service"
    # the template ships no shop laser; a repo may add its own in laser_vendors_local.dhall,
    # built with shop.dhall (kerf in CAD, no SKU rules by default)
    for slug, v in vendors.items():
        if v["kind"] == "shop":
            assert v["slug"] == slug and v["kerf_in_cad"] is True, slug
    assert SVC["kerf_in_cad"] is False and SVC["kerf_mm"] == 0.0
    assert SVC["layers"] == ["CUT"] and SVC["one_part_per_file"] and not SVC["text_allowed"]
    assert SVC["max_part_mm"] == {"x": 1100.0, "y": 750.0}
    assert AL23["t_mm"] == 2.3 and AL23["bend"]["k"] == 0.4
    # every row says it is an example, so nobody orders from it by mistake
    assert all("EXAMPLE" in r["source"] for r in SVC["skus"]) and "EXAMPLE" in SVC["source"]


def test_clean_plate_passes(tmp_path):
    rep = run(make(tmp_path, holes=[(20, 25, 3.2), (60, 25, 23.6)]))
    assert rep["ok"], rep["errors"]
    assert rep["contours"] == {"outer": 1, "holes": 2, "islands": 0}
    assert rep["min_hole_mm"] == 3.2


def test_hole_below_floor_fails_and_below_t_warns(tmp_path):
    rep = run(make(tmp_path, holes=[(20, 25, 1.0), (60, 25, 2.0)]))
    assert len(errs(rep, "hole 1.000 mm")) == 1
    assert not errs(rep, "hole 2.000 mm")
    assert any("hole 2.000 mm" in w for w in rep["warnings"])


def test_narrow_web_between_holes_fails(tmp_path):
    # 4 mm holes 4.5 mm apart: web 0.5 mm < 0.9 mm bridge.
    rep = run(make(tmp_path, holes=[(20, 25, 4.0), (24.5, 25, 4.0)]))
    assert errs(rep, "between holes")
    assert rep["min_bridge_mm"] == pytest.approx(0.5, abs=0.03)


def test_hole_too_close_to_edge_fails_and_2t_warns(tmp_path):
    rep = run(make(tmp_path, holes=[(2.5, 25, 4.0), (40, 4.0, 4.0)]))
    assert len(errs(rep, "hole-to-edge")) == 1  # 0.5 mm web
    assert any("hole-to-edge web 2.000" in w for w in rep["warnings"])  # 2.0 < 2t = 4.6


def test_text_rejected_for_a_cut_service(tmp_path):
    rep = run(make(tmp_path, extra=lambda m: m.add_text("A", dxfattribs={"layer": "ENGRAVE", "insert": (10, 10)})))
    assert errs(rep, "converted to outlines")
    assert errs(rep, "on layer 'ENGRAVE'")


def test_two_parts_and_islands_rejected(tmp_path):
    def extra(m):
        m.add_lwpolyline([(100, 5), (120, 5), (120, 25), (100, 25)], close=True, dxfattribs={"layer": "CUT"})
        m.add_circle((45, 30), 10.0, dxfattribs={"layer": "CUT"})  # hole
        m.add_circle((45, 30), 4.0, dxfattribs={"layer": "CUT"})   # island inside it
    rep = run(make(tmp_path, extra=extra))
    assert errs(rep, "2 separate parts")
    assert errs(rep, "floating island")


def test_extents_against_vendor_limits(tmp_path):
    assert errs(run(make(tmp_path, w=1200, h=100, name="big.dxf")), "exceed vendor example_service max part")
    assert errs(run(make(tmp_path, w=5, h=5, name="small.dxf")), "below vendor example_service min part")
    # 750 x 1100 fits rotated (either orientation).
    assert run(make(tmp_path, w=700, h=1000, name="rot.dxf"))["ok"]


def test_sku_required_when_vendor_lists_skus(tmp_path):
    rep = run(make(tmp_path), sku=None)
    assert errs(rep, "needs --sku")


def test_unknown_sku_and_vendor_exit():
    with pytest.raises(SystemExit):
        L.find_sku(SVC, "AL-9.9")
    with pytest.raises(SystemExit):
        L.load_vendor(CONSTANTS, "no_such_vendor")


def test_duplicate_and_open_paths_fail_without_vendor(tmp_path):
    def extra(m):
        m.add_line((10, 10), (20, 10), dxfattribs={"layer": "CUT"})
        m.add_line((20, 10), (10, 10), dxfattribs={"layer": "CUT"})
    rep = L.lint(make(tmp_path, extra=extra), {"CUT", "SCORE", "ENGRAVE"}, None)
    assert errs(rep, "duplicate LINE")
    rep2 = L.lint(make(tmp_path, name="open.dxf",
                       extra=lambda m: m.add_line((10, 10), (20, 12), dxfattribs={"layer": "CUT"})),
                  {"CUT", "SCORE", "ENGRAVE"}, None)
    assert errs(rep2, "open or branching")


def test_shop_vendor_checks_bed_and_allows_engrave(tmp_path):
    shop = shop_vendor()
    ok = make(tmp_path, w=250, h=150, holes=[(20, 20, 0.5)], name="ok.dxf",
              extra=lambda m: m.add_text("A", dxfattribs={"layer": "ENGRAVE", "insert": (30, 30)}))
    rep = run(ok, vendor=shop, sku=None)
    assert rep["ok"], rep["errors"]  # no SKUs: no hole rules; text off CUT allowed
    rep = run(make(tmp_path, w=350, h=100, name="wide.dxf"), vendor=shop, sku=None)
    assert errs(rep, "exceed vendor my_shop max part 300.0 x 200.0")


def test_cli_with_constants(tmp_path, capsys):
    p = make(tmp_path, holes=[(20, 25, 3.2)])
    assert L.main([p, "--constants", str(CONSTANTS), "--vendor", "example_service", "--sku", "AL-2.3"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["vendor"] == "example_service" and out["t_mm"] == AL23["t_mm"]


def test_default_constants_path_is_the_repo_file():
    assert L.DEFAULT_CONSTANTS.parts[-3:] == ("ssot", "generated", "constants.json")
    root = L.DEFAULT_CONSTANTS.parent.parent.parent
    assert (root / "tools" / "laser" / "dxf_lint.py").is_file()  # the repo root


# ---------------------------------------------------------------- hardening

def test_partial_overlap_of_collinear_lines_fails(tmp_path):
    def extra(m):
        # a closed square drawn with LINEs, plus a stray segment over half of its bottom edge
        pts = [(10, 10), (30, 10), (30, 30), (10, 30)]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            m.add_line(a, b, dxfattribs={"layer": "CUT"})
        m.add_line((15, 10), (25, 10), dxfattribs={"layer": "CUT"})
    rep = L.lint(make(tmp_path, extra=extra), {"CUT"}, None)
    assert errs(rep, "overlap for 10.000 mm")


def test_self_crossing_contour_fails(tmp_path):
    def extra(m):  # a bow-tie hole
        m.add_lwpolyline([(20, 20), (30, 30), (30, 20), (20, 30)], close=True, dxfattribs={"layer": "CUT"})
    rep = run(make(tmp_path, extra=extra))
    assert errs(rep, "crosses itself")
    assert L.self_crosses([(0, 0), (1, 0), (1, 1), (0, 1)]) is False


def test_outline_neck_below_bridge_fails(tmp_path):
    """Two notches from opposite edges leave a 0.5 mm neck (< AL-2.3 bridge 0.9)."""
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    pts = [(5, 5), (45, 5), (45, 29.75), (60, 29.75), (60, 5), (85, 5), (85, 55), (60, 55), (60, 30.25),
           (45, 30.25), (45, 55), (5, 55)]
    doc.modelspace().add_lwpolyline(pts, close=True, dxfattribs={"layer": "CUT"})
    p = tmp_path / "neck.dxf"
    doc.saveas(p)
    rep = run(str(p))
    assert errs(rep, "outline pinches to 0.500 mm")
    assert rep["min_neck_mm"] == pytest.approx(0.5, abs=1e-3)
    # the same outline with a 3 mm neck passes
    pts[2], pts[3], pts[8], pts[9] = (45, 28.5), (60, 28.5), (60, 31.5), (45, 31.5)
    doc2 = ezdxf.new()
    doc2.units = ezdxf.units.MM
    doc2.modelspace().add_lwpolyline(pts, close=True, dxfattribs={"layer": "CUT"})
    doc2.saveas(tmp_path / "ok.dxf")
    assert run(str(tmp_path / "ok.dxf"))["ok"]


def test_slot_arm_narrower_than_hole_floor_fails(tmp_path):
    """An L cutout whose 0.8 mm arm is below the AL-2.3 hole floor 1.15 (the bbox side is 10)."""
    def extra(m):
        m.add_lwpolyline([(20, 20), (30, 20), (30, 30), (29.2, 30), (29.2, 20.8), (20, 20.8)], close=True,
                         dxfattribs={"layer": "CUT"})
    rep = run(make(tmp_path, extra=extra))
    assert errs(rep, "slot in a cutout narrows to 0.800 mm")


def test_rounded_corners_are_not_necks(tmp_path):
    """A rounded rectangle, a large circle and a corner-radius slot report no neck."""
    def extra(m):
        m.add_lwpolyline([(20, 20, 0, 0, 0), (40, 20), (40, 26), (20, 26)], close=True, dxfattribs={"layer": "CUT"})
    rep = run(make(tmp_path, holes=[(60, 25, 23.6)], extra=extra))
    assert rep["ok"], rep["errors"]
    assert rep["min_neck_mm"] is None


def test_finish_needs_hang_hole_min_hole_and_window(tmp_path):
    alu = L.find_sku(SVC, "AL-3.2")  # t 3.2: anodize window 25 x 75 min
    small = make(tmp_path, w=70, h=50, holes=[(20, 25, 3.5)], name="small.dxf")
    rep = L.lint(small, {"CUT"}, None, SVC, alu, "anodize")
    assert errs(rep, "below example_service anodize min")  # 70 mm < 75 mm long side
    ok = make(tmp_path, w=100, h=40, holes=[(20, 20, 3.5)], name="ok.dxf")
    assert L.lint(ok, {"CUT"}, None, SVC, alu, "anodize")["ok"]
    nohole = make(tmp_path, w=100, h=40, name="nohole.dxf")
    assert errs(L.lint(nohole, {"CUT"}, None, SVC, alu, "anodize"), "needs a hanging hole")
    with pytest.raises(SystemExit):
        L.finish_window(SVC, "chrome")


def test_hole_histogram_counts_tap_drills(tmp_path):
    m3 = next(t["drill_mm"] for t in SVC["tap_drills"] if t["thread"] == "M3x0.5")
    rep = run(make(tmp_path, holes=[(10, 10, m3), (70, 10, m3), (40, 25, 6.0)]))
    assert rep["hole_d_mm"] == {f"{m3:.3f}": 2, "6.000": 1}


def test_profile_carries_finish_and_secondary_rules():
    assert SVC["hang_hole_mm"] == 1.6 and SVC["finish_min_hole_mm"] == 1.0
    assert SVC["countersink_min_t_mm"] == 3.2 and SVC["tap_min_t_mm"] == 1.5
    threads = {t["thread"] for t in SVC["tap_drills"]}
    assert {"M2.5x0.45", "M3x0.5", "M4x0.7", "M5x0.8", "M6x1.0", "6-32"} <= threads
    acrylic = L.find_sku(SVC, "ACRYLIC-3.0")
    assert acrylic["min_part_mm"] == {"x": 25.0, "y": 50.0} and acrylic.get("bend") is None
