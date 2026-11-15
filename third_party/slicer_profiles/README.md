# Slicer profiles

The `slice_check` Bazel macro slices a model with the OrcaSlicer CLI and checks grams, hours and tool changes against a budget. It reads one directory per printer:

```
third_party/slicer_profiles/<printer>/printer.json
third_party/slicer_profiles/<printer>/process.json
third_party/slicer_profiles/<printer>/filament.json
```

The template ships no profiles. Export your own from OrcaSlicer, or write them by hand, and name the directory after the printer slug in `ssot/constants/printers.dhall`. Profiles that inherit OrcaSlicer vendor presets are flattened before slicing (`tools/bazel/orca_profiles.py`): the presets are read from the installed app or fetched once from the OrcaSlicer repository. A directory holding an already flattened `machine.json` is used as is.

Record where each file came from. OrcaSlicer's own vendor profiles carry its licence, so do not commit a copy of them here without checking it.
