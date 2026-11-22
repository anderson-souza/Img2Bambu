import json
import os
import zipfile

import numpy as np
import pytest

from img2bambu import bambu, export3mf, geometry, pipeline, segment
from img2bambu.params import Params

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEE = os.path.join(ROOT, "..", "new abelha", "Mascote Abelha com Placa ABELHÃO.png")


def synthetic(alpha=True):
    """Black disc with a yellow square and a white bar, on transparent (or white) background."""
    h = w = 400
    img = np.zeros((h, w, 4), np.uint8)
    yy, xx = np.mgrid[:h, :w]
    disc = (yy - 200) ** 2 + (xx - 200) ** 2 < 180 ** 2
    img[disc] = (20, 20, 20, 255)
    img[120:220, 120:220] = (250, 210, 0, 255)
    img[260:300, 100:300] = (240, 240, 240, 255)
    if not alpha:
        img[~disc] = (255, 255, 255, 255)
    return img


@pytest.mark.parametrize("alpha", [True, False])
def test_segment_three_colors(alpha):
    p = Params(width_mm=100, n_colors=3)
    an = segment.analyze(synthetic(alpha), p)
    assert bool(an.note) == (not alpha)
    assert an.sil.shape == (360, 360) or abs(an.sil.shape[0] - 360) <= 2
    base = an.palette.colors[an.palette.base_index]
    assert max(base) < 60, f"base should be the dark ring color, got {base}"
    sil_m, masks = segment.build_masks(an, an.palette, p)
    assert len(masks) == 2
    for m in masks.values():
        assert not (m & ~sil_m.astype(bool)).any()
    a, b = masks.values()
    assert not (a & b).any(), "raised color masks must be disjoint"


def test_parts_watertight_and_heights():
    p = Params(width_mm=100, base_mm=8, relief_mm=1.2)
    an = segment.analyze(synthetic(), p)
    sil_m, masks = segment.build_masks(an, an.palette, p)
    parts = geometry.build_parts(sil_m, masks, an.palette, p)
    assert len(parts) == 3
    assert all(pt.mesh.is_watertight for pt in parts)
    assert parts[0].mesh.bounds[1][2] == pytest.approx(8)
    assert parts[0].mesh.extents[0] == pytest.approx(100, abs=0.5)
    for pt in parts[1:]:
        assert pt.mesh.bounds[0][2] == pytest.approx(8)
        assert pt.mesh.bounds[1][2] == pytest.approx(9.2)


def test_merge_reduces_parts():
    p = Params(width_mm=100)
    an = segment.analyze(synthetic(), p)
    pal = an.palette
    others = [i for i in range(3) if i != pal.base_index]
    pal.merges[others[1]] = others[0]
    sil_m, masks = segment.build_masks(an, pal, p)
    assert list(masks) == [others[0]]


def test_streak_filter_drops_thin_lines():
    img = synthetic()
    img[60:63, 150:250] = (245, 245, 245, 255)       # ~0.75 mm wide streak at 100 mm width
    p = Params(width_mm=100, streak_radius_mm=1.0)
    an = segment.analyze(img, p)
    white = [i for i, c in enumerate(an.palette.colors) if min(c) > 200][0]
    assert white in an.palette.streak
    _, masks = segment.build_masks(an, an.palette, p)
    up = p.upsample
    assert not masks[white][int(50 / 400 * 360) * up:int(70 / 400 * 360) * up].any()


def _fake_cli_project(path, n_fil):
    settings = {"filament_settings_id": ["X"] * n_fil, "filament_colour": ["#00AE42"],
                "filament_type": ["PLA"], "nozzle_temperature": ["220"], "layer_height": "0.2",
                "flush_volumes_matrix": ["0"] * 16, "flush_volumes_vector": ["140"] * 8}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Metadata/project_settings.config", json.dumps(settings))
        z.writestr("3D/3dmodel.model", "<model/>")


