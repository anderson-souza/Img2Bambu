# STATE

## Decisions

### AD-001
- **Decision**: In-app 3D rendering uses Qt Quick 3D (`QQuickWidget` + `QQuick3DGeometry`); Qt 3D (`Qt3DCore`/`Qt3DExtras`) is not used.
- **Reason**: Qt documents Qt 3D as obsolete and unmaintained; Qt Quick 3D is its supported replacement, ships with PySide6, needs no new dependency, and a spike rendered real `build_parts` meshes correctly.
- **Trade-off**: bundle +≈32 MB measured (321,180,810 B → 352,960,487 B) — only after filtering in `img2bambu.spec`; untrimmed PySide6 Qt Quick hooks pull the whole qml tree incl. WebEngine (+314 MB). Offscreen platform renders blank, so headless tests check scene state, not pixels.
- **Scope**: GUI (`img2bambu/gui/`), any future 3D view.
- **Date**: 2026-10-22
- **Status**: active

### AD-002
- **Decision**: Undo stores state snapshots (`History` in `img2bambu/history.py`), not per-control commands; every new control in groups 2 and 3 of the window records the state before its change.
- **Reason**: re-detection wipes merges, base and streak choices and has no inverse; only a snapshot restores it.
- **Trade-off**: each re-detection step keeps an `Analysis` in memory (≈100 MB at 2000×2000), so the history holds at most 10 distinct ones and drops the oldest steps beyond that (user, 2026-11-23).
- **Scope**: GUI (`img2bambu/gui/main_window.py`).
- **Date**: 2026-11-23
- **Status**: active

## Handoff

- **Feature**: `.specs/features/preview-3d/`
- **Phase / Task**: Execute done (T1–T11, F1, F2); Verifier PASS (iteration 3)
- **Completed**: all tasks; validation.md written
- **In-progress** (file:line): none
- **Next step**: User manual UAT (list in validation.md); decide comment-convention conflict; then merge feat/preview-3d
- **Blockers**: none
- **Uncommitted files**: none
- **Branch**: feat/preview-3d
