import json
import time

import pytest

from img2bambu import bambu, preview3d
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
