import cv2
import numpy as np
import pytest
import shapely
from shapely import box, unary_union
from shapely.geometry import LineString
from test_lines import DARK, LIGHT, PINK, canvas, masks_of, rect

from img2bambu import contours, geometry, segment
from img2bambu.params import Palette, Params

MM = 150


def grid(n):
    return np.mgrid[:n, :n]


def disc(n, d_mm=MM):
    y, x = grid(n)
    return (np.hypot(x - (n - 1) / 2, y - (n - 1) / 2) <= d_mm / MM * n / 2).astype(np.uint8)


def polygon_mask(n, pts):
    """Pixels whose center is inside the polygon (pixel units)."""
    y, x = grid(n)
    return shapely.contains_xy(shapely.Polygon(pts), x + 0.5, y + 0.5).astype(np.uint8)


def star(n, k, r_out, r_in=None, deg=0.0):
    a = np.radians(deg) + np.arange(k if r_in is None else 2 * k) * 2 * np.pi / (k if r_in is None else 2 * k)
    r = np.where(np.arange(len(a)) % 2 == 0, r_out, r_out if r_in is None else r_in)
    return np.column_stack([n / 2 + 0.3 + r * np.cos(a), n / 2 + 0.2 + r * np.sin(a)])


def turns(coords):
    d = np.diff(np.vstack([coords, coords[1]]), axis=0)
    a = np.arctan2(d[:, 1], d[:, 0])
    return np.degrees(np.abs((np.diff(a) + np.pi) % (2 * np.pi) - np.pi))


def outline(poly):
    return np.array(poly.exterior.coords)


def direction_change(poly, p, leg):
    """Turn at the point of the outline nearest to p, measured over `leg` on each side."""
    ring = LineString(poly.exterior.coords)
    s = ring.project(shapely.Point(p))
    a, b, c = (np.array(ring.interpolate((s + k * leg) % ring.length).coords[0]) for k in (-1, 0, 1))
    u, v = b - a, c - b
    return np.degrees(abs(np.arctan2(u[0] * v[1] - u[1] * v[0], u @ v)))


def pixel_polygon(m):
    """Mask as the exact union of its pixel squares (pixels, Y down)."""
    h = []
    for y, row in enumerate(m):
        d = np.flatnonzero(np.diff(np.concatenate([[0], row, [0]])))
        h += [box(a, y, b, y + 1) for a, b in zip(d[::2], d[1::2], strict=True)]
    return unary_union(h)


def to_px(poly, px, h):
    return shapely.transform(poly, lambda c: np.column_stack([c[:, 0] / px, h - c[:, 1] / px]))


def check_parts(sil, masks, px):
    base, colors = geometry.to_polys(sil, masks, px)
    whole = unary_union(base)
    for k, (m, polys) in enumerate(zip([sil] + masks, [base] + colors, strict=True)):
        assert len(polys) == cv2.connectedComponents(m, connectivity=4)[0] - 1, f"part {k} lost a piece"
        mesh = geometry.extrude(polys, 0, 1)
        assert mesh is None or mesh.is_watertight
        assert unary_union(polys).difference(whole).area <= 1e-6
    for i in range(len(colors)):
        for j in range(i):
            assert unary_union(colors[i]).intersection(unary_union(colors[j])).area <= 1e-6
    return base, colors


def s_split(n):
    y, x = grid(n)
    return x < n / 2 + n * 0.1 * np.sin(y / n * 8)


