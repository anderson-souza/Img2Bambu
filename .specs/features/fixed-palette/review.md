# Review: fixed-palette (cor na imagem × cor do filamento)

Scope: commits 66902ca and 7ddadac (after 6a81296), plus the uncommitted `plan.md` status line.
Reviewed against `request.md` and `plan.md`.

## Verdict

**All 10 criteria are built and tested, with one spec-level problem to raise with the user.**
In the main flow the user's goal works: on `workdir/cha-bebe/...yah5.png` with 4 colors, editing
three swatches gives "2 verdes, 1 rosa, 1 branco" in the preview. The tests are strong: 10 of 10
mutations made to the rules were caught. But the carry-over rule (criterion 9), built exactly as
the spec says, can throw away a color the user wanted when "Nº de cores" changes. On the user's
own image, the pink butterfly disappears at N 4→5. This is a flaw in the spec, not in the code,
so the user should decide the rule (CLAUDE.md rule 7). There are also two minor findings.

## How it was checked

- `python -m pytest -m "not slow"`: 78 passed.
- Mutation testing on a throwaway copy of the repo (`/tmp/claude-1000/review-scratch/repo`). Each
  rule was broken once and the suite re-run. Every mutation failed at least one test:
  tie `<`→`<=` (2 failed), carry-over drops samples (2), carry-over keeps unedited rows (2), count
  label back to `len(active())` (1), no k-means shortcut when unedited (2), preview painted with
  samples (4), STL parts colored with samples (1), `fresh_image` not reset on open (1), `edited` not
  marked on pick (3), initial sample = median instead of center (1).
- Headless GUI (offscreen) on the user's image at 1280×800 and 1000×700, opened through
  `open_image` with a stubbed `QFileDialog`. Color dialogs were stubbed through
  `QColorDialog.getColor`. QSettings was redirected with `XDG_CONFIG_HOME` to a scratch dir, so the
  real app's settings were not touched. Screenshots are in `/tmp/claude-1000/review-scratch/shots/`.
- No database exists; no other data was needed.

## Captures

`captures/` does not exist. The only capture, the user's screenshot, was pasted in chat and never
saved. The plan treats it as the current state, not a target. I compared it against its written
description instead (`request.md`): Cores (prévia), 4 colors, dark olive base, pink, light green,
white/pale. The running app's initial state matches: rows `(92,90,55)` base 14%, `(222,142,148)`
11%, `(171,171,107)` 30%, `(215,213,179)` 46% (`1280x800_1_initial.png`). Filtro reflexo is checked
by default only on the pale row. In the capture the user had also checked pink and light green,
which was their own choice. At both sizes the new row (`sample → filament`, Base, Filtro reflexo,
merge, %) fits without clipping.

## Request, sentence by sentence

| Request | Built? | Evidence |
| --- | --- | --- |
| "quero ... utilizar apenas 4 cores. 2 verdes, 1 rosa e 1 branco" | yes | samples set to `(70,68,40)`, `(150,152,90)`; filaments set to dark green, green, white → preview shows 2 greens, pink, white; label "4 filamento(s)" (`1280x800_2_edited.png`) |
| "a visualização não está ficando boa" | yes | preview, 3D and export all go through `segment.assign` → `build_masks`, colored with the filament |
| "ajudar na detecção e ajustes mais finos das cores" | yes | the "cor na imagem" swatch moves pixels between rows (row 0: 14%→10%) |
| Proposal item 1: "seletor de cor **ou** as cores dos presets Bambu" | color picker only | see Problem 4 |
| Proposal item 1: "sem k-means" | replaced by a hybrid (k-means gives the initial values) | approved by the user ("Duas cores por linha"); not a deviation |

## Criteria and their tests

