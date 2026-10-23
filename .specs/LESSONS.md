# LESSONS — auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation — do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 — Assert the per-item values a view hands to its scene (e.g. colour), not only the item count
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: preview-3d
- evidence: validation.md M9 (img2bambu/gui/view3d.py:79) (gui)
- last seen: 2026-10-23T03:22:40Z

### L-002 — Test stale-tag discarding on both the success and the failure signal of every tagged task
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: preview-3d
- evidence: validation.md M10 (img2bambu/gui/main_window.py:429) (gui)
- last seen: 2026-10-23T03:22:41Z

### L-003 — Every edge case listed in the tasks coverage matrix must have a spec-defined outcome
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · harmful: 0
- features: preview-3d
- evidence: validation.md Gap 6 (empty model; tasks.md coverage matrix)
- last seen: 2026-10-23T03:22:42Z

### L-004 — Give every spec edge case its own test, even when code review suggests it is low risk
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: preview-3d
- evidence: validation.md Gap 3 (edge cases: export concurrent, >4 parts)
- last seen: 2026-10-23T03:22:49Z

### L-005 — Make concurrency tests hold the concurrent task open with an explicit sync primitive instead of relying on timing
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `gui` · harmful: 0
- features: preview-3d
- evidence: validation.md M17 (tests/test_gui_preview3d.py:231) (gui)
- last seen: 2026-10-23T03:28:58Z

## Quarantined (failed when applied — ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
