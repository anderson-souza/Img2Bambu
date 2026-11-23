from dataclasses import dataclass

import cv2
import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from .params import Palette, Params, hex_color


@dataclass
class Part:
    name: str
    color: tuple
    mesh: trimesh.Trimesh


def to_polys(m, mm_per_px_up, simplify_mm):
    """Binary mask (row 0 = top) -> shapely polygons in mm, Y up."""
    cs, hier = cv2.findContours(m.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return []
    hier = hier[0]
    h = m.shape[0]

    def conv(c):
        c = c[:, 0, :].astype(float)
        return np.column_stack([c[:, 0] * mm_per_px_up, (h - c[:, 1]) * mm_per_px_up])

    polys = []
    for i, c in enumerate(cs):
        if hier[i][3] != -1 or len(c) < 3:
            continue
        holes, j = [], hier[i][2]
        while j != -1:
            if len(cs[j]) >= 3:
                holes.append(conv(cs[j]))
            j = hier[j][0]
        p = Polygon(conv(c), holes).buffer(0).simplify(simplify_mm, preserve_topology=True)
        if not p.is_empty:
            polys.append(p)
    # why: diagonal pixel links leave regions/holes touching at a single point,
    # which extrudes non-manifold; a 1 µm inset splits those points apart
    g = unary_union(polys).buffer(-1e-3, join_style="mitre")
    if g.is_empty:
        return []
    return list(g.geoms) if isinstance(g, MultiPolygon) else [g]


def extrude(polys, z0, height):
    meshes = []
    for p in polys:
        for q in (p.geoms if isinstance(p, MultiPolygon) else [p]):
            if q.area < 0.05:
                continue
            mesh = trimesh.creation.extrude_polygon(q, height)
            mesh.apply_translation([0, 0, z0])
            meshes.append(mesh)
    if not meshes:
        return None
    m = trimesh.util.concatenate(meshes)
    m.merge_vertices()
    return m


def build_parts(sil_m, masks, palette: Palette, params: Params):
    mpp_up = params.width_mm / sil_m.shape[1]
    base = extrude(to_polys(sil_m, mpp_up, params.simplify_mm), 0, params.base_mm)
    if base is None:
        raise ValueError("Silhueta vazia após limpeza.")
    parts = [Part(f"Base {hex_color(palette.colors[palette.base_index])}",
                  palette.colors[palette.base_index], base)]
    for c, m in masks.items():
        mesh = extrude(to_polys(m, mpp_up, params.simplify_mm), params.base_mm, params.relief_mm)
        if mesh is not None:
            parts.append(Part(f"Cor {hex_color(palette.colors[c])}", palette.colors[c], mesh))
    bad = [p.name for p in parts if not p.mesh.is_watertight]
    if bad:
        raise ValueError("Malha não fechada (watertight) em: " + ", ".join(bad))
    return parts
