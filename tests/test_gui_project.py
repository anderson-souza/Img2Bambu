import json
import os

import pytest
from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from test_core import synthetic
from test_gui_preview3d import calls, settle  # noqa: F401 — why: shared fixtures
from test_project import members

from img2bambu import bambu, project
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