| # | Built | Test | Would it fail if the rule were wrong? |
| --- | --- | --- | --- |
| 1 | yes | `test_analysis_initial_samples_and_filaments`, `test_initial_sample_is_cluster_center_not_median`, `test_rows_show_sample_and_filament` | yes (median-as-sample mutation caught) |
| 2 | yes | `test_sample_edit_pulls_pixels_filament_edit_does_not`, `test_equal_samples_tie_goes_to_lower_index` | yes (tie mutation caught). The spec's literal example pixel `(214,212,178)` is not used; an equivalent PATCH pixel is |
| 3 | yes | `test_unedited_rows_keep_kmeans_split` | yes (shortcut removal caught) |
| 4 | yes | `test_sample_dialog_reassigns_pixels` (title, %, preview pixel) | yes |
| 5 | yes | `test_filament_dialog_recolors_only` | yes |
| 6 | yes | `test_cancel_changes_nothing` | yes |
| 7 | yes | `test_export_uses_filament_not_sample` (3MF colors, preview PNG); STL part colors are covered indirectly | yes (preview and parts mutations caught) |
| 8 | yes, as written | `test_empty_row_not_counted` | yes for the 0-pixel case; see Problem 2 |
| 9 | yes, as written | `test_carry_over_keeps_edited_rows`, `test_reanalysis_keeps_edited_row` | yes |
| 10 | yes | `test_new_image_starts_fresh` | yes (`fresh_image` mutation caught) |

## Problems

### 1. Major (spec): index-based carry-over drops colors the user wanted when N changes

Criterion 9 keeps edited rows by **index**. But k-means labels are sorted dark→light, so when N
changes, the same index points to a different cluster. A kept row then overwrites whatever new
cluster landed at its index.

Reproduced in the GUI on the user's image. At N=4, rows 0, 2 and 3 were edited (dark green, green,
white) and pink stayed at row 1. Then "Nº de cores" was set to 5. The k-means result for N=5 is
`[(84,82,45), (128,125,86), (223,143,149) pink, (171,171,108), (215,213,179)]`. Rows 2 and 3 are
replaced by the edited green and white. Result:

```
samples [(70,68,40), (132,124,86), (150,152,90), (215,212,176), (215,212,176)]
pct     ['8%', '11%', '30%', '51%', '0%']   "4 filamento(s) no projeto."
```

The pink cluster is gone. The butterfly is drawn olive, green and white
(`1280x800_3_n5.png`). Row 4 now has the same sample as row 3 and gets 0%, with no message to the
user (CLAUDE.md rule 12). Going N=5→3 left one unedited row holding 83% of the image.

The code matches the spec's own example ("N 4→6 with row 3 edited → row 3 as edited"), so this is
not an implementation bug. But it defeats the user's answer "Manter as ajustadas". The plan logs
the related assumption ("A row counts as edited ...") as unconfirmed (`n`). **The user should
choose the rule.** Options:

- match each kept row to the nearest new cluster by sample, not by index;
- or keep edited rows and fill only the remaining slots from k-means, skipping the clusters
  nearest the kept samples.

### 2. Minor: the filament count can still promise a part that export drops

`refresh_rows` counts a row when it has any **raw** assigned pixel. `build_masks` then removes small
blobs and streaks, and drops a color whose mask ends up empty. Reproduced in the GUI with the
synthetic test image plus 4 isolated red pixels, and one row's sample set to red. The row shows
"0%", the label says "3 filamento(s) no projeto.", and `pipeline.model` builds 2 parts.

Criterion 8 is met as written, because it is limited to "0 pixels". It is not met as intended:
"matching the parts export produces", and the code's own `why:` comment says the count "must not
promise a filament export omits". This is unlikely on the user's image: every sample I tried kept
its mask, down to 0.26% raw. A fix would be to take the count from the last preview's `masks` keys,
or to call it out in the plan.

### 3. Note: one edit slightly moves the borders of rows that were not edited

Once any sample differs from k-means, every row is assigned by its RGB-rounded sample instead of
the float LAB center. With one row's sample set to pure blue on the user's image, 200 of 241,279
pixels in the other rows changed label (0.08%). Criterion 3 only covers the case with no edits, and
the test comment documents this. It is acceptable; I mention it so nobody is surprised later.

### 4. Low: Bambu preset filament colors were scoped out as "not asked"

The proposal the user approved says "seletor de cor ou as cores dos presets Bambu". The plan's Out
of scope row says "new capability; not asked". The "ou" makes presets optional, and the color
picker was built, so this is not a missing requirement. But the reason given is inaccurate: the
user did see presets offered. Worth one line to the user.

### 5. Low: the spec's literal example is not a test fixture

Criterion 2 names samples `(215,213,179)`/`(171,171,107)` and pixel `(214,212,178)`. The tests use
the same colors with a different probe pixel, `PATCH (180,178,120)`, plus a filament change to
white. They check the same behavior, so there is no gap in coverage. Noted only for traceability.

## Nothing changed

No code or commit changes were made, and nothing outside the repo was touched apart from the scratch
dir. This file is the only write.
