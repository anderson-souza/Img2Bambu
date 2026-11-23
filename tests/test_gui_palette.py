from PIL import Image
from PySide6.QtGui import QColor

from img2bambu.gui import main_window
from img2bambu.params import hex_color
from test_core import GREEN, PATCH, SAGE, sage_green
from test_gui_preview3d import calls, presets, settle, win  # noqa: F401 — why: shared fixtures


def load_sg(qapp, w):
    w.rgba = sage_green()
    w.reanalyze()
    settle(qapp, w)


def row_of(w, color):
    return min(range(len(w.palette.colors)),
               key=lambda i: sum((a - b) ** 2 for a, b in zip(w.palette.colors[i], color)))


def answer(monkeypatch, color, titles):
    def fake(initial, parent, title):
        titles.append(title)
        return QColor(*color) if color else QColor()
    monkeypatch.setattr(main_window.QColorDialog, "getColor", fake)


def pcts(w):
    return [r.pct.text() for r in w.rows]


def preview_px(w, y, x):
    img = w.view_prev.item.pixmap().toImage()
    c = img.pixelColor(x * w.params.upsample, y * w.params.upsample)
    return c.red(), c.green(), c.blue()


def test_rows_show_sample_and_filament(qapp, win):
    load_sg(qapp, win)
    sage = row_of(win, SAGE)
    r = win.rows[sage]
    assert hex_color(win.palette.samples[sage]) in r.sample.styleSheet()
    assert hex_color(SAGE) in r.swatch.styleSheet()
    assert r.sample.toolTip().startswith("Cor na imagem")


def test_sample_dialog_reassigns_pixels(qapp, win, monkeypatch):
    load_sg(qapp, win)
    sage, green = row_of(win, SAGE), row_of(win, GREEN)
    before = pcts(win)
    titles = []
    answer(monkeypatch, PATCH, titles)
    win.rows[sage].sample.click()
    settle(qapp, win)
    assert titles == ["Cor na imagem"]
    assert win.palette.samples[sage] == PATCH and sage in win.palette.edited
    after = pcts(win)
    assert int(after[sage][:-1]) > int(before[sage][:-1])
    assert int(after[green][:-1]) < int(before[green][:-1])
    assert preview_px(win, 180, 250) == SAGE


def test_filament_dialog_recolors_only(qapp, win, monkeypatch):
    load_sg(qapp, win)
    sage = row_of(win, SAGE)
    before = pcts(win)
    titles = []
    answer(monkeypatch, (255, 255, 255), titles)
    win.rows[sage].swatch.click()
    settle(qapp, win)
    assert titles == ["Cor do filamento"]
    assert pcts(win) == before
    assert preview_px(win, 100, 100) == (255, 255, 255)
    assert sage in win.palette.edited


def test_cancel_changes_nothing(qapp, win, monkeypatch):
    load_sg(qapp, win)
    sage = row_of(win, SAGE)
    snap = (list(win.palette.colors), list(win.palette.samples), set(win.palette.edited), pcts(win))
    answer(monkeypatch, None, [])
    win.rows[sage].sample.click()
    win.rows[sage].swatch.click()
    settle(qapp, win)
    assert (list(win.palette.colors), list(win.palette.samples), set(win.palette.edited), pcts(win)) == snap


def test_empty_row_not_counted(qapp, win, monkeypatch):
    load_sg(qapp, win)
    assert win.lbl_colors.text().startswith("3 filamento(s)")
    sage, green = row_of(win, SAGE), row_of(win, GREEN)
    lo, hi = sorted((sage, green))
    answer(monkeypatch, win.palette.samples[lo], [])
    win.rows[hi].sample.click()
    settle(qapp, win)
    assert win.rows[hi].pct.text() == "0%"
    assert win.lbl_colors.text().startswith("2 filamento(s)")


