"""Region masks -> polygons whose shared boundaries are traced and smoothed only once (pixels, Y down)."""
import cv2
import numpy as np
import shapely
from shapely.geometry import LinearRing, LineString, Polygon

# E, S, W, N as (dx, dy); turning left is index - 1
STEP = ((1, 0), (0, 1), (-1, 0), (0, -1))
# pixel (dy, dx) to the left of a crack leaving a vertex in each direction; the right one is LEFT[d + 1]
LEFT = ((-1, 0), (0, 0), (0, -1), (-1, -1))
OUTSIDE = -1
CORNER_DEG = 45
# why: directions measured on a pixel staircase are off by a few degrees, so an exact 45° corner may read less
CORNER_SLACK_DEG = 5
CORNER_LEG_MM = 1.0
# why: the final scaling moves the outline a little more, and the total has to stay within 1 px
MAX_SHIFT_PX = 0.75
MAX_CORNER_SHIFT_PX = 0.8
MAX_VERTEX_SHIFT_PX = 0.95          # pixel corners stick out of the line through the edge midpoints
# (low-pass sigma in pixel edges, simplification in px), smoothest first (None = one straight line);
# the first within MAX_SHIFT_PX is used
LEVELS = ((0, None), (8, 0.35), (8, 0.2), (6, 0.2), (4, 0.2), (3, 0.2), (2, 0.2), (1, 0.2))
ARC_STEP_DEG = 6


class Stretch:
    """Boundary between two regions, from one junction to the next (or a closed loop without junctions)."""

    def __init__(self, verts, d0, d1, left, right, loop):
        self.verts, self.d0, self.d1, self.left, self.right, self.loop = verts, d0, d1, left, right, loop
        self.ends = None if loop else (tuple(verts[0]), tuple(verts[-1]))
        self.smooth, self.raw = None, False


def _stretches(lab):
    """Splits the pixel-edge boundaries of the label grid (padded with OUTSIDE) at the junctions."""
    h, w = lab.shape
    out = np.zeros((4, h + 1, w + 1), bool)
    out[0, 1:h, :w] = lab[1:] != lab[:-1]
    out[1, :h, 1:w] = lab[:, 1:] != lab[:, :-1]
    out[2, :, 1:] = out[0, :, :-1]
    out[3, 1:, :] = out[1, :-1, :]
    degree = out.sum(0)
    used = np.zeros_like(out)

    def walk(x, y, d):
        verts, d0, start = [(x, y)], d, (x, y)
        while True:
            used[d, y, x] = True
            x, y = x + STEP[d][0], y + STEP[d][1]
            used[(d + 2) % 4, y, x] = True
            verts.append((x, y))
            if degree[y, x] != 2 or (x, y) == start:
                break
            d = next(k for k in range(4) if out[k, y, x] and k != (d + 2) % 4)
        vx, vy = start
        (ly, lx), (ry, rx) = LEFT[d0], LEFT[(d0 + 1) % 4]
        loop = degree[vy, vx] == 2
        return Stretch(np.array(verts), d0, d, lab[vy + ly, vx + lx], lab[vy + ry, vx + rx], loop)

    found = []
    for y, x in np.argwhere(degree > 2):
        found += [walk(x, y, d) for d in range(4) if out[d, y, x] and not used[d, y, x]]
    for y, x in np.argwhere(degree == 2):
        if not used[:, y, x].any():
            found.append(walk(x, y, next(d for d in range(4) if out[d, y, x])))
    return found


def _turn(u, v):
    return np.degrees(np.abs(np.arctan2(u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0], (u * v).sum(-1))))


def _pairs(stretches, leg):
    """{(stretch, end): (stretch, end)} of the stretches that continue each other through a 3-way junction."""
    at = {}
    for i, s in enumerate(stretches):
        if s.ends:
            for e in (0, 1):
                at.setdefault(s.ends[e], []).append((i, e))
    mate = {}
    for ends in at.values():
        if len(ends) != 3:
            continue

        def away(end):
            v = stretches[end[0]].verts
            v = v if end[1] == 0 else v[::-1]
            mid = (v[:-1] + v[1:]) / 2
            return mid[min(leg, len(mid) - 1)] - mid[0] if len(mid) > 1 else np.subtract(v[-1], v[0])

        def edge(end):
            return OUTSIDE in (stretches[end[0]].left, stretches[end[0]].right)
        rim = [end for end in ends if edge(end)]
        if len(rim) == 2:
            a, b = rim
        else:
            a, b = min((ends[:2], ends[1:], ends[::2]), key=lambda p: _turn(-away(p[0]), away(p[1])))
            if _turn(-away(a), away(b)) >= CORNER_DEG:
                continue
        mate[a], mate[b] = b, a
    return mate


