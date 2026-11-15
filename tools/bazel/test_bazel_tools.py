"""Unit tests for the Bazel macro helpers (stdlib parts only; no CAD kernel)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).absolute().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _root() -> Path:
    for p in [Path.cwd(), *Path(__file__).absolute().parents]:
        if (p / "ssot" / "generated" / "constants.json").is_file():
            return p
    raise FileNotFoundError("ssot/generated/constants.json")


def test_bed_fit_as_built_and_any(tmp_path):
    bf = _load("bed_fit")
    # 150 mm tall part on a 300 x 300 x 100 bed: fails upright, fits lying down.
    assert bf.fit([20, 30, 150], (300, 300, 100), 5.0, "as_built")["fits"] is False
    lying = bf.fit([20, 30, 150], (300, 300, 100), 5.0, "any")
    assert lying["fits"] and lying["dims_mm"][2] < 95
    # as-built is preferred whenever it fits
    assert bf.fit([80, 50, 3.6], (270, 270, 270), 5.0, "any")["orientation"] == "xyz"
    # margin is per side in XY: 210 + 2*5 = 220 fits exactly, 211 does not
    assert bf.fit([210, 10, 10], (220, 220, 250), 5.0, "as_built")["fits"]
    assert not bf.fit([211, 10, 10], (220, 220, 250), 5.0, "as_built")["fits"]
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps({"bbox_mm": {"size": [240, 20, 100]}}))
    consts = str(_root() / "ssot" / "generated" / "constants.json")
    base = ["--report", str(rep), "--constants", consts]
    # 240 mm long: fits example_large (270) flat; example_small (220 x 220 x 250) only stood up.
    assert bf.main(base + ["--printer", "example_large"]) == 0
    assert bf.main(base + ["--printer", "example_large", "--printer", "example_small"]) == 1
    assert bf.main(base + ["--printer", "example_small", "--orientation", "any"]) == 0
    assert bf.main(base + ["--printer", "example_small", "--orientation", "yzx"]) == 0


def test_slice_budget_helpers(monkeypatch, tmp_path):
    monkeypatch.setenv("SLICE_REPORT_PY", str(_root() / "tools/print/slice_report.py"))
    params = tmp_path / "p.json"
    params.write_text(json.dumps({"slice_budget_g": 30, "slice_budget_toolchanges_count": 4}))
    monkeypatch.setenv("SLICE_PARAMS", str(params))
    monkeypatch.setenv("SLICE_MAX_GRAMS", "12.5")
    monkeypatch.setenv("SLICE_MAX_HOURS", "2")
    monkeypatch.delenv("SLICE_MAX_TOOLCHANGES", raising=False)
    sc = _load("slice_check_test")
    b = sc.budgets()
    assert b == {"grams": 12.5, "hours": 2.0, "toolchanges": 4.0}
    assert sc.over_budget({"seconds": 3600, "grams": 13}, b) == ["grams 13.0 > budget 12.5"]
    sc.test_budget_logic()


def test_slice_env_path_unquotes_accent_names(monkeypatch):
    """Bazel shell-quotes a $(rootpath) with [ or ] in env (not tokenized): a Voron [a]_ name
    reached the slicer with its quotes and failed."""
    sc = _load("slice_check_test")
    monkeypatch.setenv("SLICE_INPUT", "'mods/c/m/[a]_label_x2.3mf'")
    assert sc.env_path("SLICE_INPUT") == "mods/c/m/[a]_label_x2.3mf"
    monkeypatch.setenv("SLICE_INPUT", "mods/c/m/body.3mf")  # plain names are left alone
    assert sc.env_path("SLICE_INPUT") == "mods/c/m/body.3mf"
    monkeypatch.setenv("SLICE_INPUT", "'mods/c/m/it'\\''s.3mf'")  # ShellEscaper form of a quote
    assert sc.env_path("SLICE_INPUT") == "mods/c/m/it's.3mf"


def test_cad_export_part_imports_tools_fab(tmp_path):
    """A cad_part module doing `from tools.fab import coupon` loads under the exporter's runfiles,
    where rules_python made `tools` a regular package without fab (earlier parts loaded
    coupon.py by file path to get around it)."""
    runfiles = tmp_path / "cad_export.runfiles" / "_main"
    for d in ("tools", "tools/bazel"):
        (runfiles / d).mkdir(parents=True, exist_ok=True)
        (runfiles / d / "__init__.py").write_text("")
    execroot = tmp_path / "execroot"
    (execroot / "tools" / "fab").mkdir(parents=True)
    (execroot / "tools" / "fab" / "__init__.py").write_text("")
    (execroot / "tools" / "fab" / "coupon.py").write_text("MARK = 'coupon'\n")
    cad = execroot / "mods" / "c" / "m" / "CAD"
    cad.mkdir(parents=True)
    (cad / "part.py").write_text("from tools.fab import coupon\nVALUE = coupon.MARK\n")
    script = (
        "import importlib.util, sys\n"
        f"sys.path.insert(0, {str(runfiles)!r})\n"
        f"spec = importlib.util.spec_from_file_location('cad_export', {str(HERE / 'cad_export.py')!r})\n"
        "ce = importlib.util.module_from_spec(spec); spec.loader.exec_module(ce)\n"
        "print(ce.load_module('mods/c/m/CAD/part.py').VALUE)\n"
    )
    # -I: no cwd on sys.path, as for the Bazel genrule (cwd = execroot).
    proc = subprocess.run([sys.executable, "-I", "-c", script], cwd=execroot, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "coupon"


def test_orca_profiles_flatten_offline(tmp_path, monkeypatch):
    """inherits chains resolve parent-first against an unpacked app bundle (no network)."""
    op = _load("orca_profiles")
    app = tmp_path / "Orca.app" / "Contents"
    (app / "MacOS").mkdir(parents=True)
    exe = app / "MacOS" / "OrcaSlicer"
    exe.write_text("")
    res = app / "Resources" / "profiles"
    for vendor, items in {
        "Example": {"machine_list": [{"name": "base_m", "sub_path": "machine/base_m.json"}],
                      "process_list": [{"name": "base_p", "sub_path": "process/base_p.json"}],
                      "filament_list": [{"name": "base_f", "sub_path": "filament/base_f.json"}]},
        "OrcaFilamentLibrary": {},
    }.items():
        (res / vendor).mkdir(parents=True)
        (res / f"{vendor}.json").write_text(json.dumps(items))
    for kind, data in (("machine", {"name": "base_m", "a": 1, "b": 1}),
                       ("process", {"name": "base_p", "wall_loops": "2", "compatible_printers": []}),
                       ("filament", {"name": "base_f", "t": "200"})):
        (res / "Example" / kind).mkdir()
        (res / "Example" / kind / f"base_{kind[0]}.json").write_text(json.dumps(data))
    prof = tmp_path / "prof"
    prof.mkdir()
    (prof / "printer.json").write_text(json.dumps({"name": "M", "printer_model": "Example P1",
                                                   "inherits": "base_m", "b": 2, "from": "system"}))
    (prof / "process.json").write_text(json.dumps({"name": "P", "inherits": "base_p"}))
    (prof / "filament.json").write_text(json.dumps({"name": "F", "inherits": "base_f"}))
    monkeypatch.setenv("ORCA_PROFILE_CACHE", str(tmp_path / "cache"))
    flat = op.flatten_dir(prof, str(exe), tmp_path / "out", overrides={"wall_loops": "4"})
    m = json.loads(flat["machine"].read_text())
    # "from": "system" so Orca 2.3/2.4 match the process to the machine (cli_machine).
    assert (m["a"], m["b"], m["from"], "inherits" in m) == (1, 2, "system", False)
    p = json.loads(flat["process"].read_text())
    assert p["wall_loops"] == "4" and p["compatible_printers"] == ["M"]
    f = json.loads(flat["filaments"][0].read_text())
    assert f["t"] == "200" and f["compatible_printers"] == ["M"]
    assert "Example/machine/base_m.json" in flat["vendor_sha256"]
    # A missing parent is a ProfileUnavailable (the slice test skips on it), not a crash.
    (prof / "process.json").write_text(json.dumps({"name": "P", "inherits": "nope"}))
    try:
        op.flatten_dir(prof, str(exe), tmp_path / "out2")
    except op.ProfileUnavailable:
        pass
    else:
        raise AssertionError("expected ProfileUnavailable")


def test_orca_profiles_copy_flat_marks_machine_system(tmp_path):
    """A pre-flattened profile ("from": "User", no inherits) is handed to the CLI as a
    system machine, else Orca 2.3/2.4 exit -17 (process not compatible)."""
    op = _load("orca_profiles")
    lane = tmp_path / "flat" / "lane"
    lane.mkdir(parents=True)
    (lane / "machine.json").write_text(json.dumps({"name": "M", "from": "User", "type": "machine"}))
    (lane / "process.json").write_text(json.dumps({"name": "P", "from": "User", "compatible_printers": ["X"]}))
    (lane / "filament.json").write_text(json.dumps({"name": "F", "from": "User"}))
    flat = op.flatten_dir(lane, None, tmp_path / "out")
    m = json.loads(flat["machine"].read_text())
    p = json.loads(flat["process"].read_text())
    f = json.loads(flat["filaments"][0].read_text())
    assert (m["from"], "inherits" in m, flat["tag"]) == ("system", False, "pre-flattened")
    assert p["compatible_printers"] == ["M"] and f["compatible_printers"] == ["M"]


def test_metadata_check_flags_unlisted_files(tmp_path):
    mc = _load("metadata_check")
    mod = tmp_path / "mods" / "me" / "part"
    for d in ("CAD", "STLs", "docs", "CAD/__pycache__"):
        (mod / d).mkdir(parents=True)
    (mod / "CAD" / "part.step").write_text("x")
    (mod / "STLs" / "part.stl").write_text("x")
    (mod / "CAD" / "__pycache__" / "part.cpython-312.pyc").write_text("x")
    meta = mod / ".metadata.yml"
    base = ("creator: me\nslug: part\ntitle: t\ndescription: d\nmod_version: 1\n"
            "process: [fdm]\nprinters: [example_large]\ncad: [CAD/part.step]\nstls: [STLs/part.stl]\n")
    meta.write_text(base)
    assert mc.check(meta) == []
    (mod / "docs" / "notes.md").write_text("x")
    errs = mc.check(meta)
    assert len(errs) == 1 and "not listed" in errs[0] and "docs/notes.md" in errs[0]
    meta.write_text(base + "docs: [docs/notes.md]\n")
    assert mc.check(meta) == []


def test_metadata_check_empty_printers_only_without_fdm(tmp_path):
    """A sheet-metal-only mod (process [laser]) may list no printers; an fdm mod may not."""
    mc = _load("metadata_check")
    mod = tmp_path / "mods" / "me" / "panel"
    mod.mkdir(parents=True)
    meta = mod / ".metadata.yml"
    head = "creator: me\nslug: panel\ntitle: t\ndescription: d\nmod_version: 1\n"
    meta.write_text(head + "process: [laser]\nprinters: []\n")
    assert mc.check(meta) == []
    meta.write_text(head + "process: [laser, cnc]\nprinters: []\n")
    assert mc.check(meta) == []
    meta.write_text(head + "process: [laser]\n")
    assert any("missing printers" in e for e in mc.check(meta))
    meta.write_text(head + "process: [fdm, laser]\nprinters: []\n")
    errs = mc.check(meta)
    assert len(errs) == 1 and "missing printers" in errs[0] and "fdm" in errs[0]
