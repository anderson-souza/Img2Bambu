import io
import json
import os
import zipfile

import numpy as np
import pytest
from PIL import Image
from test_core import synthetic

from img2bambu import project, segment
from img2bambu.params import Params

LIMITS = {"bg_tolerance": (1, 120), "n_colors": (2, 8), "filaments": (0, 8), "smooth": (0, 5),
          "min_detail_mm": (0.1, 3.0), "streak_radius_mm": (0.0, 3.0), "width_mm": (10, 500),
          "base_mm": (1, 50), "relief_mm": (0.2, 10)}


def png(rgba):
    b = io.BytesIO()
    Image.fromarray(rgba).save(b, "PNG")
    return b.getvalue()


def make(smooth=0, rgba=None):
    """A project with every palette property away from what detection suggests."""
    rgba = synthetic() if rgba is None else rgba
    p = Params(width_mm=90.0, n_colors=4, smooth=smooth, min_detail_mm=0.7, protect_lines=True)
    an = segment.analyze(rgba, p)
    pal = an.palette
    pal.samples[1] = (200, 160, 30)
    pal.colors[2] = (1, 2, 3)
    pal.edited = {1, 2}
    pal.merges = {3: 2}
    pal.streak, pal.outline = {1}, {0, 2}
    pal.base_index = 0
    return project.Project("abelha.png", png(rgba), p, pal, an, "M1", "P1", "F1", False, "peça")


def members(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_save_writes_the_format(tmp_path):
    p, path = make(), str(tmp_path / "x.i2b")
    project.save(path, p)
    m = members(path)
    assert set(m) == {"project.json", "image", "labels.png", "lab.png"}
    assert m["image"] == p.image
    d = json.loads(m["project.json"])
    assert d == json.loads(json.dumps(project.settings(p)))
    assert d["format"] == 1 and d["presets"] == {"machine": "M1", "process": "P1", "filament": "F1"}
    assert d["name"] == "peça" and d["check"] is False and d["palette"]["merges"] == [[3, 2]]
    lab = np.array(Image.open(io.BytesIO(m["labels.png"])))
    assert np.array_equal(lab.astype(int) - 1, p.analysis.labels)


def test_save_leaves_group_and_other_permissions_alone(tmp_path):
    path, plain = tmp_path / "x.i2b", tmp_path / "plain"
    plain.write_bytes(b"")
    project.save(str(path), make())
    assert path.stat().st_mode == plain.stat().st_mode


def test_failed_save_keeps_old_file(tmp_path, monkeypatch):
    path, p = tmp_path / "x.i2b", make()
    path.write_bytes(b"old")

    def broken(*_):
        raise OSError("disco cheio")
    for target in ("replace", "fsync"):
        with monkeypatch.context() as m:
            m.setattr(os, target, broken)
            with pytest.raises(OSError, match="disco cheio"):
                project.save(str(path), p)
        assert path.read_bytes() == b"old" and os.listdir(tmp_path) == ["x.i2b"]


def reload(tmp_path, p):
    path = str(tmp_path / "x.i2b")
    project.save(path, p)
    return project.load(path, LIMITS)


def same_masks(a, b):
    (sil_a, ma), (sil_b, mb) = (segment.build_masks(x.analysis, x.palette, x.params) for x in (a, b))
    assert ma
    assert np.array_equal(sil_a, sil_b) and ma.keys() == mb.keys()
    assert all(np.array_equal(ma[k], mb[k]) for k in ma)


def noisy():
    """Colors that detection, with and without smoothing, does not see as exact values."""
    rgba = synthetic()
    noise = np.random.default_rng(3).integers(-12, 13, rgba.shape[:2] + (3,))
    rgba[..., :3] = np.clip(rgba[..., :3].astype(int) + noise, 0, 255)
    return rgba


def test_round_trip_keeps_every_value(tmp_path):
    p = make()
    q = reload(tmp_path, p)
    assert q.image_name == "abelha.png" and q.image == p.image and q.notes == []
    assert (q.machine, q.process, q.filament, q.check, q.name) == ("M1", "P1", "F1", False, "peça")
    assert q.params == p.params and q.palette == p.palette
    assert np.array_equal(q.rgba, synthetic())
    a, b = p.analysis, q.analysis
    for k in ("rgba", "sil", "labels", "centers", "lab"):
        x, y = getattr(a, k), getattr(b, k)
        assert np.array_equal(x, y) and x.dtype == y.dtype, k
    assert a.samples == b.samples and a.offset == b.offset and a.base == b.base


def test_masks_equal_after_round_trip(tmp_path):
    for smooth in (0, 5):
        p = make(smooth, noisy())
        same_masks(p, reload(tmp_path, p))
        fresh = segment.analyze(noisy(), p.params)      # no edited sample: labels come from the file as they are
        p.analysis, p.palette = fresh, fresh.palette
        same_masks(p, reload(tmp_path, p))


def test_later_sample_edit_gives_same_masks(tmp_path):
    for smooth in (0, 5):
        p = make(smooth, noisy())
        q = reload(tmp_path, p)
        before = segment.assign(p.analysis, p.palette)
        for x in (p, q):
            x.palette.samples[0] = (190, 150, 40)
            x.palette.samples[1] = (30, 30, 30)
        assert not np.array_equal(before, segment.assign(p.analysis, p.palette))
        assert np.array_equal(segment.assign(p.analysis, p.palette), segment.assign(q.analysis, q.palette))
        same_masks(p, q)
