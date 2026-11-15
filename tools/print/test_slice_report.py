"""pytest: slice_info.config and G-code footer parsing."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import slice_report  # noqa: E402

INFO = b"""<?xml version="1.0" encoding="UTF-8"?>
<config><plate>
<metadata key="index" value="1"/><metadata key="prediction" value="5400"/><metadata key="weight" value="62.50"/>
<filament id="1" type="PETG" used_m="18.2" used_g="55.1"/><filament id="2" type="TPU" used_m="2.3" used_g="7.4"/>
</plate></config>"""


def test_3mf(tmp_path):
    p = tmp_path / "t.gcode.3mf"
    with zipfile.ZipFile(p, "w") as z:
        # Explicit timestamps: build shells may set a pre-1980 SOURCE_DATE_EPOCH.
        ts = (2026, 1, 1, 0, 0, 0)
        z.writestr(zipfile.ZipInfo("Metadata/slice_info.config", ts), INFO)
        z.writestr(zipfile.ZipInfo("Metadata/plate_1.gcode", ts), "T0\nG1 X1\nT1\nT0\nT0\n")
    r = slice_report.from_3mf(str(p))
    assert r["seconds"] == 5400 and r["grams"] == 62.5 and r["toolchanges"] == 2
    assert [f["type"] for f in r["plates"][0]["filaments"]] == ["PETG", "TPU"]


def test_prusa_footer():
    lines = ["; filament used [g] = 10.20, 1.30", "; estimated printing time (normal mode) = 1d 2h 5m 30s"]
    r = slice_report.from_gcode_text(lines)
    assert r["seconds"] == ((24 + 2) * 60 + 5) * 60 + 30
    assert abs(r["grams"] - 11.5) < 1e-9
