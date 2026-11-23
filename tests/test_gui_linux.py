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
