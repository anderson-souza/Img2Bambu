import copy
import threading

import pytest
from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from test_core import GREEN, PATCH, SAGE, synthetic
from test_gui_palette import answer, load_sg, pcts, preview_px, row_of
from test_gui_preview3d import calls, load, presets, settle, win  # noqa: F401 — why: shared fixtures

from img2bambu import pipeline, segment
from img2bambu.gui import main_window

NOTHING = "Nada para desfazer."


@pytest.fixture
def slow(qapp, win):
    """Every change is 10 s after the previous one, so nothing groups by time."""
    t = [0.0]

    def clock():
        t[0] += 10
        return t[0]
    win.history.clock = clock
    yield win
    settle(qapp, win)


def press(qapp, w, target=None):
    w.show()
    w.activateWindow()
    target = target or w.sp_w
    target.setFocus()
    qapp.processEvents()
    assert qapp.focusWidget() is target
    QTest.keyClick(target, Qt.Key_Z, Qt.ControlModifier)
    qapp.processEvents()


def msg(w):
    return w.statusBar().currentMessage()


def test_dimension_undo_restores_value_height_and_status(qapp, slow):
    w = slow
    load(qapp, w)
    height = w.lbl_h.text()
    w.sp_w.setValue(180)
    settle(qapp, w)
    assert w.lbl_h.text() != height and msg(w).startswith("Prévia pronta")
    press(qapp, w, w.sp_w)
    assert w.sp_w.value() == 150 and w.lbl_h.text() == height
    settle(qapp, w)
    assert msg(w) == "Desfeito: Largura."
    assert w.params.width_mm == 150
    w.sp_w.setValue(190)
    settle(qapp, w)
    assert msg(w).startswith("Prévia pronta")


def test_undo_updates_visible_3d(qapp, slow, calls):
    w = slow
    load(qapp, w)
    w.tabs.setCurrentWidget(w.view3d)
    settle(qapp, w)
    before = w.view3d.info_text()
    w.sp_w.setValue(180)
    settle(qapp, w)
    assert w.view3d.info_text() != before
    n = len(calls)
    press(qapp, w)
    settle(qapp, w)
    assert len(calls) == n + 1 and w.view3d.info_text() == before


def test_steps_undo_newest_first_and_empty_history_says_so(qapp, slow):
    w = slow
    press(qapp, w)
    assert msg(w) == NOTHING
    w.sp_w.setValue(180)
    w.sp_relief.setValue(2)
    press(qapp, w)
    assert (w.sp_w.value(), w.sp_relief.value()) == (180, 1)
    assert msg(w) == "Desfeito: Relevo das cores."
    press(qapp, w)
    assert w.sp_w.value() == 150
    press(qapp, w)
    assert msg(w) == NOTHING and w.sp_w.value() == 150


def test_numeric_fields_use_the_app_undo(qapp, slow):
    w = slow
    w.show()
    w.sp_w.selectAll()
    QTest.keyClicks(w.sp_w, "200")
    w.sp_relief.setValue(2)
    press(qapp, w, w.sp_w)
    assert w.sp_relief.value() == 1 and w.sp_w.value() == 200


@pytest.mark.parametrize("name", ["sp_tol", "log", "bt_gen", "cb_bg", "view_prev"])
def test_other_controls_use_the_app_undo(qapp, slow, name):
    slow.sp_w.setValue(180)
    press(qapp, slow, getattr(slow, name))
    assert slow.sp_w.value() == 150


@pytest.mark.parametrize("name", ["ed_exe", "ed_out", "ed_name"])
def test_text_fields_keep_the_native_undo(qapp, slow, name):
    w, ed = slow, getattr(slow, name)
    ed.setText("")
    w.sp_w.setValue(180)
    w.show()
    QTest.keyClicks(ed, "abc")
    press(qapp, w, ed)
    assert ed.text() == "" and w.sp_w.value() == 180
    press(qapp, w, ed)
    press(qapp, w, ed)
    assert w.sp_w.value() == 180
    press(qapp, w)
    assert w.sp_w.value() == 150


def test_quick_run_in_a_field_is_one_step(qapp, win):
    win.history.clock = lambda: 1.0
    for v in (155, 160, 165):
        win.sp_w.setValue(v)
    press(qapp, win)
    assert win.sp_w.value() == 150
    win.sp_base.setValue(11)
    press(qapp, win)
    assert win.sp_base.value() == 10 and msg(win) == "Desfeito: Espessura da base."


def view_of(w):
    """Everything a user sees of the colors, plus the state behind it."""
    return (w.palette, pcts(w), [r.sample.styleSheet() for r in w.rows], [r.swatch.styleSheet() for r in w.rows],
            [r.base.isChecked() for r in w.rows], [r.streak.isChecked() for r in w.rows],
            [r.merge.currentData() for r in w.rows], w.view_prev.item.pixmap().toImage())


