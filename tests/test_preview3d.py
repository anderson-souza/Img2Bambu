import json

import numpy as np
import pytest

from img2bambu import bambu, geometry, pipeline, preview3d, segment
from img2bambu.params import Params
from test_core import synthetic


def test_model_matches_export_parts():
    p = Params()
    an = segment.analyze(synthetic(), p)
    ref = geometry.build_parts(*segment.build_masks(an, an.palette, p), an.palette, p)
    got = pipeline.model(an, an.palette, p)
    assert len(got) == len(ref) == 3
    for g, r in zip(got, ref):
        assert g.name == r.name
        assert tuple(g.color) == tuple(r.color)
        assert np.allclose(g.mesh.bounds, r.mesh.bounds)


def test_model_z_bounds_follow_base_and_relief():
    p = Params(base_mm=3.0, relief_mm=2.0)
    an = segment.analyze(synthetic(), p)
    base, *colors = pipeline.model(an, an.palette, p)
    assert base.mesh.bounds[:, 2] == pytest.approx([0.0, 3.0])
    assert colors
    for pt in colors:
        assert pt.mesh.bounds[:, 2] == pytest.approx([3.0, 5.0])


def test_model_all_merged_is_base_only():
    p = Params()
    an = segment.analyze(synthetic(), p)
    pal = an.palette
    for i in range(len(pal.colors)):
        if i != pal.base_index:
            pal.merges[i] = pal.base_index
    parts = pipeline.model(an, pal, p)
    assert len(parts) == 1
    assert parts[0].name.startswith("Base ")


def test_model_empty_silhouette_raises():
    p = Params()
    an = segment.analyze(synthetic(), p)
    an.sil[:] = False
    with pytest.raises(ValueError, match="^Silhueta vazia após limpeza.$"):
        pipeline.model(an, an.palette, p)


def _db(tmp_path, **machine):
    d = tmp_path / "machine"
    d.mkdir()
    (d / "m.json").write_text(json.dumps({"name": "M", "instantiation": "true", **machine}), encoding="utf-8")
    return bambu.PresetDB(root=str(tmp_path))


SQUARE = ["0x0", "256x0", "256x256", "0x256"]


def test_bed_area_and_height(tmp_path):
    db = _db(tmp_path, printable_area=SQUARE, printable_height="256")
    assert db.bed("M") == (0, 0, 256, 256, 256.0)


def test_bed_missing_height(tmp_path):
    assert _db(tmp_path, printable_area=SQUARE).bed("M") == (0, 0, 256, 256, None)


@pytest.mark.parametrize("area", [None, [], ["abc", "1x2"]])
def test_bed_missing_or_bad_area(tmp_path, area):
    machine = {"printable_height": "256"}
    if area is not None:
        machine["printable_area"] = area
    assert _db(tmp_path, **machine).bed("M") is None


def test_bed_center_uses_bed(tmp_path):
    assert _db(tmp_path, printable_area=SQUARE).bed_center("M") == (128.0, 128.0)


def test_bed_center_non_origin_area(tmp_path):
    db = _db(tmp_path, printable_area=["10x20", "210x20", "210x220", "10x220"])
    assert db.bed_center("M") == (110.0, 120.0)


def test_bed_center_fallback_without_bed(tmp_path):
    assert _db(tmp_path).bed_center("M") == (128.0, 128.0)


@pytest.fixture(scope="module")
def model_parts():
    p = Params()
    an = segment.analyze(synthetic(), p)
    return an, p, pipeline.model(an, an.palette, p)


def test_mesh_data_vertex_length(model_parts):
    for pt in model_parts[2]:
        assert len(preview3d.mesh_data(pt).vertices) == len(pt.mesh.faces) * 3 * 24


def test_mesh_data_positions_and_flat_normals(model_parts):
    for pt in model_parts[2]:
        v = np.frombuffer(preview3d.mesh_data(pt).vertices, np.float32).reshape(-1, 6)
        assert np.allclose(v[:, :3], pt.mesh.triangles.reshape(-1, 3), atol=1e-4)
        assert np.allclose(v[:, 3:], np.repeat(pt.mesh.face_normals, 3, axis=0), atol=1e-6)


def test_mesh_data_metadata(model_parts):
    for pt in model_parts[2]:
        md = preview3d.mesh_data(pt)
        assert md.name == pt.name
        assert md.color == tuple(pt.color)
        assert np.allclose(md.lo, pt.mesh.bounds[0]) and np.allclose(md.hi, pt.mesh.bounds[1])


def test_build_follows_model_order(model_parts):
    an, p, parts = model_parts
    meshes = preview3d.build(an, an.palette, p)
    assert [m.name for m in meshes] == [pt.name for pt in parts]
    assert [m.color for m in meshes] == [tuple(pt.color) for pt in parts]
    assert all(np.allclose(m.lo, pt.mesh.bounds[0]) for m, pt in zip(meshes, parts))


def test_size_of_synthetic_model():
    p = Params(width_mm=150, base_mm=10, relief_mm=1)
    an = segment.analyze(synthetic(), p)
    x, y, z = preview3d.size(preview3d.build(an, an.palette, p))
    sil_m, _ = segment.build_masks(an, an.palette, p)
    # why: to_polys traces contours through pixel centres, losing one upsampled pixel of width (same as export)
    assert x == pytest.approx(150.0, abs=p.simplify_mm + p.width_mm / sil_m.shape[1])
    assert z == pytest.approx(11.0)


BED = (0, 0, 256, 256, 256.0)


@pytest.mark.parametrize("sz, ok", [
    ((256, 256, 256), True),
    ((256.1, 256, 256), False),
    ((256, 256.1, 256), False),
    ((256, 256, 256.1), False),
])
def test_fits_boundary(sz, ok):
    assert preview3d.fits(sz, BED) is ok


def test_fits_ignores_z_without_height():
    assert preview3d.fits((256, 256, 9999), (0, 0, 256, 256, None)) is True
    assert preview3d.fits((256.1, 256, 1), (0, 0, 256, 256, None)) is False


def _md(lo, hi):
    return preview3d.MeshData("p", (0, 0, 0), b"", lo, hi)


SMALL = [_md((10, 20, 0), (160, 140.3, 10)), _md((30, 40, 10), (100, 90, 11)), _md((12, 22, 10), (20, 30, 11))]
BIG = [_md((0, 0, 0), (300, 120, 11))]


def test_describe_size_and_count_fitting():
    assert preview3d.describe(SMALL, BED) == "150.0 × 120.3 × 11.0 mm — 3 partes"


def test_describe_warns_when_too_big():
    assert preview3d.describe(BIG, BED) == \
        "300.0 × 120.0 × 11.0 mm — 1 parte\n⚠ Modelo maior que a mesa (256 × 256 × 256 mm)."


def test_describe_warning_without_height():
    assert preview3d.describe(BIG, (0, 0, 256, 256, None)).endswith("⚠ Modelo maior que a mesa (256 × 256 mm).")


def test_describe_without_bed():
    assert preview3d.describe(SMALL, None) == "150.0 × 120.3 × 11.0 mm — 3 partes\nMesa indisponível"
