# Preview 3D Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

---

**Spec**: `.specs/features/preview-3d/spec.md`
**Design**: `.specs/features/preview-3d/design.md`
**Status**: Draft

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec — confirm before Execute. Guidelines found: `CLAUDE.md` (rule 9 "tests must check behavior"; commands section), `pyproject.toml` (`testpaths = ["tests"]`, `slow` marker). No coverage threshold, no CI. Existing samples: `tests/test_core.py` (pytest, behavior asserts on real pipeline output, `tmp_path`), `tests/gui_smoke.py` (offscreen script). Strong defaults applied where guidelines are silent.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Pipeline / geometry / preview3d (Qt-free logic) | unit | All branches; 1:1 to spec ACs; every listed edge case (empty model, all merged, missing bed fields, boundary fit) | `tests/test_preview3d.py` | `python -m pytest tests/test_preview3d.py` |
| `bambu.PresetDB` (preset parsing) | unit | Key parse paths + every missing/invalid field branch; existing `bed_center` behavior preserved | `tests/test_preview3d.py` | `python -m pytest tests/test_preview3d.py` |
| GUI widget `View3D` | integration (offscreen `QApplication`, scene state — not pixels, see AD-001) | Every public method: happy + empty + error states; spec strings exact | `tests/test_view3d.py` | `python -m pytest tests/test_view3d.py` |
| GUI `MainWindow` wiring | integration (offscreen, `preview3d.build` monkeypatched to count calls) | Every trigger path (tab hidden/visible/switch, stale tag, failure, new image, machine change) + 2D preview regression | `tests/test_gui_preview3d.py` | `python -m pytest tests/test_gui_preview3d.py` |
| Camera feel, pixels, packaged exe | manual UAT (real window) | Orbit/zoom/pan, model visible on bed, exe 3D tab works | — | `python app.py`; `dist\Img2Bambu\Img2Bambu.exe` |
| PyInstaller spec / QML datas | none | build gate only | — | build gate |

Shared offscreen fixture: `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` (setdefault) and provides a session `qapp` fixture.

## Gate Check Commands

> Generated from codebase — confirm before Execute.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tasks with unit tests only (T1–T4) | `python -m pytest -m "not slow"` |
| Full | Tasks touching GUI (T5–T9) | `python -m pytest -m "not slow"` + `python tests/gui_smoke.py <image> <outdir> <shot.png>` (exit 0) |
| Build | T10 / end of feature | Full gate + `python -m PyInstaller --noconfirm img2bambu.spec` succeeds + `dist\Img2Bambu` contains `view3d.qml` |

Baseline before T1: `8 passed, 1 deselected` (`python -m pytest -m "not slow"`, 2026-10-22). Test count must never drop below the previous task's count.

---

## Execution Plan

### Phase 1: Foundation (Qt-free)

```
T1 → T2 → T3 → T4
```

### Phase 2: View widget

```
T5 → T6 → T7
```

### Phase 3: Integration & packaging

```
T8 → T9 → T10
```

---

## Task Breakdown

### T1: `pipeline.model`

**What**: Add `model(an, palette, params) -> list[Part]` = `segment.build_masks` + `geometry.build_parts`; `export` untouched.
**Where**: `img2bambu/pipeline.py`; tests in `tests/test_preview3d.py` (new)
**Depends on**: None
**Reuses**: `segment.build_masks`, `geometry.build_parts`, `tests/test_core.py::synthetic`
**Requirement**: PREV3D-01

**Tools**: MCP: NONE · Skill: NONE

**Done when**:

- [ ] For `synthetic()` with default `Params`, `model()` returns same count, names, colors and `mesh.bounds` (allclose) as `geometry.build_parts(*segment.build_masks(...))`
- [ ] Base Z bounds == `[0, base_mm]`; each color part Z bounds == `[base_mm, base_mm + relief_mm]` (non-default base/relief values, e.g. 3.0 / 2.0)
- [ ] All colors merged into base → 1 part
- [ ] Empty silhouette → `ValueError` propagates (same message as `build_parts`)
- [ ] Gate quick passes; ≥ 12 passed (8 + ≥ 4 new)

**Tests**: unit · **Gate**: quick
**Commit**: `feat(pipeline): add model() returning export-identical parts`

---

### T2: `PresetDB.bed`

