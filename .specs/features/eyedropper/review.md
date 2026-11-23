# Review: eyedropper (conta-gotas)

Scope: commits 54419a8 and 9a58378 (after a863b79), plus the uncommitted `plan.md` edit (it only sets
"Review: sent at 9a58378").

## Verdict

**Approved, with minor fixes recommended.** All 13 criteria are implemented and behave as the plan
says. The request's sentences are covered, either as built or as decisions the user made in the plan:

- per-row button instead of "linha selecionada / menu"
- 5×5 mean
- no new row
- no global shortcut (only Esc)
- works on Cores (prévia) too

`python -m pytest -m "not slow"`: 100 passed. Nothing blocks shipping. Findings 1 and 2 are behavior
nits, findings 3 and 4 are about the tests.

## How it was checked

- Read the request (`melhorias-cores.md` §2) and the plan's 13 criteria against the diff of
  `img2bambu/segment.py`, `img2bambu/gui/main_window.py`, `tests/test_core.py` and
  `tests/test_gui_palette.py`.
- **Ran the app** offscreen (`QT_QPA_PLATFORM=offscreen`) at the default 1300×820, with
  `workdir/cha-bebe/Gemini_Generated_Image_yah5wqyah5wqyah5.png`. I drove it with QTest from scratch
  scripts and took screenshots. There are no captures, so I checked layout against the plan's text:
  - The 💧 button sits left of the "cor na imagem" swatch, 28×24, and shows as checked while armed.
  - The status text matches criterion 2.
  - Unarmed drag pans (scroll moved 200 px). Armed drag does not pan (0 px), and the press sampled instead.
  - Wheel zoom works while armed (3.0 → 3.6).
  - Esc cancels even with focus in a spin box.
  - The 3D tab ignores clicks.
- **Mutation testing**: I applied mutations to a throwaway copy of the repo in the scratchpad and
  re-ran `tests/test_core.py` and `tests/test_gui_palette.py`. No repo code was changed. There is no
  browser or database here, so no stubbing was needed. The synthetic `sage_green` fixture covers the
  other states.
- QSettings: my drive scripts never call `open_image`/`generate`, so they write no settings. The
  project's test suite does write them, see finding 4.

## Rule → test → would it fail if the rule were wrong?

| Criterion | Test(s) | Mutation tried | Fails? |
| --- | --- | --- | --- |
| 1 tooltip | `test_eyedropper_button_per_row` | (exact string compare) | yes |
| 2 arm: cross cursor, status N=i+1 | `test_arm_shows_cross_and_status` | cursor → PointingHand; `{i}` instead of `{i+1}` | yes / yes |
| 3 5×5 window | `test_sample_at_means_a_mixed_window`, `test_preview_and_original_give_same_sample` | r=1 (3×3) | yes |
| 3 rounded mean | same | truncation instead of round | yes |
| 3 silhouette only | `test_sample_at_ignores_background_pixels` | include background pixels | yes |
| 3 crop offset (Original) | `test_original_click_uses_crop_offset` | drop offset subtraction | yes |
| 3 marks edited, re-renders | `test_original_click_sets_sample`, `test_sampled_row_carried_over` | skip `edited.add` | yes |
| 4 miss keeps pick armed + message | `test_click_outside_object_keeps_pick_armed`, `test_preview_click_outside_object` | disarm on miss | yes |
| 4 outside image → None | `test_sample_at_outside_object_is_none` | (only far-outside points; see finding 2) | partial |
| 5 Esc | `test_esc_cancels` | Esc shortcut never enabled | yes |
| 6 same button cancels / other moves | `test_same_button_cancels_other_button_moves` | remove same-row toggle | yes |
| 7 no pan while armed | `test_pan_only_when_not_armed` | drag mode not switched | yes |
| 7 wheel zoom keeps working | none | n/a (`wheelEvent` unchanged) | **no test** |
| 8 unarmed click/drag/double-click as before | `test_pan_only_when_not_armed` | remove `self.picking` guard in `mousePressEvent` (every unarmed left press swallowed, so pan breaks) | **no, still passes** (finding 3) |
| 9 reanalysis / new image disarm | `test_reanalysis_and_new_image_disarm` | remove disarm in `build_rows`; in `open_image` | yes / yes |
| 10 fixed-palette rules | `test_original_click_sets_sample`, `test_sampled_row_carried_over`, `test_original_click_uses_crop_offset` (filament untouched) | skip `edited.add` | yes |
| 11 preview maps `// upsample` | `test_preview_click_samples_image_not_filament`, `test_preview_and_original_give_same_sample` | no division | yes |
| 11 floor (`//`), not round | same | `round(p / upsample)` | **no, still passes** (finding 3) |
| 11 samples image, not filament | `test_preview_click_samples_image_not_filament` | (filament red, expects PATCH) | yes |
| 12 preview miss | `test_preview_click_outside_object` | disarm on miss | yes |
| 13 3D click ignored | `test_3d_tab_click_keeps_pick_armed` | n/a (View3D has no hook) | trivially true |

