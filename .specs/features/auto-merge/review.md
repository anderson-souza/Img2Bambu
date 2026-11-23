# Review: auto-merge (Filamentos)

Scope: commits 9d1d7f5, 320afda and e5c1d9e (everything after 756c9be), plus the uncommitted `plan.md` edit (it only sets the review line).
Reviewed 2026-11-22 against `request.md` (the user's answers), `plan.md` criteria 1-22, and `.specs/melhorias-cores.md` §4.

## Verdict

**Built correctly, but the tests have gaps.** Every sentence of the request and all 22 criteria are built, and they behave as specified in the code, the CLI and the running GUI. `pytest -m "not slow"` passes (159 tests) and `ruff check .` is clean. Two rules are not protected by the tests: the distance-only criterion (criterion 5's "strong case") and the distance basis. In both, a wrong implementation passes the whole suite and still changes the result on the image that motivated the feature (see P1 and P2). I recommend adding those tests before merging. I found no defect in the product code.

## How it was checked

- **Request vs. what was built:** I read the code diff (`segment.auto_merge`, `analyze`, `MainWindow.apply_auto_merge`, `sp_fil`, `read_params`, the CLI `--filaments`) against each answer in `request.md`. I also checked that `Filamentos` is never written to `QSettings` (the only `setValue` calls are `dir` and the export keys exe/machine/process/filament/check).
- **CLI on the sample image** (`--colors 8 --filaments 4 --stl-only`). It prints `Mesclagem automática: 8 cores → 4 filamentos.` and the merges `#2F2D1D/#62613F → #514F28`, `#818257 → #ABAB6C`, `#E5B0B0 → #CC858A`. The groups match the Problem statement: two greens, one pink, one cream. `--filaments 9` and `--filaments a` exit with code 2, and the argparse error names `--filaments`.
- **Running GUI:** real `MainWindow`, offscreen, at the default size of 1300×820, with `XDG_CONFIG_HOME` and `APPDATA` pointed at a throwaway folder in the scratchpad. Nothing on the machine was changed: no real QSettings and no Bambu presets. I loaded the sample image with background "color" and Nº de cores 8, then stepped Filamentos through desligado → 4 → 1 → 8 → 4.
  - **Edited rows:** to get five edited rows, I set five rows' filament colors and added them to `palette.edited` directly. This is the same state the color dialog produces. Then I called `palette_changed()` and changed Tolerância to trigger a re-analysis.
  - **Screenshots:** in the scratchpad folder `/tmp/claude-1000/-media-andersonsouza-SSD-3-repos-img2bambu/07b5044d-0e59-4294-9c22-9eaa8c7b82f1/scratchpad/shots/`.
- **Captures:** there are none. `.specs/features/auto-merge/captures/` does not exist, and the plan cites no capture. So the screen was judged against criterion 10's text, not against a capture.
- **Rule tests:** for each rule, I broke the rule in a throwaway copy of the repo (`scratchpad/mut/`) and ran the suite to see whether some test fails. The results are in the table below.

## What the GUI showed

| State | Result | OK? |
| --- | --- | --- |
| Group "2. Cores" form rows | `Nº de cores:`, `Filamentos:`, `Suavização:`, … and the spin box shows "desligado" | ✓ crit. 10 |
| k=8, desligado | no merges, base = row 2 (`#62613F`), "8 filamento(s) … ⚠ mais que 4 cores", no Mesclagem log line | ✓ crit. 2, 12 |
| k=8, Filamentos 4 | combos show `→ #514F28` ×2, `→ #ABAB6C`, `→ #CC858A`; Base and Filtro reflexo disabled on the merged rows; base moves to `#514F28` (the suggested base row 2 was merged into it); "4 filamento(s) no projeto."; log `Mesclagem automática: 8 cores → 4 filamentos.` | ✓ crit. 6, 7, 11, 12 |
| Filamentos 1 | everything goes into `#D7D5B3`, 1 filament, log `… 8 cores → 1 filamentos.` | ✓ (see P4) |
| Filamentos 8 (= k) | no merges, base back to row 2 | ✓ crit. 3 |
| Filament edits after an auto-merge | merges unchanged | ✓ crit. 14 |
| Re-analysis with 5 edited rows, Filamentos 4 | the 5 edited rows stay active and the 3 unedited rows are absorbed; log `Mesclagem automática: só foi possível chegar a 5 filamentos (5 cores editadas).` | ✓ crit. 16, 17, 19 |

## Does each rule's test fail when the rule is broken?

| Rule (criterion) | How I broke it | Test that caught it |
| --- | --- | --- |
| 1 default 0 | (read) | `test_filaments_defaults_off` asserts the value directly |
| 2 off = today | merges or base not reset | `test_rerun_starts_from_suggested_base`. `test_filaments_zero_is_todays_analysis` compares against a direct k-means |
| 3 ≥ rows → none | analyze skips auto_merge | `test_filaments_at_or_above_rows_merges_nothing[7-1]` |
| 4 exactly m active | base not resolved | `test_filaments_leaves_exactly_m_active[1]` |
| 5 closest pair | OpenCV-scaled L | `test_distance_is_cielab_not_opencv_scaled` |
| 5 share-weighted centroid | unweighted mean, or equal weights | `test_group_centroid_is_share_weighted` |
| **5 distance only, "area does not make a small distinct color go first"** | **area-weighted (Ward) cost, both `d²·wa·wb/(wa+wb)` and `d·wa·wb/(wa+wb)`** | **nothing: 159/159 pass (P1)** |
| 6 larger share survives | smaller survives | `test_closest_pair_merges_into_larger` |
| 6 equal share → lower label | higher label survives | `test_small_distinct_color_survives_close_large_ones_merge` |
| 7 base follows the survivor | not resolved | caught (see criterion 4) |
| 8 acyclic | (structural: every row points to its group's head) | `_acyclic` in several tests |
| 9 deterministic | tie between equal distances → later pair (`<=`) | nothing. The tie-break is a plan assumption, not a criterion (P3) |
| Distance basis (plan assumption: exact centers until a sample is edited, then samples) | always samples / never samples | **nothing (P2)** |
| 10 spin box | (read) | `test_filaments_spin_box` checks range, step, special text, tooltip and form position |
| 11 change re-analyzes | `valueChanged` not connected; value not read in `read_params` | `test_filaments_change_reanalyzes_and_shows_merge` |
| 12 log line | wrong k/m in the message | same test |
| 13 manual merge stands | auto_merge also run in `palette_changed` | `test_manual_merge_stands_until_reanalysis` |
| 14 edits do not recompute | same mutation | `test_edit_does_not_recompute_merges` |
| 15 no image → nothing | (guard in `reanalyze`) | `test_filaments_without_image_does_nothing` |
| 16 recompute after carry_over | `apply_auto_merge` removed | `test_reanalysis_recomputes_merges_with_edited_rows` |
| 17 edited row absorbs | survivor chosen by share only | `test_edited_row_absorbs_instead_of_being_merged` |
| 18 skip edited pair | skip removed | `test_pair_of_edited_rows_is_skipped` |
| 19 stop early + log | stop log disabled | `test_too_many_edited_rows_logs_stop` |
| 20 flag passed to analyze | hard-coded 0 | `test_cli_filaments_flag_merges_and_prints` |
| 21 CLI prints merges | merge lines renamed | same test |
| 22 range 0–8 → exit 2 | `choices=range(11)` | `test_cli_filaments_out_of_range_exits_2[9]` |

## Problems

### P1: The distance-only rule (criterion 5, strong case) has no test that fails when it is wrong (major)

The request says "LAB distance only". The plan's out-of-scope table says Ward was rejected because "it folds the 1% dark outline into the dark green". Criterion 5 asks for a test where "a 2% tone far from all others survives while two 30% tones close to each other merge".

`test_small_distinct_color_survives_close_large_ones_merge` is meant to be that test, but its tones do not tell the two criteria apart. Under Ward the C/C′ pair still costs less (6²·0.15 = 5.4 against 66.6²·0.019 ≈ 83 for D–C′). With the distance replaced by either Ward form, all 159 tests pass.

On the sample image (k=8, Filamentos 4), Ward gives a different result:

| Criterion | Groups |
| --- | --- |
| Distance (as built) | `{#2F2D1D, #514F28, #62613F}`, `{#CC858A, #E5B0B0}`, `{#818257, #ABAB6C}`, `{#D7D5B3}` |
| Ward | `{#2F2D1D, #514F28, #62613F, #818257}`, `{#CC858A, #E5B0B0}`, `{#ABAB6C}`, `{#D7D5B3}` |

So a regression to an area-weighted criterion would ship unnoticed.

**Fix:** use tones where the small, far tone has the lowest Ward cost but not the lowest distance. Example: two 45% tones ΔE 10 apart and a 1% tone ΔE 25 from one of them. Then assert that the two large tones merge.

### P2: The distance basis is untested, and it decides the motivating result (major)

`auto_merge` uses the exact k-means centers while no sample is edited, and `palette.samples` once any sample is. The plan logs this as a mid-build finding: the sample image has a near-tie (ΔE ≈ 21) that the RGB round trip flips.

Forcing either branch ("always samples" or "never samples") still passes all 159 tests. With "always samples", the sample image merges the cream background `#D7D5B3` with both sage tones and leaves the dark outline `#2F2D1D` alone. That is the "cream falls into the sage" failure the feature exists to fix.

Nothing pins the Problem statement's measured result (two greens / one pink / one cream).

**Fix:** add a test that pins that result: either on a synthetic near-tie built so that the centers and the RGB samples disagree, or on the sample image if the repo can carry it (today it lives in untracked `workdir/`). Also add a test for the edited branch.

### P3: The distance tie-break is untested (minor)

The plan's Assumptions table says "equal distance → the pair with the lower labels". Changing `d < best[0]` to `d <= best[0]` passes the suite. Criterion 9 only requires the same result on every run, which either version gives, so this is not a criterion violation. The assumption is just not protected.

### P4: `Filamentos = 1` is an unconfirmed assumption, and its log line is ungrammatical (minor)

The request says "N ≥ 2 merges closest colors until N remain". It does not say what N = 1 does, yet the 0–8 spin box allows it. The plan marks "everything merges into one group" as **Confirmed: n**. That needs the user's yes.

With N = 1 the log line reads `Mesclagem automática: 8 cores → 1 filamentos.` (and the CLI prints the same), which is wrong Portuguese for 1. It follows the plan's fixed `<m> filamentos` template, so it is not a spec deviation. It is still visible to the user. Either ask the user to accept "1 filamentos", or get a decision on the singular form.

### P5: A `why:` comment sits on the wrong line (nit, CLAUDE.md conventions)

In `img2bambu/segment.py`, `auto_merge`, the comment `# why: OpenCV's 8-bit LAB stores L as L*·2.55 …` sits above `edits = …`. It explains the `* (100 / 255, 1, 1)` scaling, which is two lines lower.

## Not caused by this feature (for the record)

Exporting the sample image fails with `ValueError: Malha não fechada (watertight) em: …` in this Linux environment. This happens at every Filamentos value, including desligado, and at `--colors 4`, which is today's path. It is equally reproducible on the base commit 756c9be (extracted with `git archive` into the scratchpad). So it is an existing geometry or environment issue and not a regression from auto-merge. The tests use synthetic images and do not hit it.

Two smaller observations, both existing behavior and not regressions: the "—" combo percentages show each row's own share, not its group's, the same as with a manual merge today. A merged-away row can still have "Filtro reflexo" checked (it is shown disabled).
