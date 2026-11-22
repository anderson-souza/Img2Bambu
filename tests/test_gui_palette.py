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
