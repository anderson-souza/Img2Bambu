import pytest
from PySide6.QtQuick import QQuickWindow

from img2bambu import preview3d, segment
from img2bambu.gui import view3d
from img2bambu.gui.view3d import View3D
from img2bambu.params import Params
from test_core import synthetic


@pytest.fixture(scope="module")
def meshes():
    p = Params()
    an = segment.analyze(synthetic(), p)
    return preview3d.build(an, an.palette, p)


@pytest.fixture
def view(qapp):
    v = View3D()
    v.resize(400, 300)
    yield v
    v.deleteLater()


def test_set_parts_shows_every_part(view, meshes):
    assert view.ok is True
    view.set_parts(meshes, reframe=True)
    assert view.part_count() == len(meshes) == 3
    assert view.info_text() == preview3d.describe(meshes, None)


def test_set_parts_replaces_previous(view, meshes):
    view.set_parts(meshes, reframe=True)
    view.set_parts(meshes[:1], reframe=False)
    assert view.part_count() == 1
    assert view.info_text() == preview3d.describe(meshes[:1], None)


def test_show_message_clears_model(view, meshes):
    view.set_parts(meshes, reframe=True)
    view.show_message("x")
    assert view.part_count() == 0
    assert view.info_text() == "x"


def test_fresh_view_shows_empty_state(view):
    assert view.part_count() == 0
    assert view.info_text() == "Abra uma imagem para ver o modelo 3D."


def test_broken_qml_reports_unavailable(qapp, monkeypatch, tmp_path, meshes):
    monkeypatch.setattr(view3d, "QML", str(tmp_path / "missing.qml"))
    v = View3D()
    assert v.ok is False
    assert v.info_text().startswith("Visualização 3D indisponível")
    v.set_parts(meshes, reframe=True)
    assert v.part_count() == 0
    assert v.info_text().startswith("Visualização 3D indisponível")


def test_scene_graph_error_reports_unavailable(view, meshes):
    view.set_parts(meshes, reframe=True)
    view.quick.sceneGraphError.emit(QQuickWindow.SceneGraphError.ContextNotAvailable, "sem GPU")
    assert view.ok is False
    assert view.part_count() == 0
    assert view.info_text() == "Visualização 3D indisponível: sem GPU"


BED = (0, 0, 256, 256, 256.0)


def _model_centre(view, meshes):
    pos = view._node("model").property("position")
    lo = [min(m.lo[i] for m in meshes) for i in range(2)]
    hi = [max(m.hi[i] for m in meshes) for i in range(2)]
    return pos.x() + (lo[0] + hi[0]) / 2, pos.y() + (lo[1] + hi[1]) / 2


def test_set_bed_draws_bed_and_centres_model(view, meshes):
    view.set_parts(meshes, reframe=True)
    view.set_bed(BED)
    bed = view._node("bed")
    assert bed.property("visible") is True
    sc = bed.property("scale")
    assert (sc.x() * 100, sc.y() * 100) == pytest.approx((256, 256))
    pos = bed.property("position")
    assert (pos.x(), pos.y()) == pytest.approx((128, 128))
    assert _model_centre(view, meshes) == pytest.approx((128, 128))
    assert view.info_text() == preview3d.describe(meshes, BED)
    assert "Mesa indisponível" not in view.info_text()


def test_set_bed_none_hides_bed(view, meshes):
    view.set_bed(BED)
    view.set_parts(meshes, reframe=True)
    view.set_bed(None)
    assert view._node("bed").property("visible") is False
    assert "Mesa indisponível" in view.info_text()
    assert view.part_count() == 3


def test_bed_change_updates_warning_without_remesh(view, monkeypatch):
    big = [preview3d.MeshData("Base", (0, 0, 0), b"\0" * 72 * 4, (0, 0, 0), (300, 120, 11))]
    view.set_parts(big, reframe=True)
    view.set_bed(BED)
    assert "⚠ Modelo maior que a mesa (256 × 256 × 256 mm)." in view.info_text()
    monkeypatch.setattr(view, "set_parts", lambda *a, **k: pytest.fail("set_bed must not remesh"))
    monkeypatch.setattr(view3d, "MeshGeometry", lambda *a: pytest.fail("set_bed must not remesh"))
    view.set_bed((0, 0, 350, 320, 325.0))
    assert "⚠" not in view.info_text()
    assert view.info_text() == "300.0 × 120.0 × 11.0 mm — 1 parte"
    assert _model_centre(view, big) == pytest.approx((175, 160))
