# Project File Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, the walk, check_proofs, the Verifier and the screens sub-agent).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/project-file/design.md`
**Status**: In Progress
**Approved**: 2026-11-23 - user: "aprovado, pode implementar"
**Build**: `python -m ruff check .; timeout 900 python -m pytest -m "not slow"`
**Run project**: `timeout 600 python -m pytest -v tests/test_project.py tests/test_gui_project.py`

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: `CLAUDE.md`, `pyproject.toml`, `.github/workflows` - no coverage threshold; strong defaults applied.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Qt-free module (`img2bambu/*.py`) | unit | all branches, 1:1 to criteria, every validation rule | `tests/test_project.py` | `python -m pytest tests/test_project.py` |
| Window (`img2bambu/gui/*.py`) | integration | every criterion: happy, error, cancel; offscreen Qt | `tests/test_gui_project.py` | `timeout 600 python -m pytest tests/test_gui_project.py` |
| Docs | none | build gate only | `README.md` | build gate only |

GUI tests: `w.settings` is a temporary ini; dialogs are stubbed; each test ends with `settle`; images load through `open_image` from a real PNG.

## Gate Check Commands

> Generated from codebase - confirm before Execute.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | T1-T3 | `python -m ruff check . && python -m pytest tests/test_project.py tests/test_core.py` |
| Full | T4-T7 | `python -m ruff check . && timeout 900 python -m pytest -m "not slow"` |
| Build | T8 | `python -m ruff check . && timeout 900 python -m pytest -m "not slow"` |

---

## Execution Plan

### Phase 1: File format

```
T1 → T2 → T3
```

### Phase 2: Window

```
T3 → T4 → T5 → T6 → T7
```

### Phase 3: Docs

```
T7 → T8
```

8 tasks fit one batch: executed inline, no batch workers.

---

## Task Breakdown

### T1: Project file writer

**What**: Project file writer
**Where**: `img2bambu/project.py`
**Depends on**: None
**Reuses**: `params.py`, `segment.Analysis`
**Requirement**: PROJ-03

**Done when**:

- [x] `Project`, `settings` and `save` write the members of design.md
- [x] C38 passes
- [x] Quick gate passes; no existing test deleted or weakened

**Tests**: unit
**Gate**: quick

**Commit**: `feat(project-file): write project files`

---

### T2: Project file reader rebuilding image, palette and `Analysis`

**What**: Project file reader rebuilding image, palette and `Analysis`
**Where**: `img2bambu/project.py` (modify)
**Depends on**: T1
**Reuses**: `segment.load_image`
**Requirement**: PROJ-01

**Done when**:

- [x] `load` round-trips every value, without detection
- [x] C4, C6 pass
- [x] Quick gate passes; no existing test deleted or weakened

**Tests**: unit
**Gate**: quick

**Commit**: `feat(project-file): read project files`

---

### T3: Validation of untrusted project files

**What**: Validation of untrusted project files
**Where**: `img2bambu/project.py` (modify)
**Depends on**: T2
**Reuses**: limits passed by the caller
**Requirement**: PROJ-03

**Done when**:

- [x] every rule under **Validation** in design.md is enforced
- [x] C35, C36, C41 pass
- [x] Quick gate passes; no existing test deleted or weakened

**Tests**: unit
**Gate**: quick

**Commit**: `feat(project-file): refuse invalid project files`

---

### T4: Menu Arquivo and saving from the window

**What**: Menu Arquivo and saving from the window
**Where**: `img2bambu/gui/main_window.py` (modify)
**Depends on**: T3
**Reuses**: `settings` fallback for the dialog folder
**Requirement**: PROJ-01

**Done when**:

- [x] `open_image` keeps the loaded bytes
- [x] C8-C12, C17-C21, C23, C39, C55 pass
- [x] Full gate passes; no existing test deleted or weakened

**Tests**: integration
**Gate**: full

**Commit**: `feat(project-file): save projects from the window`

---

### T5: Opening a project into the window

**What**: Opening a project into the window
**Where**: `img2bambu/gui/main_window.py` (modify)
**Depends on**: T4
**Reuses**: restore sequence of `undo`
**Requirement**: PROJ-01

**Done when**:

- [x] controls are filled with signals blocked
- [x] C1-C3, C5, C7, C13-C16, C22, C32-C34, C37, C40, C54, C56 pass
- [x] Full gate passes; no existing test deleted or weakened

**Tests**: integration
**Gate**: full

**Commit**: `feat(project-file): open projects in the window`

---

### T6: Presets missing on this computer

**What**: Presets missing on this computer
**Where**: `img2bambu/gui/main_window.py` (modify)
**Depends on**: T5
**Reuses**: `machine_changed`, `PresetDB.defaults`
**Requirement**: PROJ-02

**Done when**:

