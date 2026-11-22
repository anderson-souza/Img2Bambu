# Preview 3D Validation

**Date**: 2026-10-23 (iteration 3 of 3, final)
**Spec**: `.specs/features/preview-3d/spec.md` (working-tree version, incl. amendments: XYZ bed fit with `printable_height`; X tolerance ± `simplify_mm` + 1 upsampled pixel; Mesa AC1 = rectangular plane; "Modelo vazio" = N/A)
**Diff range**: `1e03f15..dc97619` (branch `feat/preview-3d`; main = `972fb0b`). Iteration 3 delta: `529646a..dc97619` = `db946da` (T11, `img2bambu.spec` only) + `dc97619` (F2, `tests/test_gui_preview3d.py` only)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict**: ✅ PASS (automated). All 15 ACs and 5 edge cases have spec-anchored evidence. The gate is green and every mutant injected in the final state was caught. Pixel-level and interaction-feel behaviour remains **manual UAT pending** (AD-001: offscreen Qt Quick 3D renders blank). One convention conflict is reported below (unprefixed trailing comments) but was not fixed, as instructed.

---

## Iteration history

| Iter | Commit | Gate | Sensor (that iteration) | Verdict |
| ---- | ------ | ---- | ----------------------- | ------- |
| 1 | `d4e0906` | 59 passed | 14/16 killed (M9, M10 survived) | ❌ FAIL |
| 2 | `529646a` | 64 passed | M9, M10, M18, M19 killed; M17 survived | ❌ FAIL |
| 3 | `dc97619` | 64 passed | M17, M20 killed | ✅ PASS |

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1–T9 | ✅ Done | d9b51d3 … ecee1c8 |
| T10 packaging + smoke | ✅ Done | d4e0906; smoke exit 0 (iteration 1) |
| T11 trim Qt modules | ✅ Done (automated checks); manual UAT pending | db946da; see T11 check below |
| F1 coverage fixes | ✅ Done | 529646a |
| F2 overlap test | ✅ Done | dc97619 |

### T11 check (vs Done-when, tasks.md:311-318)

| Done-when | Evidence | Result |
| --------- | -------- | ------ |
| Required set derived empirically; each item present in `dist\Img2Bambu` | Worker reports a `QML_IMPORT_TRACE` + loaded-DLL trace (45 files). I listed `dist\Img2Bambu\_internal\PySide6` independently. Present: `qml/QtQml/{qmldir,qmlplugin.dll}`, `qml/QtQuick/{qmldir,qtquick2plugin.dll}`, `qml/QtQuick3D/{qmldir,qquick3dplugin.dll}`, `qml/QtQuick3D/Helpers/{qmldir,qtquick3dhelpersplugin.dll,OrbitCameraController.qml}`, `Helpers/impl/{qmldir,qtquick3dhelpersimplplugin.dll}` (a `depends` of Helpers), `Qt6Quick3D*.dll` (Quick3D, Helpers, HelpersImpl, RuntimeRender, Utils), `Qt6Quick.dll`, `Qt6Qml*.dll`, `Qt6QuickWidgets.dll`, `Qt6ShaderTools.dll`, `Qt6OpenGL.dll`, `plugins/platforms/qwindows.dll`, `plugins/styles/qmodernwindowsstyle.dll`, `img2bambu/gui/view3d.qml`. `OrbitCameraController.qml` imports only `QtQuick` and `QtQuick3D` | ✅ |
| `Qt6WebEngineCore.dll` and excluded QML trees absent | `ls -R` has no `webengine` match. `qml/` contains only `Qt QtCore QtNetwork QtQml QtQuick QtQuick3D` | ✅ |
| Bundle ≤ ~361 MB | Reported 352,960,487 B (main 321,180,810 B, i.e. +31.8 MB). **Not independently measured**: a harness hook blocked `du` on `dist/` | ⚠️ Reported, unverified |
| Exe starts ≥ 10 s; `--cli --stl-only` produces STLs | I ran `dist\Img2Bambu\Img2Bambu.exe --cli smoke.png --width 100 --colors 3 --stl-only` with `IMG2BAMBU_LOG`: exit 0, 3 STLs + preview written, log `"[100%] Concluído (somente STLs)."`. The GUI ≥ 10 s start is per the worker report only | ✅ CLI / ⚠️ GUI start not re-run |
| Gate build; test count 64 | 64 passed. The dist was built at 00:35:34 and db946da committed at 00:37:49, consistent with a build of the spec immediately before commit (exact source identity not provable by listing) | ✅ |
| Manual UAT: exe 3D tab shows model | — | ⏳ Pending |