def test_reanalysis_keeps_edited_row(qapp, win, monkeypatch):
    load_sg(qapp, win)
    sage = row_of(win, SAGE)
    answer(monkeypatch, (255, 255, 255), [])
    win.rows[sage].swatch.click()
    settle(qapp, win)
    kept = (win.palette.colors[sage], win.palette.samples[sage])
    win.sp_n.setValue(4)
    settle(qapp, win)
    assert len(win.rows) == 4
    (j,) = win.palette.edited
    assert (win.palette.colors[j], win.palette.samples[j]) == kept
    assert max(abs(a - b) for a, b in zip(win.analysis.samples[j], SAGE)) <= 3   # landed on the sage row
    assert sum(1 for c in win.palette.colors if c == (255, 255, 255)) == 1


def test_count_follows_built_masks(qapp, win, monkeypatch):
    load_sg(qapp, win)
    real = main_window.pipeline.render

    def drop_one(an, pal, params):
        sil_m, masks, img = real(an, pal, params)
        masks.pop(next(iter(masks)))                   # a color cleaned away despite having pixels
        return sil_m, masks, img
    monkeypatch.setattr(main_window.pipeline, "render", drop_one)
    win.sp_relief.setValue(2.0)
    settle(qapp, win)
    assert all(r.pct.text() != "0%" for r in win.rows)
    assert win.lbl_colors.text().startswith("2 filamento(s)")


def test_new_image_starts_fresh(qapp, win, monkeypatch, tmp_path):
    img = tmp_path / "sg.png"
    Image.fromarray(sage_green()).save(img)
    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", lambda *a, **k: (str(img), ""))
    win.open_image()
    settle(qapp, win)
    sage = row_of(win, SAGE)
    answer(monkeypatch, (255, 255, 255), [])
    win.rows[sage].swatch.click()
    settle(qapp, win)
    win.open_image()
    settle(qapp, win)
    assert win.palette.edited == set()
    assert (255, 255, 255) not in win.palette.colors


# ---------- eyedropper ----------

