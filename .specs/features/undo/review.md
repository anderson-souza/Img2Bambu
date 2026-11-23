# Review: Desfazer com Ctrl+Z

Reviewed: `89561b9..7231190` plus the working tree (nothing uncommitted except `.claude/worktrees/`, not touched).

## Verdict

**Not complete: criteria 3, 5 and 10 each have one failing case.** Everything else asked for works. No undo restored a wrong state: 40 random steps over all group 2/3 controls (except base clicks on disabled rows and the eyedropper), undone one by one, matched on palette, rows, percentages, preview pixels, fields, height and filament count.

Request ("CTRL+z depois de qualquer alteração na UI"): built for groups 2 and 3 only. The plan quotes the user narrowing it ("Grupos 2 e 3 apenas"), so this is not a gap.

`pytest -m "not slow"`: 225 passed, 1 deselected. `ruff check .`: clean.

## Problems

### P1 (medium) - Criterion 10: a cyclic merge is not refused and creates a step
`MainWindow.set_merge` tests `palette.resolve(target) == i`. `Palette.resolve` stops when it returns to `target`, so it returns `target` and never `i`: the guard never fires, for 2- or 3-color cycles.
- Evidence: row 1 -> row 2, then row 2 -> row 1. No warning; `merges == {0: 1, 1: 0}`; both combos show a merge; `active()` still lists both colors; two `Mesclagem` steps, where the plan requires the second to add none.
- The guard is older than this work (`972fb0b`), but the approved criterion 10 relies on it.
- `test_actions_that_change_nothing_are_no_step` does not test the cycle case, so nothing caught it.
- When fixing: the refusal path does `merges.pop(i)`, which would drop the row's previous merge. That would be a real change and so a step; the refusal has to restore the previous target.

### P2 (low) - Criterion 3: `Nada para desfazer.` is overwritten
`undo()` leaves `self.undone` set when history is empty, so a preview still running ends with the old `Desfeito: …`.
- Evidence: Largura 150->180, Ctrl+Z twice without waiting: `Nada para desfazer.`, then `Desfeito: Largura.` when the preview finishes. Same with 2 steps and 3 quick presses, the natural use of the shortcut.
- `test_steps_undo_newest_first_and_empty_history_says_so` has no image, hence no preview, and cannot see it.

### P3 (low) - Criterion 5: a run that returns to its start still leaves a step in detection fields
Nº de cores 3->4->3 within 1 s, no manual work: history holds `Nº de cores`; Ctrl+Z says `Desfeito: Nº de cores.` and the palette is identical before and after. The final snapshot has `pending=True` and the first `False`, so `before == after` never matches. Likewise Largura 150->155->150 leaves a step if a detection finishes between the two changes.
- Conflict to settle: criterion 5 says "nenhum passo", but when manual merges/base/streaks exist, the re-detection wipes them and the step is what brings them back (criterion 12). Dropping the step is right only if nothing was lost. Ask the user rather than simply dropping it.

### P4 (low) - Image opened but detection fails: undo is off for the rows still shown
Open a fully transparent PNG over a working image. `fresh_image` stays true, so snapshots hold no palette.
- Evidence: the old image's rows stay on screen; toggling `Filtro reflexo` creates no step, Ctrl+Z gives `Nada para desfazer.` and the toggle stays (criterion 8). Largura 150->180 then Ctrl+Z does restore 150, but reruns detection, which fails: status ends `Erro.` instead of `Desfeito: Largura.` (criterion 2) and the height label stays at `180.0 mm` (criterion 1).
- Showing the old rows after a failed open predates this work.

### P5 (risk, not a criterion) - Memory of re-detection steps
Measured: one 2000x2000 analysis holds 100 MB, all different per step. 50 separate re-detections would hold about 5 GB (computed from that, not run). AD-002 accepts "an `Analysis` … up to 50 steps" without a size. The user should know the figure.

## Criteria

| # | Result | Would its test fail if the rule were wrong? |
| --- | --- | --- |
| 1 | ok; real STL export after undo has a 149.8 mm base (from 150, not 180) | yes for value, height, 3D (mutated). Export is checked only through `params.width_mm`; `Espessura da base` is checked only in `test_quick_run…` without preview |
| 2 | ok except P4 | yes (mutated) |
| 3 | P2 | partly, see P2 |
| 4 | ok | yes (signal blocking and last-state removal mutated) |
| 5 | P3 | yes for numbers, gap, keys (mutated); not for detection fields |
| 6 | ok | yes, at `History` level (limit removed, limit 49) |
| 7 | ok; also pressed with focus on row widgets, 3D view, image views, and after rows are rebuilt under the focus | yes (filter disabled). Row widgets have no test |
| 8 | ok except P4 | yes (shallow snapshot and wrong label mutated) |
| 9 | ok | yes |
| 10 | P1 | no for the cycle case, yes by reading for the others |
| 11 | ok | yes (mutated) |
| 12 | ok | yes (mutated: analysis not restored) |
| 13 | ok | partly: removing `self.req += 1` in `undo()` survives, because `run_preview`/`reanalyze` also take a new tag, so behavior is unchanged |
| 14 | ok, also with a row change made during detection | yes (mutated twice) |
| 15 | ok | yes (all three clears mutated) |
| 16 | ok | params yes (mutated). Palette: exporting `self.palette` without a copy survives; harmless for undo, which replaces the palette object |

27 mutations were listed: 24 failed the undo tests, 3 survived (the two above, and removing `debounce.stop()`, which only causes a redundant preview).

Note, not judged a failure: with a combo's popup list open, Ctrl+Z does nothing (the popup has the keyboard). Seen offscreen only.

## How it was checked

- Offscreen real `MainWindow` with the test fixtures' synthetic images; preset database, dialogs and settings replaced where needed. Not checked: a visible desktop, Windows, Bambu Studio, and 3D pixels (offscreen renders 3D blank, so scene state was used).
- Throwaway, under `/tmp/claude-1000/-media-andersonsouza-SSD-3-repos-img2bambu/4b1c4343-e126-483f-b77e-110967baa2b9/scratchpad/review`: `repo/` (copy of HEAD, where mutations ran), `test_probe.py`, `repo/tests/test_probe2.py`, `mut.py`, `a.png`, `b.png`, `xdg/`. States made there: forced clocks, held or failing detections, the transparent PNG, temporary ini settings.