- [x] C24-C31 pass
- [x] Full gate passes; no existing test deleted or weakened

**Tests**: integration
**Gate**: full

**Commit**: `feat(project-file): substitute missing presets`

---

### T7: Unsaved mark and guards

**What**: Unsaved mark and guards
**Where**: `img2bambu/gui/main_window.py` (modify)
**Depends on**: T6
**Reuses**: `project.settings`
**Requirement**: PROJ-04

**Done when**:

- [x] C42-C53 pass
- [x] Full gate passes; no existing test deleted or weakened

**Tests**: integration
**Gate**: full

**Commit**: `feat(project-file): guard unsaved changes`

---

### T8: README section on projects

**What**: README section on projects
**Where**: `README.md` (modify)
**Depends on**: T7
**Reuses**: none
**Requirement**: PROJ-01

**Done when**:

- [x] README explains saving, opening and sharing, and that image metadata travels in the file
- [x] Build gate passes
- [x] Build gate passes; no existing test deleted or weakened

**Tests**: none
**Gate**: build

**Commit**: `docs(project-file): explain project files`

---

## Checks

**C1** - Menu "Arquivo" holds the three actions with Ctrl+O, Ctrl+S, Ctrl+Shift+S (PROJ-01, AC 1)
Proof: run project | tests/test_gui_project.py::test_menu_and_shortcuts PASSED

**C2** - All 16 listed controls, each set away from its default, come back in a new window (PROJ-01, AC 2)
Proof: run project | tests/test_gui_project.py::test_reopen_restores_every_control PASSED

**C3** - Sample, filament, base, streak, outline, merge and edited come back for each row (PROJ-01, AC 3)
Proof: run project | tests/test_gui_project.py::test_reopen_restores_every_row PASSED

**C4** - `build_masks` gives equal arrays before saving and after loading (PROJ-01, AC 4)
Proof: run project | tests/test_project.py::test_masks_equal_after_round_trip PASSED

**C5** - With Suavização 5, opening calls neither `segment.analyze`, `kmeans_palette` nor `smoothed` (PROJ-01, AC 5)
Proof: run project | tests/test_gui_project.py::test_open_runs_no_detection PASSED

**C6** - A sample edit after loading gives the masks of the same edit in the saving session, Suavização 0 and 5 (PROJ-01, AC 6)
Proof: run project | tests/test_project.py::test_later_sample_edit_gives_same_masks PASSED

**C7** - Changing Nº de cores after opening gives the palette the saving session gets (PROJ-01, AC 7)
Proof: run project | tests/test_gui_project.py::test_later_redetection_carries_edited_rows PASSED

**C8** - Ctrl+S with a file associated rewrites it and opens no dialog (PROJ-01, AC 8)
Proof: run project | tests/test_gui_project.py::test_save_overwrites_without_asking PASSED

**C9** - The first save proposes `<image folder>/<image name>.i2b` (PROJ-01, AC 9)
Proof: run project | tests/test_gui_project.py::test_first_save_suggests_image_name PASSED

**C10** - After Salvar como, Ctrl+S writes the new file and leaves the first untouched (PROJ-01, AC 10)
Proof: run project | tests/test_gui_project.py::test_save_as_changes_the_file PASSED

**C11** - Choosing `x` writes `x.i2b` (PROJ-01, AC 11)
Proof: run project | tests/test_gui_project.py::test_suffix_is_appended PASSED

**C12** - Choosing `x` with `x.i2b` present asks; "Não" leaves its bytes unchanged (PROJ-01, AC 12)
Proof: run project | tests/test_gui_project.py::test_appended_name_asks_before_overwriting PASSED

**C13** - Pasta de saída is `<project folder>/img2bambu_saida` (PROJ-01, AC 13)
Proof: run project | tests/test_gui_project.py::test_output_folder_beside_project PASSED

**C14** - Ctrl+Z after opening shows "Nada para desfazer." and changes no control (PROJ-01, AC 14)
Proof: run project | tests/test_gui_project.py::test_open_clears_undo PASSED

**C15** - A detection, preview and 3D result delivered late leaves the opened project unchanged (PROJ-01, AC 15)
Proof: run project | tests/test_gui_project.py::test_open_discards_running_tasks PASSED

**C16** - Original, Cores (prévia), 3D part count and image name are those of the project (PROJ-01, AC 16)
Proof: run project | tests/test_gui_project.py::test_open_shows_project_image PASSED

**C17** - "Abra uma imagem primeiro." and no file (PROJ-01, AC 17)
Proof: run project | tests/test_gui_project.py::test_save_without_image PASSED

**C18** - "Aguarde a detecção de cores terminar para salvar." and no file (PROJ-01, AC 18)
Proof: run project | tests/test_gui_project.py::test_save_while_detecting PASSED