def change_and_undo(qapp, w, change, label):
    settle(qapp, w)
    before = copy.deepcopy(view_of(w)[:-1]) + view_of(w)[-1:]
    n = len(w.history.steps)
    change()
    settle(qapp, w)
    assert w.palette != before[0] and len(w.history.steps) == n + 1
    press(qapp, w)
    settle(qapp, w)
    assert view_of(w) == before
    assert len(w.history.steps) == n and msg(w) == f"Desfeito: {label}."


@pytest.mark.parametrize("button, title", [("sample", "Cor na imagem"), ("swatch", "Cor do filamento")])
def test_color_dialog_undo(qapp, slow, monkeypatch, button, title):
    load_sg(qapp, slow)
    answer(monkeypatch, PATCH, [])
    sage = row_of(slow, SAGE)
    change_and_undo(qapp, slow, getattr(slow.rows[sage], button).click, title)
    assert slow.palette.edited == set()


def test_eyedropper_undo(qapp, slow):
    w = slow
    load_sg(qapp, w)
    sage = row_of(w, SAGE)

    def pick():
        w.rows[sage].drop.click()
        w.pick_at(180, 250)
    change_and_undo(qapp, w, pick, "Cor na imagem")
    assert preview_px(w, 180, 250) != SAGE


def test_base_streak_and_merge_undo(qapp, slow):
    w = slow
    load_sg(qapp, w)
    sage, green = row_of(w, SAGE), row_of(w, GREEN)
    other = next(r for r in w.rows if not r.base.isChecked())
    change_and_undo(qapp, w, other.base.click, "Base")
    change_and_undo(qapp, w, w.rows[sage].streak.click, "Filtro reflexo")
    combo = w.rows[sage].merge
    change_and_undo(qapp, w, lambda: combo.setCurrentIndex(combo.findData(green)), "Mesclagem")
    base = w.palette.base_index                # merging the base color away also moves the base
    combo = w.rows[base].merge
    change_and_undo(qapp, w, lambda: combo.setCurrentIndex(1), "Mesclagem")
    assert w.rows[base].base.isChecked()


def test_color_rows_never_group(qapp, win):
    load_sg(qapp, win)
    win.history.clock = lambda: 1.0
    win.rows[0].streak.click(); win.rows[0].streak.click()
    settle(qapp, win)
    assert len(win.history.steps) == 2


def test_filter_fields_undo_preview_and_group(qapp, win):
    load(qapp, win)
    win.history.clock = lambda: 1.0
    before = win.view_prev.item.pixmap().toImage()
    for sp, label in ((win.sp_detail, "Detalhe mínimo"), (win.sp_streak, "Filtro reflexo (raio)")):
        old = sp.value()
        for v in (2, 3):
            sp.setValue(v)
        settle(qapp, win)
        press(qapp, win)
        settle(qapp, win)
        assert sp.value() == old and msg(win) == f"Desfeito: {label}."
        assert win.view_prev.item.pixmap().toImage() == before


def test_actions_that_change_nothing_are_no_step(qapp, slow, monkeypatch):
    w = slow
    load_sg(qapp, w)
    answer(monkeypatch, None, [])
    w.rows[0].sample.click()
    w.rows[w.palette.base_index].base.click()
    w.rows[0].drop.click(); w.rows[0].drop.click()
    assert w.history.steps == []


def test_undo_disarms_the_eyedropper(qapp, slow):
    w = slow
    load_sg(qapp, w)
    w.sp_w.setValue(180)
    w.rows[0].drop.click()
    press(qapp, w)
    settle(qapp, w)
    assert w.pick_row is None and not w.view_prev.picking and not w.rows[0].drop.isChecked()
    assert msg(w) == "Desfeito: Largura."


@pytest.fixture
def analyses(monkeypatch):
    """Records n_colors of each detection; `gate` holds detections back while cleared."""
    seen, gate, real = [], threading.Event(), segment.analyze
    gate.set()

    def fake(rgba, params):
        seen.append(params.n_colors)
        gate.wait(30)
        return real(rgba, params)
    monkeypatch.setattr(segment, "analyze", fake)
    yield seen, gate
    gate.set()


@pytest.mark.parametrize("name, value, label", [
    ("sp_n", 5, "Nº de cores"), ("sp_fil", 2, "Filamentos"), ("sp_smooth", 3, "Suavização")])
def test_detection_field_undo_brings_manual_work_back(qapp, slow, analyses, monkeypatch, name, value, label):
    w = slow
    load_sg(qapp, w)
    w.sp_n.setValue(4)
    settle(qapp, w)
    answer(monkeypatch, (1, 2, 250), [])
    w.rows[0].swatch.click()
    w.rows[2].merge.setCurrentIndex(w.rows[2].merge.findData(3))
    w.rows[1].streak.click()
    next(r for r in w.rows if r.base.isEnabled() and not r.base.isChecked()).base.click()
    settle(qapp, w)
    before = copy.deepcopy(view_of(w)[:-1]) + view_of(w)[-1:]
    old, an = getattr(w, name).value(), w.analysis
    getattr(w, name).setValue(value)
    settle(qapp, w)
    assert w.palette != before[0]
    n = len(analyses[0])
    press(qapp, w)
    settle(qapp, w)
    assert getattr(w, name).value() == old and view_of(w) == before and w.analysis is an
    assert len(analyses[0]) == n and msg(w) == f"Desfeito: {label}."