def _lines(stretches, mate):
    """Long lines: [(stretch, reversed)], closed."""
    seen, out = set(), []

    def follow(i, rev):
        seq = []
        while i not in seen:
            seen.add(i)
            seq.append((i, rev))
            nxt = mate.get((i, 0 if rev else 1))
            if nxt is None:
                return seq, False
            i, rev = nxt[0], nxt[1] == 1
        return seq, True

    for i, s in enumerate(stretches):
        for e in (0, 1):
            if i not in seen and not s.loop and (i, e) not in mate:
                out.append(follow(i, e == 1))
    out += [(follow(i, False)[0], True) for i in range(len(stretches)) if i not in seen]
    return out


def _corners(verts, mid, closed, px_mm):
    """[(vertex index, position)] of the corners of a line given its pixel vertices and edge midpoints."""
    n = len(mid)
    # why: a staircase has no direction of its own over a few pixels
    long = max(CORNER_LEG_MM / px_mm, 10)
    path = np.abs(np.diff(mid, axis=0)).sum(1) if n > 1 else np.zeros(0)
    if n < 4 or path.sum() < 2 * long:
        return []

    def legs(size):
        # why: edges per mm depend on the slope, so each leg is found by distance, not by edge count
        idx = np.arange(1, n) if not closed else np.arange(n)
        back, fore = idx - 1, idx % n
        reach = int(np.ceil(size * 1.5)) + 1
        res = []
        for sign, first in ((-1, back), (1, fore)):
            end = first.copy()
            done = np.zeros(len(idx), bool)
            for k in range(1, reach + 1):
                j = first + sign * k
                j = j % n if closed else np.clip(j, 0, n - 1)
                end = np.where(done, end, j)
                done |= np.hypot(*(mid[j] - mid[first]).T) >= size
            res.append((first, end, done))
        return idx, res

    idx, ((b0, b1, bd), (f0, f1, fd)) = legs(long)
    wide = _turn(mid[b0] - mid[b1], mid[f1] - mid[f0]) * (bd & fd)
    _, ((s0, s1, _), (t0, t1, _)) = legs(long / 2)
    near = _turn(mid[s0] - mid[s1], mid[t1] - mid[t0])
    # why: on an arc the turn halves with the leg; at a corner it stays
    score = np.where((wide >= CORNER_DEG - CORNER_SLACK_DEG) & (near >= 0.62 * wide), wide + near, 0)
    picked, order = [], np.argsort(-score, kind="stable")
    for k in order:
        if score[k] <= 0:
            break
        gap = [min(abs(k - q), len(idx) - abs(k - q)) if closed else abs(k - q) for q in picked]
        if all(g >= long for g in gap):
            picked.append(k)
    out = []
    for k in sorted(picked):
        i, p = int(idx[k]), _apex(mid, b0[k], b1[k], f0[k], f1[k])
        if p is not None:
            # why: a tip beyond the pixels would make the piece larger than the size asked for
            p = np.clip(p, verts.min(0), verts.max(0))
            # why: the staircase hides the exact corner; the pixel vertex nearest to where the legs meet is it
            near = np.arange(i - 6, i + 7)
            near = near % n if closed else near[(near > 0) & (near < n)]
            off = np.hypot(*(verts[near] - p).T)
            i, p = int(near[off.argmin()]), p if off.min() <= MAX_CORNER_SHIFT_PX else None
        out.append((i, verts[i] if p is None else p))
    # why: two corners may land on one vertex
    return sorted({i: (i, p) for i, p in out}.values(), key=lambda c: c[0])


