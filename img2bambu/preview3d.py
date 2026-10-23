from dataclasses import dataclass

import numpy as np

from . import pipeline
from .params import Params, Palette


@dataclass
class MeshData:
    name: str
    color: tuple
    vertices: bytes      # float32 interleaved pos(3)+normal(3), flat-shaded, 24 B/vertex
    lo: tuple
    hi: tuple


def mesh_data(part):
    m = part.mesh
    pos = m.triangles.reshape(-1, 3)
    nrm = np.repeat(m.face_normals, 3, axis=0)
    vertices = np.hstack([pos, nrm]).astype(np.float32).tobytes()
    lo, hi = m.bounds
    return MeshData(part.name, tuple(part.color), vertices, tuple(lo), tuple(hi))


def build(an, palette: Palette, params: Params):
    return [mesh_data(p) for p in pipeline.model(an, palette, params)]
