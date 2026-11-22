import json
import time

import pytest

from img2bambu import bambu, preview3d
from img2bambu.gui import main_window, view3d
from img2bambu.gui.main_window import MainWindow
from test_core import synthetic

RealDB = bambu.PresetDB
MACHINES = {
    "M1": {"printable_area": ["0x0", "256x0", "256x256", "0x256"], "printable_height": "256"},
    "M2": {"printable_area": ["0x0", "350x0", "350x320", "0x320"], "printable_height": "325"},
}


@pytest.fixture
def presets(tmp_path):
    d = tmp_path / "machine"
    d.mkdir()
    for name, fields in MACHINES.items():
        (d / f"{name}.json").write_text(json.dumps({"name": name, "instantiation": "true", **fields}),
                                        encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def calls(monkeypatch):
    seen, real = [], preview3d.build

    def counting(*a, **k):
        seen.append(1)
        return real(*a, **k)
    monkeypatch.setattr(preview3d, "build", counting)
    return seen


@pytest.fixture
def win(qapp, monkeypatch, presets, calls):
    monkeypatch.setattr(bambu, "PresetDB", lambda: RealDB(root=presets))
    w = MainWindow()
    w.resize(1000, 700)
    settle(qapp, w)
    yield w
    w.close()
    w.deleteLater()


def settle(qapp, w, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if w.debounce.isActive() or w.pool.activeThreadCount():
            time.sleep(0.01)
            continue
        qapp.processEvents()
        if not w.debounce.isActive() and not w.pool.activeThreadCount():
            return
    raise AssertionError("GUI did not settle")


def wait_until(qapp, cond, timeout=60):
    end = time.time() + timeout
    while not cond():
        if time.time() > end:
            raise AssertionError("condition not reached")
        qapp.processEvents()
        time.sleep(0.01)


def load(qapp, w):
    w.rgba = synthetic()
    w.reanalyze()
    settle(qapp, w)
    assert w.analysis is not None


def test_no_image_shows_empty_state(qapp, win, calls):
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    assert calls == []
    assert win.view3d.part_count() == 0
    assert win.view3d.info_text() == "Abra uma imagem para ver o modelo 3D."


def test_hidden_tab_does_not_build(qapp, win, calls):
    load(qapp, win)
    win.sp_relief.setValue(2.0)
    settle(qapp, win)
    assert calls == []
    assert win.dirty3d is True
    assert win.view3d.part_count() == 0


def test_switching_to_tab_builds_once(qapp, win, calls):
    load(qapp, win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    assert len(calls) == 1
    assert win.view3d.part_count() == 3
    win.tabs.setCurrentWidget(win.view_prev)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    assert len(calls) == 1
    assert win.view3d.part_count() == 3


def test_visible_tab_rebuilds_after_param_change(qapp, win, calls):
    load(qapp, win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    assert "× 11.0 mm — 3 partes" in win.view3d.info_text()
    win.sp_relief.setValue(2.0)
    assert len(calls) == 1          # debounce pending: nothing rebuilt yet
    settle(qapp, win)
    assert len(calls) == 2
    assert win.view3d.part_count() == 3
    assert "× 12.0 mm — 3 partes" in win.view3d.info_text()


def test_stale_model_result_ignored(qapp, win, calls):
    load(qapp, win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    before = win.view3d.info_text()
    stale = [preview3d.MeshData("Base", (0, 0, 0), b"\0" * 72 * 4, (0, 0, 0), (300, 120, 11))]
    win.model_done(win.req3d - 1, stale)
    assert win.view3d.part_count() == 3
    assert win.view3d.info_text() == before


def test_2d_preview_updates_with_3d_tab_current(qapp, win, calls):
    load(qapp, win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    key = win.view_prev.item.pixmap().cacheKey()
    win.sp_n.setValue(2)
    settle(qapp, win)
    assert len(calls) == 2
    assert win.view_prev.item.pixmap().cacheKey() != key
    assert "Prévia pronta" in win.statusBar().currentMessage()
    assert win.view3d.part_count() == 2


def test_build_failure_shows_message(qapp, win, calls, monkeypatch):
    load(qapp, win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    assert win.view3d.part_count() == 3

    def boom(*a, **k):
        raise ValueError("Silhueta vazia")
    monkeypatch.setattr(preview3d, "build", boom)
    win.sp_relief.setValue(2.0)
    settle(qapp, win)
    assert win.view3d.part_count() == 0
    assert win.view3d.info_text() == "Silhueta vazia"
    assert "Erro: Silhueta vazia" in win.log.toPlainText()
    assert win.bt_gen.isEnabled()


def _frame(view):
    o = view._node("orbit").property("position")
    return o.x(), o.y(), o.z()


def test_new_image_reframes_once(qapp, win, monkeypatch, tmp_path):
    from PIL import Image
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QVector3D
    img = tmp_path / "a.png"
    Image.fromarray(synthetic()).save(img)
    win.settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", lambda *a, **k: (str(img), ""))
    seen, real = [], win.view3d.set_parts
    monkeypatch.setattr(win.view3d, "set_parts", lambda m, reframe: (seen.append(reframe), real(m, reframe)))
    win.tabs.setCurrentWidget(win.view3d)
    win.open_image()
    settle(qapp, win)
    assert seen == [True]
    framed = _frame(win.view3d)
    assert (framed[0], framed[2]) == pytest.approx((128, -128), abs=1)   # M1 bed centre
    win.view3d._node("orbit").setProperty("position", QVector3D(5, 6, 7))
    win.sp_relief.setValue(2.0)
    settle(qapp, win)
    assert seen == [True, False]
    assert _frame(win.view3d) == pytest.approx((5, 6, 7))
    win.open_image()
    settle(qapp, win)
    assert seen[-1] is True
    # relief is now 2.0: origin back at the model centre, height (base 10 + relief 2) / 2
    assert _frame(win.view3d) == pytest.approx((framed[0], 6.0, framed[2]), abs=1e-3)


def test_machine_change_updates_bed_without_rebuild(qapp, win, calls, monkeypatch):
    load(qapp, win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    assert win.cb_machine.currentText() == "M1"
    assert win.view3d.info_text() == preview3d.describe(win.view3d.meshes, (0, 0, 256, 256, 256.0))
    beds, real = [], win.view3d.set_bed
    monkeypatch.setattr(win.view3d, "set_bed", lambda b: (beds.append(b), real(b)))
    win.cb_machine.setCurrentText("M2")
    settle(qapp, win)
    assert beds == [(0, 0, 350, 320, 325.0)]
    assert len(calls) == 1
    assert win.view3d._node("bed").property("visible") is True
    assert win.view3d.info_text() == preview3d.describe(win.view3d.meshes, (0, 0, 350, 320, 325.0))


def test_no_presets_shows_bed_unavailable(qapp, monkeypatch, tmp_path, calls):
    monkeypatch.setattr(bambu, "PresetDB", lambda: RealDB(root=str(tmp_path)))
    w = MainWindow()
    beds, real = [], w.view3d.set_bed
    monkeypatch.setattr(w.view3d, "set_bed", lambda b: (beds.append(b), real(b)))
    settle(qapp, w)
    assert w.db.ok is False
    assert beds == [None]
    load(qapp, w)
    w.tabs.setCurrentWidget(w.view3d)
    settle(qapp, w)
    assert w.view3d.part_count() == 3
    assert "Mesa indisponível" in w.view3d.info_text()
    w.close()
    w.deleteLater()


def test_stale_model_failure_ignored(qapp, win, calls):
    load(qapp, win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    before = win.view3d.info_text()
    win.model_failed(win.req3d - 1, "x")
    assert win.view3d.part_count() == 3
    assert win.view3d.info_text() == before
    assert "Erro: x" not in win.log.toPlainText()


def test_model_updates_while_export_runs(qapp, win, calls, tmp_path, monkeypatch):
    import threading
    from types import SimpleNamespace
    from PySide6.QtCore import QSettings
    load(qapp, win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    release, started = threading.Event(), threading.Event()

    def held_export(*a, **k):
        started.set()
        release.wait()
        return SimpleNamespace(stls=[], project=None, check=None, warnings=[])
    monkeypatch.setattr(main_window.pipeline, "export", held_export)
    win.settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    win.ed_exe.setText("")
    win.ed_out.setText(str(tmp_path / "out")); win.ed_name.setText("t")
    try:
        win.generate()
        assert started.wait(10)
        win.sp_relief.setValue(2.0)
        wait_until(qapp, lambda: len(calls) == 2 and "× 12.0 mm" in win.view3d.info_text())
        assert win.busy_export is True and not release.is_set()     # export still held open
        assert "× 12.0 mm — 3 partes" in win.view3d.info_text()
        assert win.view3d.part_count() == 3
    finally:
        release.set()
    settle(qapp, win)
    assert win.busy_export is False


def test_broken_3d_view_keeps_rest_of_gui(qapp, monkeypatch, presets, tmp_path):
    monkeypatch.setattr(bambu, "PresetDB", lambda: RealDB(root=presets))
    monkeypatch.setattr(view3d, "QML", str(tmp_path / "missing.qml"))
    w = MainWindow()
    settle(qapp, w)
    load(qapp, w)
    assert "Prévia pronta" in w.statusBar().currentMessage()
    w.tabs.setCurrentWidget(w.view3d)
    settle(qapp, w)
    assert w.view3d.info_text().startswith("Visualização 3D indisponível")
    assert w.bt_gen.isEnabled()
    w.close()
    w.deleteLater()