**Filter review (`img2bambu.spec:15-23`).** The regex is applied to destination paths. Over-broad risks I checked:
- `Qt3D` does not match `Quick3D` (no `Qt3D` substring in `Qt6Quick3D*.dll` / `qml/QtQuick3D`).
- `Quick3DAsset` drops `Qt6Quick3DAssetImport/AssetUtils`. These are not dependencies of the kept Quick3D runtime, per the worker trace, and `view3d.qml` uses neither `RuntimeLoader` nor asset import.
- `QuickControls2|QtQuick/(Controls|…)` is safe: the 2D GUI is QtWidgets and the QML uses no Controls.
- `QtTest`/`Qt6Test` only affect test modules.

No pattern matches anything that `view3d.qml` or the widget GUI needs. Minor leftovers, which are harmless and only affect size: `qml/QtQuick/Scene2D` and `qml/QtQuick/Scene3D` plugin DLLs remain while their `Qt63D*` dependencies were removed (they are never imported). `plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll` and `Qt6VirtualKeyboard.dll` remain while the VirtualKeyboard QML is filtered (loaded only if `QT_IM_MODULE=qtvirtualkeyboard`). `Qt6Pdf.dll` remains.

---

## F2 test review (`tests/test_gui_preview3d.py:240-268`)

The test now satisfies the edge case "export em andamento → preview 3D continua funcionando":
- `pipeline.export` is replaced by `held_export`, which sets `started` and blocks on `release`.
- `started.wait(10)` proves the export task is running before the relief change.
- `wait_until(len(calls) == 2 and "× 12.0 mm" in info)` is followed by `assert win.busy_export is True and not release.is_set()`, which proves the rebuild was shown while the export was still open.
- `part_count() == 3` is asserted.
- `finally: release.set()` and the final `busy_export is False` confirm that the export completes afterwards.

Removed asserts:
- `len(calls) == 2` moved into the `wait_until` condition, which raises `AssertionError` on timeout. It is equally strict: exactly 2, because 3 would never satisfy `== 2`. **Not weakened.**
- `(tmp_path / "out").is_dir()` asserted a side effect of the real export. That is not part of this edge case (which concerns the 3D preview), and real export output is covered by `tests/test_core.py`. **No spec outcome lost.**

---

## Spec-Anchored Acceptance Criteria