def test_patch_project_expands_arrays(tmp_path):
    src, dst = str(tmp_path / "a.3mf"), str(tmp_path / "b.3mf")
    _fake_cli_project(src, 3)
    bambu.patch_project(src, dst, ["#000000", "#FFFF00", "#FFFFFF"], {"nozzle_temperature"})
    with zipfile.ZipFile(dst) as z:
        d = json.loads(z.read("Metadata/project_settings.config"))
        assert z.read("3D/3dmodel.model") == b"<model/>"
    assert d["filament_colour"] == ["#000000", "#FFFF00", "#FFFFFF"]
    assert d["filament_type"] == ["PLA"] * 3
    assert d["nozzle_temperature"] == ["220"] * 3
    assert d["layer_height"] == "0.2"
    assert len(d["flush_volumes_matrix"]) == 9 and d["flush_volumes_matrix"][0] == "0"
    assert len(d["flush_volumes_vector"]) == 6


def test_patch_project_rejects_wrong_count(tmp_path):
    src = str(tmp_path / "a.3mf")
    _fake_cli_project(src, 1)
    with pytest.raises(RuntimeError):
        bambu.patch_project(src, str(tmp_path / "b.3mf"), ["#000000", "#FFFFFF"])


def test_minimal_3mf_assigns_extruders(tmp_path):
    p = Params(width_mm=60)
    an = segment.analyze(synthetic(), p)
    parts = geometry.build_parts(*segment.build_masks(an, an.palette, p), an.palette, p)
    out = export3mf.write_minimal_3mf(parts, str(tmp_path / "m.3mf"), "Teste & <x>")
    with zipfile.ZipFile(out) as z:
        cfg = z.read("Metadata/model_settings.config").decode()
        model = z.read("3D/3dmodel.model").decode()
    assert 'name="Application"' not in model
    for i in (1, 2, 3):
        assert f'<metadata key="extruder" value="{i}"/>' in cfg


@pytest.mark.slow
@pytest.mark.skipif(not (bambu.find_exe() and os.path.isfile(BEE)), reason="needs Bambu Studio + bee image")
def test_bee_end_to_end(tmp_path):
    p = Params(width_mm=150)
    an = segment.analyze(BEE, p)
    db = bambu.PresetDB()
    m = "Bambu Lab A1 0.4 nozzle"
    proc, fil = db.defaults(m)
    choice = pipeline.BambuChoice(bambu.find_exe(), m, proc, fil, check=True)
    res = pipeline.export(an, an.palette, p, str(tmp_path), "abelha", choice, db)
    assert len(res.stls) == 3 and os.path.isfile(res.project)
    assert res.check["changes"] > 0
    assert len(res.check["colours"]) == 3


SAGE, GREEN, PATCH = (215, 213, 179), (171, 171, 107), (180, 178, 120)


def sage_green():
    """Dark disc; left half sage, right half green, with a sage-ish-green patch inside the green half."""
    img = synthetic()
    img[60:340, 60:200] = (*SAGE, 255)
    img[60:340, 200:340] = (*GREEN, 255)
    img[150:250, 240:300] = (*PATCH, 255)
    return img


def _row_of(an, color):
    return min(range(len(an.palette.colors)),
               key=lambda i: sum((a - b) ** 2 for a, b in zip(an.palette.colors[i], color)))


def test_analysis_initial_samples_and_filaments():
    an = segment.analyze(sage_green(), Params(width_mm=100, n_colors=3))
    pal = an.palette
    assert len(pal.samples) == len(pal.colors) == 3
    assert pal.edited == set()
    sage = _row_of(an, SAGE)
    assert pal.colors[sage] == SAGE                                  # filament = cluster median
    assert max(abs(a - b) for a, b in zip(pal.samples[sage], SAGE)) <= 3   # sample = cluster center


def test_initial_sample_is_cluster_center_not_median():
    img = sage_green()
    img[60:140, 200:340] = (*PATCH, 255)          # ~44% of the green+patch cluster: median != mean
    an = segment.analyze(img, Params(width_mm=100, n_colors=3))
    green = _row_of(an, GREEN)
    assert an.palette.colors[green] == GREEN
    lab = an.lab[an.labels[an.sil] == green].mean(0)
    mean_rgb = segment._to_rgb(lab[None, :])[0]
    assert max(abs(a - b) for a, b in zip(an.palette.samples[green], mean_rgb)) <= 1
    assert an.palette.samples[green] != GREEN


