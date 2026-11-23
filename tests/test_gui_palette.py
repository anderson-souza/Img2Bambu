from PIL import Image
from PySide6.QtGui import QColor
from test_core import GREEN, PATCH, SAGE, sage_green
from test_gui_preview3d import calls, presets, settle, win  # noqa: F401 — why: shared fixtures

from img2bambu.gui import main_window
from img2bambu.params import hex_color


def load_sg(qapp, w):
    w.rgba = sage_green()
    w.reanalyze()
    settle(qapp, w)


def row_of(w, color):
    return min(range(len(w.palette.colors)),
               key=lambda i: sum((a - b) ** 2 for a, b in zip(w.palette.colors[i], color, strict=True)))


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
    assert max(abs(a - b) for a, b in zip(win.analysis.samples[j], SAGE, strict=True)) <= 3   # landed on the sage row
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
    from PySide6.QtCore import QSettings
    win.settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)   # why: keep user settings untouched
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


def test_preview_click_samples_image_not_filament(qapp, win, monkeypatch):
    load_sg(qapp, win)
    sage, green = row_of(win, SAGE), row_of(win, GREEN)
    answer(monkeypatch, (255, 0, 0), [])
    win.rows[green].swatch.click()                   # PATCH area is drawn red in the preview
    settle(qapp, win)
    oy, ox = win.analysis.offset
    up = win.params.upsample
    py, px = (200 - oy) * up + 1, (270 - ox) * up + 1
    assert preview_px(win, 200 - oy, 270 - ox) == (255, 0, 0)
    win.rows[sage].drop.click()
    click_view(qapp, win.view_prev, py, px)
    settle(qapp, win)
    assert win.palette.samples[sage] == PATCH
    assert win.pick_row is None


def test_preview_and_original_give_same_sample(qapp, win):
    load_sg(qapp, win)
    oy, ox = win.analysis.offset
    up = win.params.upsample
    win.rows[0].drop.click()
    click_view(qapp, win.view_orig, 100, 200)        # sage|green boundary: mixed window
    settle(qapp, win)
    via_orig = win.palette.samples[0]
    win.rows[1].drop.click()
    click_view(qapp, win.view_prev, (100 - oy) * up, (200 - ox) * up)
    settle(qapp, win)
    assert win.palette.samples[1] == via_orig == (189, 188, 136)


def test_preview_click_outside_object(qapp, win):
    load_sg(qapp, win)
    snap = snapshot(win)
    win.rows[0].drop.click()
    click_view(qapp, win.view_prev, 4, 4)            # crop corner, background
    settle(qapp, win)
    assert snapshot(win) == snap
    assert win.pick_row == 0
    assert win.statusBar().currentMessage() == "Clique dentro do objeto."


def test_3d_tab_click_keeps_pick_armed(qapp, win):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    load_sg(qapp, win)
    snap = snapshot(win)
    win.tabs.setCurrentWidget(win.view3d)
    settle(qapp, win)
    win.rows[0].drop.click()
    QTest.mouseClick(win.view3d, Qt.LeftButton, Qt.NoModifier, QPoint(50, 50))
    settle(qapp, win)
    assert snapshot(win) == snap
    assert win.pick_row == 0


def test_hint_survives_preview_of_previous_pick(qapp, win):
    load_sg(qapp, win)
    win.rows[0].drop.click()
    click_view(qapp, win.view_orig, 200, 270)
    win.rows[1].drop.click()                         # armed again before the first preview lands
    settle(qapp, win)
    assert win.pick_row == 1
    assert win.statusBar().currentMessage() == \
        "Clique na imagem para definir a cor na imagem da cor 2 (Esc cancela)."


def edge_image():
    img = sage_green()
    img[150:250, 0:60] = (*SAGE, 255)                # object reaches the left image edge
    return img


