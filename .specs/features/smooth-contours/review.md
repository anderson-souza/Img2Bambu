# Review: smooth contours without gaps

Reviewed 3f22135..a813ac7, clean tree. **Verdict: changes needed.** Shared contours, width, closed real-image
meshes, determinism and strip filling work. The main promise, smooth walls, is not met on masks the app
really produces (P1), and one wall in seven is rough even on ideal masks (P2).

Suite: `388 passed, 1 deselected`; ruff clean. No captures exist, so no screen was compared. The GUI ran offscreen
(scratch settings): 3D tab reports "150.0 x 159.8 x 11.0 mm - 3 partes"; the offscreen platform cannot draw the 3D
image, so its look was not checked. The 3MF and slicing paths were not run (code read only: both export and 3D call `build_parts`).
Probe scripts were throwaway; mutations were run in a copy of the tree, not in the repository.

## Problems

### P1 (high) - The disc from the Problem table is not close to 1 turn; at 2400 px it got worse
Request success criterion "giro do disco próximo de 1 volta"; criterion 2 (<= 1.2 turns).
Image disc, two colors, default `Params`, through `analyze` + `build_masks` + `to_polys`; the old code (throwaway copy
of 3f22135) reproduces the plan's baseline (170 / 90 / 14), so the baseline was measured this way:

| image | before | now | points now |
| --- | --- | --- | --- |
| 600 px | 163.3 turns | 14.7 | 1692 |
| 1200 px | 99.1 | 23.7 | 2864 |
| 2400 px | 12.8 | **46.8** | 5770 |

(max per-vertex turn 6.0-6.3, width 149.999: fine.) Rectangles at 10 / 20 / 33 degrees through the same path:
26.3 / 27.6 / 2.9 turns (before 117.8 / 231.3 / 199.3). Dino: base outline 18.5 turns. 49% of its boundary length
uses the weak sigma 1-2 levels, 29% sigma 3.
Cause: upsample 2 turns an image pixel into 2-px steps. One spot over 0.75 px sends the whole piece, corner to
corner, to a weaker level. `LEVELS` is chosen per piece, not locally.
The tests miss it: `test_disc_outline_is_round` uses ideal masks at mask resolution, never `build_masks` output;
the plan's spike states that gap too. Criterion 3 (1 px of the *upsampled* mask) may conflict with criterion 2 on
real masks: if so it needs the user's decision, not a silent loss of 2.

### P2 (high) - Straight edges keep the staircase on ideal masks (criterion 6)
Rotated squares, 1 degree steps 0-44 at 600/1200/2400 px, ideal mask: 19 of 135 have total outline turn > 450
(ideal 360), e.g. 600 px/6 deg 2065, 1200/4 deg 2141, 2400/43 deg 2253. No fallback is involved: e.g. 2400/43 deg is
sent to sigma 2 by one pixel vertex 1.06 px away, 1200/4 deg by 1-2 points. Per edge, 600 px/5 deg: 559 deg
where <= 15 is allowed. `test_straight_edges_have_no_staircase` tries only 7/30/45 at 600 px, all lucky.

### P3 (medium) - Corners between 1 mm edges are lost when the px is coarse (criterion 5)
`long = max(CORNER_LEG_MM / px_mm, 10)` raises the leg above 1 mm whenever px > 0.1 mm (a 600 px image at 150 mm
has 0.125 mm). Axis-aligned bars, whose ends are exact on the mask: px 0.125, 1.0 mm wide -> no vertex within 4.5 px
of the corner; px 0.25, 1.0 / 1.25 / 1.5 / 2.0 mm -> 3.7 / 3.7 / 3.1 / 2.5 px; px 0.5, up to 4 mm wide. Ends come out round.
Criterion 5 says 1 mm and logs no such limit; the plan's "detail under 1 mm" assumption does not cover it.
Corner tests use one mask size, with large shapes.

