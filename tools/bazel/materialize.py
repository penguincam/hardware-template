#!/usr/bin/env python3
"""Build a mod's Bazel outputs and copy them into its Voron-style folders.

    materialize.py mods/<creator>/<slug> --kind print   # .step->CAD .stl->STLs .3mf->3MF
    materialize.py mods/<creator>/<slug> --kind laser   # .dxf->DXF
    materialize.py mods/<creator>/<slug> --kind step    # .step->CAD

Used by the just export-print / export-laser / export-step recipes. Every
genrule in the mod package is built (genrules tagged external-tool with
--config=external), outputs are listed with `bazel cquery --output=files`
and copied by extension. File names are the target names, so they must follow
the Voron rules (snake_case, optional [a]_/[o]_/[c]_ prefix, optional _xN).
Prints one line per copied file plus each cad_part report (bbox, volume,
mass). Stdlib only; run from the repo root inside the devShell.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

KINDS = {
    "print": {".step": "CAD", ".stl": "STLs", ".3mf": "3MF"},
    "laser": {".dxf": "DXF"},
    "step": {".step": "CAD"},
}
NAME_RE = re.compile(r"^(?!.*_x0[0-9]*$)(\[[aoc]\]_)?[a-z0-9]+(?:[_-][a-z0-9]+)*(_x[1-9][0-9]*)?$")


def bazel(bz: str, *args: str) -> str:
    proc = subprocess.run([bz, *args], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(f"{bz} {' '.join(args[:2])} failed ({proc.returncode})")
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mod", help="mods/<creator>/<slug>")
    ap.add_argument("--kind", choices=sorted(KINDS), required=True)
    ap.add_argument("--bazel", default=os.environ.get("BAZEL", "bazelisk"))
    a = ap.parse_args(argv)

    mod = a.mod.rstrip("/")
    if not os.path.isfile(os.path.join(mod, "BUILD.bazel")):
        raise SystemExit(f"{mod}/BUILD.bazel not found (run from the repo root)")
    pkg = "//" + mod
    scope = f"kind(genrule, {pkg}:all)"
    rules = bazel(a.bazel, "query", scope, "--output=label").split()
    external = set(bazel(a.bazel, "query", f'attr(tags, "external-tool", {scope})', "--output=label").split())
    plain = [r for r in rules if r not in external]
    if not rules:
        raise SystemExit(f"no genrule targets in {pkg} (cad_part, laser_sheet)")
    files: list[str] = []
    for group, extra in ((plain, []), (sorted(external), ["--config=external"])):
        if not group:
            continue
        bazel(a.bazel, "build", *extra, *group)
        files += bazel(a.bazel, "cquery", *extra, " + ".join(group), "--output=files").split()

    want = KINDS[a.kind]
    copied, bad = [], []
    for src in files:
        stem, ext = os.path.splitext(os.path.basename(src))
        if ext not in want:
            continue
        if not NAME_RE.match(stem):
            bad.append(stem + ext)
            continue
        dest_dir = os.path.join(mod, want[ext])
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, stem + ext)
        shutil.copyfile(src, dest)
        os.chmod(dest, 0o644)
        copied.append(dest)
        print(f"  {dest}  ({os.path.getsize(dest)} bytes)")
    if a.kind == "print":
        for src in files:
            if src.endswith(".report.json"):
                rep = json.load(open(src, encoding="utf-8"))
                print(f"  report {os.path.basename(src)}: bbox {rep['bbox_mm']['size']} mm, "
                      f"volume {rep['volume_mm3']} mm3, solid mass {rep.get('mass_solid_g', 'n/a')} g")
    if bad:
        raise SystemExit(f"target names break Voron naming, rename them: {bad}")
    if not copied:
        raise SystemExit(f"no {sorted(want)} outputs in {pkg}")
    print(f"materialized {len(copied)} file(s); list new paths in mod.dhall and run just ssot-render")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