def test_undo_during_detection_drops_its_result(qapp, slow, analyses):
    w = slow
    load_sg(qapp, w)
    before = copy.deepcopy(w.palette)
    analyses[1].clear()
    w.sp_n.setValue(5)
    press(qapp, w)
    analyses[1].set()
    settle(qapp, w)
    assert w.sp_n.value() == 3 and w.palette == before and len(w.rows) == 3
    assert msg(w) == "Desfeito: Nº de cores."


def test_step_taken_during_detection_detects_again(qapp, slow, analyses):
    w = slow
    load_sg(qapp, w)
    before = copy.deepcopy(w.palette)
    analyses[1].clear()
    w.sp_n.setValue(5)
    w.sp_w.setValue(180)
    QTest.qWait(500)                           # past the preview debounce
    analyses[1].set()
    settle(qapp, w)
    assert len(w.rows) == 5
    five = copy.deepcopy(w.palette)
    press(qapp, w)
    settle(qapp, w)
    assert (w.sp_w.value(), w.sp_n.value(), w.palette) == (150, 5, five)
    assert msg(w) == "Desfeito: Largura." and analyses[0][-2:] == [5, 5]
    press(qapp, w)
    settle(qapp, w)
    assert (w.sp_n.value(), w.palette, len(w.rows)) == (3, before, 3)


def test_failed_detection_still_previews_and_undoes(qapp, slow, monkeypatch):
    w = slow
    load_sg(qapp, w)
    gate = threading.Event()

    def broken(*a):
        gate.wait(30)
        raise ValueError("quebrou")
    monkeypatch.setattr(segment, "analyze", broken)
    old = w.view_prev.item.pixmap().toImage()
    w.sp_n.setValue(5)
    w.sp_detail.setValue(3)
    QTest.qWait(500)
    gate.set()
    settle(qapp, w)
    assert "quebrou" in w.log.toPlainText() and w.view_prev.item.pixmap().toImage() != old
    w.rows[0].streak.click()
    press(qapp, w); settle(qapp, w)
    assert msg(w) == "Desfeito: Filtro reflexo."


def open_png(monkeypatch, path):
    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", lambda *a: (str(path), ""))


def test_background_changes_forget_the_history(qapp, slow):
    w = slow
    load_sg(qapp, w)
    for change in (lambda: w.sp_tol.setValue(50), lambda: w.cb_bg.setCurrentIndex(1)):
        w.sp_w.setValue(w.sp_w.value() + 5)
        change()
        settle(qapp, w)
        width = w.sp_w.value()
        press(qapp, w)
        assert msg(w) == NOTHING and w.sp_w.value() == width


def test_open_image_forgets_the_history_only_on_success(qapp, slow, monkeypatch, tmp_path):
    w = slow
    load_sg(qapp, w)
    w.rows[0].streak.click()
    w.settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *a: None)
    (tmp_path / "bad.png").write_text("x")
    for path in ("", tmp_path / "bad.png"):
        open_png(monkeypatch, path)
        w.open_image()
        assert len(w.history.steps) == 1
    Image.fromarray(synthetic()).save(tmp_path / "ok.png")
    open_png(monkeypatch, tmp_path / "ok.png")
    w.open_image()
    assert w.history.steps == []
    w.sp_w.setValue(180)                       # before the new image is detected
    settle(qapp, w)
    new = copy.deepcopy(w.palette)
    press(qapp, w); settle(qapp, w)
    assert w.sp_w.value() == 150 and w.palette == new
    press(qapp, w)
    assert msg(w) == NOTHING


def test_undo_during_export_leaves_the_export_alone(qapp, slow, monkeypatch, tmp_path):
    w, gate, got = slow, threading.Event(), []
    w.settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    load_sg(qapp, w)

    def export(an, palette, params, *a, **k):
        gate.wait(30)
        got.append((params.width_mm, copy.deepcopy(palette.streak)))
        return pipeline.Result([])
    monkeypatch.setattr(pipeline, "export", export)
    w.sp_w.setValue(180)
    w.rows[0].streak.click()
    streak = set(w.palette.streak)
    w.ed_out.setText(str(tmp_path)); w.ed_name.setText("x"); w.ed_exe.setText("")
    w.generate()
    press(qapp, w); press(qapp, w)
    assert w.sp_w.value() == 150 and w.palette.streak != streak
    gate.set()
    settle(qapp, w)
    assert got == [(180, streak)]
