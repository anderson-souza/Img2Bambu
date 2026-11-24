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