def test_sample_edit_pulls_pixels_filament_edit_does_not():
    p = Params(width_mm=100, n_colors=3)
    an = segment.analyze(sage_green(), p)
    pal = an.palette
    sage, green = _row_of(an, SAGE), _row_of(an, GREEN)
    y, x = 200 - 20, 270 - 20                    # patch pixel, in the cropped frame (crop offset 20)
    assert segment.assign(an, pal)[y, x] == green
    pal.samples[sage] = PATCH
    labels = segment.assign(an, pal)
    assert labels[y, x] == sage
    assert labels[100, 100] == sage and labels[100, 260] == green
    pal.colors[sage] = (255, 255, 255)
    assert (segment.assign(an, pal) == labels).all()
    sil_m, masks, prev = pipeline.render(an, pal, p)
    up = p.upsample
    assert tuple(prev[y * up, x * up]) == (255, 255, 255)


def test_unedited_rows_keep_kmeans_split():
    rng = np.random.default_rng(1)
    img = sage_green()
    noise = rng.integers(-25, 26, img[..., :3].shape)
    img[..., :3] = np.clip(img[..., :3].astype(int) + noise, 0, 255).astype(np.uint8)
    an = segment.analyze(img, Params(width_mm=100, n_colors=4))
    pal = an.palette
    assert segment.assign(an, pal) is an.labels
    pal.samples[0] = tuple(pal.samples[0])          # same value re-entered: still unedited
    assert (segment.assign(an, pal) == an.labels).all()
    far = 3
    pal.samples[far] = (0, 0, 255)                  # pure blue: nothing in the image is near it
    labels = segment.assign(an, pal)
    kept = (an.labels >= 0) & (an.labels != far)
    # why: edited palettes use rounded RGB samples, so only boundary pixels may move
    assert (labels[kept] == an.labels[kept]).mean() > 0.99
    assert not (labels == far).any()


def test_equal_samples_tie_goes_to_lower_index():
    an = segment.analyze(sage_green(), Params(width_mm=100, n_colors=3))
    pal = an.palette
    sage, green = _row_of(an, SAGE), _row_of(an, GREEN)
    lo, hi = sorted((sage, green))
    pal.samples[hi] = tuple(pal.samples[lo])
    labels = segment.assign(an, pal)
    assert not (labels == hi).any()
    assert (labels[an.labels == hi] == lo).all()


def test_export_uses_filament_not_sample(tmp_path, monkeypatch):
    p = Params(width_mm=100, n_colors=3)
    an = segment.analyze(sage_green(), p)
    pal = an.palette
    sage = _row_of(an, SAGE)
    pal.samples[sage] = PATCH
    pal.colors[sage] = (255, 255, 255)
    seen = {}
    monkeypatch.setattr(bambu, "export_project", lambda *a, **k: seen.setdefault("colors", a[7]))

    class DB:
        def bed_center(self, m):
            return (128.0, 128.0)
    choice = pipeline.BambuChoice("bambu-studio", "M", "P", "F")
    res = pipeline.export(an, pal, p, str(tmp_path), "t", choice, DB())
    expected = [bambu_hex(pal.colors[i]) for i in [pal.base_index] + [i for i in range(3) if i != pal.base_index]]
    assert sorted(seen["colors"]) == sorted(expected)
    assert "#FFFFFF" in seen["colors"] and bambu_hex(PATCH) not in seen["colors"]
    from PIL import Image
    prev = np.array(Image.open(res.preview))
    up = p.upsample
    assert tuple(prev[180 * up, 250 * up][:3]) == (255, 255, 255)


def bambu_hex(c):
    from img2bambu.params import hex_color
    return hex_color(c)


def _pal(n, edited=()):
    from img2bambu.params import Palette
    return Palette(colors=[(i, i, i) for i in range(n)], samples=[(i, 0, 0) for i in range(n)], edited=set(edited))


def test_carry_over_keeps_edited_rows():
    from img2bambu.params import carry_over
    old = _pal(4, {3})
    old.colors[3], old.samples[3] = (255, 255, 255), (215, 213, 179)
    grown = carry_over(old, _pal(6))
    assert grown.colors[3] == (255, 255, 255) and grown.samples[3] == (215, 213, 179)
    assert grown.edited == {3}
    assert [grown.colors[i] for i in (0, 1, 2, 4, 5)] == [(i, i, i) for i in (0, 1, 2, 4, 5)]
    shrunk = carry_over(old, _pal(3))
    assert shrunk.colors == [(i, i, i) for i in range(3)] and shrunk.edited == set()
    assert carry_over(None, _pal(3)).colors == [(i, i, i) for i in range(3)]