**What**: Add `bed(machine) -> (x0, y0, x1, y1, height|None) | None`; reimplement `bed_center` on it with same `(128.0, 128.0)` fallback.
**Where**: `img2bambu/bambu.py`; tests in `tests/test_preview3d.py`
**Depends on**: T1
**Reuses**: existing `"XxY"` parsing in `bed_center`, `PresetDB(root=...)`
**Requirement**: PREV3D-07

**Tools**: MCP: NONE · Skill: NONE

**Done when**:

- [ ] Fake preset tree under `tmp_path` (machine JSON with `printable_area` `["0x0","256x0","256x256","0x256"]`, `printable_height` `"256"`) → `(0, 0, 256, 256, 256.0)`
- [ ] Missing `printable_height` → height `None`; missing/empty/unparseable `printable_area` → `None`
- [ ] `bed_center` returns `(128.0, 128.0)` for the 256 bed, centre of a non-origin area (e.g. `10x20..210x220` → `(110, 120)`), and fallback `(128.0, 128.0)` when `bed()` is `None`
- [ ] Gate quick passes; ≥ 16 passed

**Tests**: unit · **Gate**: quick
**Commit**: `feat(bambu): expose printable bed area and height`

---

### T3: `preview3d.MeshData` / `mesh_data` / `build`

**What**: New Qt-free module with `MeshData` dataclass, `mesh_data(part)` (flat-shaded interleaved float32 pos+normal) and `build(an, palette, params)` (worker entry, uses `pipeline.model`).
**Where**: `img2bambu/preview3d.py` (new); tests in `tests/test_preview3d.py`
**Depends on**: T1
**Reuses**: `pipeline.model`, `Part`
**Requirement**: PREV3D-01

**Tools**: MCP: NONE · Skill: NONE

**Done when**:

- [ ] `len(vertices) == faces * 3 * 24` per part
- [ ] Decoding `vertices` as float32 `(-1, 6)`: positions == `mesh.triangles` flattened; normals == `face_normals` repeated ×3
- [ ] `lo`/`hi` == `mesh.bounds`; `name`/`color` == `Part.name`/`Part.color`
- [ ] `build()` output order/count == `pipeline.model()` output
- [ ] Gate quick passes; ≥ 20 passed

**Tests**: unit · **Gate**: quick
**Commit**: `feat(preview3d): convert parts to render-ready mesh data`

---

### T4: `preview3d.size` / `fits` / `describe`

**What**: Pure helpers: combined bbox extents, fit check vs bed, and the info-line text shown in the tab.
**Where**: `img2bambu/preview3d.py`; tests in `tests/test_preview3d.py`
**Depends on**: T2, T3
**Reuses**: `MeshData.lo/hi`, `PresetDB.bed` tuple shape
**Requirement**: PREV3D-06, PREV3D-07

**Tools**: MCP: NONE · Skill: NONE

**Done when**:

- [ ] `size` of synthetic model at width 150, base 10, relief 1 → X ≈ 150.0 (± `simplify_mm`), Z == 11.0
- [ ] `fits`: equal to bed dims → True; 0.1 mm over in X, Y or Z → False each; height `None` ignores Z
- [ ] `describe(meshes, bed)` exact strings: `"150.0 × 120.3 × 11.0 mm — 3 partes"` format (1 decimal); + `"⚠ Modelo maior que a mesa (256 × 256 × 256 mm)."` when not fitting; `"(256 × 256 mm)"` form when height `None`; `"Mesa indisponível"` when bed `None`
- [ ] Gate quick passes; ≥ 26 passed

**Tests**: unit · **Gate**: quick
**Commit**: `feat(preview3d): model size, bed fit check and info text`

---

### T5: `View3D` widget + QML (models, messages)

**What**: `view3d.qml` (View3D, −90° X container node, `Repeater3D` + `PrincipledMaterial`, lights, `OrbitCameraController`) and `View3D(QWidget)` with `MeshGeometry`, `set_parts`, `show_message`, `part_count`, `info_text`, `ok`; `tests/conftest.py` with offscreen `qapp`.
**Where**: `img2bambu/gui/view3d.py`, `img2bambu/gui/view3d.qml` (new); `tests/conftest.py`, `tests/test_view3d.py` (new)
**Depends on**: T4
**Reuses**: spike `scratchpad/spike/q3d_quick.py`; `preview3d.describe`
**Requirement**: PREV3D-01, PREV3D-05, PREV3D-06

**Tools**: MCP: `context7` (Qt for Python `/websites/doc_qt_io_qtforpython-6`) · Skill: NONE

**Done when**:

- [ ] `ok` True offscreen; `set_parts(build(...), reframe=True)` → `part_count() == len(meshes)` and `info_text()` == `describe(meshes, None)`
- [ ] Second `set_parts` with fewer meshes replaces (count drops), no leftovers
- [ ] `show_message("x")` → `part_count() == 0`, `info_text() == "x"`
- [ ] Fresh widget shows `"Abra uma imagem para ver o modelo 3D."`
- [ ] Broken QML path (monkeypatched) → `ok` False and message starts `"Visualização 3D indisponível"`; no exception
- [ ] `QQuickWidget.sceneGraphError` existence checked; connected if present, otherwise gap recorded in design Risks
- [ ] Gate full passes; ≥ 31 passed

**Tests**: integration · **Gate**: full
**Commit**: `feat(gui): add Qt Quick 3D view widget`

---

### T6: `View3D.set_bed`

**What**: Bed plane (`#Rectangle` scaled to bed, z −0.01), model centred on bed centre, fit warning via `describe`; no remesh.
**Where**: `img2bambu/gui/view3d.py`, `img2bambu/gui/view3d.qml`; tests in `tests/test_view3d.py`
**Depends on**: T5
**Reuses**: `PresetDB.bed` tuple, `preview3d.fits/describe`
**Requirement**: PREV3D-07

**Tools**: MCP: `context7` · Skill: NONE

**Done when**:

- [ ] `set_bed((0,0,256,256,256))` → QML bed visible with scale matching 256×256; model offset puts bbox centre at (128, 128)
- [ ] `set_bed(None)` → bed hidden, `info_text()` contains `"Mesa indisponível"`, `part_count()` unchanged
- [ ] Model larger than bed → warning text; changing bed to large one clears warning without calling `set_parts`
- [ ] Gate full passes; ≥ 34 passed

**Tests**: integration · **Gate**: full
**Commit**: `feat(gui): draw printer bed and size warning in 3D view`

---

### T7: Camera reframe + middle/right-button pan

**What**: Reframe (orbit origin = model centre, distance from max dimension) only when `reframe=True`; extra `DragHandler` (`Qt.MiddleButton | Qt.RightButton`) translating orbit origin along its right/up vectors.
**Where**: `img2bambu/gui/view3d.qml`, `img2bambu/gui/view3d.py`; tests in `tests/test_view3d.py`
**Depends on**: T6
**Reuses**: `OrbitCameraController` (stock orbit/zoom)
**Requirement**: PREV3D-04

**Tools**: MCP: `context7` · Skill: NONE

**Done when**:

- [ ] After `set_parts(..., reframe=True)` camera/origin properties frame model (origin == model centre); moving camera then `set_parts(..., reframe=False)` leaves camera/origin unchanged
- [ ] Larger model → larger camera distance on reframe
- [ ] Pan handler present with middle/right buttons (QML object inspected); feel verified in manual UAT
- [ ] Gate full passes; ≥ 37 passed

**Tests**: integration · **Gate**: full
**Commit**: `feat(gui): camera reframing and mouse pan in 3D view`

---

### T8: MainWindow "3D" tab + model task wiring

**What**: Add tab; `req3d`, `dirty3d`; `run_model`/`model_done`/`model_failed`; hook at end of `run_preview`; `tabs.currentChanged` trigger.
**Where**: `img2bambu/gui/main_window.py`; tests in `tests/test_gui_preview3d.py` (new)
**Depends on**: T7
**Reuses**: `Task`, `run_preview`/`preview_done` pattern, debounce
**Requirement**: PREV3D-02, PREV3D-03, PREV3D-05

**Tools**: MCP: NONE · Skill: NONE

**Done when**:

- [ ] 3D tab not current + param change → `preview3d.build` call count 0, `dirty3d` True
- [ ] Switching to 3D tab → exactly 1 call; switching away/back with no change → still 1
- [ ] 3D tab current + param change → 1 new call after debounce; result shown (`part_count`)
- [ ] `model_done` with stale tag ignored (view unchanged)
- [ ] 2D preview still updates with 3D tab current (`"Prévia pronta"` status reached, `preview_done` applied)
- [ ] `build` raising → `info_text()` == error msg, log contains `"Erro:"`, generate button still enabled
- [ ] Gate full passes (incl. `gui_smoke.py` exit 0); ≥ 43 passed

**Tests**: integration · **Gate**: full
**Commit**: `feat(gui): wire 3D preview tab to model task`

