---
description: Bambu Studio CLI quirks that look like bugs but are deliberate workarounds. Read before changing how the 3MF is written, how the CLI is invoked, or how its result is patched.
paths:
  - "img2bambu/bambu.py"
  - "img2bambu/export3mf.py"
  - "img2bambu/pipeline.py"
---

# Bambu Studio CLI quirks (do not "fix" these away)

- CLI exit code is unreliable (often crashes with 0xC0000005 after success); success is judged by checking output files exist.
- CLI-exported 3MF leaves per-filament config arrays at length 1, which the GUI rejects as "invalid config". `patch_project` expands them to N, sets `filament_colour`, and rebuilds `flush_volumes_matrix` (N×N, zero diagonal) and `flush_volumes_vector` (2N).
- The CLI resolves neither `inherits` nor `include` of a preset: unresolved keys silently become generic slicer defaults. Pass `PresetDB.write_flat` copies, never the system files. `include` is not optional: the A1 start and filament-change gcode live there (precedence: inherited < include < own).
- The CLI caps `machine_max_acceleration_*` from its own `cli_config.json`, and keeps one value per filament of the `filament_dev_*drying*` arrays (AMS drying info). Both are expected differences from the preset.
- The CLI always writes the prime tower at (15, 220), even off the A1 mini bed. The tower grows with the number of colors; `tower.side` is fitted to 2.9.1 slices (re-measure after a Bambu Studio update).
- `--outputdir` must exist before slicing: on failure the CLI does not create it and `result.json` (the reason) is lost.
- Minimal 3MF must NOT include `Application` metadata — CLI crashes if the file claims to be a Bambu project without `project_settings`.
- More than 4 parts triggers a warning (exceeds one AMS).
- Flatpak has a private `/tmp`: work files go to `~/.cache/img2bambu` (`work_dir`) and are removed after export. Do not switch back to plain `tempfile`.
- `sandbox_sees` probes a file, not the folder: `/tmp` also exists inside the sandbox, with other contents.