def _apex(mid, b0, b1, f0, f1):
    """Where the lines of both legs meet, if they do."""
    n = len(mid)

    def fit(a, b, sign):
        pts = mid[[(a + sign * k) % n for k in range(2, (sign * (b - a)) % n + 1)]]
        if len(pts) < 3:
            return None
        c = pts.mean(0)
        return c, np.linalg.svd(pts - c)[2][0]

    p, q = fit(b0, b1, -1), fit(f0, f1, 1)
    if p is None or q is None:
        return None
    m = np.column_stack([p[1], -q[1]])
    if abs(np.linalg.det(m)) < 0.2:
        return None
    return p[0] + np.linalg.solve(m, q[0] - p[0])[0] * p[1]


def _rounded(pts, closed):
    """Replaces each vertex (the ends of an open line excepted) by an arc that stays within 0.2 pixel of it."""
    n, out = len(pts), []
    for i in range(n):
        p = pts[i]
        if not closed and i in (0, n - 1):
            out.append([p])
            continue
        a, b = pts[i - 1] - p, pts[(i + 1) % n] - p
        la, lb = np.hypot(*a), np.hypot(*b)
        turn = _turn(-a, b)
        if turn < ARC_STEP_DEG / 4 or not la or not lb:
            out.append([p])
            continue
        d = min(la / 2, lb / 2, 0.4 / np.sin(np.radians(turn / 2)))
        # why: an odd count, so the arc has a middle point to be cut at
        t = np.linspace(0, 1, 2 * int(np.ceil(turn / ARC_STEP_DEG / 2)) + 1)[:, None]
        u, v = p + a / la * d, p + b / lb * d
        out.append((1 - t) ** 2 * u + 2 * t * (1 - t) * p + t ** 2 * v)
    return out


def _close(raw, line):
    """Both lines within MAX_SHIFT_PX of each other."""
    if len(line) < 2:
        return False
    a, b = LineString(raw), LineString(line)
    shapely.prepare([a, b])
    # why: the smooth line has long segments, so its vertices alone would not bound the distance
    dense = shapely.get_coordinates(shapely.segmentize(b, 1.0))
    return (shapely.dwithin(b, shapely.points((raw[:-1] + raw[1:]) / 2), MAX_SHIFT_PX).all()
            and shapely.dwithin(b, shapely.points(raw), MAX_VERTEX_SHIFT_PX).all()
            and shapely.dwithin(a, shapely.points(dense), MAX_SHIFT_PX).all())


def _smooth_piece(verts, start, end, marks, loop):
    """Rounded vertices (one array each) of the smoothed `verts`, from start to end or all around, and their indices."""
    mid = (verts[:-1] + verts[1:]) / 2
    src = np.vstack([start, mid, end])
    at = np.concatenate([[0], np.arange(len(mid)) + 0.5, [len(mid)]])
    for sigma, tol in LEVELS:
        pts = _low_pass(src, sigma, loop)
        idx = np.array([0, len(pts) - 1]) if tol is None else _dp(pts, tol)
        # why: ring of a closed stretch pinned to one junction must not collapse to a line
        if (loop or np.array_equal(start, end)) and len(idx) < 4:
            continue
        got = _with_marks(pts[idx], at[idx], marks)
        if loop:
            parts = _rounded(got[0][:-1], True)
            k = len(parts[0]) // 2
            parts.append(parts[0][:k + 1])
            parts[0] = parts[0][k:]
        else:
            parts = _rounded(got[0], False)
        line = np.vstack(parts)
        if _close(np.vstack([start, verts[1:-1], end]) if len(verts) > 2 else src, line):
            return parts, got[1]
    return None, None


def _low_pass(pts, sigma, loop):
    """Gaussian low-pass with the shrinkage added back; the end points stay, except on a loop."""
    if not sigma or len(pts) < 3:
        return pts
    r = min(4 * sigma, len(pts) - 2)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()

    def blur(p):
        # why: mirroring through the end point keeps it fixed and the line straight there
        if loop:
            q = np.vstack([p[-r - 1:-1], p, p[1:r + 1]])
        else:
            q = np.vstack([2 * p[0] - p[r:0:-1], p, 2 * p[-1] - p[-2:-r - 2:-1]])
        return np.column_stack([np.convolve(q[:, c], k, "valid") for c in (0, 1)])
    once = blur(pts)
    return once + blur(pts - once)


