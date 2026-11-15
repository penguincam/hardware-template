"""pytest: sheet_quote order package (order-level rules, deterministic output) for the example service."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import ezdxf

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location("sheet_quote", HERE / "sheet_quote.py")
Q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Q)
CONSTANTS = Q.DEFAULT_CONSTANTS
SVC = json.loads(CONSTANTS.read_text())["laser_vendors"]["example_service"]
M3 = next(t["drill_mm"] for t in SVC["tap_drills"] if t["thread"] == "M3x0.5")


def plate(mod: Path, name: str, w=120.0, h=60.0, holes=()):
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_lwpolyline([(5, 5), (5 + w, 5), (5 + w, 5 + h), (5, 5 + h)], close=True, dxfattribs={"layer": "CUT"})
    for x, y, d in holes:
        msp.add_circle((5 + x, 5 + y), d / 2, dxfattribs={"layer": "CUT"})
    (mod / "DXF").mkdir(parents=True, exist_ok=True)
    doc.saveas(mod / "DXF" / f"{name}.dxf")
    return f"DXF/{name}.dxf"


def part(name, dxf, sku="AL-2.3", **kw):
    p = {"name": name, "dxf": dxf, "step": None, "sku": sku, "qty": 1, "finish": None, "finish_color": None,
         "tapped": [], "hardware": [], "countersinks": 0, "bends": 0, "note": ""}
    p.update(kw)
    return p


def order(*parts):
    return {"vendor": "example_service", "mod": "example", "issue": "issue 42", "parts": list(parts)}


def build(tmp_path, spec):
    return Q.build(tmp_path, spec, CONSTANTS)


def errors(res):
    return res["errors"] + [e for p in res["parts"] for e in p["errors"]]


def test_tapped_holes_counted_against_the_tap_drill(tmp_path):
    dxf = plate(tmp_path, "bracket", holes=[(10, 10, M3), (110, 10, M3), (60, 30, 6.0)])
    ok = build(tmp_path, order(part("bracket", dxf, tapped=[{"thread": "M3x0.5", "count": 2}])))
    assert ok["ok"], errors(ok)
    assert any("2 holes at the" in e for e in ok["parts"][0]["evidence"])
    bad = build(tmp_path, order(part("bracket", dxf, tapped=[{"thread": "M3x0.5", "count": 3}])))
    assert any("only 2 holes" in e for e in errors(bad))
    unknown = build(tmp_path, order(part("bracket", dxf, tapped=[{"thread": "M7", "count": 1}])))
    assert any("not in example_service tap_drills" in e for e in errors(unknown))


def test_tapping_window_and_thickness(tmp_path):
    # 20 x 30 mm is below the tapping window (25 x 38).
    dxf = plate(tmp_path, "tiny", w=20, h=30, holes=[(10, 15, M3)])
    res = build(tmp_path, order(part("tiny", dxf, tapped=[{"thread": "M3x0.5", "count": 1}])))
    assert any("tapping window" in e for e in errors(res))


def test_hardware_k_distance_from_edge(tmp_path):
    # An example press-in M3 nut: hole 4.22, K 6.35: one hole 4 mm from the edge fails.
    dxf = plate(tmp_path, "pem", holes=[(4, 30, 4.22), (60, 30, 4.22)])
    hw = [{"part_number": "EXAMPLE-M3-NUT", "count": 2, "hole_mm": 4.22, "k_mm": 6.35}]
    res = build(tmp_path, order(part("pem", dxf, hardware=hw)))
    assert any("under catalogue K 6.35" in e for e in errors(res))
    dxf2 = plate(tmp_path, "pem2", holes=[(10, 30, 4.22), (60, 30, 4.22)])
    assert build(tmp_path, order(part("pem2", dxf2, hardware=hw)))["ok"]
    # K is to ANY cut edge: a big hole 3 mm from a press-in hole fails.
    dxf3 = plate(tmp_path, "pem3", holes=[(15, 30, 4.22), (60, 30, 4.22), (30, 30, 24.0)])
    res = build(tmp_path, order(part("pem3", dxf3, hardware=hw)))
    assert any("nearest cut edge" in e for e in errors(res))


def test_bends_need_step_and_bendable_sku(tmp_path):
    dxf = plate(tmp_path, "bent", holes=[(60, 30, 6.0)])
    res = build(tmp_path, order(part("bent", dxf, bends=2)))
    assert any("no STEP" in e for e in errors(res))
    (tmp_path / "CAD").mkdir()
    (tmp_path / "CAD" / "bent.step").write_text("ISO-10303-21;\n")
    res = build(tmp_path, order(part("bent", dxf, bends=2, step="CAD/bent.step", note="flanges bend away from the viewer")))
    assert res["ok"], errors(res)
    acr = build(tmp_path, order(part("bent", dxf, sku="ACRYLIC-3.0", bends=1, step="CAD/bent.step", note="x")))
    assert any("no bend data" in e for e in errors(acr))


def test_finish_material_rules(tmp_path):
    dxf = plate(tmp_path, "panel", holes=[(60, 30, 6.0)])
    assert build(tmp_path, order(part("panel", dxf, finish="anodize", finish_color="black")))["ok"]
    steel = build(tmp_path, order(part("panel", dxf, sku="STEEL-1.9", finish="anodize", finish_color="black")))
    assert any("anodize needs aluminium" in e for e in errors(steel))
    acr = build(tmp_path, order(part("panel", dxf, sku="ACRYLIC-3.0", finish="powder_coat", finish_color="red")))
    assert any("powder coat needs a metal" in e for e in errors(acr))


def test_countersink_needs_the_minimum_thickness(tmp_path):
    dxf = plate(tmp_path, "cs", holes=[(60, 30, 3.4)], w=120, h=110)
    res = build(tmp_path, order(part("cs", dxf, sku="AL-2.3", countersinks=1)))
    assert any("countersink minimum" in e for e in errors(res))
    assert build(tmp_path, order(part("cs", dxf, sku="AL-3.2", countersinks=1)))["ok"]


def test_missing_dxf_and_duplicate_names(tmp_path):
    res = build(tmp_path, order(part("a", "DXF/none.dxf"), part("a", "DXF/none.dxf")))
    assert any("duplicate part names" in e for e in errors(res))
    assert any("not found" in e for e in errors(res))


def test_package_is_written_and_deterministic(tmp_path):
    mod = tmp_path / "mod"
    dxf = plate(mod, "bracket", holes=[(10, 10, M3), (110, 10, M3)])
    spec = order(part("bracket", dxf, qty=3, tapped=[{"thread": "M3x0.5", "count": 2}], finish="anodize",
                      finish_color="clear"))
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    args = [str(mod), "--spec-json", str(tmp_path / "spec.json"), "--constants", str(CONSTANTS)]
    assert Q.main(args) == 0
    out = mod / "order"
    first = {p.name: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert set(first) == {"bracket.dxf", "bracket.json", "parts.csv", "bom.csv", "order.json", "spec.json", "checklist.md"}
    rows = list(csv.DictReader((out / "parts.csv").open()))
    assert rows[0]["sku"] == "AL-2.3" and rows[0]["thickness_mm"] == "2.300" and rows[0]["finish"] == "anodize"
    assert rows[0]["tapping"] == "2 x M3x0.5" and rows[0]["qty"] == "3"
    bom = list(csv.DictReader((out / "bom.csv").open()))
    assert [(b["item"], b["qty"]) for b in bom] == [("bracket", "3"), ("tap M3x0.5", "6")]
    assert "comment on issue 42" in (out / "checklist.md").read_text()
    assert Q.main(args) == 0
    assert {p.name: p.read_bytes() for p in out.rglob("*") if p.is_file()} == first


def test_failing_spec_writes_nothing(tmp_path):
    mod = tmp_path / "mod"
    dxf = plate(mod, "bad", holes=[(1.5, 30, 2.0)])  # 0.5 mm hole-to-edge web
    (tmp_path / "spec.json").write_text(json.dumps(order(part("bad", dxf))))
    assert Q.main([str(mod), "--spec-json", str(tmp_path / "spec.json")]) == 1
    assert not (mod / "order").exists()


def test_verify_detects_a_stale_package(tmp_path):
    mod = tmp_path / "mod"
    dxf = plate(mod, "bracket", holes=[(60, 30, 6.0)])
    (tmp_path / "spec.json").write_text(json.dumps(order(part("bracket", dxf))))
    args = [str(mod), "--spec-json", str(tmp_path / "spec.json")]
    assert Q.main(args + ["--verify"]) == 1  # nothing committed yet
    assert Q.main(args) == 0
    assert Q.main(args + ["--verify"]) == 0
    plate(mod, "bracket", holes=[(60, 30, 8.0)])  # the part changed, the package did not
    assert Q.main(args + ["--verify"]) == 1
