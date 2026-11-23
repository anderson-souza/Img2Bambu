# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Img2Bambu: PNG/JPG image → multicolor 3MF project for Bambu Studio. Output = one object with a base part (silhouette, default 10 mm, color = dominant edge color) plus one raised part per remaining color (default 1 mm). Part i is pre-assigned to filament i. Windows-only in practice (Bambu Studio paths, `winreg`, PyInstaller `.exe`). User-facing strings and README are in Portuguese; code and comments in English.

## Coding Behavior Contract (12 Rules)

1. Think before coding. State your assumptions. Surface tradeoffs. Ask before guessing. Push back when a simpler approach exists.
2. Simplicity first. Minimum code that solves the problem. No speculative features. No abstractions for single-use code.
3. Surgical changes. Touch only what is asked. Do not "improve" adjacent code, comments, or formatting. Match existing style.
4. Goal-driven execution. Define success criteria. Loop until verified. Do not narrate steps; tell me what success looks like.
5. Do not make the model do non-language work. Retry policies, routing, escalation thresholds belong in deterministic code.
6. Hard token budgets, no exceptions. Stop and ask if a task is trending past its budget.
7. Surface conflicts, do not average them. If two parts of the codebase disagree, flag the disagreement and ask which to follow.
8. Read before you write. Understand adjacent code (the file and nearby siblings) before adding new code.
9. Tests are required but are not the goal. A passing test that tests nothing useful is a failure. Tests must check behavior.
10. Long-running operations require checkpoints. After every significant step, summarize what was done and confirm before proceeding.
11. Convention beats novelty. In an established codebase, match the existing pattern even if a "better" one exists.
12. Fail visibly, not silently. Surface every skipped record, every rolled-back transaction, every constraint violation. Never report success when something was bypassed.

## Commands

- Install: `pip install -r requirements.txt`
- GUI: `python app.py`
- CLI: `python -m img2bambu image.png --width 150 --colors 3 --check` (`--stl-only` skips Bambu Studio; `--printer/--process/--filament` take Bambu system preset names). Packaged exe: `Img2Bambu.exe --cli image.png ...`, output via `IMG2BAMBU_LOG` env var (windowed build has no stdout).
- Tests: `python -m pytest`; single test: `python -m pytest tests/test_core.py::test_merge_reduces_parts`; skip slow: `python -m pytest -m "not slow"`.
  - `slow` test slices a real image via the Bambu Studio CLI; it is auto-skipped unless Bambu Studio is installed and `../new abelha/Mascote Abelha com Placa ABELHÃO.png` exists (outside the repo).
- Lint: `python -m ruff check .` (config in `pyproject.toml`; `ruff format` is intentionally not used).
- GUI smoke (headless, offscreen Qt): `python tests/gui_smoke.py <image> <outdir> <screenshot.png>`
- Build exe: `python -m PyInstaller --noconfirm img2bambu.spec` → `dist\Img2Bambu\` (ship whole folder). `build/` and `dist/` are artifacts.

## Architecture

Pipeline (`pipeline.export`) — same path for CLI (`__main__.py`) and GUI:

1. `segment.analyze` — load RGBA, compute silhouette (alpha, or flood-fill from corners with `bg_tolerance` when image has no transparency), crop to bbox, k-means in LAB → `Palette` (labels sorted dark→light for determinism), suggest base (most common label on outer ring) and streak-filter colors (light, low-saturation).
2. `segment.build_masks` — at `upsample`× resolution: clean masks (blur, morph open/close by `min_detail_mm`, drop small blobs/holes), apply `Palette.merges` via `resolve`, optional `drop_streaks` (removes glossy-highlight lines thinner than `streak_radius_mm`). Raised masks are disjoint and inside the silhouette (tests enforce this).
3. `geometry.build_parts` — contours → shapely polygons (mm, Y up) → `trimesh` extrusions. Base at z=0..base_mm, colors at base_mm..+relief_mm. Raises if any mesh not watertight.
4. `export3mf` — write per-color STLs always; if Bambu Studio found, write a *minimal* 3MF (one object, components = parts, extruder metadata per part) as CLI input.
5. `bambu.export_project` — run Bambu Studio CLI (`--load-settings machine;process`, `--load-filaments` ×N, `--export-3mf`), then `patch_project` fixes the result. Optional `slice_check` slices the project to verify filament changes.

Key state: `Params` (user dimensions/tuning) and `Palette` (colors, base_index, merges, streak set) in `params.py`. `Palette.active()` = labels not merged away.

`bambu.PresetDB` reads system presets from `%APPDATA%\BambuStudio\system\BBL\{machine,process,filament}\*.json`, resolves `inherits` chains, and filters by `instantiation == "true"` and `compatible_printers`. User presets are not loadable by the CLI, so only system presets are offered.

GUI (`gui/main_window.py`, PySide6): long work runs as `gui/worker.Task` (QRunnable on the global QThreadPool); each task carries a `tag` so stale analysis/preview results are discarded. Settings persisted with `QSettings`.

## Bambu Studio CLI quirks (do not "fix" these away)

- CLI exit code is unreliable (often crashes with 0xC0000005 after success); success is judged by checking output files exist.
- CLI-exported 3MF leaves per-filament config arrays at length 1, which the GUI rejects as "invalid config". `patch_project` expands them to N, sets `filament_colour`, and rebuilds `flush_volumes_matrix` (N×N, zero diagonal) and `flush_volumes_vector` (2N).
- Minimal 3MF must NOT include `Application` metadata — CLI crashes if the file claims to be a Bambu project without `project_settings`.
- More than 4 parts triggers a warning (exceeds one AMS).

## Conventions

- Comments are sparse and prefixed `why:`, `hazard:` or `invariant:` — no narration comments.
- Error/progress messages shown to users are Portuguese.
