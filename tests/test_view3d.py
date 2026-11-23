import pytest
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QVector3D
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from test_core import synthetic

from img2bambu import preview3d, segment
from img2bambu.gui import view3d
from img2bambu.gui.view3d import View3D
from img2bambu.params import Params


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


def _vec(v):
    return v.x(), v.y(), v.z()


def test_reframe_targets_model_centre(view, meshes):
    view.set_bed(BED)
    view.set_parts(meshes, reframe=True)
    zc = (min(m.lo[2] for m in meshes) + max(m.hi[2] for m in meshes)) / 2
    # model is centred on the bed (128, 128) in mm, Z up; scene is Y up with model Y towards -Z
    assert _vec(view._node("orbit").property("position")) == pytest.approx((128, zc, -128), abs=1e-3)
    assert view._node("camera").property("z") > 0


def test_no_reframe_keeps_camera(view, meshes):
    view.set_parts(meshes, reframe=True)
    orbit, cam = view._node("orbit"), view._node("camera")
    orbit.setProperty("position", QVector3D(5, 6, 7))
    orbit.setProperty("eulerRotation", QVector3D(-10, 20, 0))
    cam.setProperty("z", 123.0)
    view.set_parts(meshes[:2], reframe=False)
    assert _vec(orbit.property("position")) == pytest.approx((5, 6, 7))
    assert _vec(orbit.property("eulerRotation")) == pytest.approx((-10, 20, 0))
    assert cam.property("z") == pytest.approx(123.0)


def test_larger_model_reframes_farther(view):
    def box(w):
        return [preview3d.MeshData("Base", (0, 0, 0), b"\0" * 72 * 4, (0, 0, 0), (w, w / 2, 11))]
    view.set_parts(box(100), reframe=True)
    near = view._node("camera").property("z")
    view.set_parts(box(250), reframe=True)
    assert view._node("camera").property("z") > near


@pytest.mark.parametrize("button", [Qt.MiddleButton, Qt.RightButton])
def test_middle_and_right_drag_pan(qapp, view, button):
    pan = view._node("pan")
    assert pan.property("acceptedButtons") == Qt.MiddleButton | Qt.RightButton
    view.show()
    orbit = view._node("orbit")
    before = _vec(orbit.property("position"))
    QTest.mousePress(view.quick, button, Qt.NoModifier, QPoint(200, 150))
    for i in range(1, 8):
        QTest.mouseMove(view.quick, QPoint(200 + 10 * i, 150 + 5 * i))
        qapp.processEvents()
    QTest.mouseRelease(view.quick, button, Qt.NoModifier, QPoint(270, 185))
    after = _vec(orbit.property("position"))
    assert after[0] < before[0] and after[1] > before[1]


def test_bed_change_moves_orbit_with_model(view, meshes):
    view.set_bed(BED)
    view.set_parts(meshes, reframe=True)
    model, orbit = view._node("model"), view._node("orbit")
    m0, o0 = _vec(model.property("position")), _vec(orbit.property("position"))
    view.set_bed((0, 0, 350, 320, 325.0))
    m1, o1 = _vec(model.property("position")), _vec(orbit.property("position"))
    assert (m1[0] - m0[0], m1[1] - m0[1]) == pytest.approx((47, 32))
    # invariant: model (x, y) maps to scene (x, -z) under the container's -90° X rotation
    assert (o1[0] - o0[0], o1[1] - o0[1], o1[2] - o0[2]) == pytest.approx((47, 0, -32))


def _material_colors(view):
    mats = [o for o in view._node("model").findChildren(QObject)
            if o.metaObject().className() == "QQuick3DPrincipledMaterial"]
    return [o.property("baseColor").getRgb()[:3] for o in mats]


def test_each_part_rendered_in_its_color(view, meshes):
    view.set_parts(meshes, reframe=True)
    assert _material_colors(view) == [tuple(m.color) for m in meshes]


def test_more_than_four_parts_all_shown(view, meshes):
    five = (list(meshes) * 2)[:5]
    view.set_parts(five, reframe=True)
    assert view.part_count() == 5
    assert "— 5 partes" in view.info_text()
