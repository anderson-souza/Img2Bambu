import io
import json
import ntpath
import os
import secrets
import zipfile
from contextlib import suppress
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from .params import LIMITS, Palette, Params
from .segment import Analysis, load_image

FORMAT = 1
SUFFIX = ".i2b"
MAX_MEMBER = 1 << 30
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
    tmp = os.path.join(os.path.dirname(path), f".{secrets.token_hex(4)}.tmp")
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


def _file_name(value, notes):
    # why: the name is joined to the output folder, so a received file must not choose another folder
    name = ntpath.basename(value)            # invariant: handles both separators and drives on every system
    if name != value:
        notes.append(f"Nome '{value}' do projeto reduzido a '{name}'.")
    return name


def _bad(what):
    return ProjectError(f"valor inválido no projeto: {what}.")


def _typed(value, kind, what):
    # why: bool is an int in Python, but true is not a number in the file
    ok = type(value) in (int, float) if kind is float else type(value) is kind
    if not ok:
        raise _bad(what)
    if kind is str:
        try:
            value.encode()                  # why: a lone surrogate would open and then make saving fail
        except UnicodeEncodeError as e:
            raise _bad(what) from e
    return value


def _number(value, kind, lo, hi, what):
    _typed(value, kind, what)
    if not lo <= value <= hi:               # why: written this way NaN is refused too
        raise _bad(what)
    return value


def _list(value, what, n=None):
    _typed(value, list, what)
    if n is not None and len(value) != n:
        raise _bad(what)
    return value


def _setting(d, key, default, notes):
    if key not in d:
        notes.append(f"Ajuste '{key}' ausente no projeto: usado o padrão ({default}).")
        return default
    return _typed(d[key], type(default), key)


def _param(d, key, notes):
    value = _setting(d, key, getattr(Params(), key), notes)
    if key == "background" and value not in ("alpha", "color"):
        raise _bad(key)
    if key in LIMITS:
        _number(value, type(getattr(Params(), key)), *LIMITS[key], key)
    return value


def _rgbs(rows, n, what):
    return [tuple(_number(v, int, 0, 255, what) for v in _list(c, what, 3)) for c in _list(rows, what, n)]


def _labels(value, n, what):
    return {_number(v, int, 0, n - 1, what) for v in _list(value, what)}


def _palette(d):
    lo, hi = LIMITS["n_colors"]
    n = len(_list(d["colors"], "colors"))
    _number(n, int, lo, hi, "colors")
    merges = {}
    for pair in _list(d["merges"], "merges"):
        a, b = (_number(v, int, 0, n - 1, "merges") for v in _list(pair, "merges", 2))
        if a in merges:
            raise _bad("merges")
        merges[a] = b
    for i in merges:
        seen = set()
        while i in merges:
            if i in seen:
                raise _bad("merges")
            seen.add(i)
            i = merges[i]
    pal = Palette(_rgbs(d["colors"], n, "colors"), _number(d["base_index"], int, 0, n - 1, "base_index"), merges,
                  _labels(d["streak"], n, "streak"), _labels(d["outline"], n, "outline"),
                  _rgbs(d["samples"], n, "samples"), _labels(d["edited"], n, "edited"))
    if pal.resolve(pal.base_index) != pal.base_index:
        raise _bad("base_index")
    if pal.streak & pal.outline:
        raise _bad("outline")
    return pal


def _member(z, name):
    if z.getinfo(name).file_size > MAX_MEMBER:
        raise ProjectError(f"parte grande demais: {name}.")
    return z.read(name)


def load(path):
    """Reads a project. ProjectError or OSError leaves nothing changed."""
    with open(path, "rb") as f:
        try:
            with zipfile.ZipFile(f) as z:
                d = _typed(json.loads(_member(z, "project.json")), dict, "project.json")
                if _number(d["format"], int, 1, float("inf"), "format") > FORMAT:
                    raise ProjectError("Este projeto foi salvo por uma versão mais nova do Img2Bambu.")
                return _build(d, *(_member(z, n) for n in ("image", "labels.png", "lab.png")))
        except ProjectError:
            raise
        except KeyError as e:
            raise ProjectError(f"falta uma parte do projeto: {e.args[0]}") from e
        except Exception as e:  # noqa: BLE001 — why: a damaged ZIP, JSON or image raises many unrelated types
            raise ProjectError(f"arquivo danificado ou que não é um projeto do Img2Bambu ({e}).") from e


def _detection_images(labels_png, lab_png, n, offset, image_size):
    """(labels, lab) arrays; sizes are compared before any pixel is decoded."""
    y0, x0 = offset
    with Image.open(io.BytesIO(labels_png), formats=["PNG"]) as a, \
            Image.open(io.BytesIO(lab_png), formats=["PNG"]) as b:
        if (a.mode, b.mode) != ("L", "RGB") or a.size != b.size \
                or x0 + a.width > image_size[0] or y0 + a.height > image_size[1]:
            raise ProjectError("a detecção de cores não corresponde à imagem do projeto.")
        labels, lab = np.array(a).astype(int) - 1, np.array(b)
    if labels.max() >= n or (labels < 0).all():
        raise ProjectError("a detecção de cores não corresponde à paleta do projeto.")
    return labels, lab


def _build(d, image, labels_png, lab_png):
    notes = []
    image_name = _file_name(_typed(d["image_name"], str, "image_name"), notes)
    raw = _typed(d.get("params", {}), dict, "params")
    params = Params(**{k: _param(raw, k, notes) for k in PARAM_KEYS})
    det = _typed(d["detection"], dict, "detection")
    palette = _palette(_typed(d["palette"], dict, "palette"))
    n = len(palette.colors)
    raw = _typed(d.get("presets", {}), dict, "presets")
    presets = {k: _setting(raw, k, "", notes) for k in PRESET_KEYS}
    check = _setting(d, "check", True, notes)
    name = _file_name(_setting(d, "name", os.path.splitext(image_name)[0], notes), notes)
    # why: k-means adds up in float32, so a center of a large white area drifts past 255; kept exact, never clipped
    centers = [[_number(v, float, -10, 300, "centers") for v in _list(c, "centers", 3)]
               for c in _list(det["centers"], "centers", n)]
    samples = tuple(_rgbs(det["samples"], n, "samples"))
    offset = tuple(_number(v, int, 0, 1 << 30, "offset") for v in _list(det["offset"], "offset", 2))
    base = _number(det["base"], int, 0, n - 1, "base")

    labels, lab = _detection_images(labels_png, lab_png, n, offset, check_image(image))
    rgba = load_image(io.BytesIO(image))
    sil = labels >= 0
    (y0, x0), (h, w) = offset, labels.shape
    an = Analysis(rgba[y0:y0 + h, x0:x0 + w].copy(), sil, labels, palette, "", np.array(centers, np.float32),
                  lab[sil].astype(np.float32), samples, offset, base)
    return Project(image_name, image, params, palette, an, **presets, check=check, name=name, rgba=rgba, notes=notes)