def test_click_past_image_edge_picks_nothing(qapp, win):
    win.rgba = edge_image()
    win.reanalyze()
    settle(qapp, win)
    win.view_orig.set_image(win.rgba, refit=True)
    assert win.analysis.offset[1] == 0
    snap = snapshot(win)
    win.rows[0].drop.click()
    click_view(qapp, win.view_orig, 200, -1)
    click_view(qapp, win.view_prev, (200 - win.analysis.offset[0]) * win.params.upsample, -1)
    settle(qapp, win)
    assert snapshot(win) == snap
    assert win.pick_row == 0
    assert win.statusBar().currentMessage() == "Clique dentro do objeto."


def test_preview_click_floors_to_image_pixel(qapp, win):
    load_sg(qapp, win)
    oy, ox = win.analysis.offset
    up = win.params.upsample
    b = 200 - ox                                     # first green column, cropped frame
    # why: an odd c makes round(c + 0.5) land on c + 1, so rounding instead of flooring changes the window
    c, want = (b - 1, (197, 196, 150)) if (b - 1) % 2 else (b, (189, 188, 136))   # 3+2 or 2+3 sage+green columns
    win.rows[0].drop.click()
    click_view(qapp, win.view_prev, (100 - oy) * up + up - 1, c * up + up - 1)
    settle(qapp, win)
    assert win.palette.samples[0] == want


def test_unarmed_drag_pans_and_double_click_fits(qapp, win):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    load_sg(qapp, win)
    win.show()
    v = win.view_orig
    v.set_image(win.rgba, refit=True)
    win.tabs.setCurrentWidget(v); qapp.processEvents()
    v.resetTransform(); v.scale(4, 4); v.centerOn(200, 200); qapp.processEvents()
    bar = v.horizontalScrollBar().value()
    vp = v.viewport()
    p0 = QPointF(vp.width() / 2, vp.height() / 2)
    p1 = p0 + QPointF(60, 0)

    def send(kind, pos, button, buttons):
        qapp.sendEvent(vp, QMouseEvent(kind, pos, vp.mapToGlobal(pos), button, buttons, Qt.NoModifier))
    send(QEvent.MouseButtonPress, p0, Qt.LeftButton, Qt.LeftButton)
    send(QEvent.MouseMove, p1, Qt.NoButton, Qt.LeftButton)
    send(QEvent.MouseButtonRelease, p1, Qt.LeftButton, Qt.NoButton)
    qapp.processEvents()
    assert v.horizontalScrollBar().value() < bar
    QTest.mouseDClick(vp, Qt.LeftButton, Qt.NoModifier, p0.toPoint())
    qapp.processEvents()
    assert v.transform().m11() < 4


def test_smooth_spinbox(qapp, win):
    sp = win.sp_smooth
    assert (sp.minimum(), sp.maximum(), sp.singleStep(), sp.value()) == (0, 5, 1, 0)
    assert sp.toolTip() == "Achata degradês antes de detectar as cores (0 = desligado)"
    form = sp.parentWidget().layout().itemAt(0).layout()            # "2. Cores" form
    assert form.labelForField(sp).text() == "Suavização:"
    assert sp.parentWidget().title() == "2. Cores"


def test_smooth_change_reanalyzes_and_keeps_edits(qapp, win, monkeypatch):
    load_sg(qapp, win)
    sage = row_of(win, SAGE)
    answer(monkeypatch, (255, 255, 255), [])
    win.rows[sage].swatch.click()
    settle(qapp, win)
    kept = (win.palette.colors[sage], win.palette.samples[sage])
    seen, real = [], main_window.segment.analyze
    monkeypatch.setattr(main_window.segment, "analyze", lambda img, p: (seen.append(p.smooth), real(img, p))[1])
    previews, real_render = [], main_window.pipeline.render
    monkeypatch.setattr(main_window.pipeline, "render", lambda *a: (previews.append(1), real_render(*a))[1])
    win.sp_smooth.setValue(2)
    assert win.statusBar().currentMessage() == "Detectando cores…"
    settle(qapp, win)
    assert seen == [2] and win.params.smooth == 2 and previews
    (j,) = win.palette.edited
    assert (win.palette.colors[j], win.palette.samples[j]) == kept


