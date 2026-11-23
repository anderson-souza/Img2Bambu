# Review: Smoothing before clustering (Suavização)

**Scope:** commits 71789aa, 41fbcca (everything after cf39b3d) plus the uncommitted edit to `plan.md`
(only the `**Review:**` line). Reviewed against `plan.md` and the source request
(`.specs/melhorias-cores.md` §3, quoted in `request.md`). No captures exist for this feature.

## Verdict

**Pass, no blocking problems.** All 11 criteria are built and each one has a test. I broke each rule on
purpose in a throwaway copy of the repo (see below), and every one of those changes made a test fail.
I found three minor things, and none of them blocks the merge.

## How it was checked

- Full suite: `QT_QPA_PLATFORM=offscreen python -m pytest -q` → 121 passed, 1 skipped (the `slow`
  Bambu Studio test).
- Mutation testing in a throwaway copy of `img2bambu/` + `tests/` in the scratchpad (the repo itself
  was not touched). Each mutation was run against the feature's tests.
- CLI end to end on `workdir/cha-bebe/Gemini_Generated_Image_yah5wqyah5wqyah5.png` with `--smooth 0/3/5/6`.
- GUI driven headless (offscreen Qt, 1400×900): loaded the sample image, background "color", then set
  Suavização 0 → 5. I captured the status bar and took screenshots. Nothing was persisted: generate was
  never called, so no `QSettings` writes happened.
- Timing of `segment.analyze` on the sample image upscaled to 3000×3200.

## Request, sentence by sentence

| Request (§3) | Built |
| --- | --- |
| optional pre-filter before k-means and assignment | `segment.smoothed` feeds `kmeans_palette`. `lab` (read by `assign`) comes from the filtered pixels, so preview, percentages, 3D and export all see it |
| `pyrMeanShiftFiltering` or `bilateralFilter` | mean-shift (user's choice, recorded in the plan) |
| a "Suavização" control, 0 = off | GUI spin box 0–5, default 0. At 0 `smoothed` returns the input unchanged |
| achata degradês / fewer islands | sample image k=6: 7346 → 7028 (level 3) → 5764 (level 5) label components |
| decide default | off (0) |
| apply only inside the silhouette | outside pixels are filled from the nearest silhouette pixel before filtering. The analysis no longer depends on transparent-pixel RGB (tested) |
| cost on large images | full resolution, analysis only (see minor 1) |
| `segment.analyze`, `Params` new field, GUI spin box | all three, plus the CLI `--smooth` from the plan |
| synthetic gradient test: fewer connected components | `test_smooth_reduces_islands` |

## Criteria and their tests

| # | Rule | Test | Would it fail if the rule were wrong? |
| --- | --- | --- | --- |
| 1 | `Params.smooth` int, default 0 | `test_smooth_defaults_off` | yes (trivial) |
| 2 | smooth 0 == today's analysis | `test_smooth_zero_is_todays_analysis` | yes. Mutation `level <= 0` → `level < 0` (filter runs at 0/0) fails it |
| 3 | `sp=4k, sr=8k`, clustering on the filtered image | `test_smooth_level_sets_mean_shift_strength[1,3,5]` | yes. Swapping sp/sr fails 3 cases. It also asserts `an.lab` == LAB of the filtered output |
| 4 | fewer 8-connected components on gradient+noise | `test_smooth_reduces_islands` | yes. Disabling the filter fails it |
| 5 | independent of transparent RGB, no dark ring | `test_smooth_ignores_rgb_of_transparent_pixels` | yes. Removing the nearest-pixel fill fails it (dark-ring count assertion) |
| 6 | `Analysis.rgba` stays original; eyedropper reads original | `test_smooth_keeps_original_image_for_eyedropper` | yes. Storing the filtered RGBA in `Analysis` fails it |
| 7 | spin box in "2. Cores", 0–5, step 1, default 0, tooltip, label | `test_smooth_spinbox` | yes. Checks range, step, value, exact tooltip, label text and group title |
| 8 | change re-analyzes, status "Detectando cores…", keeps edits, refreshes preview | `test_smooth_change_reanalyzes_and_keeps_edits` | yes. Each of these makes it fail: dropping `p.smooth` in `read_params`, dropping the `valueChanged` connection, bypassing `carry_over` |
| 9 | no image → nothing | `test_smooth_change_without_image_does_nothing` | yes. It would catch an analysis or error with no image loaded |
| 10 | CLI `--smooth N` passes N; default 0 | `test_cli_smooth_flag`, `test_cli_smooth_defaults_to_zero` | yes. Not passing `smooth=a.smooth` fails it |
| 11 | out of range / non-int → exit 2 naming `--smooth`, before reading the image | `test_cli_smooth_out_of_range_exits_2[6,-1,1.5,x]` | yes. Removing `choices` fails the `6` and `-1` cases. `1.5`/`x` are rejected by `type=int` |

Real CLI: `--smooth 6` → `error: argument --smooth: invalid choice: '6' ...`, exit 2. In the GUI, changing the
value set the status to "Detectando cores…", then "Prévia pronta…". `params.smooth == 5`, and the palette
was re-detected. Screenshot: the spin box sits right under "Nº de cores:" in "2. Cores" and the layout is intact.

## Problems found

### Minor 1 — cost is about twice the plan's figure

The plan uses a measurement to keep "Running the filter at reduced resolution" out of scope: "~1.7 s at
3000×3200 for level-5-like strength". Measured here (sample image upscaled to 3000×3200, k=6),
`analyze` takes 1.97 s at level 0, 1.93 s at level 1, 3.33 s at level 3 and 5.51 s at level 5. So level 5
adds about 3.5 s, not 1.7 s. It runs in the background worker, and stale results are discarded by tag.
But stepping the spin box 0→5 queues five analyses that are not cancelled, the same way "Nº de cores"
does. Not a defect against any criterion. The tradeoff's premise is weaker than written, which matters
if users load large images.

### Minor 2 — the sample image cannot be exported via the CLI, at any smoothing level (existing problem, unrelated)

`python -m img2bambu <sample> --stl-only --out ...` fails at `geometry.build_parts` with
"Malha não fechada (watertight)" at `--smooth 0`, as well as at 3 and 5. The analysis path at 0 is proven
identical to before (criterion 2), so this is not caused by the feature. Because of it, I could only verify
the CLI end to end up to the mesh stage on this image. The CLI tests use the synthetic image and do
reach exit 0.

### Minor 3 — the large-image claim in the Problem section is unverified (documentation)

`plan.md` says the gain "is expected to matter on images with strong gradients". The only
real-image measurement shows a small gain at level 3 (7346 → 7028 islands, final regions about the same).
Level 5 gives 5764. This matches the plan's honesty that it is off by default. I note it only so nobody
reads the feature as a proven quality win.

## Not problems (checked)

- `smoothed` fill: `distanceTransformWithLabels` on `~sil` with `DIST_LABEL_PIXEL` gives each silhouette
  pixel its own label. The LUT built in `np.nonzero` order matches `idx[sil]` order. A silhouette that fills
  the whole bbox (no outside pixels) also works (checked).
- No other reader uses `Analysis.rgba` for color. Only `sample_at` does, and that matches the plan.
- Nothing is persisted. `sp_smooth` is not stored in `QSettings`, which matches "Out of scope".
- Comment and style conventions match the neighbouring code (`hazard:` prefix, inline `Params` comment
  like `background`).
