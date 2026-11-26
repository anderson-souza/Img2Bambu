import numpy as np
import shapely
from shapely.geometry import Polygon, box

# why: the CLI always writes this position, whatever the bed size
DEFAULT = (15.0, 220.0)
BRIM = 3.2
CLEARANCE = 2.0
SLACK = 1.5
STEP = 5.0


def side(n_colors, layer_mm, prime_volume=45.0):
    """Estimated side (mm, without brim) of the square tower.

    why: fitted to Bambu Studio 2.9.1 slices (2 to 8 colors, 0.08 to 0.28 mm layers); the CLI does not
    report the size before slicing.
    """
    return float(np.sqrt((n_colors - 1) * (77.6 / layer_mm + 100) * prime_volume / 45) + SLACK)


def footprint(mesh, center):
    """Outline of the base mesh, centred on the bed like `write_minimal_3mf` places it."""
    tri = mesh.triangles
    low = tri[(tri[:, :, 2] <= mesh.bounds[0][2] + 1e-6).all(axis=1)][:, :, :2]
    mid = (mesh.bounds[0][:2] + mesh.bounds[1][:2]) / 2
    polys = shapely.polygons(low - mid + np.asarray(center))
    return shapely.union_all(polys[shapely.area(polys) > 1e-9])


def place(bed, exclude, part, size):
    """Free tower position (lower-left corner, mm) closest to the default one; None when there is none."""
    x0, y0, x1, y1 = bed[:4]
    lo = np.array([x0, y0]) + BRIM
    hi = np.array([x1, y1]) - BRIM - size
    if (hi < lo).any():
        return None
    blocked = shapely.union_all([part.buffer(CLEARANCE)] + ([Polygon(exclude)] if len(exclude) > 2 else []))

    def free(p):
        return (np.array(p) >= lo).all() and (np.array(p) <= hi).all() and not blocked.intersects(
            box(p[0] - BRIM, p[1] - BRIM, p[0] + size + BRIM, p[1] + size + BRIM))

    if free(DEFAULT):
        return DEFAULT
    xs, ys = (np.append(np.arange(a, b, STEP), b) for a, b in zip(lo, hi, strict=True))
    for x, y in sorted(((float(x), float(y)) for x in xs for y in ys),
                       key=lambda p: (p[0] - DEFAULT[0]) ** 2 + (p[1] - DEFAULT[1]) ** 2):
        if free((x, y)):
            return round(x, 3), round(y, 3)
    return None
