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
