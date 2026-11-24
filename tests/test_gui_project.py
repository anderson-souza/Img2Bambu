import copy
import io
import json
import os
import threading
import zipfile

import pytest
from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from test_core import synthetic
from test_gui_preview3d import calls, settle  # noqa: F401 — why: shared fixtures
from test_project import edit_json, members, rewrite

from img2bambu import bambu, pipeline, project, segment
from img2bambu.gui import main_window
from img2bambu.gui.main_window import MainWindow

RealDB = bambu.PresetDB
A1 = "Bambu Lab A1 0.4 nozzle"
# printer -> (processes, filaments), the first of each is its default
PRINTERS = {A1: (["P a1", "P a1 fino"], ["F a1", "F a1 seda"]), "M0": (["P m0"], ["F m0"]),
            "M1": (["P um", "P dois"], ["F um", "F dois"])}


def preset_dir(root, printers):
    for name, (procs, fils) in printers.items():
        files = {("machine", name): {"default_print_profile": procs[-1], "default_filament_profile": [fils[-1]]}}
        files.update({("process", n): {"compatible_printers": [name]} for n in procs})
        files.update({("filament", n): {"compatible_printers": [name]} for n in fils})
        for (kind, n), d in files.items():
            (root / kind).mkdir(parents=True, exist_ok=True)
            (root / kind / f"{n}.json").write_text(json.dumps({"name": n, "instantiation": "true", **d}),
                                                   encoding="utf-8")
    return str(root)


class Dialogs:
    """Stands in for every modal dialog; an unexpected file dialog fails the test."""

    def __init__(self, monkeypatch):
        self.shown, self.asked, self.suggested = [], [], []
        self.save_to, self.open_from, self.answer = None, None, None
        for kind in ("information", "warning", "critical"):
            monkeypatch.setattr(main_window.QMessageBox, kind,
                                lambda parent, title, text, kind=kind: self.shown.append((kind, text)))
        monkeypatch.setattr(main_window.QMessageBox, "exec", lambda box: self.run(box))
        monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName", self.save_name)
        monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName", self.open_name)

    def run(self, box):
        texts = [b.text() for b in box.buttons()]
        self.asked.append((box.text(), texts))
        assert self.answer in texts, f"unexpected question: {box.text()}"
        box.buttons()[texts.index(self.answer)].click()

    def save_name(self, parent, title, suggest, flt):
        assert self.save_to is not None, "unexpected save dialog"
        self.suggested.append(suggest)
        return str(self.save_to), flt

    def open_name(self, parent, title, start, flt):
        assert self.open_from is not None, "unexpected open dialog"
        return str(self.open_from), flt


@pytest.fixture
def dialogs(monkeypatch):
    return Dialogs(monkeypatch)


@pytest.fixture
def make_win(qapp, monkeypatch, tmp_path, dialogs, calls):
    wins = []

    def make(printers=PRINTERS):
        root = preset_dir(tmp_path / f"presets{len(wins)}", printers)
        monkeypatch.setattr(bambu, "PresetDB", lambda: RealDB(root=root))
        ini = QSettings(str(tmp_path / f"s{len(wins)}.ini"), QSettings.IniFormat)
        monkeypatch.setattr(main_window, "QSettings", lambda *_: ini)
        w = MainWindow()
        w.resize(1000, 700)
        settle(qapp, w)
        wins.append(w)
        return w
    yield make
    for w in wins:
        settle(qapp, w)
        w.project_path = None
        w.close()
        w.deleteLater()


@pytest.fixture
def img(tmp_path):
    d = tmp_path / "fotos"
    d.mkdir()
    Image.fromarray(synthetic()).save(d / "abelha.png")
    return d / "abelha.png"


def open_img(qapp, w, dialogs, path):
    dialogs.open_from = path
    w.open_image()
    dialogs.open_from = None
    settle(qapp, w)


def save(w, dialogs, path):
    dialogs.save_to = path
    ok = w.save_project_as()
    dialogs.save_to = None
    return ok


def key(qapp, w, k, mod=Qt.ControlModifier):
    w.show()
    w.activateWindow()
    qapp.processEvents()
    QTest.keyClick(w, k, mod)
    qapp.processEvents()


