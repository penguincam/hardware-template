"""Check a mod's rendered .metadata.yml (stdlib + pyyaml).

Usage: metadata_check.py mods/<creator>/<slug>/.metadata.yml [...]
Checks required keys, slug/creator against the directory, that every listed
file exists with a Voron-valid name, and that every file present under CAD/,
STLs/, 3MF/, DXF/, images/ and docs/ is listed (no unlisted exports or docs).
`printers` may be an empty list when no process is fdm (a sheet-metal-only mod cut by
a service prints nothing); an fdm mod must name at least one printer.
Exit 1 on any error. Used by the metadata_test Bazel macro and `just metadata-check`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REQUIRED = ("creator", "slug", "title", "description", "mod_version", "process", "printers")
# Keys that must be present but may be an empty list when the mod does not print.
EMPTY_OK_WITHOUT_FDM = ("printers",)
LISTS = ("cad", "stls", "threemf", "dxf", "images", "docs")
NAME_RE = re.compile(r"^(\[a\]_)?[a-z0-9_]+(_x\d+)?\.[a-z0-9]+$")
DIRS = ("CAD", "STLs", "3MF", "DXF", "images", "docs")
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}
# __init__.py: rules_python creates empty ones in runfiles (legacy_create_init).
IGNORED_NAMES = {".gitkeep", ".DS_Store", "__init__.py"}


def present_files(root: Path) -> list[str]:
    """Files under the mod's export and docs dirs, relative to the mod root."""
    out = []
    for d in DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            rel = f.relative_to(root)
            if (f.is_dir() or f.name in IGNORED_NAMES or f.suffix == ".pyc"
                    or IGNORED_PARTS.intersection(rel.parts)):
                continue
            out.append(rel.as_posix())
    return out


def check(path: Path) -> list[str]:
    errs: list[str] = []
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        return [f"{path}: not a mapping"]
    root = path.parent
    prints = "fdm" in [str(p).lower() for p in (data.get("process") or [])]
    for key in REQUIRED:
        if key in EMPTY_OK_WITHOUT_FDM and data.get(key) == [] and not prints:
            continue
        if key not in data or data[key] in (None, "", []):
            errs.append(f"{path}: missing {key}" + (" (an fdm mod names at least one printer)"
                                                     if key == "printers" and prints else ""))
    if data.get("slug") and data["slug"] != root.name:
        errs.append(f"{path}: slug {data['slug']!r} != directory {root.name!r}")
    if data.get("creator") and data["creator"] != root.parent.name:
        errs.append(f"{path}: creator {data['creator']!r} != directory {root.parent.name!r}")
    for key in LISTS:
        for rel in data.get(key) or []:
            f = root / rel
            if not f.is_file():
                errs.append(f"{path}: {key} entry not found: {rel}")
            if key != "docs" and not NAME_RE.match(Path(rel).name):
                errs.append(f"{path}: {key} name not snake_case: {rel}")
    listed = {str(rel) for key in LISTS for rel in (data.get(key) or [])}
    for rel in present_files(root):
        if rel not in listed:
            errs.append(f"{path}: file present but not listed in mod.dhall: {rel}")
    return errs


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    errs = [e for a in argv for e in check(Path(a))]
    for e in errs:
        print(f"error  {e}")
    print(f"metadata-check: {len(argv)} file(s), {len(errs)} error(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