def test_smooth_change_without_image_does_nothing(qapp, win, monkeypatch):
    seen = []
    monkeypatch.setattr(main_window.segment, "analyze", lambda *a: seen.append(a))
    win.sp_smooth.setValue(3)
    settle(qapp, win)
    assert seen == [] and win.analysis is None


def log_lines(w):
    return w.log.toPlainText().splitlines()


def load_sg4(qapp, w, filaments):
    w.sp_n.setValue(4)
    w.sp_fil.setValue(filaments)
    load_sg(qapp, w)


def test_filaments_spin_box(qapp, win):
    s = win.sp_fil
    assert (s.minimum(), s.maximum(), s.singleStep(), s.value()) == (0, 8, 1, 0)
    assert s.specialValueText() == "desligado" and s.text() == "desligado"
    assert s.toolTip() == ("Quantos filamentos usar: as cores mais parecidas são mescladas até sobrar "
                           "esse número (desligado = não mesclar)")
    form = win.sp_n.parentWidget().layout().itemAt(0).layout()
    row_n, _ = form.getWidgetPosition(win.sp_n)
    assert form.getWidgetPosition(s) == (row_n + 1, form.getWidgetPosition(win.sp_n)[1])
    assert form.labelForField(s).text() == "Filamentos:"


def test_filaments_change_reanalyzes_and_shows_merge(qapp, win):
    win.sp_n.setValue(4)
    load_sg(qapp, win)
    assert win.palette.merges == {}
    statuses = []
    win.status = lambda m: statuses.append(m)
    win.sp_fil.setValue(3)
    assert statuses[0] == "Detectando cores…"
    settle(qapp, win)
    assert win.params.filaments == 3
    green, patch = row_of(win, GREEN), row_of(win, PATCH)
    assert win.palette.merges == {patch: green}
    assert win.rows[patch].merge.currentText() == f"→ {hex_color(win.palette.colors[green])}"
    assert log_lines(win)[-1] == "Mesclagem automática: 4 cores → 3 filamentos."


def test_filaments_off_logs_nothing(qapp, win):
    load_sg4(qapp, win, 0)
    assert win.palette.merges == {}
    assert not any(line.startswith("Mesclagem automática") for line in log_lines(win))


def test_manual_merge_stands_until_reanalysis(qapp, win):
    load_sg4(qapp, win, 3)
    patch, sage = row_of(win, PATCH), row_of(win, SAGE)
    r = win.rows[patch].merge
    r.setCurrentIndex(0)                                   # "—" undoes the automatic merge
    settle(qapp, win)
    assert patch not in win.palette.merges
    r = win.rows[sage].merge
    r.setCurrentIndex(r.findData(row_of(win, GREEN)))
    settle(qapp, win)
    assert win.palette.merges == {sage: row_of(win, GREEN)}
    win.sp_tol.setValue(win.sp_tol.value() + 1)            # re-analysis recomputes
    settle(qapp, win)
    assert win.palette.merges == {row_of(win, PATCH): row_of(win, GREEN)}


def test_edit_does_not_recompute_merges(qapp, win, monkeypatch):
    load_sg4(qapp, win, 3)
    sage, patch = row_of(win, SAGE), row_of(win, PATCH)
    before = dict(win.palette.merges)
    answer(monkeypatch, PATCH, [])
    win.rows[sage].sample.click()                          # sage row now samples the patch tone
    settle(qapp, win)
    win.rows[sage].swatch.click()
    settle(qapp, win)
    assert win.palette.merges == before == {patch: row_of(win, GREEN)}


def test_filaments_without_image_does_nothing(qapp, win, monkeypatch):
    calls = []
    monkeypatch.setattr(win.pool, "start", lambda t: calls.append(t))     # hazard: pool is the global QThreadPool
    win.sp_fil.setValue(3)
    assert calls == [] and win.analysis is None
