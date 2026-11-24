# Smooth contours without gaps

**Approved**: 2026-11-23 - user: "aprovado"
**Settled mid-build:** after the review, user chose: "2 px, giro ≤ 2 (Recomendado)" (criterion 3: 2 px; criterion 2: ≤ 2 turns on real masks, ≤ 1.2 on ideal ones); "Remover a S2 (Recomendado)" (criteria 11-15 dropped); "Deixar como base (Recomendado)" (transparent slits; no effect without S2)
**Review:** sent at b3d1d4d
**Fix pass:** done - P1, P2, P4: smoothing limited locally, tests on real masks; P3: exact right angles; P5: each axis scaled by itself; P6, P7: S2 removed (user); P8: one retry. Left: base outline of a disc touching the crop (2.7 and 3.2 turns at 1200 and 2400 px, ledge made by `clean`); up to 2.3 px on 21 of ~166,000 dino boundary points; criterion 7 on a slanted line is tested against the mask's mean width; criterion 9 test does not isolate `_conflicts`

## Problem

Walls of the exported piece follow the pixel staircase, and neighbouring colors do not touch, so the
base color can show between them. Whoever prints pays in rough walls and unwanted lines.
Measured 2026-11-23 on `main` (code of `eaf6052`), 150 mm, default `Params`, a disc split in two colors:

| Image | Gap between colors | Accumulated turn of the outline (ideal 1) | Width |
| --- | --- | --- | --- |
| 600 px | 0.130 mm | 170 turns | 149.87 mm |
| 1200 px | 0.066 mm | 90 turns | 149.93 mm |
| 2400 px | 0.034 mm | 14 turns | 149.97 mm |

Causes: `findContours` runs through pixel centers; `simplify_mm` 0.04 is below the pixel size of the
first two. On the dino image (8 colors → 4 filaments) mask cleaning also leaves bare strips up to
about 0.5 mm between colors: 458 mm² of 17,167 mm², 250 mm² of it not base-colored in the image.

Nothing has been printed or sliced for this measurement.

When this ships, curved and slanted walls come out smooth, sharp corners stay sharp, and
neighbouring colors meet along one line.

## Shape

This reuses `build_masks`, `build_parts` and `extrude`; CLI, 3D and export already go through them.
Every rule runs in `img2bambu/contours.py` and `img2bambu/geometry.py` (contours), reached by
`tests/test_core.py` and siblings.

1. image, palette and params -> `segment.build_masks` (exists) - cleans and protects lines as today; hands on disjoint masks
2. `pipeline.render` (exists) - draws the 2D preview from those masks, pixel by pixel as today
3. `geometry.build_parts` (exists) - hands the silhouette and all masks together to the tracer
4. `contours.trace`, called by `geometry` (new) - splits pixel-edge boundaries at points where three or more regions meet, smooths each shared stretch once, keeps corners, rebuilds one polygon set per part
5. `geometry.extrude` (exists) - makes the meshes; the existing watertight check stays
6. out: meshes -> `preview3d.build` (exists) and `pipeline.export` (exists) -> 3D tab, STLs, 3MF

```mermaid
flowchart LR
    A["1. segment.build_masks (exists)"] --> B["2. pipeline.render (exists)"]
    A --> C["3. geometry.build_parts (exists)"]
    C --> D["4. contours.trace (new)"]
    D --> E["5. geometry.extrude (exists)"]
    E --> F["6. preview3d.build / pipeline.export (exists)"]
```

**Changes underneath**

| Front | What changes |
| --- | --- |
| domain | a part's polygons depend on all masks, no longer on its own mask alone; contours run along pixel edges |
| stored data | nothing - no persisted field or setting |
| readers | 3D tab, STLs, 3MF (criterion 8); 2D preview unchanged |
| domain | `Params.simplify_mm` and `geometry.to_polys` per mask are gone: `to_polys` takes all masks |
| readers | `test_preview3d.py` width tolerance, which states the old lost pixel: tightened with criterion 4 |
| readers | color percentages: unchanged, counted before cleaning |

Data: none - nothing stored is touched.

Feasibility spike (ideal disc masks of 150 and 4 mm): smoothing the midpoints of pixel edges with about 1 px
tolerance gives 1.00 turn and at most 0.67 px of deviation. It did not cover `build_masks` output,
junctions, corners or thin lines.

## Surface

