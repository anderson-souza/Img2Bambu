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
