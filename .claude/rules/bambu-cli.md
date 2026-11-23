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
- Minimal 3MF must NOT include `Application` metadata — CLI crashes if the file claims to be a Bambu project without `project_settings`.
- More than 4 parts triggers a warning (exceeds one AMS).
