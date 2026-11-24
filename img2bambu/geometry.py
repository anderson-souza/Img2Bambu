from dataclasses import dataclass

import numpy as np
import shapely
import trimesh
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union

from . import contours
from .params import Palette, Params, hex_color


@dataclass
class Part:
    name: str
    color: tuple
    mesh: trimesh.Trimesh


def to_polys(sil_m, masks, mpp_up):
    """Binary masks (row 0 = top) -> (silhouette, [mask]) polygons in mm, Y up; neighbours share boundaries."""
    base, colors = contours.trace(sil_m, masks, mpp_up)
    if not base:
        return [], [[] for _ in masks]
    h = sil_m.shape[0]
    lo, hi = (np.array([f(np.flatnonzero(sil_m.any(a))) for a in (0, 1)]) for f in (np.min, np.max))
    b = np.array(unary_union(base).bounds)
    # why: smoothing may move the extreme points by a fraction of a pixel; the size asked for is kept
    scale = (hi + 1 - lo) / (b[2:] - b[:2])

    def to_mm(c):
        return ((c - b[:2]) * scale + lo - (0, h)) * (mpp_up, -mpp_up)

    def finish(polys, inset):
        # why: regions/holes linked by a pixel diagonal touch at a single point, which extrudes
        # non-manifold; a tiny inset splits those points apart
        out = []
        for p in polys:
            g = shapely.transform(p, to_mm).buffer(-inset, join_style="mitre", mitre_limit=2)
            # why: earcut skips vertices a few nm apart and leaves the mesh open
            out += [q for q in shapely.get_parts(shapely.remove_repeated_points(g, 1e-4)) if not q.is_empty]
        return out
    # why: the base recedes at most 2x its inset, so a raised part never sticks out of it
    return finish(base, 5e-4), [finish(p, 1e-3) for p in colors]


def extrude(polys, z0, height):
    meshes = []
    for p in polys:
        for q in (p.geoms if isinstance(p, MultiPolygon) else [p]):
            if q.area < 0.05:
                continue
            mesh = trimesh.creation.extrude_polygon(q, height)
            if not mesh.is_watertight:
                # why: earcut may fail on holes that almost touch; half a micron apart is enough
                parts = [g for g in shapely.get_parts(q.buffer(-5e-4, join_style="mitre")) if g.area > 0]
                mesh = trimesh.util.concatenate([trimesh.creation.extrude_polygon(g, height) for g in parts])
            mesh.apply_translation([0, 0, z0])
            meshes.append(mesh)
    if not meshes:
        return None
    m = trimesh.util.concatenate(meshes)
    m.merge_vertices()
    return m


def build_parts(sil_m, masks, palette: Palette, params: Params):
    mpp_up = params.width_mm / sil_m.shape[1]
    base_polys, color_polys = to_polys(sil_m, list(masks.values()), mpp_up)
    base = extrude(base_polys, 0, params.base_mm)
    if base is None:
        raise ValueError("Silhueta vazia após limpeza.")
    parts = [Part(f"Base {hex_color(palette.colors[palette.base_index])}",
                  palette.colors[palette.base_index], base)]
    for c, polys in zip(masks, color_polys, strict=True):
        mesh = extrude(polys, params.base_mm, params.relief_mm)
        if mesh is not None:
            parts.append(Part(f"Cor {hex_color(palette.colors[c])}", palette.colors[c], mesh))
    bad = [p.name for p in parts if not p.mesh.is_watertight]
    if bad:
        raise ValueError("Malha não fechada (watertight) em: " + ", ".join(bad))
    return parts
