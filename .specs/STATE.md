# STATE

## Decisions

### AD-001
- **Decision**: In-app 3D rendering uses Qt Quick 3D (`QQuickWidget` + `QQuick3DGeometry`); Qt 3D (`Qt3DCore`/`Qt3DExtras`) is not used.
- **Reason**: Qt documents Qt 3D as obsolete and unmaintained; Qt Quick 3D is its supported replacement, ships with PySide6, needs no new dependency, and a spike rendered real `build_parts` meshes correctly.
- **Trade-off**: ≈31 MB more DLLs in the PyInstaller bundle and a QML file to ship; offscreen platform renders blank, so headless tests check scene state, not pixels.
- **Scope**: GUI (`img2bambu/gui/`), any future 3D view.
- **Date**: 2026-10-22
- **Status**: active

## Handoff

- **Feature**: `.specs/features/preview-3d/`
- **Phase / Task**: Tasks drafted (T1–T10), awaiting user approval
- **Completed**: spec.md, context.md, design.md (approved, spec delta applied), tasks.md
- **In-progress** (file:line): none
- **Next step**: Approve tasks + tools, then Execute starting T1 (offer sub-agents: 2 batches)
- **Blockers**: none
- **Uncommitted files**: `.specs/` (all)
- **Branch**: main
