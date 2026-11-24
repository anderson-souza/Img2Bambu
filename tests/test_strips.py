import numpy as np
import pytest
from test_lines import DARK, LIGHT, MPP, PINK, analysis, canvas, masks_of, rect

from img2bambu import pipeline, segment

GREEN = (60, 160, 70)
UP = 2


def scene(width_mm, color, base=DARK):
    """PINK | vertical strip of `color` | LIGHT, on a DARK frame (the base)."""
    img = canvas(color=base)
    rect(img, PINK, 5, 5, 25, 12)
    rect(img, LIGHT, 5, 17 + width_mm, 25, 12)
    rect(img, color, 5, 17, 25, width_mm)
    rect(img, color, 31, 10, 4, 12)       # a thick part, so the color exists as a label
    return img


def strip_of(masks, width_mm):
    """Union of masks over the strip's pixels, away from its ends."""
    s = int(round(17 / MPP)) * UP
    return slice(int(8 / MPP) * UP, int(27 / MPP) * UP), slice(s, s + int(round(width_mm / MPP)) * UP)


def covered(masks, at):
    return sum(m.astype(int) for m in masks.values())[at]


@pytest.mark.parametrize("width, filled", [(0.3, True), (0.4, True), (0.7, False)])
def test_strip_of_a_dropped_color_is_filled_up_to_half_a_millimetre(width, filled):
    masks, label, sil, *_ = masks_of(scene(width, GREEN), DARK, n=4, min_detail_mm=1.0)
    c = covered(masks, strip_of(masks, width))
    if filled:
        assert (c == 1).all()
    else:
        assert (c == 0).mean() > 0.5


def fill(pink, light, resolved, lines=None, streak=(), px=0.1, sil=None, radius=1.0):
    """fill_strips on hand-made 20-pixel-wide rows: label 0 = base, 1, 2 colors, 3 dropped color."""
    an, pal, p, _ = analysis(scene(0.3, GREEN), DARK, n=4)
    pal.base_index, pal.streak, p.streak_radius_mm, p.upsample = 0, set(streak), radius, 1
    masks = {2: pink.astype(np.uint8), 1: light.astype(np.uint8)}
    sil = np.ones(pink.shape, np.uint8) if sil is None else sil
    segment.fill_strips(masks, resolved, lines or {}, pal, p, sil, px)
    return masks


def rows(gap):
    a, b = np.zeros((6, 20), bool), np.zeros((6, 20), bool)
    a[:, :6] = True
    b[:, 6 + gap:] = True
    r = np.full(a.shape, 3)
    r[a], r[b] = 2, 1
    return a, b, r


@pytest.mark.parametrize("gap, filled", [(1, True), (4, True), (5, True), (7, False)])
def test_width_limit(gap, filled):
    a, b, r = rows(gap)
    m = fill(a, b, r)
    got = (m[1] | m[2])[2:4, 6:6 + gap]
    assert got.all() if filled else not got.any()


def test_tie_goes_to_the_lower_label():
    a, b, r = rows(3)
    m = fill(a, b, r)
    assert m[2][3, 6] and m[1][3, 8]
    assert m[1][3, 7] and not m[2][3, 7]


def test_each_side_takes_its_half():
    a, b, r = rows(4)
    m = fill(a, b, r)
    assert m[2][3, 6:8].all() and m[1][3, 8:10].all()


def test_two_colors_side_by_side_do_not_fill_the_band_beside_them():
    a, b = np.zeros((12, 20), bool), np.zeros((12, 20), bool)
    a[:6, :10] = True
    b[:6, 10:] = True
    r = np.full(a.shape, 3)
    m = fill(a, b, r)
    assert not (m[1] | m[2])[6:].any()


def test_bend_of_a_diagonal_strip_is_filled():
    y, x = np.mgrid[:20, :20]
    a, b = x + y < 18, x + y > 18
    r = np.full(a.shape, 3)
    m = fill(a, b, r)
    assert (m[1] | m[2])[4:16, 4:16].all()


def test_base_colored_pixels_stay_bare():
    a, b, r = rows(4)
    r[:, 7:9] = 0
    m = fill(a, b, r)
    assert not (m[1] | m[2])[:, 7:9].any()
    assert m[2][3, 6] and m[1][3, 9]


def test_protected_base_line_stays_bare():
    a, b, r = rows(4)
    line = np.zeros(a.shape, np.uint8)
    line[:, 6:9] = 1
    m = fill(a, b, r, lines={0: line})
    assert not (m[1] | m[2])[:, 6:9].any() and m[1][3, 9]


@pytest.mark.parametrize("radius, filled", [(1.0, False), (0.0, True)])
def test_filtro_reflexo_pixels_stay_bare(radius, filled):
    a, b, r = rows(3)
    m = fill(a, b, r, streak={3}, radius=radius)
    assert (m[1] | m[2])[2:4, 6:9].all() == filled


def test_strip_within_one_color_or_along_the_edge_stays():
    a, b, r = rows(3)
    m = fill(a | b, np.zeros_like(a), r)
    assert not m[2][:, 6:9].any()
    sil = np.ones(a.shape, np.uint8)
    sil[:, 9:] = 0
    m = fill(a, b & (sil > 0), r, sil=sil)
    assert not (m[1] | m[2])[:, 6:].any()


def test_contorno_base_line_keeps_its_gap():
    img = scene(0.3, DARK)
    masks, label, sil, pal, p = masks_of(img, DARK, (DARK,), n=3, min_detail_mm=1.0)
    px = p.width_mm / sil.shape[1]
    c = covered(masks, (slice(int(8 / MPP) * UP, int(27 / MPP) * UP), slice(int(15 / MPP) * UP, int(19 / MPP) * UP)))
    assert ((c == 0).sum(1) * px >= 0.42 - px - 1e-9).all()


def without_filling(monkeypatch, an, pal, p):
    with monkeypatch.context() as mp:
        mp.setattr(segment, "fill_strips", lambda *a: None)
        return segment.build_masks(an, pal, p)


def test_filling_only_adds_and_stays_disjoint(monkeypatch):
    an, pal, p, _ = analysis(scene(0.3, GREEN), DARK, n=4, min_detail_mm=1.0)
    _, before = without_filling(monkeypatch, an, pal, p)
    sil, after = segment.build_masks(an, pal, p)
    assert list(before) == list(after)
    assert all((after[c] >= before[c]).all() for c in after)
    assert any((after[c] > before[c]).any() for c in after)
    total = sum(m.astype(int) for m in after.values())
    assert total.max() == 1 and not total[sil == 0].any()


def test_image_without_strips_is_unchanged(monkeypatch):
    img = canvas(color=DARK)
    rect(img, PINK, 5, 5, 25, 10)
    rect(img, LIGHT, 5, 20, 25, 12)
    an, pal, p, _ = analysis(img, DARK, n=3)
    _, before = without_filling(monkeypatch, an, pal, p)
    _, after = segment.build_masks(an, pal, p)
    assert all(np.array_equal(before[c], after[c]) for c in before)


def test_preview_shows_the_filled_strip():
    an, pal, p, label = analysis(scene(0.3, GREEN), DARK, n=4, min_detail_mm=1.0)
    _, masks, img = pipeline.render(an, pal, p)
    got = img[strip_of(masks, 0.3)].reshape(-1, 3)
    assert {tuple(int(v) for v in c) for c in got} == {pal.colors[label(PINK)], pal.colors[label(LIGHT)]}