**C19** - "As cores desta imagem não foram detectadas." and no file (PROJ-01, AC 19)
Proof: run project | tests/test_gui_project.py::test_save_after_failed_detection PASSED

**C20** - Status bar shows "Projeto salvo: x.i2b." (PROJ-01, AC 20)
Proof: run project | tests/test_gui_project.py::test_save_reports_file_name PASSED

**C21** - With the image edited on disk, or deleted, after loading, the file holds the loaded bytes (PROJ-02, AC 1)
Proof: run project | tests/test_gui_project.py::test_saves_bytes_as_loaded PASSED

**C22** - With the image deleted, the project opens, saves and opens again (PROJ-02, AC 2)
Proof: run project | tests/test_gui_project.py::test_opens_and_saves_without_original_image PASSED

**C23** - No member contains the image folder, output folder or executable path (PROJ-02, AC 3)
Proof: run project | tests/test_gui_project.py::test_file_holds_no_local_path PASSED

**C24** - A1 0.4 is selected when installed, the first printer when it is not (PROJ-02, AC 4)
Proof: run project | tests/test_gui_project.py::test_missing_printer_uses_default PASSED

**C25** - The selected printer's default process and filament are selected (PROJ-02, AC 5)
Proof: run project | tests/test_gui_project.py::test_missing_process_and_filament_use_printer_defaults PASSED

**C26** - One warning names every missing preset and its substitute (PROJ-02, AC 6)
Proof: run project | tests/test_gui_project.py::test_substitutions_in_one_warning PASSED

**C27** - One log line per substitution (PROJ-02, AC 7)
Proof: run project | tests/test_gui_project.py::test_substitutions_in_log PASSED

**C28** - The file saved after a substitution holds the substitute names (PROJ-02, AC 8)
Proof: run project | tests/test_gui_project.py::test_saving_writes_substitutes PASSED

**C29** - With no presets installed, saving writes the names the file had (PROJ-02, AC 9)
Proof: run project | tests/test_gui_project.py::test_no_presets_keeps_names PASSED

**C30** - With no presets installed, one warning names the presets of the file (PROJ-02, AC 10)
Proof: run project | tests/test_gui_project.py::test_no_presets_warns_once PASSED

**C31** - A project with no printer leaves the selection and shows no warning (PROJ-02, AC 11)
Proof: run project | tests/test_gui_project.py::test_empty_preset_keeps_selection PASSED

**C32** - `QSettings` machine, process, filament, check and exe are unchanged by opening (PROJ-02, AC 12)
Proof: run project | tests/test_gui_project.py::test_open_writes_no_settings PASSED

**C33** - Non-ZIP, truncated file and each missing member show "Não foi possível abrir o projeto:" and a cause (PROJ-03, AC 1)
Proof: run project | tests/test_gui_project.py::test_bad_file_shows_error PASSED

**C34** - format 2 shows "Este projeto foi salvo por uma versão mais nova do Img2Bambu." (PROJ-03, AC 2)
Proof: run project | tests/test_gui_project.py::test_newer_format_is_refused PASSED

**C35** - Each wrong type (bool, NaN, text), out of range value, bad row index, merge cycle raises ValueError; the bounds load (PROJ-03, AC 3)
Proof: run project | tests/test_project.py::test_invalid_values_are_refused PASSED

**C36** - Label and LAB images of other sizes, crop past the image, label above the rows raise ValueError (PROJ-03, AC 4)
Proof: run project | tests/test_project.py::test_mismatched_detection_is_refused PASSED

**C37** - Controls, image, palette, undo steps and associated file are the same after a failed opening (PROJ-03, AC 5)
Proof: run project | tests/test_gui_project.py::test_failed_open_changes_nothing PASSED

**C38** - A write or replace error leaves the old bytes and no temporary file (PROJ-03, AC 6)
Proof: run project | tests/test_project.py::test_failed_save_keeps_old_file PASSED

**C39** - Dialog "Não foi possível salvar o projeto:" with the cause (PROJ-03, AC 7)
Proof: run project | tests/test_gui_project.py::test_failed_save_shows_error PASSED

**C40** - Each removed setting takes its default and its name is logged (PROJ-03, AC 8)
Proof: run project | tests/test_gui_project.py::test_missing_setting_uses_default_and_logs PASSED

**C41** - Loading a file with extra and `..` members creates no file; names are reduced to the last component; no pickle (PROJ-03, AC 9)
Proof: run project | tests/test_project.py::test_load_writes_and_runs_nothing PASSED

**C42** - Title is `x.i2b — Img2Bambu` (PROJ-04, AC 1)
Proof: run project | tests/test_gui_project.py::test_title_shows_project PASSED

**C43** - Changing each saved control and row property makes the title `x.i2b* — Img2Bambu` (PROJ-04, AC 2)
Proof: run project | tests/test_gui_project.py::test_every_saved_value_marks_unsaved PASSED

