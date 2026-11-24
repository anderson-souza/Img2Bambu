import cv2
import numpy as np
import pytest

from img2bambu import geometry, segment
from img2bambu.params import Palette, Params

DARK, LIGHT, PINK = (30, 30, 30), (200, 190, 120), (220, 100, 130)
MPP = 0.1                             # mm per image pixel of the 400 px = 40 mm canvas


def canvas(size=400, color=LIGHT):
    img = np.empty((size, size, 4), np.uint8)
    img[:] = (*color, 255)
    img[-size // 10:, -size // 10:, 3] = 0     # why: an opaque image would have its background color removed
    return img


def rect(img, color, y_mm, x_mm, h_mm, w_mm, mpp=MPP):
    y, x, h, w = (int(round(v / mpp)) for v in (y_mm, x_mm, h_mm, w_mm))
    img[y:y + h, x:x + w] = (*color, 255)


def analysis(img, base, outline=(), n=2, streak=(), **kw):
    p = Params(width_mm=kw.pop("width_mm", 40), n_colors=n, **kw)
    an = segment.analyze(img, p)
    pal = an.palette

    def label(color):
        return min(range(n), key=lambda i: sum((a - b) ** 2 for a, b in zip(pal.colors[i], color, strict=True)))
    pal.base_index = label(base)
    pal.streak = {label(c) for c in streak}
    pal.outline = {label(c) for c in outline}
    return an, pal, p, label


def masks_of(img, base, outline=(), **kw):
    an, pal, p, label = analysis(img, base, outline, **kw)
    sil, masks = segment.build_masks(an, pal, p)
    return masks, label, sil, pal, p


def pieces(m):
    return cv2.connectedComponents(m.astype(np.uint8), connectivity=8)[0] - 1


def test_defaults_are_off():
    assert Palette([DARK]).outline == set()
    assert segment.analyze(canvas(), Params(n_colors=2)).palette.outline == set()


@pytest.mark.parametrize("outline, kept", [((DARK,), True), ((), False)])
def test_thin_line_survives_only_when_marked(outline, kept):
    img = canvas()
    rect(img, DARK, 20, 0, 0.6, 40)
    rect(img, DARK, 5, 5, 8, 8)               # a thick part, so the color is there either way
    masks, label, *_ = masks_of(img, LIGHT, outline, min_detail_mm=1.0)
    row = masks[label(DARK)][int(20.3 / MPP) * 2]
    assert row.all() if kept else not row.any()
    col = masks[label(DARK)][int(18 / MPP) * 2:int(23 / MPP) * 2, 600]
    assert not kept or col.sum() * MPP / 2 == pytest.approx(0.6, abs=MPP / 2)


@pytest.mark.parametrize("diagonal", [False, True])
def test_one_pixel_line_stays_in_one_piece_and_is_widened(diagonal):
    img = canvas(160)                         # 0.25 mm per pixel
    if diagonal:
        for i in range(20, 140):
            img[i, i] = (*DARK, 255)
    else:
        img[80, 20:140] = (*DARK, 255)
    masks, label, *_ = masks_of(img, LIGHT, (DARK,))
    m = masks[label(DARK)]
    assert pieces(m) == 1
    if not diagonal:
        widths = m[:, 60:260].sum(0) * 0.125
        assert widths.min() >= 0.42 - 0.125 and widths.max() <= 0.42 + 0.125
    else:
        # why: across a diagonal the anti-diagonal pixel count steps by 2 * 0.707
        assert m.sum() * 0.125 ** 2 / (120 * 0.25 * 2 ** 0.5) == pytest.approx(0.42, abs=0.125)


@pytest.mark.parametrize("px, expect", [(2, 0.42), (4, 0.42), (6, 0.6)])
def test_widening_reaches_042_and_leaves_wider_lines(px, expect):
    img = canvas()
    img[200:200 + px, 50:350] = (*DARK, 255)
    masks, label, *_ = masks_of(img, LIGHT, (DARK,), min_detail_mm=1.0)
    widths = masks[label(DARK)][:, 200:600].sum(0) * MPP / 2
    assert widths == pytest.approx(np.full(len(widths), expect), abs=MPP / 2 + 1e-9)


@pytest.mark.parametrize("h, w", [(0.8, 0.8), (0.5, 1.5), (0.4, 1.8)])
def test_specks_and_short_dashes_of_a_marked_color_go(h, w):
    img = canvas()
    rect(img, DARK, 20, 20, h, w)
    rect(img, DARK, 30, 5, 8, 8)
    masks, label, *_ = masks_of(img, LIGHT, (DARK,), min_detail_mm=1.0)
    assert not masks[label(DARK)][:500].any()


def test_stubby_piece_longer_than_2mm_is_no_line():
    img = canvas()
    rect(img, DARK, 10, 10, 1.4, 2.8)         # 2x its width
    rect(img, DARK, 30, 5, 8, 8)
    masks, label, *_ = masks_of(img, LIGHT, (DARK,), min_detail_mm=2.0)
    assert not masks[label(DARK)][:400].any()


@pytest.mark.parametrize("marked", [True, False])
def test_base_ring_opens_a_gap_only_when_marked(marked):
    img = canvas(color=DARK)
    rect(img, LIGHT, 4, 4, 32, 32)
    cv2.circle(img, (200, 200), 60, (*DARK, 255), 3)
    masks, label, *_ = masks_of(img, DARK, (DARK,) if marked else ())
    m = masks[label(LIGHT)]
    assert pieces(m) == (2 if marked else 1)
    if marked:
        gap = 1 - m[400, 500:580]             # crosses the ring once, at x = 260 px
        assert gap.sum() * MPP / 2 >= 0.42 - MPP / 2


def test_marked_line_cuts_other_colors_and_lower_label_wins():
    img = canvas(color=DARK)
    rect(img, LIGHT, 4, 4, 32, 32)
    img[200:203, 80:320] = (*PINK, 255)
    img[80:320, 200:203] = (*DARK, 255)       # crosses the pink line
    masks, label, sil, pal, p = masks_of(img, DARK, (DARK, PINK), n=3)
    pink, light = masks[label(PINK)], masks[label(LIGHT)]
    assert not (pink & light).any() and not (pink & ~sil.astype(bool)).any()
    assert pieces(pink) == 2
    assert all(pt.mesh.is_watertight for pt in geometry.build_parts(sil, masks, pal, p))


def test_lower_label_wins_where_widened_lines_collide():
    img = canvas()
    img[200:202, 50:350] = (*DARK, 255)
    img[202:204, 50:350] = (*PINK, 255)       # touching 0.2 mm lines: both widen into each other
    masks, label, *_ = masks_of(img, LIGHT, (DARK, PINK), n=3)
    d, k = masks[label(DARK)], masks[label(PINK)]
    assert label(DARK) < label(PINK) and not (d & k).any()
    assert d[:, 400].sum() >= k[:, 400].sum() and d[403, 400]
    assert d[:, 400].sum() * MPP / 2 == pytest.approx(0.42, abs=MPP / 2 + 1e-9)


def test_small_piece_cut_off_is_dropped():
    img = canvas(color=DARK)
    rect(img, LIGHT, 5, 5, 30, 30)
    rect(img, DARK, 15, 15, 1.1, 1.1)         # 0.2 mm ring around a 0.49 mm² square,
    rect(img, LIGHT, 15.2, 15.2, 0.7, 0.7)    # which the widened ring cuts to about 0.25 mm²
    masks, label, *_ = masks_of(img, DARK, (), min_detail_mm=0.1)
    assert pieces(masks[label(LIGHT)]) == 2
    masks, label, *_ = masks_of(img, DARK, (DARK,), min_detail_mm=0.1)
    assert pieces(masks[label(LIGHT)]) == 1


def test_merged_away_mark_has_no_effect():
    img = canvas()
    rect(img, DARK, 20, 0, 0.6, 40)
    an, pal, p, label = analysis(img, LIGHT, (DARK,), min_detail_mm=1.0)
    pal.merges = {label(DARK): label(LIGHT)}
    assert segment.build_masks(an, pal, p)[1] == {}


def test_carry_over_keeps_the_mark_of_edited_rows_only():
    def pal(outline=(), edited=(), streak=()):
        return Palette([DARK, LIGHT, PINK], samples=[DARK, LIGHT, PINK], outline=set(outline), edited=set(edited),
                       streak=set(streak))
    got = segment.carry_over(pal(outline={1, 2}, edited={1}), pal(streak={1, 2}))
    assert got.outline == {1} and got.streak == {2}
    assert segment.carry_over(pal(outline={1}), pal(streak={1})).outline == set()
    assert segment.carry_over(pal(edited={1}), pal(streak={1})).streak == {1}
    # follows the color, not the position
    new = Palette([LIGHT, DARK, PINK], samples=[LIGHT, DARK, PINK])
    assert segment.carry_over(pal(outline={1}, edited={1}), new).outline == {0}