### P1: Ver modelo 3D e ajustar

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| AC1 one part per `build_parts` item, each with its `Part.color` | count + colour | `tests/test_preview3d.py:16` `len(got) == len(ref) == 3`; `:19` colours equal; `tests/test_view3d.py:32` `part_count() == len(meshes) == 3`; `tests/test_view3d.py:189` `_material_colors(view) == [tuple(m.color) for m in meshes]` | ✅ PASS |
| AC2 base z ∈ [0, base]; colours z ∈ [base, base+relief] | exact bounds | `tests/test_preview3d.py:27` `== approx([0.0, 3.0])`; `:30` `== approx([3.0, 5.0])`; `:117` | ✅ PASS |
| AC3 visible + control change → rebuild after debounce | replaced after debounce | `tests/test_gui_preview3d.py:115` `len(calls) == 1` (pending); `:117` `== 2`; `:119` `"× 12.0 mm — 3 partes"`; `:140-143` (n_colors path) | ✅ PASS (the `palette_changed` route converges on `run_preview`, `main_window.py:400`) |
| AC4 hidden → no build; shown stale → once | 0 / exactly 1 | `tests/test_gui_preview3d.py:91` `calls == []`; `:92` `dirty3d is True`; `:100`, `:105` `len(calls) == 1` | ✅ PASS |
| AC5 only latest shown | stale done and failed dropped | `tests/test_gui_preview3d.py:128-130`; `:234-236` | ✅ PASS |
| AC6 orbit / zoom / pan | camera moves | `tests/test_view3d.py:156` `acceptedButtons == Middle \| Right`; `:166` origin moved | ✅ PASS (pan, scene state) / ⏳ UAT (orbit, zoom, feel) |
| AC7 keep camera on params; reframe on new image | unchanged / reframed | `tests/test_view3d.py:128,139-141,150`; `tests/test_gui_preview3d.py:181,187-188,191-193` | ✅ PASS (scene) / ⏳ UAT (whole model in frame) |
| AC8 no image → "Abra uma imagem para ver o modelo 3D." | exact | `tests/test_gui_preview3d.py:84`; `tests/test_view3d.py:52` | ✅ PASS |
| AC9 error → PT message, model removed, logged, usable | as spec | `tests/test_gui_preview3d.py:157-160`; `tests/test_preview3d.py:49` | ✅ PASS |

### P2: Dimensões do modelo

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| AC1 "X × Y × Z mm" (1 decimal) + nº de partes | format | `tests/test_preview3d.py:165` `== "150.0 × 120.3 × 11.0 mm — 3 partes"`; `:134-135` | ✅ PASS |
| AC2 recalculated → new bbox | text changes | `tests/test_gui_preview3d.py:113` → `:119` | ✅ PASS |

### P2: Mesa da impressora

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| AC1 plane sized to `printable_area`, just below z=0, model centred | as spec | `tests/test_view3d.py:87,89,91,92` | ✅ PASS (z −0.01 → UAT) |
| AC2 printer change → redraw, no remesh | as spec | `tests/test_view3d.py:111-116,176-178`; `tests/test_gui_preview3d.py:206-207` | ✅ PASS |
| AC3 oversize warning strings (with/without height) | exact | `tests/test_preview3d.py:169-170,174,141-153` | ✅ PASS |
| AC4 no presets / area → "Mesa indisponível", model shown | exact | `tests/test_preview3d.py:178,72-77`; `tests/test_view3d.py:101-103`; `tests/test_gui_preview3d.py:219,223-224` | ✅ PASS |

(Line numbers in `tests/test_gui_preview3d.py` shifted +9 vs iteration 2 because of the new `wait_until` helper.)

### Edge Cases

| Edge case | `file:line` + assertion | Result |
| --------- | ----------------------- | ------ |
| OpenGL/3D fails → message; rest of GUI works | `tests/test_view3d.py:58-62,68-70`; `tests/test_gui_preview3d.py:271-283` | ✅ PASS |
| Export running → 3D preview keeps working | `tests/test_gui_preview3d.py:259-263` (`busy_export is True and not release.is_set()` after the rebuild is shown) | ✅ PASS |
| All colours merged → base only | `tests/test_preview3d.py:41` | ✅ PASS |
| > 4 parts → all shown | `tests/test_view3d.py:195-196` | ✅ PASS |
| Modelo vazio | Spec N/A (unreachable; `build_parts` raises first, see P1 AC9) | ✅ Resolved |

### Requirement Traceability

| ID | Status |
| -- | ------ |
| PREV3D-01 | ✅ Verified (packaged: exe CLI verified; exe 3D tab = UAT) |
| PREV3D-02 | ✅ Verified |
| PREV3D-03 | ✅ Verified |
| PREV3D-04 | ✅ Verified (scene state); feel = UAT |
| PREV3D-05 | ✅ Verified |
| PREV3D-06 | ✅ Verified |
| PREV3D-07 | ✅ Verified |

