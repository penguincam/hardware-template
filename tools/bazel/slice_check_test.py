"""slice_check: slice a 3MF headlessly with OrcaSlicer and assert grams/hours budgets.

Run by the slice_check macro (defs.bzl) through pytest_main.py. Inputs come
from the environment the macro sets (runfiles-relative paths):

  SLICE_INPUT        model 3MF (or STL) to slice
  SLICE_PRINTER_JSON printer.json in a profile dir that also holds
                     process.json[, filament.json] (third_party/slicer_profiles)
  SLICE_REPORT_PY    tools/print/slice_report.py
  SLICE_PARAMS       optional params.json; keys slice_budget_g and
                     slice_budget_toolchanges_count (unit-suffixed names) are
                     used when the macro gives no max_grams / max_toolchanges
  SLICE_MAX_GRAMS / SLICE_MAX_HOURS / SLICE_MAX_TOOLCHANGES  budgets ("" = none)

The slicer is $ORCA_SLICER, else orca-slicer / OrcaSlicer on PATH, else the
macOS app bundle (orca_profiles.find_orca). Printer profiles usually inherit
vendor presets the CLI cannot resolve from --load-settings, so they are
flattened first (orca_profiles.flatten_dir; vendor JSON fetched once per
OrcaSlicer tag into ~/.cache/orca_profiles) and sliced with an empty
--datadir. The test is SKIPPED with the reason when no slicer is present or a
vendor preset cannot be read or fetched (offline); it fails only on a slicer
error or a real over-budget. Time and grams come from
Metadata/slice_info.config of the sliced .gcode.3mf (slice_report.py).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).absolute().parent


def env_path(key: str) -> str:
    """A runfiles path from the macro's env. Bazel shell-quotes a $(rootpath) that holds a
    shell metacharacter, and env values are not tokenized, so a Voron accent name
    ([a]_label.3mf) arrives as 'mods/.../[a]_label.3mf' with the quotes: undo that."""
    v = os.environ[key]
    if v.startswith("'"):
        parts = shlex.split(v)
        if len(parts) == 1:
            return parts[0]
    return v


def _orca_profiles():
    spec = importlib.util.spec_from_file_location("orca_profiles", HERE / "orca_profiles.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _report_mod():
    path = env_path("SLICE_REPORT_PY")
    spec = importlib.util.spec_from_file_location("slice_report", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_slicer() -> str | None:
    return _orca_profiles().find_orca()


def budgets() -> dict:
    params = {}
    if os.environ.get("SLICE_PARAMS"):
        params = json.loads(Path(env_path("SLICE_PARAMS")).read_text())

    def pick(env: str, key: str | None):
        raw = os.environ.get(env, "")
        if raw:
            return float(raw)
        return float(params[key]) if key and key in params else None

    return {
        "grams": pick("SLICE_MAX_GRAMS", "slice_budget_g"),
        "hours": pick("SLICE_MAX_HOURS", None),  # no hours unit suffix: macro max_hours
        "toolchanges": pick("SLICE_MAX_TOOLCHANGES", "slice_budget_toolchanges_count"),
    }


def over_budget(rep: dict, b: dict) -> list[str]:
    fails = []
    if not rep.get("seconds") and not rep.get("grams"):
        fails.append("slicer output has no time or mass (was it sliced?)")
    if b["grams"] is not None and rep.get("grams", 0) > b["grams"]:
        fails.append(f"grams {rep['grams']:.1f} > budget {b['grams']}")
    hours = (rep.get("seconds") or 0) / 3600.0
    if b["hours"] is not None and hours > b["hours"]:
        fails.append(f"hours {hours:.2f} > budget {b['hours']}")
    if b["toolchanges"] is not None and (rep.get("toolchanges") or 0) > b["toolchanges"]:
        fails.append(f"toolchanges {rep['toolchanges']} > budget {b['toolchanges']}")
    return fails


def test_budget_logic():
    """The budget path works without a slicer (synthetic slice_info.config)."""
    xml = (b'<?xml version="1.0"?><config><plate><metadata key="index" value="1"/>'
           b'<metadata key="prediction" value="5400"/><metadata key="weight" value="20.5"/>'
           b'<filament id="1" type="PETG" used_g="20.5" used_m="6.8"/></plate></config>')
    rep = _report_mod().from_slice_info(xml)
    assert rep["seconds"] == 5400 and rep["grams"] == 20.5
    assert over_budget(rep, {"grams": 25, "hours": 2, "toolchanges": None}) == []
    assert len(over_budget(rep, {"grams": 10, "hours": 1, "toolchanges": None})) == 2


def test_slice_within_budget(tmp_path):
    b = budgets()
    assert b["grams"] is not None or b["hours"] is not None, "slice_check needs a grams or hours budget"
    slicer = find_slicer()
    if slicer is None:
        pytest.skip("orca-slicer not found (ORCA_SLICER, PATH, /Applications); the Nix devShell ships it "
                    "only on Linux. Install OrcaSlicer or run on Linux to enforce the slice budget.")
    op = _orca_profiles()
    prof = Path(env_path("SLICE_PRINTER_JSON")).parent
    try:
        flat = op.flatten_dir(prof, slicer, tmp_path / "profiles")
    except op.ProfileUnavailable as e:
        pytest.skip(f"vendor presets unavailable, cannot flatten {prof.name} profiles: {e}")
    settings = f"{flat['machine']};{flat['process']}"
    out = tmp_path / "out.gcode.3mf"
    datadir = tmp_path / "datadir"  # empty: never pick up the GUI's user presets
    (datadir / "system").mkdir(parents=True)
    cmd = [slicer, "--datadir", str(datadir), "--load-settings", settings]
    if flat["filaments"]:
        cmd += ["--load-filaments", ";".join(str(f) for f in flat["filaments"])]
    cmd += ["--slice", "0", "--outputdir", str(tmp_path), "--export-3mf", out.name,
            os.path.abspath(env_path("SLICE_INPUT"))]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=tmp_path)
    produced = out if out.is_file() else next(iter(tmp_path.glob("*.gcode.3mf")), None)
    assert proc.returncode == 0 and produced, (
        f"slicer failed rc={proc.returncode}: {' '.join(cmd)}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    rep = _report_mod().from_3mf(str(produced))
    print(json.dumps({**{k: rep.get(k) for k in ("seconds", "grams", "toolchanges")},
                      "orca_profile_tag": flat["tag"], "vendor_sha256": flat["vendor_sha256"]}))
    # A slice with no filament preset reports 0 g, which passes any grams budget
    # vacuously (seen once when a profile dir had no filament.json).
    assert not (b["grams"] is not None and not rep.get("grams")), (
        f"slice reported {rep.get('grams')} g: no filament preset loaded from {prof} "
        "(add filament.json beside printer.json)")
    fails = over_budget(rep, b)
    assert not fails, "; ".join(fails)
