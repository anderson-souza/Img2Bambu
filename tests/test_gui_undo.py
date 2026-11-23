import copy

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_core import GREEN, PATCH, SAGE
from test_gui_palette import answer, load_sg, pcts, preview_px, row_of
from test_gui_preview3d import calls, load, presets, settle, win  # noqa: F401 — why: shared fixtures

NOTHING = "Nada para desfazer."


@pytest.fixture
def slow(win):
    """Every change is 10 s after the previous one, so nothing groups by time."""
    t = [0.0]

    def clock():
        t[0] += 10
        return t[0]
    win.history.clock = clock
    return win


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
