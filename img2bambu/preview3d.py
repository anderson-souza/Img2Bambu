from dataclasses import dataclass

import numpy as np

from . import pipeline
from .bambu import fits
from .params import Palette, Params


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


def size(meshes):
    lo = np.min([m.lo for m in meshes], axis=0)
    hi = np.max([m.hi for m in meshes], axis=0)
    return tuple(float(v) for v in hi - lo)


def describe(meshes, bed):
    x, y, z = size(meshes)
    n = len(meshes)
    lines = [f"{x:.1f} × {y:.1f} × {z:.1f} mm — {n} {'parte' if n == 1 else 'partes'}"]
    if bed is None:
        lines.append("Mesa indisponível")
    elif not fits((x, y, z), bed):
        dims = [bed[2] - bed[0], bed[3] - bed[1]] + ([bed[4]] if bed[4] is not None else [])
        lines.append(f"⚠ Modelo maior que a mesa ({' × '.join(f'{v:g}' for v in dims)} mm).")
    return "\n".join(lines)