@pytest.mark.parametrize("n", [600, 1200, 2400])
@pytest.mark.parametrize("split", ["straight", "curved"])
def test_neighbouring_colors_touch_along_the_whole_boundary(n, split):
    sil = disc(n)
    left = s_split(n) if split == "curved" else grid(n)[1] < n / 2
    a, b = (sil & left).astype(np.uint8), (sil & ~left).astype(np.uint8)
    px = MM / n
    base, (pa, pb) = check_parts(sil, [a, b], px)
    ga, gb = unary_union(pa), unary_union(pb)
    # shared boundary = the pixel cracks between both masks
    y, x = np.nonzero(a[:, :-1] & b[:, 1:])
    pts = shapely.points(np.column_stack([(x + 1) * px, (n - y - 0.5) * px]))
    inner = shapely.dwithin(ga.boundary, pts, 2 * px)
    assert inner.all()
    near = shapely.points(shapely.get_coordinates(shapely.segmentize(
        ga.boundary.intersection(shapely.MultiPoint(pts).buffer(1.5 * px)), px)))
    near = near[shapely.distance(near, base[0].boundary) > 3 * px]
    assert len(near) > n / 4
    assert shapely.distance(near, gb).max() <= 0.005
    # no uncovered area left between them
    assert base[0].difference(ga.union(gb).buffer(0.003)).area < 1e-3