None - nothing consumed outside; no control or CLI option is added

## Landing

None - no persisted schema, no new dependency, no contract; the geometry is recomputed on every run

- Nothing else in this change is hard to reverse

## Criteria

"px" = one pixel of the upsampled mask, in mm. "Corner" = a change of direction ≥ 45° of the mask's
boundary, measured between stretches of at least 1 mm on each side.

### S1: Smooth shared contours in every export (P1)

The user exports as today; curves are smooth and colors touch.

**Acceptance Criteria**

1. WHEN two colors are adjacent in the masks THEN the distance between their polygons SHALL be ≤ 0.005 mm
   all along the shared boundary, with overlap area 0 (≤ 1e-6 mm²)
   - two half discs at 600, 1200 and 2400 px; strong case: curved S-shaped boundary, and three colors
     meeting at one point
2. The outline of a disc SHALL turn ≤ 1.2 turns in total (≤ 2 on masks from `build_masks`) and ≤ 15° at any vertex
   - 150 mm disc at 600, 1200 and 2400 px; strong case: 4 mm disc at 600 px over 150 mm
3. The smoothed boundaries SHALL stay within 2 px of the mask's pixel-edge boundary, in both directions
4. The base's width SHALL equal the silhouette mask's width, counted in full pixels, ± 0.02 mm
   - disc at 600, 1200 and 2400 px → 150 ± 0.02; a filled rectangle → 150 ± 0.02
5. WHEN the mask's boundary has a corner THEN the polygon SHALL have a vertex within 1 px of it
   whose direction change, over 1 mm stretches, is within 10° of the mask's
   - square, also rotated 30°; star with 36° tips; strong case: a 60° deviation (hexagon) stays,
     and a disc gains no corner
6. IF an edge has only changes of direction below 45° THEN no vertex SHALL turn more than 15°
   because of the staircase
   - straight edges at 7°, 30° and 45°: accumulated turn ≤ 15° over the edge
7. The lines protected by "Contorno" SHALL stay ≥ 0.42 mm − 1 px wide, as a raised color and as a gap of the
   base color, and stay in one piece
8. The 3D tab, STLs and 3MF SHALL be made from the same parts; all meshes SHALL be watertight and every
   raised part inside the base outline (area outside ≤ 1e-6 mm²), heights unchanged
   - regions linked only by a diagonal pixel; strong case: a ring closed by one; a hole filled by another color
9. IF smoothing makes boundaries cross or a region invalid THEN the system SHALL use the pixel-edge
   boundary for the stretches involved, with criteria 1 and 8 still true
   - mask with boundaries 1 px apart → no part lost, no mesh error
10. The same image and parameters SHALL give identical meshes on two runs

S2 (filling bare strips, criteria 11-15) was built in b3d1d4d and removed after the review: user chose "Remover a S2".

## Out of scope

| Excluded | Why |
| --- | --- |
| A control or CLI option to turn smoothing off | user chose always on |
| Smooth contours in the 2D preview | user chose to keep pixels |
| Filling bare strips left by cleaning | removed by the user after the review |
| Chamfer, inlay, different heights per color | other items of the list; user picked 1 and 2 |
| Corners already rounded by mask cleaning | corners are preserved relative to the mask; cleaning is separate |
| Confirmation on a printed piece | needs the user's printer |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Control | always on | user chose it | y |
| Strips | not filled | user chose to remove S2 | y |
| Corners | deviation ≥ 45° over 1 mm on each side | user chose it | y |
| 2D preview | stays pixel-based | user chose it | y |
| Detail under 1 mm | an edge too short for the corner rule may be rounded, up to 2 px | criterion 3 bounds it | n |
| Pixel art | its steps ≥ 1 mm on both sides stay, smaller ones smooth | follows the corner rule and "always on" | n |
| Contact | the 1 µm inset per side may stay, a 0.002 mm gap | keeps diagonal links manifold; below the 0.005 bound | n |
| Scale | base and colors scaled together, each axis by its own factor, to meet criterion 4 | smoothing may shift an extreme by a fraction of a px | n |

**Open questions:** none - all resolved or logged above.

## Differences from the source

None - the product matches the source

## Sources

- `request.md` - binding - items 1 and 2 and their success criteria
- `workdir/cha-bebe/Gemini_Generated_Image_yah5wqyah5wqyah5.png` - non-binding - measurement only (Problem)