---

## Discrimination Sensor

All mutants ran in detached scratch worktrees (`d4e0906`, `529646a`, `dc97619`). Each worktree was removed afterwards and the real tree is untouched.

| # | File:line | Mutation | Iter 1 | Iter 2 | Iter 3 |
| - | --------- | -------- | ------ | ------ | ------ |
| M1 | `main_window.py:416` | `run_model` bumps shared `self.req` | ✅ | — | — |
| M2 | `main_window.py:400` | build when 3D tab hidden | ✅ | — | — |
| M3 | `preview3d.py:39` | `fits` X `<=` → `<` | ✅ | — | — |
| M4 | `preview3d.py:39` | `fits` ignores Z | ✅ | — | — |
| M5 | `main_window.py:297` | no `reframe3d = True` on new image | ✅ | — | — |
| M6 | `view3d.py:112` | `set_bed` does not move orbit | ✅ | — | — |
| M7 | `pipeline.py:35` | swap `base_mm`/`relief_mm` | ✅ | — | — |
| M8 | `preview3d.py:50` | warning drops final "." | ✅ | — | — |
| M9 | `view3d.py:79` | every part grey | ❌ | ✅ | — |
| M10 | `main_window.py:429` | `model_failed` ignores stale tag | ❌ | ✅ | — |
| M11 | `main_window.py:412` | tab switch rebuilds when not dirty | ✅ | — | — |
| M12 | `view3d.py:94` | fixed camera distance | ✅ | — | — |
| M13 | `main_window.py:432` | failure keeps old model | ✅ | — | — |
| M14 | `main_window.py:269` | machine change skips `set_bed` | ✅ | — | — |
| M15 | `preview3d.py:45` | always "partes" | ✅ | — | — |
| M16 | `view3d.py:66` | placement ignores bed centre | ✅ | — | — |
| M17 | `main_window.py:415` | `run_model` returns while `busy_export` | — | ❌ | ✅ (`test_model_updates_while_export_runs`) |
| M18 | `view3d.py:77` | `set_parts` caps at 4 | — | ✅ | — |
| M19 | `view3d.py:79` | colours reversed | — | ✅ | — |
| M20 | `main_window.py:423` | `model_done` drops results while `busy_export` | — | — | ✅ (`test_model_updates_while_export_runs`) |

**Sensor depth**: expanded (20 behavior-level mutations)
**Result (final state)**: every mutation whose covering test changed was re-run on the final commit and caught. All 20 have been caught at some point. M1–M8 and M11–M16 were checked only on `d4e0906`; production code is unchanged since then and their killing tests are unmodified. ✅ PASS

---

## Gate Check

- **Gate command**: `python -m pytest -m "not slow"`
- **Result**: 64 passed, 0 failed, 1 deselected (the `slow` Bambu Studio slicing test, environment-gated by design)
- **Test count**: 8 before the feature → 64 (+56). No tests were deleted or skipped. F2 moved one assert into a wait condition and dropped one out-of-scope side-effect assert (see the F2 review). `tests/test_core.py` is unchanged vs `main`
- **GUI smoke**: exit 0 in iteration 1. Production Python/QML code is unchanged since then (db946da touches only `img2bambu.spec`)
- **Build gate**: I ran the packaged exe CLI (`--stl-only`): exit 0, 3 STLs. I did not rebuild

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / no scope creep | ✅ All files within task `Where` (T11 approved by user) |
| Matches patterns | ✅ |
| Comment convention (`why:`/`hazard:`/`invariant:`) | ⚠️ 6 unprefixed comments, see below |
| User strings in Portuguese | ✅ |
| Spec-anchored outcome check | ✅ |
| Every test maps to a requirement | ✅ |
| Guidelines followed | `CLAUDE.md` (rules 9, 12; conventions) |

