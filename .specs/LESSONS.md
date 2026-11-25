# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Plan/Checks)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - Assert the per-item values a view hands to its scene (e.g. colour), not only the item count
- signal: `weak_test` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: preview-3d
- evidence: validation.md M9 (img2bambu/gui/view3d.py:79) (gui)
- last seen: 2026-10-23T03:22:40Z

### L-002 - Test stale-tag discarding on both the success and the failure signal of every tagged task
- signal: `weak_test` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: preview-3d
- evidence: validation.md M10 (img2bambu/gui/main_window.py:429) (gui)
- last seen: 2026-10-23T03:22:41Z

### L-003 - Every edge case listed in the tasks coverage matrix must have a spec-defined outcome
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · harmful: 0
- features: preview-3d
- evidence: validation.md Gap 6 (empty model; tasks.md coverage matrix)
- last seen: 2026-10-23T03:22:42Z

### L-004 - Give every spec edge case its own test, even when code review suggests it is low risk
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: preview-3d
- evidence: validation.md Gap 3 (edge cases: export concurrent, >4 parts)
- last seen: 2026-10-23T03:22:49Z

### L-005 - Make concurrency tests hold the concurrent task open with an explicit sync primitive instead of relying on timing
- signal: `weak_test` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: preview-3d
- evidence: validation.md M17 (tests/test_gui_preview3d.py:231) (gui)
- last seen: 2026-10-23T03:28:58Z

### L-006 - Test a file reader with real detection output on extreme images, because k-means centers drift outside 0-255.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `project` · harmful: 0
- features: project-file
- evidence: F1/C4 (project)
- last seen: 2026-11-24T23:08:44Z

### L-007 - Refuse text that cannot be encoded in UTF-8 when reading a file.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `project` · harmful: 0
- features: project-file
- evidence: F2 (project)
- last seen: 2026-11-24T23:08:44Z

### L-008 - Test per-image state with a previous good image already loaded.
- signal: `weak_test` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: project-file
- evidence: F3/C19 (gui)
- last seen: 2026-11-24T23:08:44Z

### L-009 - Deliver a late 3D result with the 2D tab shown to prove it is discarded.
- signal: `weak_test` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: project-file
- evidence: F4/C15 (gui)
- last seen: 2026-11-24T23:08:44Z

### L-010 - Test both sides of every validation bound.
- signal: `weak_test` · recurrence: 1 feature(s) · scope: `project` · harmful: 0
- features: project-file
- evidence: F5/C35 (project)
- last seen: 2026-11-24T23:08:44Z

### L-011 - State in the spec every value that a reader changes on loading.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `project` · harmful: 0
- features: project-file
- evidence: F6 (project)
- last seen: 2026-11-24T23:08:44Z

### L-012 - Temporary file names must not be longer than the target name.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `project` · harmful: 0
- features: project-file
- evidence: F7 (project)
- last seen: 2026-11-24T23:08:44Z

### L-013 - Test a derived mark after an asynchronous detection returns to the saved values.
- signal: `weak_test` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: project-file
- evidence: F8 (gui)
- last seen: 2026-11-24T23:08:44Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