def test_three_colors_meet_at_one_point():
    n = 600
    sil = disc(n)
    y, x = grid(n)
    third = ((np.arctan2(y - 300, x - 300) + np.pi) // (2 * np.pi / 3)).clip(0, 2)
    masks = [((third == k) & (sil > 0)).astype(np.uint8) for k in range(3)]
    base, colors = check_parts(sil, masks, MM / n)
    assert base[0].difference(unary_union([p for c in colors for p in c]).buffer(0.003)).area < 1e-3


@pytest.mark.parametrize("n, d, cut", [(600, 150, False), (1200, 150, False), (2400, 150, False), (600, 150, True),
                                       (600, 4, False), (1200, 4, False)])
def test_disc_outline_is_round(n, d, cut):
    """`cut`: two colors end on the outline, which must stay as smooth."""
    sil = disc(n, d)
    left = grid(n)[1] < n / 2
    masks = [(sil & left).astype(np.uint8), (sil & ~left).astype(np.uint8)] if cut else []
    base, _ = geometry.to_polys(sil, masks, MM / n)
    t = turns(outline(base[0]))
    assert t.sum() <= 1.2 * 360
    assert t.max() <= 15


def test_disc_color_is_round_inside_the_base():
    n = 600
    base, (c,) = geometry.to_polys(np.ones((n, n), np.uint8), [disc(n, 100)], MM / n)
    t = turns(outline(c[0]))
    assert t.sum() <= 1.2 * 360 and t.max() <= 15


def shapes(n=600):
    y, x = grid(n)
    rng = np.random.default_rng(1)
    blob = np.argmax([cv2.GaussianBlur(rng.random((n, n)), (0, 0), 12) for _ in range(3)], 0)
    return {"disc": [disc(n), []], "star": [polygon_mask(n, star(n, 5, 250, 95, 10)), []],
            "curved": [disc(n), [(disc(n) & s_split(n)).astype(np.uint8)]],
            "blobs": [np.ones((n, n), np.uint8), [(blob == 1).astype(np.uint8), (blob == 2).astype(np.uint8)]]}


@pytest.mark.parametrize("name", list(shapes(40)))
def test_smooth_boundary_stays_within_one_pixel(name):
    n = 600
    sil, masks = shapes()[name]
    px = MM / n
    base, colors = geometry.to_polys(sil, masks, px)
    raw = unary_union([pixel_polygon(m).boundary for m in [sil] + masks])
    line = unary_union([to_px(unary_union(polys), px, n).boundary for polys in [base] + colors])
    for a, b in ((raw, line), (line, raw)):
        pts = shapely.points(shapely.get_coordinates(shapely.segmentize(a, 1.0)))
        shapely.prepare(b)
        assert shapely.dwithin(b, pts, 1.01).all()


@pytest.mark.parametrize("n", [600, 1200, 2400])
def test_width_is_the_silhouette_width(n):
    base, _ = geometry.to_polys(disc(n), [], MM / n)
    x0, _, x1, _ = base[0].bounds
    assert x1 - x0 == pytest.approx(150, abs=0.02)


def test_width_of_a_rectangle_not_touching_the_canvas():
    m = np.zeros((300, 500), np.uint8)
    m[40:260, 25:475] = 1
    base, _ = geometry.to_polys(m, [], 0.2)
    x0, y0, x1, y1 = base[0].bounds
    assert (x0, x1, y0, y1) == pytest.approx((5, 95, 8, 52), abs=0.02)


@pytest.mark.parametrize("k, r_in, deg, turn", [
    (4, None, 0, 90), (4, None, 30, 90), (4, None, 45, 90), (6, None, 0, 60), (6, None, 11, 60), (3, None, 17, 120),
    (8, None, 22.5, 45), (5, 191, 10, 144), (5, 191, 0, 144)])
def test_corners_stay_sharp(k, r_in, deg, turn):
    n = 1200
    pts = star(n, k, 500, r_in, deg)
    m = polygon_mask(n, pts)
    px = MM / n
    base, _ = geometry.to_polys(m, [], px)
    # a tip may end in pixels linked only by their corners
    poly = to_px(max(base, key=lambda q: q.area), px, n)
    raw = max(shapely.get_parts(pixel_polygon(m)), key=lambda q: q.area)
    verts = outline(poly)
    for i, p in enumerate(pts):
        want = turn if r_in is None or i % 2 == 0 else 72
        pixels = shapely.get_coordinates(raw)
        tip = shapely.Point(pixels[np.hypot(*(pixels - p).T).argmin()])
        # the mask's corner is known only to a pixel: its nearest vertex, or the corner it was drawn from
        assert min(np.hypot(*(verts - q).T).min() for q in ([tip.x, tip.y], p)) <= 1.0
        v = verts[np.hypot(*(verts - [tip.x, tip.y]).T).argmin()]
        assert direction_change(poly, v, 1 / px) == pytest.approx(want, abs=10)


@pytest.mark.parametrize("deg", [7, 30, 45])
def test_straight_edges_have_no_staircase(deg):
    n = 600
    pts = star(n, 4, 250, deg=deg - 45)
    px = MM / n
    poly = to_px(geometry.to_polys(polygon_mask(n, pts), [], px)[0][0], px, n)
    v = outline(poly)[:-1]
    t = turns(np.vstack([v, v[0]]))
    t = np.roll(t, 1)
    far = np.min([np.hypot(*(v - p).T) for p in pts], axis=0) > 8
    edge = np.array([LineString([pts[i], pts[(i + 1) % 4]]).distance(shapely.Point(q)) < 2
                     for i in range(4) for q in v]).reshape(4, -1)
    for e in edge:
        assert t[e & far].sum() <= 15
    assert t[far].max(initial=0) <= 15


@pytest.mark.parametrize("slanted", [False, True])
def test_contorno_line_keeps_its_width(slanted):
    img = canvas()
    if slanted:
        cv2.line(img, (20, 60), (330, 250), (*DARK, 255), 2)
    else:
        rect(img, DARK, 20, 2, 0.3, 30)
    masks, label, sil, pal, p = masks_of(img, LIGHT, (DARK,), min_detail_mm=1.0)
    px = p.width_mm / sil.shape[1]
    _, colors = check_parts(sil, list(masks.values()), px)
    line = max(colors[list(masks).index(label(DARK))], key=lambda q: q.area)
    assert len(colors[list(masks).index(label(DARK))]) == 1
    h = sil.shape[0] * px
    mask = shapely.transform(pixel_polygon(masks[label(DARK)]),
                             lambda c: np.column_stack([c[:, 0] * px, h - c[:, 1] * px]))
    ts = np.linspace(0.1, 0.9, 400)[:, None]
    a, b = (np.array([[2, 6], [33, 25]]) if slanted else np.array([[2, 20.15], [32, 20.15]]))
    n = np.array([-(b - a)[1], (b - a)[0]]) / np.hypot(*(b - a))
    for c in a + (b - a) * ts:
        cross = LineString([(c - 2 * n) * [1, -1] + [0, h], (c + 2 * n) * [1, -1] + [0, h]])
        # a slanted mask line is itself narrower than 0.42 mm at some pixels
        want = min(0.42, mask.intersection(cross).length) if slanted else 0.42
        assert line.intersection(cross).length >= want - px - 0.003


def test_contorno_gap_of_the_base_keeps_its_width():
    img = canvas()
    rect(img, PINK, 8, 4, 24, 28)
    rect(img, DARK, 20, 4, 0.3, 28)
    masks, label, sil, pal, p = masks_of(img, DARK, (DARK,), n=3, min_detail_mm=1.0)
    px = p.width_mm / sil.shape[1]
    _, colors = check_parts(sil, list(masks.values()), px)
    top, bottom = sorted((q for q in colors[list(masks).index(label(PINK))]), key=lambda q: q.centroid.y)
    assert bottom.distance(top) >= 0.42 - px


def test_diagonal_links_holes_and_islands():
    cells = np.array([[0, 1, 1, 1, 0], [1, 1, 0, 1, 0], [0, 1, 1, 1, 0], [0, 0, 0, 0, 1], [1, 0, 0, 1, 0]], np.uint8)
    m = np.pad(np.kron(cells, np.ones((6, 6), np.uint8)), 2)
    sil = np.pad(np.kron(np.ones((5, 5), np.uint8), np.ones((6, 6), np.uint8)), 2)
    hole = np.zeros_like(m)
    hole[2 + 6:2 + 12, 2 + 12:2 + 18] = 1
    check_parts(sil, [m, hole], 0.1)
    check_parts(m, [], 0.1)


def test_boundaries_one_pixel_apart_lose_no_part():
    n = 120
    y, x = grid(n)
    band = ((x - y * 0.37) // 1).astype(int)
    masks = [(band % 4 == k).astype(np.uint8) for k in (0, 1)]
    check_parts(np.ones((n, n), np.uint8), masks, 0.1)


@pytest.mark.parametrize("seed", range(6))
def test_noisy_regions_stay_valid(seed):
    rng = np.random.default_rng(seed)
    lab = np.argmax([cv2.GaussianBlur(rng.random((70, 70)), (0, 0), 1) for _ in range(4)], 0)
    sil = (lab > 0).astype(np.uint8) if seed % 2 else np.ones((70, 70), np.uint8)
    masks = [((lab == k) & (sil > 0)).astype(np.uint8) for k in (1, 2, 3)]
    check_parts(sil, masks, 0.1)


def test_crossing_lines_fall_back_to_pixels(monkeypatch):
    """Smooth lines pushed across each other must not reach the result."""
    real = contours._smooth_line

    def broken(seq, closed, stretches, px_mm):
        real(seq, closed, stretches, px_mm)
        for i, _ in seq:
            stretches[i].smooth = stretches[i].smooth[:1] + (stretches[i].smooth - stretches[i].smooth[:1]) * -1.0
    monkeypatch.setattr(contours, "_smooth_line", broken)
    n = 80
    sil = disc(n)
    left = grid(n)[1] < n / 2
    base, _ = check_parts(sil, [(sil & left).astype(np.uint8), (sil & ~left).astype(np.uint8)], 0.5)
    assert base[0].area == pytest.approx(sil.sum() * 0.25, rel=0.01)


def test_same_input_gives_identical_meshes():
    sil, masks = shapes(200)["blobs"]
    pal = Palette([DARK, LIGHT, PINK])
    a, b = (geometry.build_parts(sil, dict(enumerate(masks, 1)), pal, Params()) for _ in range(2))
    for x, y in zip(a, b, strict=True):
        assert np.array_equal(x.mesh.vertices, y.mesh.vertices) and np.array_equal(x.mesh.faces, y.mesh.faces)
    assert segment.preview(sil, {1: masks[0]}, pal).shape == (200, 200, 3)
