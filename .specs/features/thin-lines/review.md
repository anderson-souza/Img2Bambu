# Review: thin-lines (66fc805..a879b8f; tree clean at start)

**Verdict: mostly implemented; "Contorno" delivers the request. Two outcome defects (1, 2), then smaller defects and test gaps.**

## Problems

1. **Medium - "Proteger traços finos" breaks or drops printable lines (criterion 12).** At the scale in the plan's
   Problem (0.252 mm/px, upsample 2), synthetic lines 30 mm long, "Detalhe mínimo" 1.0, angles 0-90° in 5° steps:
   0.45 mm (>= 0.42) is kept in one piece only at 0, 45 and 90°; gone at 10, 40, 50, 80°; 4 to 10 dashes at every
   other angle. 0.50 mm: 3 pieces at 40/50°. 0.42 mm: similar. 0.60 mm: fine everywhere. At 0.21 mm/px only 0.42 mm fails.
   Cause: `raw &= _within(_px_dist(raw) >= LINE_MM/mu/2, ...)` tests width pixel by pixel with no tolerance, so a
   rasterised line is cut wherever it locally reads < 0.42 mm, and the bits then fail the length rule. Same on the real
   image (8 colors -> 4 filaments, 150 mm): with the switch on, many rings around the dino's spots are still dashes; with the
   base marked "Contorno" they are closed rings. Part of those real lines may be truly < 0.42 mm; the synthetic ones are not.
   Tests miss it: they use only horizontal 0.6 mm lines (kept) and 0.2/0.3 mm (gone) at 0.1 mm/px.
2. **Medium/low - stubby parts shorter than the rule pass as lines (criteria 3 and "Line" definition).** 0.8 x 1.8 mm
   (shorter than 2 mm, 2.25x its width) is kept with "Contorno" at 0.1 mm/px, "Detalhe mínimo" 1.0; spec says gone
   (needs 2.4 mm). Shortest kept: 0.6 -> 1.8 mm, 0.4 and 0.5 -> 1.9, 0.2 and 0.3 -> 2.0. Unmarked they all go. Cause: `4 * mean distance` under-reads
   width on short shapes (the ends pull the mean down), so `area / width` over-reads length.
   Tests miss it: cases are well inside the limit (1.5, 1.8 x 0.4, 1.4 x 2.8).
3. **Low - a speck beside a marked line is absorbed (criterion 3).** At 0.25 mm/px, a 0.75 mm square 1 px away from
   a marked 1 px line adds 0.48 mm² to the mask (speck 0.56). `raw & _within(line, 2*ups)` takes any raw pixel near
   the line, not only what is connected to it, and widening then grows it. Gone at gap >= 2 px.

## Tests

Full run: 288 passed, 1 failed (`test_bee_end_to_end`: Flatpak Bambu Studio cannot read pytest's /tmp folder; the
files it uses are not touched by this work). Ruff clean. 27 mutations were run in a throwaway copy on the two test files
(new and related tests); 19 killed. Survivors:
- `LINE_RATIO` 3 -> 6: no test keeps a line between 3x and 6x its width.
- Dropping `& sil_m` in `line_masks`: no line reaches the silhouette edge, so "within the silhouette" (4, 6) is untested.
- `if lines:` -> always: criterion 1 ("same masks, pixel for pixel") has no test; only the defaults are checked.
- `thin.ravel() > 0`, the rejoin `_within(line, 2*ups)`, and `1.5 * limit` -> `limit`: no test needs them.
- `palette.active()` in `marked`, and `& (1 - taken)` in `m | line`: not counted as a gap / survivor likely equivalent
  (a merged label has no pixels; lines are already cut from the others).
Other: carry_over, exclusion, undo, no re-detection, merged row disabled, 0.3 mm² drop, marked-over-automatic, streak
exclusion and lower-label-wins would each fail if wrong (mutated and killed, except the disjointness backstop above).

## Checked and correct

- Criterion 1: identical to 66fc805 on the real image (4 filaments and none) and on 40 random images with a streak color.
- 2, 4: marked lines at 4 scales, 7 widths, 6 angles: always one piece; mean width 0.36-0.53 for lines drawn
  <= 0.35 mm at "Detalhe mínimo" 1.0, within 1 upsampled pixel of 0.42.
- 5, 6: base lines open continuous gaps on the real image; masks disjoint and inside silhouette on the random images
  with everything on; meshes watertight on the real image. 7: no piece away from a line was dropped (same random images).
- 8, 9, 10, 11, 14 in the running window (offscreen, 1300x820, scratch settings): boxes off by default, base row
  enabled, merged rows disabled, unedited mark lost and edited mark kept on re-detection, undo, switch before opening, kept
  on opening another image, toggled during a detection. Rows need 516 px of a 714 px panel. Out-of-scope items not built.
- `captures/` does not exist and the plan cites none, so there was no capture to compare.
- Request and melhorias-cores.md §5: both alternatives exist; 0.6 mm line survives, 0.6 mm² speck goes.

## Not checked

Slicing in Bambu Studio; the 3D tab (offscreen has no 3D rendering). Preview pixels were compared from
`build_masks`; the window screenshot shows the Original tab. Edited state was set by adding to `palette.edited` in the
running window. A two-panel `cmp.png` found in the shared scratchpad was not made by this review and is not used.