def click_view(qapp, view, y, x):
    """Left-click image pixel (y, x) of the view's pixmap, zoomed so one pixel spans several on screen."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    view.resetTransform(); view.scale(4, 4); view.centerOn(x + 0.5, y + 0.5)
    pos = view.mapFromScene(QPointF(x + 0.5, y + 0.5))
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, pos)
    qapp.processEvents()


def armed_state(w):
    from PySide6.QtCore import Qt
    return (w.pick_row, [r.drop.isChecked() for r in w.rows],
            [v.viewport().cursor().shape() == Qt.CrossCursor for v in (w.view_orig, w.view_prev)])


def snapshot(w):
    return list(w.palette.colors), list(w.palette.samples), set(w.palette.edited), pcts(w)


def test_eyedropper_button_per_row(qapp, win):
    load_sg(qapp, win)
    for r in win.rows:
        assert r.drop.toolTip() == ("Conta-gotas: clique e depois clique na imagem (Original ou Prévia) "
                                    "para definir a cor na imagem (Esc cancela)")


def test_arm_shows_cross_and_status(qapp, win):
    load_sg(qapp, win)
    win.rows[1].drop.click()
    assert armed_state(win) == (1, [False, True, False], [True, True])
    assert win.statusBar().currentMessage() == \
        "Clique na imagem para definir a cor na imagem da cor 2 (Esc cancela)."


def test_original_click_sets_sample(qapp, win):
    load_sg(qapp, win)
    sage, green = row_of(win, SAGE), row_of(win, GREEN)
    before = pcts(win)
    win.rows[sage].drop.click()
    click_view(qapp, win.view_orig, 200, 270)        # inside PATCH, loaded-image coordinates
    settle(qapp, win)
    assert win.palette.samples[sage] == PATCH and sage in win.palette.edited
    assert int(pcts(win)[sage][:-1]) > int(before[sage][:-1])
    assert int(pcts(win)[green][:-1]) < int(before[green][:-1])
    assert preview_px(win, 180, 250) == SAGE
    assert armed_state(win) == (None, [False] * 3, [False, False])


def test_original_click_uses_crop_offset(qapp, win):
    load_sg(qapp, win)
    assert win.analysis.offset != (0, 0)
    green = row_of(win, GREEN)
    win.rows[green].drop.click()
    # why: without the offset this lands 20 px right/down, inside green instead of sage
    click_view(qapp, win.view_orig, 100, 190)
    settle(qapp, win)
    assert win.palette.samples[green] == SAGE
    assert win.palette.colors[green] == GREEN        # filament untouched


def test_click_outside_object_keeps_pick_armed(qapp, win):
    load_sg(qapp, win)
    snap = snapshot(win)
    win.rows[0].drop.click()
    click_view(qapp, win.view_orig, 5, 5)
    settle(qapp, win)
    assert snapshot(win) == snap
    assert armed_state(win)[0] == 0
    assert win.statusBar().currentMessage() == "Clique dentro do objeto."


def test_esc_cancels(qapp, win):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    load_sg(qapp, win)
    snap = snapshot(win)
    win.show(); win.activateWindow(); qapp.processEvents()
    win.rows[0].drop.click()
    QTest.keyClick(win.view_orig.viewport(), Qt.Key_Escape)
    qapp.processEvents()
    assert armed_state(win) == (None, [False] * 3, [False, False])
    assert win.statusBar().currentMessage() == "Conta-gotas cancelado."
    click_view(qapp, win.view_orig, 200, 270)
    settle(qapp, win)
    assert snapshot(win) == snap


def test_same_button_cancels_other_button_moves(qapp, win):
    load_sg(qapp, win)
    win.rows[0].drop.click()
    win.rows[2].drop.click()
    assert armed_state(win) == (2, [False, False, True], [True, True])
    win.rows[2].drop.click()
    assert armed_state(win) == (None, [False] * 3, [False, False])
    assert win.statusBar().currentMessage() == "Conta-gotas cancelado."


def test_pan_only_when_not_armed(qapp, win):
    from PySide6.QtWidgets import QGraphicsView
    load_sg(qapp, win)
    snap = snapshot(win)
    click_view(qapp, win.view_orig, 200, 270)        # not armed: nothing picked
    settle(qapp, win)
    assert snapshot(win) == snap
    assert win.view_orig.dragMode() == QGraphicsView.ScrollHandDrag
    win.rows[0].drop.click()
    assert win.view_orig.dragMode() == win.view_prev.dragMode() == QGraphicsView.NoDrag
    win.rows[0].drop.click()
    assert win.view_orig.dragMode() == win.view_prev.dragMode() == QGraphicsView.ScrollHandDrag


def test_reanalysis_and_new_image_disarm(qapp, win, monkeypatch, tmp_path):
    load_sg(qapp, win)
    snap = snapshot(win)
    win.rows[0].drop.click()
    win.sp_tol.setValue(win.sp_tol.value() + 1)
    settle(qapp, win)
    assert armed_state(win) == (None, [False] * 3, [False, False])
    assert snapshot(win)[:3] == snap[:3]
    img = tmp_path / "sg.png"
    Image.fromarray(sage_green()).save(img)
    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", lambda *a, **k: (str(img), ""))
    win.rows[0].drop.click()
    win.open_image()
    assert armed_state(win)[0] is None
    settle(qapp, win)


def test_sampled_row_carried_over(qapp, win):
    load_sg(qapp, win)
    sage = row_of(win, SAGE)
    win.rows[sage].drop.click()
    click_view(qapp, win.view_orig, 200, 270)
    settle(qapp, win)
    win.sp_n.setValue(4)
    settle(qapp, win)
    (j,) = win.palette.edited
    assert (win.palette.samples[j], win.palette.colors[j]) == (PATCH, SAGE)