## Findings

### 1. The "Clique na imagem…" instruction is overwritten while the pick is still armed (minor, criterion 2)

**Evidence.** I picked row 1 on the real image, then immediately armed row 2
(scratch `drive3.py`). Right after arming, the status bar shows
"Clique na imagem para definir a cor na imagem da cor 2 (Esc cancela)." 0.5 s later the row is
still armed, but the status bar reads "Prévia pronta. Ajuste as cores ou clique em Gerar 3MF."

**Cause.** The debounced `run_preview`/`preview_done` from the previous pick calls `self.status(...)`
unconditionally. The same happens to "Clique dentro do objeto." if a preview is in flight. Picking
several rows one after another is the normal workflow, so the user loses the hint and the only
visible sign of armed mode is the cross cursor.

**Possible fix.** Have `preview_done` leave the armed message in place, for example by skipping the
status update while `pick_row is not None`.

### 2. Clicks up to 2 px outside the image still sample when the object touches the image border (minor, criterion 4)

Criterion 4 lists "outside the image" as a case where the palette must not change.
`ImageView.mousePressEvent` emits for any viewport point, including the grey area around the pixmap.
`sample_at` clips the window to the image, so a window centred 1–2 px outside still overlaps
silhouette pixels.

**Evidence.** Take a 100×100 image whose object spans rows 0..59, so the offset is (0, 20).
`sample_at(an, -1, 30)` and `sample_at(an, -2, 30)` both return `(200, 50, 50)`, and
`sample_at(an, -3, 30)` returns None. `test_sample_at_outside_object_is_none` only tests points
10 px outside, so it misses this.

**Impact.** Small, because the sampled color is the edge color anyway. But it contradicts the
literal criterion. Two ways to resolve it:

- reject clicks whose centre pixel is outside the shown image, or
- confirm with the user that "near the edge" is acceptable.

### 3. Two rules have tests that would not catch a regression (test quality)

- **Criterion 8 (unarmed press pans, double-click fits).** `test_pan_only_when_not_armed` only
  asserts `dragMode()` and that an unarmed click does not change the palette. To test this,
  I removed the `self.picking` guard so every unarmed left press is swallowed and never reaches
  `super().mousePressEvent`. That breaks panning, yet all 44 tests still pass. A test that drags
  unarmed and asserts the scrollbar moved would cover it; my scratch script does this in 6 lines.
  Double-click-to-fit and wheel zoom (criterion 7) have no test at all. Their code is unchanged,
  so the risk is low.
- **Criterion 11 floor mapping.** Replacing `y // upsample` with `round(y / upsample)` passes every
  test. Both preview tests click either exactly on `k * upsample` or inside a uniform area. One
  click at `k * upsample + 1` on the sage|green boundary would pin the floor rule.

### 4. The new test writes the user's real QSettings (test hygiene, outside the repo)

`test_reanalysis_and_new_image_disarm` calls `win.open_image()`, which runs
`self.settings.setValue("dir", ...)` on the real `QSettings("img2bambu", "img2bambu")`. It does not
swap in a temporary `QSettings` the way `test_gui_preview3d.py` lines 174/254 do.

**Evidence.** After the suite runs, `~/.config/img2bambu/img2bambu.conf` holds
`dir=/tmp/pytest-of-andersonsouza/pytest-64/test_reanalysis_and_new_image_0`.

This copies an existing pattern: `test_new_image_starts_fresh` from fixed-palette does the same. So it
is convention, not new breakage. Still, running the prescribed test command changes data outside the
repo. **Disclosure:** my test runs, including the mutation runs, overwrote that `dir` key. Its earlier
value was already a pytest temp path from earlier runs, judging by the file name pattern, but I cannot
confirm that.

### Notes (no action needed unless the user disagrees)

- **Double-click while armed.** The first press of the double-click samples and disarms. Then
  `mouseDoubleClickEvent` (unchanged) fits the view and loses the user's zoom. After a miss, the pick
  stays armed and the view still refits. The spec says nothing about this.
- **Rounding.** `np.round` rounds halves to even. A full 25-pixel window can never produce a .5 mean,
  but a partial (edge) window can, so a 0.5 tie rounds to even rather than up. The spec says only
  "rounded to int".
- **Stale analysis right after opening an image.** If the user re-arms during the brief window after
  opening a new image, before its analysis finishes, a click samples the old analysis. The edit is
  discarded when the fresh palette arrives (`fresh_image`), so nothing visible goes wrong.