### P4 (medium) - Small discs gain corners (criteria 2, 5)
Ideal discs: 5 mm at 600 px 28.3 deg at a vertex, 6 mm 29.3 deg (many ~27 deg vertices), 7 mm 16.0; 3 mm at 1200 px 29.3; 10 mm at
300 px 28.3. Limit 15; "a disc gains no corner". The strong case (4 mm/600) passes; its neighbours do not.

### P5 (medium) - Boundary moves more than 1 px (criterion 3)
Mask boundary to line: dino 1.18 px (6 points), upscaled dino 1.26 px (31), tall ellipse 1980x200 1.23 px, 2980x100
1.69 px (line to mask 1.21). Two causes likely: the uniform scale in `to_polys` is fixed by the width error and magnified by
height/width (2980x100: height off by 0.195 mm = 2 px); on the dino, what the final scaling and
`_strayed`'s checks (8 vertices, per stretch) leave over.
The test uses four square synthetic shapes. Mutating `MAX_SHIFT_PX` 0.75 -> 1.5 passes all tests.

### P6 (medium) - Filling reaches areas that are not strips (criterion 11)
`(to * way).sum(1) <= 0` accepts perpendicular neighbours. In the concave corner where one color is on the left and
another below, 15 px (0.1 mm px) of a wide, >= 3 mm bare area is filled; same at the capped end of a 0.8 mm
strip, which should stay bare. `test_two_colors_side_by_side...` covers only the same-direction case.

### P7 (low) - Transparent pixels count as "not base-colored"
Image label -1 (outside silhouette, but filled in by its cleaning) is absent from `keep_bare`, so a 0.4 mm transparent slit
between two colors is filled. "strips the image does not paint in the base color" leaves this open; confirm with the user.

### P8 (low) - A mesh can still be open on noise (criterion 8)
Fuzz on per-pixel noise: 3 of 371 random maps failed `check_parts`; the one reproduced (seed 119, px 0.5 mm, sigma 0.5) is a non-watertight mesh.
The old code also fails on such maps (`build_parts` on 399 maps: old 6 failures, new 3), and the dino configurations all gave closed
meshes, so it is not a regression; the export raises visibly.

## Tests that would not fail if the rule were wrong
- Criteria 2 and 6: see P1, P2. Never on `build_masks` output.
- Criterion 3: `MAX_SHIFT_PX` 1.5 survives.
- Criterion 4: removing the width scale (`scale = 1.0`) survives, so the rule's code is untested. The tested shapes do not need it.
- Criterion 9: disabling the `_conflicts` call in `trace` survives; `_polygons`/`_overlaps` catch the test's case.
- Criterion 11: `STRIP_MM` 0.6 survives (widths tested: 0.5, then 0.7); planned 0.45 mm case is replaced by 0.4, and "0.7 -> bare" end to end is asserted as only > 50% uncovered.
- Criterion 13: unit only on hand-made masks; an end-to-end probe behaved correctly (bare with radius 1, filled with radius 0).
- Criterion 8: "STLs and 3MF from the same parts" and "heights unchanged" have no new test (existing ones cover the height of the model).
Mutations caught: corner threshold, arc-vs-corner test, opposite-sides test, protected base line, inset.

## Checked and correct
- 1: shared lines; overlap 0 and no bare sliver on S-curve, three-color point and fuzz; dino overlap 0.
- 4: 149.999 at 600/1200/2400. 8: dino all watertight, area outside base 0. 9: no "Contornos inválidos" in fuzz.
- 10: two CLI runs gave identical STL and preview hashes. 7: read the tests only, plus the passing suite.
- 11 (0.2-0.5 mm filled, 0.6-0.9 not), 12, 14 along the edge, 15 (masks only grow, disjoint).
- Dino, 8 colors to 4 filaments: bare area 2289 -> 2169 mm2; tracing takes 6.7 s (4-9 s on the runs), the user will notice it in the 3D tab.