def msg(w):
    return w.statusBar().currentMessage()


def members_of(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def content(path):
    return json.loads(members(path)["project.json"])


@pytest.fixture
def ready(qapp, make_win, dialogs, img):
    """A window with the test image detected and no project."""
    w = make_win()
    open_img(qapp, w, dialogs, img)
    assert w.analysis is not None
    return w


def test_save_overwrites_without_asking(qapp, ready, dialogs, tmp_path):
    w, path = ready, tmp_path / "x.i2b"
    assert save(w, dialogs, path)
    w.sp_w.setValue(180)
    settle(qapp, w)
    key(qapp, w, Qt.Key_S)
    assert content(path)["params"]["width_mm"] == 180
    assert dialogs.asked == [] and dialogs.shown == []


def test_first_save_suggests_image_name(qapp, ready, dialogs, img, tmp_path):
    dialogs.save_to = tmp_path / "x.i2b"
    key(qapp, ready, Qt.Key_S)
    assert [os.path.normpath(s) for s in dialogs.suggested] == [str(img.parent / "abelha.i2b")]
    assert (tmp_path / "x.i2b").exists()


def test_save_as_changes_the_file(qapp, ready, dialogs, tmp_path):
    w, a, b = ready, tmp_path / "a.i2b", tmp_path / "b.i2b"
    save(w, dialogs, a)
    first = a.read_bytes()
    dialogs.save_to = b
    key(qapp, w, Qt.Key_S, Qt.ControlModifier | Qt.ShiftModifier)
    assert b.exists()
    dialogs.save_to = None
    w.sp_w.setValue(180)
    settle(qapp, w)
    key(qapp, w, Qt.Key_S)
    assert content(b)["params"]["width_mm"] == 180
    assert a.read_bytes() == first


def test_save_dialog_cancelled_writes_nothing(ready, dialogs, tmp_path):
    before = sorted(os.listdir(tmp_path))
    assert not save(ready, dialogs, "")
    assert sorted(os.listdir(tmp_path)) == before and ready.project_path is None


def test_suffix_is_appended(ready, dialogs, tmp_path):
    assert save(ready, dialogs, tmp_path / "x")
    assert (tmp_path / "x.i2b").exists() and not (tmp_path / "x").exists()
    assert save(ready, dialogs, tmp_path / "Y.I2B")
    assert not (tmp_path / "Y.I2B.i2b").exists()
    assert dialogs.asked == []


def test_appended_name_asks_before_overwriting(ready, dialogs, tmp_path):
    path = tmp_path / "x.i2b"
    path.write_bytes(b"old")
    dialogs.answer = "Não"
    assert not save(ready, dialogs, tmp_path / "x")
    assert path.read_bytes() == b"old" and ready.project_path is None
    dialogs.answer = "Sim"
    assert save(ready, dialogs, tmp_path / "x")
    assert content(path)["format"] == 1
    assert [a[1] for a in dialogs.asked] == [["Sim", "Não"]] * 2


def test_save_without_image(make_win, dialogs, tmp_path):
    w = make_win()
    for slot in (w.save_project, w.save_project_as):
        assert not slot()
    assert dialogs.shown == [("information", "Abra uma imagem primeiro.")] * 2
    assert not list(tmp_path.rglob("*.i2b"))


def test_save_while_detecting(qapp, ready, dialogs, tmp_path):
    w, path = ready, tmp_path / "x.i2b"
    w.sp_n.setValue(4)
    for slot in (w.save_project, w.save_project_as):
        assert w.detecting and not slot()
        assert msg(w) == "Aguarde a detecção de cores terminar para salvar."
    settle(qapp, w)
    save(w, dialogs, path)
    first = path.read_bytes()
    w.sp_n.setValue(5)
    assert not w.save_project() and path.read_bytes() == first
    settle(qapp, w)


def test_save_after_failed_detection(qapp, make_win, dialogs, tmp_path):
    w = make_win()
    bad = tmp_path / "vazia.png"
    Image.fromarray(synthetic() * 0).save(bad)
    open_img(qapp, w, dialogs, bad)
    assert not w.save_project()
    assert dialogs.shown == [("warning", "As cores desta imagem não foram detectadas.")]
    assert not list(tmp_path.rglob("*.i2b"))


def test_save_reports_file_name(qapp, ready, dialogs, tmp_path):
    save(ready, dialogs, tmp_path / "x.i2b")
    assert msg(ready) == "Projeto salvo: x.i2b."


def test_saves_bytes_as_loaded(ready, dialogs, img, tmp_path):
    loaded, path = img.read_bytes(), tmp_path / "x.i2b"
    Image.fromarray(synthetic(alpha=False)).save(img)
    assert save(ready, dialogs, path) and members(path)["image"] == loaded
    img.unlink()
    assert save(ready, dialogs, path) and members(path)["image"] == loaded


def test_file_holds_no_local_path(ready, dialogs, img, tmp_path):
    w, path = ready, tmp_path / "x.i2b"
    w.ed_out.setText(str(tmp_path / "saida_secreta"))
    w.ed_exe.setText("/opt/exe_secreto/bambu-studio")
    save(w, dialogs, path)
    data = b"".join(members(path).values()) + b"".join(n.encode() for n in members(path))
    for secret in (str(img.parent), "fotos", "saida_secreta", "exe_secreto", str(tmp_path)):
        assert secret.encode() not in data
    assert content(path)["image_name"] == "abelha.png"


def test_failed_save_shows_error(ready, dialogs, tmp_path, monkeypatch):
    w, path = ready, tmp_path / "x.i2b"

    def broken(*_):
        raise OSError("disco cheio")
    monkeypatch.setattr(project.os, "replace", broken)
    assert not save(w, dialogs, path)
    assert dialogs.shown == [("critical", "Não foi possível salvar o projeto:\ndisco cheio")]
    assert w.project_path is None and not path.exists()


def test_save_recreates_deleted_file(qapp, ready, dialogs, tmp_path):
    path = tmp_path / "x.i2b"
    save(ready, dialogs, path)
    path.unlink()
    key(qapp, ready, Qt.Key_S)
    assert content(path)["format"] == 1


def open_proj(qapp, w, dialogs, path):
    dialogs.open_from = path
    w.open_project()
    dialogs.open_from = None
    settle(qapp, w)


def controls(w):
    return {"fundo": w.cb_bg.currentData(), "tol": w.sp_tol.value(), **{k: sp.value() for k, sp in w.fields.items()},
            "linhas": w.ck_lines.isChecked(), "maquina": w.cb_machine.currentText(),
            "processo": w.cb_process.currentText(), "filamento": w.cb_filament.currentText(),
            "check": w.ck_check.isChecked(), "nome": w.ed_name.text()}


def customise(qapp, w):
    """Every saved control and every row property away from its default."""
    w.cb_bg.setCurrentIndex(1)
    w.sp_tol.setValue(44)
    w.sp_n.setValue(4)
    w.sp_fil.setValue(3)
    w.sp_smooth.setValue(5)
    settle(qapp, w)
    for sp, v in ((w.sp_detail, 0.7), (w.sp_streak, 1.3), (w.sp_w, 185.25), (w.sp_base, 7.5), (w.sp_relief, 1.4)):
        sp.setValue(v)
    w.ck_lines.setChecked(True)
    w.cb_machine.setCurrentText("M1")
    w.cb_process.setCurrentText("P um")
    w.cb_filament.setCurrentText("F um")
    w.ck_check.setChecked(False)
    w.ed_name.setText("peça final")
    pal = w.palette
    pal.merges = {3: 1}
    pal.base_index = 1
    pal.samples[2], pal.colors[0] = (201, 12, 13), (9, 8, 7)
    pal.edited, pal.streak, pal.outline = {0, 2}, {2}, {0}
    w.palette_changed("teste")
    settle(qapp, w)


def rows(w):
    return [(r.sample.styleSheet(), r.swatch.styleSheet(), r.base.isChecked(), r.streak.isChecked(),
             r.outline.isChecked(), r.merge.currentText(), r.pct.text()) for r in w.rows]


@pytest.fixture
def custom(qapp, ready, dialogs, tmp_path):
    """The saving window and its file, with everything customised."""
    customise(qapp, ready)
    assert save(ready, dialogs, tmp_path / "x.i2b")
    return ready, tmp_path / "x.i2b"


def test_menu_and_shortcuts(qapp, make_win, dialogs, custom):
    w, path = make_win(), custom[1]
    menu = w.menuBar().actions()[0]
    assert menu.text() == "Arquivo"
    assert [(a.text(), a.shortcut().toString()) for a in menu.menu().actions()] == [
        ("Abrir projeto…", "Ctrl+O"), ("Salvar projeto", "Ctrl+S"), ("Salvar projeto como…", "Ctrl+Shift+S")]
    dialogs.open_from = path
    key(qapp, w, Qt.Key_O)
    assert w.project_path == str(path) and w.sp_w.value() == 185.25


def test_reopen_restores_every_control(qapp, make_win, dialogs, custom):
    old, path = custom
    w = make_win()
    default, want = controls(w), controls(old)
    assert len(want) == 16 and [k for k in want if want[k] == default[k]] == []
    open_proj(qapp, w, dialogs, path)
    assert controls(w) == want == {
        "fundo": "color", "tol": 44, "Nº de cores": 4, "Filamentos": 3, "Suavização": 5, "Detalhe mínimo": 0.7,
        "Filtro reflexo (raio)": 1.3, "Largura": 185.25, "Espessura da base": 7.5, "Relevo das cores": 1.4,
        "linhas": True, "maquina": "M1", "processo": "P um", "filamento": "F um", "check": False,
        "nome": "peça final"}
    assert dialogs.shown == []


def test_reopen_restores_every_row(qapp, make_win, dialogs, custom):
    old, path = custom
    w = make_win()
    open_proj(qapp, w, dialogs, path)
    assert w.palette == old.palette and w.palette is not old.palette
    assert rows(w) == rows(old) and len(rows(w)) == 4
    assert "#C90C0D" in rows(w)[2][0] and "#090807" in rows(w)[0][1]
    assert [r[2] for r in rows(w)] == [False, True, False, False]
    assert [r[3] for r in rows(w)] == [False, False, True, False]
    assert [r[4] for r in rows(w)] == [True, False, False, False]
    assert rows(w)[3][5].startswith("→")


def test_open_runs_no_detection(qapp, make_win, dialogs, custom, monkeypatch):
    w, ran = make_win(), []
    for name in ("analyze", "kmeans_palette", "smoothed"):
        monkeypatch.setattr(segment, name, lambda *a, name=name: ran.append(name))
    open_proj(qapp, w, dialogs, custom[1])
    assert w.sp_smooth.value() == 5 and not w.detecting
    assert ran == [] and msg(w).startswith("Prévia pronta")


def test_later_redetection_carries_edited_rows(qapp, make_win, dialogs, custom):
    old, path = custom
    w = make_win()
    open_proj(qapp, w, dialogs, path)
    before = w.palette
    for x in (old, w):
        x.sp_n.setValue(5)
        settle(qapp, x)
    assert w.palette == old.palette and w.palette != before
    assert len(w.palette.edited) == 2 and (201, 12, 13) in w.palette.samples and (9, 8, 7) in w.palette.colors


def test_output_folder_beside_project(qapp, make_win, dialogs, custom, tmp_path):
    w = make_win()
    open_proj(qapp, w, dialogs, custom[1])
    assert w.ed_out.text() == str(tmp_path / "img2bambu_saida")


def test_open_clears_undo(qapp, ready, dialogs, custom):
    w, path = custom
    w.sp_w.setValue(60)
    settle(qapp, w)
    assert w.history.steps
    w.project_path = None
    open_proj(qapp, w, dialogs, path)
    want = controls(w)
    key(qapp, w, Qt.Key_Z)
    assert msg(w) == "Nada para desfazer." and controls(w) == want and w.sp_w.value() == 185.25


def test_open_discards_running_tasks(qapp, make_win, dialogs, custom, img):
    w, path = make_win(), custom[1]
    open_img(qapp, w, dialogs, img)
    other = w.analysis
    w.tabs.setCurrentWidget(w.view3d)
    settle(qapp, w)
    late2d, late3d = w.req, w.req3d
    w.sp_n.setValue(6)
    detection = w.req
    assert w.detecting
    open_proj(qapp, w, dialogs, path)
    palette, analysis, parts = w.palette, w.analysis, w.view3d.part_count()
    assert len(w.palette.colors) == 4 and not w.detecting
    shown = w.view_prev.item.pixmap().toImage()
    w.analysis_done(detection, other)
    w.preview_done(late2d, (None, {}, synthetic()))
    w.model_done(late3d, [])
    w.task_failed(detection, "erro antigo")
    settle(qapp, w)
    assert w.palette is palette and w.analysis is analysis and len(w.rows) == 4
    assert w.view_prev.item.pixmap().toImage() == shown
    assert w.view3d.part_count() == parts > 0 and "erro antigo" not in w.log.toPlainText()


def test_open_shows_project_image(qapp, make_win, dialogs, custom, tmp_path):
    old, path = custom
    w = make_win()
    other = tmp_path / "outra.png"
    Image.fromarray(synthetic()[60:340, 60:300]).save(other)
    open_img(qapp, w, dialogs, other)
    open_proj(qapp, w, dialogs, path)
    for tab in (old, w):
        tab.tabs.setCurrentWidget(tab.view3d)
        settle(qapp, tab)
    assert w.lbl_file.text() == "abelha.png"
    assert w.view_orig.item.pixmap().toImage() == old.view_orig.item.pixmap().toImage()
    assert w.view_prev.item.pixmap().toImage() == old.view_prev.item.pixmap().toImage()
    assert w.view3d.part_count() == old.view3d.part_count() > 1
    assert w.lbl_h.text() == old.lbl_h.text()


def test_opens_and_saves_without_original_image(qapp, make_win, dialogs, custom, img, tmp_path):
    img.unlink()
    img.parent.rmdir()
    w = make_win()
    open_proj(qapp, w, dialogs, custom[1])
    again = tmp_path / "y.i2b"
    assert save(w, dialogs, again)
    w2 = make_win()
    open_proj(qapp, w2, dialogs, again)
    assert controls(w2) == controls(w) and w2.palette == w.palette
    assert members(again) == members(custom[1])


def test_open_writes_no_settings(qapp, make_win, dialogs, custom):
    w = make_win()
    for k, v in (("machine", A1), ("process", "P a1"), ("filament", "F a1"), ("check", "true"), ("exe", "/x")):
        w.settings.setValue(k, v)
    before = {k: w.settings.value(k) for k in w.settings.allKeys()}
    open_proj(qapp, w, dialogs, custom[1])
    assert {k: w.settings.value(k) for k in w.settings.allKeys()} == before
    assert w.cb_machine.currentText() == "M1"


ERROR = "Não foi possível abrir o projeto:\n"


def test_bad_file_shows_error(qapp, make_win, dialogs, custom):
    path, good = custom[1], custom[1].read_bytes()
    w, cases = make_win(), [b"", b"nada", good[:-200], good[: len(good) // 2]]
    for data in cases:
        path.write_bytes(data)
        open_proj(qapp, w, dialogs, path)
    for name in members_of(good):
        path.write_bytes(good)
        rewrite(str(path), {name: None})
        open_proj(qapp, w, dialogs, path)
    for key_ in ("format", "image_name", "palette", "detection"):
        d = json.loads(members_of(good)["project.json"])
        del d[key_]
        path.write_bytes(good)
        rewrite(str(path), {"project.json": json.dumps(d)})
        open_proj(qapp, w, dialogs, path)
    path.write_bytes(good)
    rewrite(str(path), {"image": members_of(good)["image"][:300]})
    open_proj(qapp, w, dialogs, path)
    path.unlink()
    open_proj(qapp, w, dialogs, path)
    assert len(dialogs.shown) == 4 + 4 + 4 + 2
    for kind, text in dialogs.shown:
        assert kind == "critical" and text.startswith(ERROR) and len(text) > len(ERROR)
    assert w.image is None and w.project_path is None


def test_newer_format_is_refused(qapp, make_win, dialogs, custom):
    w, path = make_win(), custom[1]
    rewrite(str(path), {"project.json": json.dumps({"format": 2, "palette": "outro"})})
    open_proj(qapp, w, dialogs, path)
    assert dialogs.shown == [("critical",
                              ERROR + "Este projeto foi salvo por uma versão mais nova do Img2Bambu.")]


def test_failed_open_changes_nothing(qapp, dialogs, custom, tmp_path):
    w, path = custom
    w.sp_w.setValue(60)
    settle(qapp, w)
    bad = tmp_path / "ruim.i2b"
    bad.write_bytes(path.read_bytes())
    edit_json(str(bad), ("detection", "offset"), [9999, 0])

    def everything():
        return (controls(w), w.ed_out.text(), w.lbl_file.text(), w.image, w.palette, id(w.analysis), id(w.rgba),
                list(w.history.steps), w.project_path, w.req, rows(w))
    before = everything()
    dialogs.answer = "Descartar"
    open_proj(qapp, w, dialogs, bad)
    assert dialogs.shown[0][1].startswith(ERROR)
    assert everything() == before and w.history.steps


def test_missing_setting_uses_default_and_logs(qapp, make_win, dialogs, custom):
    w, path, good = make_win(), custom[1], custom[1].read_bytes()
    default = controls(w)
    key_of = {"background": "fundo", "bg_tolerance": "tol", "n_colors": "Nº de cores", "filaments": "Filamentos",
              "smooth": "Suavização", "min_detail_mm": "Detalhe mínimo", "streak_radius_mm": "Filtro reflexo (raio)",
              "protect_lines": "linhas", "width_mm": "Largura", "base_mm": "Espessura da base",
              "relief_mm": "Relevo das cores"}
    for k, shown in key_of.items():
        d = json.loads(members_of(good)["project.json"])
        del d["params"][k]
        path.write_bytes(good)
        rewrite(str(path), {"project.json": json.dumps(d)})
        w.log.clear()
        open_proj(qapp, w, dialogs, path)
        assert controls(w)[shown] == default[shown], k
        assert f"'{k}'" in w.log.toPlainText()
    for k, shown, value in (("check", "check", True), ("name", "nome", "abelha")):
        d = json.loads(members_of(good)["project.json"])
        del d[k]
        path.write_bytes(good)
        rewrite(str(path), {"project.json": json.dumps(d)})
        w.log.clear()
        open_proj(qapp, w, dialogs, path)
        assert controls(w)[shown] == value and f"'{k}'" in w.log.toPlainText()
    d = json.loads(members_of(good)["project.json"])
    del d["presets"]["machine"], d["presets"]["process"]
    del d["presets"]["filament"]
    path.write_bytes(good)
    rewrite(str(path), {"project.json": json.dumps(d)})
    w.log.clear()
    open_proj(qapp, w, dialogs, path)
    assert all(f"'{k}'" in w.log.toPlainText() for k in ("machine", "process", "filament"))
    assert dialogs.shown == []


def test_reopening_same_project_reloads(qapp, dialogs, custom):
    w, path = custom
    want, palette = controls(w), rows(w)
    w.sp_w.setValue(60)
    w.set_base(0)
    settle(qapp, w)
    assert controls(w) != want
    dialogs.answer = "Descartar"
    open_proj(qapp, w, dialogs, path)
    assert controls(w) == want and rows(w) == palette


def test_export_keeps_its_values(qapp, make_win, dialogs, custom, img, tmp_path, monkeypatch):
    w, path, seen = make_win(), custom[1], {}
    open_img(qapp, w, dialogs, img)
    w.ed_out.setText(str(tmp_path / "saida"))
    w.ed_exe.setText("")
    go, started = threading.Event(), threading.Event()
    real = pipeline.export

    def waiting(*a, **k):
        started.set()
        assert go.wait(30)
        seen["args"] = a
        return real(*a, **k)
    monkeypatch.setattr(pipeline, "export", waiting)
    analysis, palette, width = w.analysis, copy.deepcopy(w.palette), w.sp_w.value()
    w.generate()
    assert started.wait(30)
    try:
        dialogs.open_from = path
        w.open_project()
    finally:
        go.set()
    settle(qapp, w)
    an, pal, params, outdir, name = seen["args"][:5]
    assert an is analysis and pal == palette and params.width_mm == width != w.sp_w.value()
    assert (outdir, name) == (str(tmp_path / "saida"), "abelha")
    assert list((tmp_path / "saida").glob("abelha*.stl")) and not w.busy_export
    assert w.ed_name.text() == "peça final" and w.palette != palette