**C44** - Ctrl+Z back to the saved values removes the `*` (PROJ-04, AC 3)
Proof: run project | tests/test_gui_project.py::test_undo_clears_mark PASSED

**C45** - Without a project the title is the current one and closing a changed window asks nothing (PROJ-04, AC 4)
Proof: run project | tests/test_gui_project.py::test_no_project_never_asks PASSED

**C46** - Closing, opening a project and opening an image each ask Salvar/Descartar/Cancelar when unsaved, not otherwise (PROJ-04, AC 5)
Proof: run project | tests/test_gui_project.py::test_guard_asks_on_close_open_and_image PASSED

**C47** - "Salvar" writes the file and the action happens (PROJ-04, AC 6)
Proof: run project | tests/test_gui_project.py::test_guard_save_continues PASSED

**C48** - "Descartar" leaves the file unchanged and the action happens (PROJ-04, AC 7)
Proof: run project | tests/test_gui_project.py::test_guard_discard_continues PASSED

**C49** - "Cancelar" keeps window, values and `*` (PROJ-04, AC 8)
Proof: run project | tests/test_gui_project.py::test_guard_cancel_changes_nothing PASSED

**C50** - A save that fails, or is refused while detecting, abandons the action (PROJ-04, AC 9)
Proof: run project | tests/test_gui_project.py::test_guard_failed_save_stops PASSED

**C51** - Cancelled dialog, bad project and bad image after "Descartar" keep the values and `*` (PROJ-04, AC 10)
Proof: run project | tests/test_gui_project.py::test_discard_then_cancelled_dialog_keeps_work PASSED

**C52** - After another image Ctrl+S asks for a name, the old file keeps its bytes and the controls keep their values (PROJ-04, AC 11)
Proof: run project | tests/test_gui_project.py::test_new_image_detaches_project PASSED

**C53** - Output folder, executable, tab and zoom changes add no `*` (PROJ-04, AC 12)
Proof: run project | tests/test_gui_project.py::test_local_settings_do_not_mark PASSED

**C54** - Opening the open file again restores its values (PROJ-05, AC 1)
Proof: run project | tests/test_gui_project.py::test_reopening_same_project_reloads PASSED

**C55** - Ctrl+S after the file was deleted writes it again (PROJ-05, AC 2)
Proof: run project | tests/test_gui_project.py::test_save_recreates_deleted_file PASSED

**C56** - An export started before opening finishes with the palette, parameters and folder it started with (PROJ-05, AC 3)
Proof: run project | tests/test_gui_project.py::test_export_keeps_its_values PASSED

---

## Handoff

**Settled mid-build:** none
**Dispatched:** none
**Walked:** none

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 ------→ T2 ------→ T3
Phase 2:  T3 ------→ T4 ------→ T5 ------→ T6 ------→ T7
Phase 3:  T7 ------→ T8
```

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Project file writer | 1 file, 1 behavior (+ its tests) | ✅ |
| T2: Project file reader rebuilding image, palette and `Analysis` | 1 file, 1 behavior (+ its tests) | ✅ |
| T3: Validation of untrusted project files | 1 file, 1 behavior (+ its tests) | ✅ |
| T4: Menu Arquivo and saving from the window | 1 file, 1 behavior (+ its tests) | ✅ |
| T5: Opening a project into the window | 1 file, 1 behavior (+ its tests) | ✅ |
| T6: Presets missing on this computer | 1 file, 1 behavior (+ its tests) | ✅ |
| T7: Unsaved mark and guards | 1 file, 1 behavior (+ its tests) | ✅ |
| T8: README section on projects | 1 file, 1 behavior (+ its tests) | ✅ |

## Diagram-Definition Cross-Check

| Task | Depends On | Diagram Shows | Status |
| ---- | ---------- | ------------- | ------ |
| T1 | None | None | ✅ |
| T2 | T1 | T1 | ✅ |
| T3 | T2 | T2 | ✅ |
| T4 | T3 | T3 | ✅ |
| T5 | T4 | T4 | ✅ |
| T6 | T5 | T5 | ✅ |
| T7 | T6 | T6 | ✅ |
| T8 | T7 | T7 | ✅ |

## Test Co-location Validation

| Task | Layer | Matrix Requires | Task Says | Status |
| ---- | ----- | --------------- | --------- | ------ |
| T1 | Qt-free module | unit | unit | ✅ |
| T2 | Qt-free module | unit | unit | ✅ |
| T3 | Qt-free module | unit | unit | ✅ |
| T4 | Window | integration | integration | ✅ |
| T5 | Window | integration | integration | ✅ |
| T6 | Window | integration | integration | ✅ |
| T7 | Window | integration | integration | ✅ |
| T8 | Docs | none | none | ✅ |