### Comment-convention violations in `1e03f15..dc97619` (reported, not fixed)

CLAUDE.md: "Comments are sparse and prefixed `why:`, `hazard:` or `invariant:`".

| # | Location | Comment |
| - | -------- | ------- |
| 1 | `img2bambu/preview3d.py:13` | `# float32 interleaved pos(3)+normal(3), flat-shaded, 24 B/vertex` |
| 2 | `tests/test_gui_preview3d.py:115` | `# debounce pending: nothing rebuilt yet` |
| 3 | `tests/test_gui_preview3d.py:183` | `# M1 bed centre` |
| 4 | `tests/test_gui_preview3d.py:192` | `# relief is now 2.0: origin back at the model centre, height (base 10 + relief 2) / 2` |
| 5 | `tests/test_gui_preview3d.py:262` | `# export still held open` |
| 6 | `tests/test_view3d.py:127` | `# model is centred on the bed (128, 128) in mm, Z up; scene is Y up with model Y towards -Z` |

`img2bambu.spec:13` continues a `# why:` block, and `img2bambu.spec:1` predates the feature, so neither counts. **Conflict to resolve (rule 7, not averaged):** pre-existing code already uses unprefixed trailing comments (`img2bambu/params.py:13,21-24`, `tests/test_core.py:71`). The CLAUDE.md rule and the codebase precedent disagree. Decide whether trailing field/assert annotations are exempt, then prefix or remove items 1–6 accordingly.

---

## Manual UAT (pending — offscreen Qt Quick 3D renders blank, AD-001)

1. `python app.py`: open an image, go to the "3D" tab. The model appears with each part in its palette colour on the grey bed plane, with no z-fighting.
2. Left drag orbits, the wheel zooms, middle and right drag pan. The feel is acceptable.
3. Opening a new image frames the whole model. Changing relief/base/width keeps the camera angle and updates the model and the "X × Y × Z mm — N partes" text.
4. Switching printer redraws the bed at the new size and the model stays in view. Width 300 mm on A1 shows "⚠ Modelo maior que a mesa (256 × 256 × 256 mm)."; 150 mm shows no warning.
5. While "Gerar 3MF" runs, the 3D tab keeps updating.
6. `dist\Img2Bambu\Img2Bambu.exe` (trimmed bundle): the GUI starts, the 3D tab shows the model, and orbit/zoom/pan work. This confirms T11 dropped nothing needed at runtime.
7. Large real image: no noticeable lag converting or uploading meshes.

---

## Gaps (non-blocking)

1. Convention conflict: 6 unprefixed comments vs CLAUDE.md rule, with pre-existing precedent (see table). Needs a user decision.
2. T11 bundle size was not independently measured (harness blocked `du`), and the GUI ≥ 10 s start was not re-run by the Verifier. Both come from the worker's report.
3. T11 leftovers (size only): `qml/QtQuick/Scene2D`, `qml/QtQuick/Scene3D` (orphaned plugins whose Qt3D DLLs were removed), the virtual-keyboard input plugin and DLL, and `Qt6Pdf.dll`.

## Lessons

`lessons.py` has only `init/add/penalize/list/prune/status` and no resolve command. `penalize` applies only to *confirmed* lessons that recur. L-001 to L-005 therefore stay as candidates; their gaps are closed by 529646a, dc97619 and the spec decisions, with this file as the evidence. Iteration 3 adds no new failure signal. The comment-convention conflict is a codebase/guideline disagreement for the user, not a verification failure, so no lesson was recorded for it.

## Summary

**Overall**: ✅ Ready for manual UAT
**Spec-anchored check**: 15/15 ACs and 5/5 edge cases matched the spec outcome; 0 open spec-precision gaps
**Sensor**: final iteration 2/2 killed (M17, M20); 20/20 caught overall
**Gate**: 64 passed, 0 failed; packaged CLI exit 0
