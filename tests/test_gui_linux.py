from pathlib import Path

import pytest
from test_core import synthetic
from test_gui_preview3d import calls, presets, settle, win  # noqa: F401 — why: shared fixtures

from img2bambu import bambu
from img2bambu.gui import main_window


@pytest.fixture
def flatpak(monkeypatch, tmp_path):
    exe = tmp_path / bambu.FLATPAK_ID
    exe.write_text("")
    monkeypatch.setattr(bambu.sys, "platform", "linux")
    return str(exe)


def test_refused_folder_shows_error_and_allows_retry(qapp, win, flatpak, monkeypatch, tmp_path):  # noqa: F811
    shown = []
    monkeypatch.setattr(bambu, "sandbox_sees", lambda d: False)
    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    # why: generate() persists the form; the test must not touch the user's settings
    monkeypatch.setattr(win.settings, "setValue", lambda k, v: None)
    win.rgba = synthetic()
    win.reanalyze()
    settle(qapp, win)
    out = tmp_path / "out"
    win.ed_out.setText(str(out)); win.ed_name.setText("t"); win.ed_exe.setText(flatpak)
    for cb in (win.cb_process, win.cb_filament):
        cb.clear(); cb.addItem("p")
    win.generate()
    settle(qapp, win)
    assert len(shown) == 1
    assert shown[0].startswith(f"O Bambu Studio (Flatpak) não acessa a pasta de saída: {out}.")
    assert win.bt_gen.isEnabled() and not win.busy_export
    assert list(out.iterdir()) == []


@pytest.mark.parametrize("platform, filt", [("linux", "Todos (*)"), ("win32", "Executável (*.exe)")])
def test_picker_filter(win, monkeypatch, platform, filt):  # noqa: F811
    asked = []

    def fake(*a):
        asked.append(a)
        return "/x/bambu", ""

    monkeypatch.setattr(bambu.sys, "platform", platform)
    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", fake)
    win.browse_exe()
    assert asked[0][3] == filt and win.ed_exe.text() == "/x/bambu"


def test_open_dir_asks_desktop(win, monkeypatch, tmp_path):  # noqa: F811
    opened = []
    monkeypatch.setattr(main_window.QDesktopServices, "openUrl", opened.append)
    win.ed_out.setText(str(tmp_path / "missing"))
    win.open_dir()
    assert opened == []
    win.ed_out.setText(str(tmp_path))
    win.open_dir()
    assert [Path(u.toLocalFile()) for u in opened] == [tmp_path]


def test_open_bambu_launches_flatpak(win, flatpak, monkeypatch):  # noqa: F811
    ran = []
    monkeypatch.setattr(main_window.subprocess, "Popen", ran.append)
    win.ed_exe.setText(flatpak)
    win.last_project = "/home/u/t.3mf"
    win.open_bambu()
    assert ran == [[flatpak, "/home/u/t.3mf"]]


def test_exe_field_filled_from_detection(qapp, flatpak, monkeypatch, presets):  # noqa: F811
    real = bambu.PresetDB
    monkeypatch.setattr(bambu, "PresetDB", lambda: real(root=presets))
    monkeypatch.setattr(bambu, "find_exe", lambda: flatpak)
    monkeypatch.setattr(main_window.QSettings, "value", lambda self, key, default=None: default)
    w = main_window.MainWindow()
    settle(qapp, w)
    assert w.ed_exe.text() == flatpak and w.cb_machine.count() > 0
    w.close()
    w.deleteLater()