def _dp(src, tol):
    """Indices kept by Douglas-Peucker."""
    n = len(src)
    keep = np.zeros(n, bool)
    keep[[0, -1]] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        v, w = src[b] - src[a], src[a + 1:b] - src[a]
        size = v @ v
        t = np.clip(w @ v / size, 0, 1) if size else np.zeros(len(w))
        d = np.hypot(*(w - t[:, None] * v).T)
        k = int(d.argmax())
        if d[k] > tol:
            keep[a + 1 + k] = True
            stack += [(a, a + 1 + k), (a + 1 + k, b)]
    return np.flatnonzero(keep)


def _with_marks(pts, at, marks):
    """Adds a vertex on the polyline for each vertex index in `marks`; returns points and {mark: position}."""
    if len(marks):
        x = np.column_stack([np.interp(marks, at, pts[:, 0]), np.interp(marks, at, pts[:, 1])])
        pts, at = np.vstack([pts, x]), np.concatenate([at, marks])
        order = np.argsort(at, kind="stable")
        pts, at = pts[order], at[order]
    return pts, at


def _cut(parts, at, marks):
    """Cuts the rounded polyline at the arc middle of each mark -> list of polylines."""
    cuts = [int(np.flatnonzero(at == m)[-1]) for m in marks]
    out, cur, prev = [], [], 0
    for c in cuts:
        mids = parts[c]
        k = len(mids) // 2
        cur += list(parts[prev:c]) + [mids[:k + 1]]
        out.append(np.vstack(cur))
        cur, prev = [mids[k:]], c + 1
    cur += list(parts[prev:])
    out.append(np.vstack(cur))
    return out


def _smooth_line(seq, closed, stretches, px_mm):
    """Sets `smooth` of every stretch of a long line."""
    chunks = [stretches[i].verts[::-1] if rev else stretches[i].verts for i, rev in seq]
    verts = np.vstack([chunks[0]] + [c[1:] for c in chunks[1:]]).astype(float)
    bounds = np.cumsum([0] + [len(c) - 1 for c in chunks])
    n = len(verts) - 1
    mid = (verts[:-1] + verts[1:]) / 2
    corners = _corners(verts, mid, closed, px_mm)
    loop = closed and not corners
    cut = bounds[:-1]
    shift = 0
    if closed:
        # why: a closed line needs a start; a corner is the natural one, else the middle of a straight run
        if corners:
            shift, start = corners[0]
        else:
            shift = _seam(mid)
            start = None
        verts = np.vstack([np.roll(verts[:-1], -shift, 0), verts[(shift) % n][None]])
        mid = np.roll(mid, -shift, 0)
        corners = sorted(((i - shift) % n, p) for i, p in corners)
        cut = np.sort((bounds[:-1] - shift) % n)
        if start is None:
            start = (mid[-1] + mid[0]) / 2
        corners = [(0, start)] + [c for c in corners if c[0] != 0] + [(n, start)]
    else:
        corners = [(0, verts[0])] + [c for c in corners if 0 < c[0] < n] + [(n, verts[-1])]
    junctions = np.array([c for c in cut if 0 < c < n], int)
    # result as one list of polylines per interval between consecutive junctions / corners
    pieces = []
    for (i, p), (j, q) in zip(corners[:-1], corners[1:], strict=True):
        marks = junctions[(junctions > i) & (junctions < j)] - i
        parts, at = _smooth_piece(verts[i:j + 1], p, q, marks, loop)
        if parts is None:
            raw = np.vstack([p, verts[i + 1:j], q])
            lims = [0, *marks, j - i]
            lines = [raw[a:b + 1] for a, b in zip(lims[:-1], lims[1:], strict=True)]
        else:
            lines = _cut(parts, at, marks)
        lims = [i, *(marks + i), j]
        pieces += list(zip(lims[:-1], lims[1:], lines, strict=True))
    for k, (s, rev) in enumerate(seq):
        a, b = (bounds[k] - shift) % n if closed else bounds[k], 0
        b = a + len(chunks[k]) - 1
        mine = [p for p in pieces if a <= p[0] and p[1] <= b]
        if closed and b > n:
            mine += [p for p in pieces if p[1] <= b - n]
        line = np.vstack([mine[0][2]] + [p[2][1:] for p in mine[1:]])
        stretches[s].smooth = line[::-1] if rev else line


