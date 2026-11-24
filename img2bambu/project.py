import io
import json
import os
import secrets
import zipfile
from contextlib import suppress
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from .params import Palette, Params
from .segment import Analysis

FORMAT = 1
SUFFIX = ".i2b"
# invariant: every key here has a control in the window; a new one takes its default from Params in older files
PARAM_KEYS = ("background", "bg_tolerance", "n_colors", "filaments", "smooth", "min_detail_mm", "streak_radius_mm",
              "protect_lines", "width_mm", "base_mm", "relief_mm")
PRESET_KEYS = ("machine", "process", "filament")
# why: a received file must not reach Pillow decoders that run programs (EPS calls Ghostscript)
IMAGE_FORMATS = ("PNG", "JPEG", "MPO", "WEBP", "BMP", "GIF", "TIFF", "AVIF")


class ProjectError(ValueError):
    """Problem with a project, with a message in Portuguese for the user."""


@dataclass
class Project:
    image_name: str
    image: bytes                   # the image file as it was loaded
    params: Params
    palette: Palette
    analysis: Analysis
    machine: str = ""
    process: str = ""
    filament: str = ""
    check: bool = True
    name: str = ""
    rgba: np.ndarray = None        # decoded image, filled by load
    notes: list = field(default_factory=list)   # what load had to replace, for the log


def settings(p: Project):
    """The JSON part of the file; equal dicts mean nothing to save."""
    pal, an = p.palette, p.analysis
    return {
        "format": FORMAT,
        "image_name": p.image_name,
        "params": {k: getattr(p.params, k) for k in PARAM_KEYS},
        "palette": {
            "colors": [list(c) for c in pal.colors],
            "samples": [list(c) for c in pal.samples],
            "base_index": pal.base_index,
            "merges": [[a, b] for a, b in sorted(pal.merges.items())],
            "streak": sorted(pal.streak), "outline": sorted(pal.outline), "edited": sorted(pal.edited),
        },
        "detection": {
            "offset": list(an.offset),
            "base": an.base,
            "centers": [[float(v) for v in c] for c in an.centers],
            "samples": [list(c) for c in an.samples],
        },
        "presets": {k: getattr(p, k) for k in PRESET_KEYS},
        "check": p.check,
        "name": p.name,
    }


def check_image(data):
    with Image.open(io.BytesIO(data)) as im:
        if im.format not in IMAGE_FORMATS:
            raise ProjectError(f"formato de imagem não aceito em projetos: {im.format}.")
        return im.size


def _png(arr):
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "PNG")
    return b.getvalue()


def _pack(p: Project):
    check_image(p.image)
    an = p.analysis
    lab = np.zeros(an.sil.shape + (3,), np.uint8)
    lab[an.sil] = an.lab.astype(np.uint8)        # why: OpenCV LAB of 8-bit pixels holds whole numbers 0-255
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", json.dumps(settings(p), ensure_ascii=False, indent=1))
        z.writestr("image", p.image, zipfile.ZIP_STORED)
        z.writestr("labels.png", _png((an.labels + 1).astype(np.uint8)), zipfile.ZIP_STORED)
        z.writestr("lab.png", _png(lab), zipfile.ZIP_STORED)
    return b.getvalue()


def save(path, p: Project):
    data = _pack(p)
    path = os.path.realpath(path)
    # why: the old file is replaced only after the new one is whole; tempfile would make it readable by the owner only
    tmp = f"{path}.{secrets.token_hex(4)}.tmp"
    try:
        with open(tmp, "xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with suppress(OSError):
            os.remove(tmp)
        raise
