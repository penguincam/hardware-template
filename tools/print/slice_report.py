#!/usr/bin/env python3
"""Extract print time, filament mass and tool changes from slicer output. Stdlib only.

Usage:
  python3 slice_report.py OUT.gcode.3mf [--max-grams G] [--max-hours H] [--max-toolchanges N]
  python3 slice_report.py OUT.gcode     [...]

Inputs
  .gcode.3mf / .3mf  OrcaSlicer or Bambu Studio sliced project.
                     Reads Metadata/slice_info.config (XML; JSON tolerated):
                     per plate <metadata key="prediction"> seconds,
                     <metadata key="weight"> grams, and <filament used_g used_m>.
                     Falls back to the embedded Metadata/plate_N.gcode header.
  .gcode             PrusaSlicer footer ("; estimated printing time (normal mode) =",
                     "; filament used [g] =", "; total filament used [g] =") or
                     Orca header ("; total filament weight [g] :",
                     "; model printing time: ... ; total estimated time: ...").

Prints JSON; exits 1 when a budget is exceeded or nothing could be parsed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

TIME_RE = re.compile(r"(?:(\d+)d\s*)?(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?")


def parse_duration(text: str) -> float | None:
    text = text.strip()
    m = TIME_RE.fullmatch(text)
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(g) if g else 0 for g in m.groups())
    return float(((d * 24 + h) * 60 + mi) * 60 + s)


def _sum_floats(text: str) -> float:
    return sum(float(x) for x in re.findall(r"[-+]?\d*\.?\d+", text))


def from_gcode_text(lines) -> dict:
    out: dict = {"source": "gcode"}
    toolchanges = 0
    last_tool = None
    for raw in lines:
        line = raw.strip()
        if line.startswith(";"):
            low = line.lower()
            if "estimated printing time (normal mode)" in low and "=" in line:
                out["seconds"] = parse_duration(line.split("=", 1)[1])
            elif "total estimated time:" in low:
                out["seconds"] = parse_duration(line.split("total estimated time:", 1)[1].split(";")[0])
            elif re.match(r";\s*total filament (used|weight) \[g\]\s*[:=]", low):
                out["grams"] = _sum_floats(re.split(r"[:=]", line, maxsplit=1)[1])
            elif re.match(r";\s*filament used \[g\]\s*[:=]", low):
                out.setdefault("grams_per_tool", [float(x) for x in re.findall(r"\d*\.?\d+", re.split(r"[:=]", line, maxsplit=1)[1])])
            continue
        m = re.match(r"^T(\d+)\b", line)
        if m:
            t = int(m.group(1))
            if last_tool is not None and t != last_tool:
                toolchanges += 1
            last_tool = t
    if "grams" not in out and "grams_per_tool" in out:
        out["grams"] = sum(out["grams_per_tool"])
    out["toolchanges"] = toolchanges
    return out


def from_slice_info(raw: bytes) -> dict:
    out: dict = {"source": "slice_info.config", "plates": []}
    text = raw.decode("utf-8", "replace").strip()
    if text.startswith("{"):
        data = json.loads(text)
        plates = data.get("plates") or [data]
        for p in plates:
            out["plates"].append({"seconds": float(p.get("prediction", 0)), "grams": float(p.get("weight", 0))})
    else:
        root = ET.fromstring(text)
        for plate in root.iter("plate"):
            meta = {m.get("key"): m.get("value") for m in plate.findall("metadata")}
            fil = [
                {"id": f.get("id"), "type": f.get("type"), "color": f.get("color"),
                 "used_g": float(f.get("used_g", 0) or 0), "used_m": float(f.get("used_m", 0) or 0)}
                for f in plate.findall("filament")
            ]
            out["plates"].append({
                "index": meta.get("index"),
                "seconds": float(meta.get("prediction", 0) or 0),
                "grams": float(meta.get("weight", 0) or 0) or sum(f["used_g"] for f in fil),
                "filaments": fil,
            })
    out["seconds"] = sum(p["seconds"] for p in out["plates"])
    out["grams"] = sum(p["grams"] for p in out["plates"])
    return out


def from_3mf(path: str) -> dict:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        info = next((n for n in names if n.lower().endswith("metadata/slice_info.config")), None)
        out = from_slice_info(z.read(info)) if info else {"source": "3mf", "plates": []}
        gcodes = sorted(n for n in names if n.lower().endswith(".gcode"))
        tc = 0
        for g in gcodes:
            sub = from_gcode_text(z.read(g).decode("utf-8", "replace").splitlines())
            tc += sub.get("toolchanges", 0)
            if not out.get("seconds") and sub.get("seconds"):
                out["seconds"] = sub["seconds"]
            if not out.get("grams") and sub.get("grams"):
                out["grams"] = sub["grams"]
        out["toolchanges"] = tc if gcodes else None
        if not gcodes:
            out.setdefault("warnings", []).append("no embedded G-code: was this exported after slicing (--slice N)?")
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path")
    p.add_argument("--max-grams", type=float)
    p.add_argument("--max-hours", type=float)
    p.add_argument("--max-toolchanges", type=int)
    a = p.parse_args(argv)
    if a.path.lower().endswith(".3mf"):
        rep = from_3mf(a.path)
    else:
        with open(a.path, encoding="utf-8", errors="replace") as fh:
            rep = from_gcode_text(fh)
    rep["file"] = a.path
    if rep.get("seconds"):
        rep["hours"] = round(rep["seconds"] / 3600.0, 3)
    fails = []
    if not rep.get("seconds") and not rep.get("grams"):
        fails.append("no time or mass found")
    if a.max_grams is not None and rep.get("grams", 0) > a.max_grams:
        fails.append(f"grams {rep['grams']:.1f} > budget {a.max_grams}")
    if a.max_hours is not None and rep.get("hours", 0) > a.max_hours:
        fails.append(f"hours {rep['hours']:.2f} > budget {a.max_hours}")
    if a.max_toolchanges is not None and (rep.get("toolchanges") or 0) > a.max_toolchanges:
        fails.append(f"toolchanges {rep['toolchanges']} > budget {a.max_toolchanges}")
    rep["failures"] = fails
    rep["ok"] = not fails
    json.dump(rep, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
