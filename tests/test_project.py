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
    return project.load(path)


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


def test_mostly_white_image_round_trips(tmp_path):
    drifted = 0
    for size, n in ((300, 3), (600, 2), (600, 3), (1000, 3)):
        rgba = np.full((size, size, 4), 255, np.uint8)
        rgba[: size // 5, :, 1:3] = 0
        rgba[0, 0, 3] = 0                         # keeps the silhouette mode on alpha
        an = segment.analyze(rgba, Params(n_colors=n))
        drifted += float(an.centers.max()) > 255
        p = project.Project("b.png", png(rgba), Params(n_colors=n), an.palette, an)
        q = reload(tmp_path, p)
        assert np.array_equal(q.analysis.centers, an.centers) and q.palette == p.palette
    assert drifted


def test_object_far_from_the_corner_round_trips(tmp_path):
    rgba = np.zeros((400, 6000, 4), np.uint8)
    rgba[:, 5600:] = synthetic()
    p = make(rgba=rgba)
    assert p.analysis.offset[1] > 5600
    q = reload(tmp_path, p)
    assert q.analysis.offset == p.analysis.offset and np.array_equal(q.analysis.rgba, p.analysis.rgba)


def test_longest_file_name_is_saved(tmp_path):
    path = tmp_path / ("a" * 251 + ".i2b")
    project.save(str(path), make())
    assert os.listdir(tmp_path) == [path.name]


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


def rewrite(path, changes):
    """Replaces members of a project file; None removes one."""
    m = members(path)
    m.update(changes)
    with zipfile.ZipFile(path, "w") as z:
        for n, data in m.items():
            if data is not None:
                z.writestr(n, data)


def edit_json(path, keys, value):
    d = json.loads(members(path)["project.json"])
    target = d
    for k in keys[:-1]:
        target = target[k]
    target[keys[-1]] = value
    rewrite(path, {"project.json": json.dumps(d)})


@pytest.fixture
def saved(tmp_path):
    path = str(tmp_path / "x.i2b")

    def fresh():
        project.save(path, make())
        return path
    fresh()
    return fresh


INVALID = [
    (("format",), "1"), (("format",), True), (("format",), 0),
    (("image_name",), 3), (("name",), None), (("check",), 1), (("presets",), []), (("presets", "machine"), 1),
    (("params",), []), (("params", "background"), "x"), (("params", "protect_lines"), 1),
    (("params", "n_colors"), 3.0), (("params", "n_colors"), True), (("params", "width_mm"), "150"),
    (("params", "width_mm"), float("nan")), (("params", "width_mm"), float("inf")), (("params", "width_mm"), True),
    (("palette", "colors", 0), [0, 0]), (("palette", "colors", 0), [0, 0, 256]), (("palette", "colors", 0), [0, 0, -1]),
    (("palette", "colors", 0), [0, 0, 1.5]), (("palette", "samples"), [[0, 0, 0]]), (("palette", "colors"), []),
    (("palette", "colors"), [[0, 0, 0]] * 9), (("palette", "base_index"), 4), (("palette", "base_index"), -1),
    (("palette", "base_index"), 3), (("palette", "merges"), [[3, 4]]), (("palette", "merges"), [[3]]),
    (("palette", "merges"), [[1, 2], [2, 1]]), (("palette", "merges"), [[1, 1]]),
    (("palette", "merges"), [[3, 2], [3, 1]]), (("palette", "streak"), [4]), (("palette", "streak"), [0]),
    (("palette", "outline"), [-1]), (("palette", "edited"), ["1"]), (("palette", "edited"), 1),
    (("detection", "base"), 4), (("detection", "centers"), [[0, 0, 0]]),
    (("detection", "centers", 0), [0, 0, float("nan")]), (("detection", "samples"), []),
    (("detection", "centers", 0), [0, 0, 301]), (("detection", "centers", 0), [-11, 0, 0]),
    (("detection", "centers", 0), [0, 0]), (("detection", "samples", 0), [0, 0, 256]),
    (("detection", "samples", 0), [0, -1, 0]), (("detection", "samples", 0), [0, 0]),
    (("palette", "edited"), [4]), (("palette", "edited"), [-1]), (("palette", "outline"), [4]),
    (("palette", "streak"), [-1]), (("palette", "samples", 0), [0, 0, 256]),
    (("image_name",), "a\ud800b"), (("name",), "\ud800"), (("presets", "process"), "\ud800"),
    (("detection", "offset"), [0]), (("detection", "offset"), [-1, 0]),
]


def test_invalid_values_are_refused(saved):
    for keys, value in INVALID:
        path = saved()
        edit_json(path, keys, value)
        with pytest.raises(project.ProjectError, match="valor inválido no projeto"):
            project.load(path)
            pytest.fail(f"accepted {keys} = {value!r}")
    for part in ("palette", "detection"):
        for v in (0, 255):
            path = saved()
            edit_json(path, (part, "samples", 0), [v, v, v])
            q = project.load(path)
            assert (q.palette if part == "palette" else q.analysis).samples[0] == (v, v, v)
    path = saved()
    edit_json(path, ("palette", "colors", 0), [255, 255, 255])
    assert project.load(path).palette.colors[0] == (255, 255, 255)
    for key, bounds in LIMITS.items():
        for bound, step in zip(bounds, (-1, 1), strict=True):
            path = saved()
            edit_json(path, ("params", key), bound)
            assert getattr(project.load(path).params, key) == bound
            edit_json(path, ("params", key), bound + step)
            with pytest.raises(project.ProjectError, match=key):
                project.load(path)


def test_mismatched_detection_is_refused(saved):
    m = members(saved())
    labels = np.array(Image.open(io.BytesIO(m["labels.png"])))
    lab = np.array(Image.open(io.BytesIO(m["lab.png"])))
    above, empty = labels.copy(), np.zeros_like(labels)
    above[above == 4] = 5
    cases = [{"labels.png": png(labels[:-1])}, {"lab.png": png(lab[:, :-1])}, {"labels.png": png(lab)},
             {"lab.png": png(labels)}, {"labels.png": png(above)}, {"labels.png": png(empty)},
             {"image": png(synthetic()[:300])}]
    for changes in cases:
        path = saved()
        rewrite(path, changes)
        with pytest.raises(project.ProjectError, match="detecção de cores não corresponde"):
            project.load(path)
    h, w = labels.shape
    for offset, ok in (([400 - h, 400 - w], True), ([401 - h, 0], False), ([0, 401 - w], False)):
        path = saved()
        edit_json(path, ("detection", "offset"), offset)
        if ok:
            assert project.load(path).analysis.rgba.shape[:2] == (h, w)
        else:
            with pytest.raises(project.ProjectError, match="detecção de cores não corresponde"):
                project.load(path)


def test_load_writes_and_runs_nothing(saved, tmp_path, monkeypatch):
    path = saved()
    rewrite(path, {"../fora.txt": b"x", "extra.pkl": b"cos\nsystem\n(S'touch pwned'\ntR."})
    monkeypatch.chdir(tmp_path)
    before = sorted(str(f) for f in tmp_path.parent.rglob("*"))
    edit_json(path, ("name",), "../../etc/x")
    edit_json(path, ("image_name",), r"C:\fotos\abelha.png")
    q = project.load(path)
    assert sorted(str(f) for f in tmp_path.parent.rglob("*")) == before
    assert q.name == "x" and q.image_name == "abelha.png"
    assert len(q.notes) == 2 and "../../etc/x" in q.notes[1]
    eps = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 400 400\n%%EndComments\nshowpage\n"
    rewrite(path, {"image": eps})
    with pytest.raises(project.ProjectError, match="formato de imagem não aceito"):
        project.load(path)


def test_oversized_member_is_refused(saved, monkeypatch):
    path = saved()
    monkeypatch.setattr(project, "MAX_MEMBER", len(members(path)["image"]) - 1)
    with pytest.raises(project.ProjectError, match="grande demais: image"):
        project.load(path)
