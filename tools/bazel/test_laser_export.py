"""laser_export vendor handling: cut service nominal geometry, shop kerf in CAD, dropped layers."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).absolute().parent
MODULE = '''
from build123d import Circle, Location, Rectangle, Text, Sketch, Align

def build_sheet(p):
    cut = Rectangle(p["w_mm"], p["h_mm"]) - Location((0, 0)) * Circle(p["d_mm"] / 2)
    return {"CUT": cut, "ENGRAVE": Location((0, -15)) * Text("A", font_size=4)}
'''


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _root() -> Path:
    for p in [Path.cwd(), *HERE.parents]:
        if (p / "ssot" / "generated" / "constants.json").is_file():
            return p
    raise FileNotFoundError("ssot/generated/constants.json")


X = _load("laser_export")
CONSTANTS = _root() / "ssot" / "generated" / "constants.json"


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "part.py").write_text(MODULE)
    (tmp_path / "params.json").write_text(json.dumps({"w_mm": 60.0, "h_mm": 40.0, "d_mm": 10.0}))
    const = json.loads(CONSTANTS.read_text())
    shop = copy.deepcopy(const["laser_vendors"]["example_service"])
    shop.update(slug="my_shop", kind="shop", kerf_in_cad=True, kerf_mm=0.2,
                layers=["CUT", "SCORE", "ENGRAVE"], text_allowed=True, skus=[],
                max_part_mm={"x": 300.0, "y": 200.0})
    const["laser_vendors"]["my_shop"] = shop
    zero = dict(shop, slug="zero", kerf_mm=0.0)
    const["laser_vendors"]["zero"] = zero
    (tmp_path / "constants.json").write_text(json.dumps(const))
    return tmp_path


def export(d: Path, *extra: str) -> dict:
    rep = d / "out.json"
    X.main(["--module", str(d / "part.py"), "--params", str(d / "params.json"), "--out", str(d / "out.dxf"),
            "--report", str(rep), "--constants", str(d / "constants.json"), *extra])
    return json.loads(rep.read_text())


def test_service_nominal_cut_only(setup):
    r = export(setup, "--vendor", "example_service", "--sku", "AL-2.3")
    assert r["kerf_comp_in_cad"] is False and r["kerf_mm"] == 0.0
    assert r["dropped_layers"] == ["ENGRAVE"] and "ENGRAVE" not in r["path_length_mm"]
    assert r["extents_mm"] == [60.0, 40.0]
    assert r["t_mm"] == pytest.approx(2.3)


def test_service_refuses_kerf_comp(setup):
    with pytest.raises(SystemExit, match="compensates kerf itself"):
        export(setup, "--vendor", "example_service", "--kerf-comp")


def test_shop_vendor_applies_kerf(setup):
    r = export(setup, "--vendor", "my_shop")
    assert r["kerf_comp_in_cad"] is True and r["kerf_mm"] == 0.2
    assert r["dropped_layers"] == []
    # Outline grows by kerf/2 per side; the hole shrinks.
    assert r["extents_mm"] == [pytest.approx(60.2, abs=1e-3), pytest.approx(40.2, abs=1e-3)]


def test_shop_vendor_without_kerf_is_an_error(setup):
    with pytest.raises(SystemExit, match="kerf coupon"):
        export(setup, "--vendor", "zero")


def test_unknown_vendor(setup):
    with pytest.raises(SystemExit, match="not in laser_vendors"):
        export(setup, "--vendor", "no_such_vendor")