---

### T9: MainWindow reframe on new image + bed on machine change

**What**: `reframe3d` set in `open_image` path and consumed in `model_done`; `machine_changed` calls `view3d.set_bed(db.bed(machine))`.
**Where**: `img2bambu/gui/main_window.py`; tests in `tests/test_gui_preview3d.py`
**Depends on**: T8
**Reuses**: `machine_changed`, `PresetDB.bed`
**Requirement**: PREV3D-04, PREV3D-07

**Tools**: MCP: NONE · Skill: NONE

**Done when**:

- [ ] First `model_done` after new image → `set_parts(reframe=True)`; later ones `reframe=False` (spy on `View3D.set_parts`)
- [ ] Machine change → `set_bed` called with `db.bed(new machine)` and `build` call count unchanged
- [ ] `db` not ok → `set_bed(None)` → `"Mesa indisponível"`
- [ ] Gate full passes; ≥ 46 passed

**Tests**: integration · **Gate**: full
**Commit**: `feat(gui): reframe 3D view on new image and track printer bed`

---

### T10: Packaging + smoke update

**What**: Add `img2bambu/gui/view3d.qml` to `datas` in `img2bambu.spec`; `gui_smoke.py` visits 3D tab and prints `part_count`/`info_text` before generating.
**Where**: `img2bambu.spec`, `tests/gui_smoke.py`
**Depends on**: T9
**Reuses**: existing spec `datas`, smoke step machine
**Requirement**: PREV3D-01 (packaged), PREV3D-05

**Tools**: MCP: NONE · Skill: NONE

**Done when**:

- [ ] `python -m PyInstaller --noconfirm img2bambu.spec` succeeds; `dist\Img2Bambu` contains `view3d.qml` and Qt Quick 3D plugins
- [ ] `gui_smoke.py` exit 0 and prints `part_count > 0`
- [ ] Bundle size delta recorded (before/after `dist\Img2Bambu` size)
- [ ] Manual UAT: exe opens, 3D tab shows model on bed, orbit/zoom/pan work (user confirms)
- [ ] Gate build passes; test count unchanged from T9

**Tests**: none · **Gate**: build
**Commit**: `build: ship 3D view QML in exe and smoke-test 3D tab`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 ──→ T2 ──→ T3 ──→ T4
Phase 2:  T5 ──→ T6 ──→ T7
Phase 3:  T8 ──→ T9 ──→ T10
```

Dependency notes: T3 needs T1 only and T4 needs T2+T3; with sequential execution the chain above satisfies both.

Batching (Execute): 10 tasks → Batch A = Phase 1 + Phase 2 (7 tasks), Batch B = Phase 3 (3 tasks). > 8 tasks → sub-agent offer at Execute.

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1 | 1 function | ✅ |
| T2 | 1 method (+ refactor of sibling to use it) | ✅ |
| T3 | 1 dataclass + 2 functions, same module, one concept | ⚠️ OK (cohesive) |
| T4 | 3 pure helpers, same module | ⚠️ OK (cohesive) |
| T5 | 1 widget + its QML + test fixture | ⚠️ OK (widget unusable without QML) |
| T6 | 1 method + QML node | ✅ |
| T7 | camera behavior (QML + 1 flag) | ✅ |
| T8 | 1 wiring concern in MainWindow | ✅ |
| T9 | 2 small hooks in MainWindow | ⚠️ OK (cohesive) |
| T10 | config + smoke script | ⚠️ OK (both packaging/verification) |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T1 | T2 → T3 (T1 earlier in chain) | ✅ |
| T4 | T2, T3 | T3 → T4 (T2 earlier) | ✅ |
| T5 | T4 | Phase 1 → T5 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | T7 | Phase 2 → T8 | ✅ |
| T9 | T8 | T8 → T9 | ✅ |
| T10 | T9 | T9 → T10 | ✅ |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | Pipeline | unit | unit | ✅ |
| T2 | PresetDB | unit | unit | ✅ |
| T3 | preview3d | unit | unit | ✅ |
| T4 | preview3d | unit | unit | ✅ |
| T5 | View3D | integration | integration | ✅ |
| T6 | View3D | integration | integration | ✅ |
| T7 | View3D (+ manual UAT for feel) | integration | integration | ✅ |
| T8 | MainWindow | integration | integration | ✅ |
| T9 | MainWindow | integration | integration | ✅ |
| T10 | PyInstaller spec / smoke script | none | none | ✅ |