def _seam(mid):
    """Vertex index in the middle of the straightest run of a closed line."""
    n = len(mid)
    k = max(1, min(8, n // 8))
    a, b = np.roll(mid, k, 0), np.roll(mid, -k, 0)
    off = np.hypot(*(mid - (a + b) / 2).T)
    return int((off + np.roll(off, 1)).argmin())


def _place(stretches, pinned):
    """Final polylines: stretches meeting at a junction end at one shared point."""
    spots = {e: np.array(e, float) for e in pinned}
    for s in stretches:
        if s.raw and s.ends:
            for e in s.ends:
                spots[e] = np.array(e, float)
    hosts = {}
    for s in stretches:
        if s.ends:
            for e, p in zip(s.ends, (s.smooth[0], s.smooth[-1]), strict=True):
                hosts.setdefault(e, []).append(p)
    for e, ps in hosts.items():
        # why: only the line that runs through the junction moved away from the pixel vertex
        moved = [p for p in ps if np.hypot(*(p - e)) > 1e-9]
        spots.setdefault(e, moved[0] if moved else np.array(e, float))
    lines = []
    for s in stretches:
        line = (s.verts.astype(float) if s.raw else s.smooth).copy()
        if s.ends:
            line[0], line[-1] = spots[s.ends[0]], spots[s.ends[1]]
        else:
            line[-1] = line[0]
        lines.append(line)
    return lines


def _strayed(stretches, lines):
    """Junctions whose move left a pixel of the boundary more than MAX_VERTEX_SHIFT_PX away."""
    found = set()
    for s, line in zip(stretches, lines, strict=True):
        if s.ends and not s.raw:
            geo = LineString(line)
            shapely.prepare(geo)
            for e, head in zip(s.ends, (s.verts[:8], s.verts[-8:]), strict=True):
                if not shapely.dwithin(geo, shapely.points(head[1:-1]), MAX_VERTEX_SHIFT_PX).all():
                    found.add(e)
    return found


def _conflicts(stretches, lines):
    """Stretches that cross themselves or each other."""
    geo = [LineString(v) for v in lines]
    bad = {i for i, g in enumerate(geo) if not g.is_simple or len(shapely.remove_repeated_points(g).coords) < 2}
    bad |= {i for i, g in enumerate(geo) if g.is_closed and len(lines[i]) < 4}
    a, b = shapely.STRtree(geo).query(geo, predicate="intersects")
    for i, j in zip(a, b, strict=True):
        if i >= j:
            continue
        shared = set(map(tuple, lines[i][[0, -1]])) & set(map(tuple, lines[j][[0, -1]]))
        hit = geo[i].intersection(geo[j])
        if hit.length > 0 or {tuple(c) for c in shapely.get_coordinates(hit)} - shared:
            bad |= {i, j}
    return bad


def _rings(stretches, inside):
    """Rings of the 4-connected region, region on the left: [[(stretch, reversed)]]."""
    start = {}
    edges = []
    for i, s in enumerate(stretches):
        on_left = inside(s.left)
        if on_left == inside(s.right):
            continue
        rev = not on_left
        edges.append((i, rev))
        if s.ends:
            d = (s.d1 + 2) % 4 if rev else s.d0
            start[(s.ends[1 if rev else 0], d)] = (i, rev)
    out, seen = [], set()
    for first in edges:
        if first in seen:
            continue
        path, cur = [], first
        while cur not in seen:
            seen.add(cur)
            path.append(cur)
            s, rev = stretches[cur[0]], cur[1]
            if not s.ends:
                break
            end = s.ends[0 if rev else 1]
            d = (s.d0 + 2) % 4 if rev else s.d1
            cur = next(start[(end, (d + t) % 4)] for t in (-1, 0, 1) if (end, (d + t) % 4) in start)
        # why: a ring that meets itself at a junction is cut there, so each ring stays simple
        stack = []
        for e in path:
            stack.append(e)
            s = stretches[e[0]]
            if not s.ends:
                continue
            end = s.ends[0 if e[1] else 1]
            for k in range(len(stack) - 1, -1, -1):
                q = stretches[stack[k][0]]
                if q.ends[1 if stack[k][1] else 0] == end:
                    out.append((first, stack[k:]))
                    del stack[k:]
                    break
    for e in edges:
        if not stretches[e[0]].ends:
            out.append((e, [e]))
    return out


def _polygons(stretches, lines, inside, lab):
    """([(polygon, its stretches)], stretches of the invalid ones) of one region."""
    comp = cv2.connectedComponents(inside(lab).astype(np.uint8), connectivity=4)[1]
    size = np.bincount(comp.ravel())
    groups = {}
    for (i, rev), ring in _rings(stretches, inside):
        s = stretches[i]
        (x, y), d = (s.verts[-1], (s.d1 + 2) % 4) if rev else (s.verts[0], s.d0)
        dy, dx = LEFT[d]
        groups.setdefault(comp[y + dy, x + dx], []).append(ring)
    polys, bad = [], set()
    for c, rings in sorted(groups.items()):
        pts = [np.vstack([lines[i][::-1][:-1] if rev else lines[i][:-1] for i, rev in r]) for r in rings]
        if any(len(p) < 3 for p in pts):
            bad |= {i for r in rings for i, _ in r}
            continue
        # why: Y points down, so the ring with the region on its left has a negative signed area
        area = [LinearRing(p).is_ccw for p in pts]
        outer = [k for k, ccw in enumerate(area) if not ccw]
        if len(outer) != 1:
            bad |= {i for r in rings for i, _ in r}
            continue
        poly = Polygon(pts[outer[0]], [p for k, p in enumerate(pts) if k != outer[0]])
        if not poly.is_valid or poly.area < size[c] / 4:
            bad |= {i for r in rings for i, _ in r}
        polys.append((poly, {i for r in rings for i, _ in r}))
    return polys, bad


def _overlaps(regions):
    """Stretches of the polygons that overlap: lines meeting at a junction can swap sides without crossing."""
    polys = [p for r in regions for p in r]
    geo = [p for p, _ in polys]
    total = sum(p.area for p in geo)
    if abs(total - shapely.union_all(geo).area) <= 1e-9 * max(total, 1):
        return set()
    bad = set()
    for i, j in zip(*shapely.STRtree(geo).query(geo, predicate="intersects"), strict=True):
        if i < j and geo[i].intersection(geo[j]).area > 1e-9:
            bad |= polys[i][1] | polys[j][1]
    return bad


def trace(sil_m, masks, px_mm):
    """(silhouette polygons, [polygons of each mask]) in pixels, Y down; neighbours share their boundary."""
    lab = np.where(sil_m > 0, 0, OUTSIDE).astype(np.int32)
    for k, m in enumerate(masks):
        lab[m > 0] = k + 1
    lab = np.pad(lab, 1, constant_values=OUTSIDE)
    stretches = _stretches(lab)
    if not stretches:
        return [], [[] for _ in masks]
    leg = int(max(CORNER_LEG_MM / px_mm, 10))
    for seq, closed in _lines(stretches, _pairs(stretches, leg)):
        _smooth_line(seq, closed, stretches, px_mm)
    # why: the bare base is checked as well; a sliver of it could flip over without any line crossing
    tests = [lambda v: v >= 0] + [lambda v, k=k: v == k for k in range(len(masks) + 1)]
    pinned = _strayed(stretches, _place(stretches, ()))
    while True:
        lines = _place(stretches, pinned)
        bad = _conflicts(stretches, lines)
        regions = []
        if not bad:
            got = [_polygons(stretches, lines, t, lab) for t in tests]
            regions = [g[0] for g in got]
            bad = set().union(*(g[1] for g in got)) or _overlaps(regions[1:])
        fresh = [i for i in bad if not stretches[i].raw]
        if not fresh:
            if bad:
                raise ValueError("Contornos inválidos na malha.")
            break
        for i in fresh:
            stretches[i].raw = True
    moved = [[shapely.transform(p, lambda c: c - 1) for p, _ in r] for r in regions]
    return moved[0], moved[2:]
