"""Flatten OrcaSlicer profiles through their `inherits` chain (stdlib only).

A printer profile under third_party/slicer_profiles/<printer>/ (printer.json,
process.json, filament.json) usually inherits vendor presets. The OrcaSlicer
CLI resolves `inherits` only against <datadir>/system, and OrcaSlicer
2.5.0-alpha ships its vendor presets packed (Resources/profiles/<vendor>.opc),
so handing it such JSON as-is fails with "Preset was not found in the loaded
bundle". Older apps with unpacked Resources/profiles/<vendor>/ silently fall
back to defaults instead. Either way the profiles must be flattened before
slicing.

Bundle resolves each chain against the app's unpacked vendor JSON when it is
there, else against the OrcaSlicer repo at ORCA_PROFILE_TAG (default
v2.5.0-alpha), fetched once into $ORCA_PROFILE_CACHE (default
~/.cache/orca_profiles/<tag>/) and hashed so a report can record exactly which
vendor files it used. The vendor directory is $ORCA_VENDOR when set, else the
first word of the machine's printer_model (OrcaSlicer names vendor directories
by brand).

Used by slice_check_test.py (slice_check macro).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

APP_PATHS = ("/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",)
ORCA_TAG = os.environ.get("ORCA_PROFILE_TAG", "v2.5.0-alpha")
RAW = "https://raw.githubusercontent.com/OrcaSlicer/OrcaSlicer/{tag}/resources/profiles/{path}"


class ProfileUnavailable(RuntimeError):
    """A vendor preset could not be read locally or fetched (offline, sandbox)."""


def find_orca() -> str | None:
    """$ORCA_SLICER, else orca-slicer / OrcaSlicer on PATH, else a macOS app bundle."""
    env = os.environ.get("ORCA_SLICER")
    if env and (shutil.which(env) or os.path.isfile(env)):
        return shutil.which(env) or env
    for name in ("orca-slicer", "OrcaSlicer"):
        if shutil.which(name):
            return shutil.which(name)
    return next((p for p in APP_PATHS if os.path.isfile(p)), None)


def cache_dir() -> Path:
    return Path(os.environ.get("ORCA_PROFILE_CACHE") or Path.home() / ".cache" / "orca_profiles")


class Bundle:
    """Vendor presets by (kind, name), for resolving `inherits` chains."""

    def __init__(self, orca: str | None, vendors: list[str], tag: str = ORCA_TAG):
        self.tag = tag
        self.local = Path(orca).resolve().parents[1] / "Resources" / "profiles" if orca else None
        self.vendors = list(dict.fromkeys(vendors + ["OrcaFilamentLibrary"]))
        self.index: dict[tuple[str, str], tuple[str, str]] = {}
        self.fetched: dict[str, str] = {}  # relative path -> sha256
        for vendor in self.vendors:
            idx = json.loads(self._read(f"{vendor}.json"))
            for kind, key in (("machine", "machine_list"), ("process", "process_list"), ("filament", "filament_list")):
                for item in idx.get(key, []):
                    # Earlier vendors win (same-named fdm_* files exist in many vendors).
                    self.index.setdefault((kind, item["name"]), (vendor, item["sub_path"]))

    def _read(self, rel: str) -> str:
        if self.local is not None and (self.local / rel).is_file():
            raw = (self.local / rel).read_bytes()
        else:
            raw = self._cached(rel)
        self.fetched[rel] = hashlib.sha256(raw).hexdigest()
        return raw.decode("utf-8")

    def _cached(self, rel: str) -> bytes:
        for base in (cache_dir(), Path(tempfile.gettempdir()) / "orca_profiles"):
            hit = base / self.tag / rel
            if hit.is_file():
                return hit.read_bytes()
        import urllib.error
        import urllib.parse
        import urllib.request

        url = RAW.format(tag=self.tag, path=urllib.parse.quote(rel))
        try:
            with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 (pinned https URL)
                data = r.read()
        except (urllib.error.URLError, OSError) as e:
            raise ProfileUnavailable(f"cannot fetch {url}: {e}") from e
        # The Bazel sandbox may refuse writes under $HOME; fall back to TMPDIR.
        for base in (cache_dir(), Path(tempfile.gettempdir()) / "orca_profiles"):
            try:
                dst = base / self.tag / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
                break
            except OSError:
                continue
        return data

    def _load(self, kind: str, name: str) -> dict:
        hit = self.index.get((kind, name))
        if hit is None:
            raise ProfileUnavailable(f"{kind} preset '{name}' not in vendors {self.vendors} at {self.tag}")
        vendor, sub = hit
        return json.loads(self._read(f"{vendor}/{sub}"))

    def resolve(self, kind: str, data: dict) -> dict:
        """Merge the inherits chain (parent first) under `data`."""
        chain = [data]
        seen: set[str] = set()
        while chain[-1].get("inherits"):
            parent = chain[-1]["inherits"]
            if parent in seen:
                raise ProfileUnavailable(f"inherits loop at {parent}")
            seen.add(parent)
            chain.append(self._load(kind, parent))
        out: dict = {}
        for layer in reversed(chain):
            out.update(layer)
        out.pop("inherits", None)
        out["from"] = "User"  # a flattened preset is not in any loaded system bundle
        return out

    def preset(self, kind: str, name: str) -> dict:
        return self.resolve(kind, self._load(kind, name))


def cli_machine(machine: dict) -> dict:
    """Mark a flattened machine "from": "system" for the CLI's compatibility check.

    OrcaSlicer 2.3.x and 2.4.x accept a --load-settings process only when its
    compatible_printers holds the machine's system name: the machine's own name
    when "from" is "system", else its "inherits" value (src/OrcaSlicer.cpp at
    v2.4.2, new_printer_system_name). A flattened machine has no inherits, so
    with "from": "User" that name is empty and every slice exits -17 (rc 239,
    CLI_PROCESS_NOT_COMPATIBLE). OrcaSlicer 2.5.0-alpha checks compatibility
    through is_compatible_with_printer and slices either way. The CLI resolves
    only `inherits`, never `from`, so the flag has no other effect on a preset
    without inherits.
    """
    machine["from"] = "system"
    return machine


def vendor_for(machine: dict) -> str:
    """$ORCA_VENDOR, else the first word of printer_model (or name), else "Custom"."""
    if os.environ.get("ORCA_VENDOR"):
        return os.environ["ORCA_VENDOR"]
    model = (machine.get("printer_model", "") or machine.get("name", "")).split()
    return model[0] if model else "Custom"


def flatten_dir(prof: Path, orca: str | None, out: Path, overrides: dict | None = None) -> dict:
    """Flatten printer.json, process.json[, filament.json] from a profile dir into `out`
    (a pre-flattened dir with machine.json is copied as is: copy_flat).

    Returns {"machine": path, "process": path, "filaments": [paths], "vendor_sha256": {...}}.
    Raises ProfileUnavailable when a vendor preset cannot be read or fetched.
    """
    if not (prof / "printer.json").is_file() and (prof / "machine.json").is_file():
        return copy_flat(prof, out, overrides)
    machine_raw = json.loads((prof / "printer.json").read_text())
    bundle = Bundle(orca, [vendor_for(machine_raw)])
    machine = cli_machine(bundle.resolve("machine", machine_raw))
    process = bundle.resolve("process", json.loads((prof / "process.json").read_text()))
    process.update(overrides or {})
    # Orca's CLI rejects a process or filament whose compatible list misses the machine.
    process["compatible_printers"] = [machine["name"]]
    process["compatible_printers_condition"] = ""
    out.mkdir(parents=True, exist_ok=True)
    filaments = []
    if (prof / "filament.json").is_file():
        fil = bundle.resolve("filament", json.loads((prof / "filament.json").read_text()))
        fil["compatible_printers"] = [machine["name"]]
        fil["compatible_printers_condition"] = ""
        fp = out / "filament.json"
        fp.write_text(json.dumps(fil, indent=1))
        filaments.append(fp)
    mp, pp = out / "machine.json", out / "process.json"
    mp.write_text(json.dumps(machine, indent=1))
    pp.write_text(json.dumps(process, indent=1))
    return {"machine": mp, "process": pp, "filaments": filaments,
            "vendor_sha256": dict(sorted(bundle.fetched.items())), "tag": bundle.tag}


def copy_flat(prof: Path, out: Path, overrides: dict | None = None) -> dict:
    """A pre-flattened profile dir: machine.json, process.json[, filament.json]
    already resolved against a pinned vendor bundle, so no vendor preset is read
    or fetched. Only the compatibility lists and the machine's "from"
    (cli_machine) are rewritten for the CLI. Same return shape as flatten_dir,
    with an empty vendor_sha256 and tag "pre-flattened"."""
    machine = cli_machine(json.loads((prof / "machine.json").read_text()))
    process = json.loads((prof / "process.json").read_text())
    process.update(overrides or {})
    out.mkdir(parents=True, exist_ok=True)
    process["compatible_printers"] = [machine["name"]]
    process["compatible_printers_condition"] = ""
    filaments = []
    if (prof / "filament.json").is_file():
        fil = json.loads((prof / "filament.json").read_text())
        fil["compatible_printers"] = [machine["name"]]
        fil["compatible_printers_condition"] = ""
        fp = out / "filament.json"
        fp.write_text(json.dumps(fil, indent=1))
        filaments.append(fp)
    mp, pp = out / "machine.json", out / "process.json"
    mp.write_text(json.dumps(machine, indent=1))
    pp.write_text(json.dumps(process, indent=1))
    return {"machine": mp, "process": pp, "filaments": filaments, "vendor_sha256": {}, "tag": "pre-flattened"}
