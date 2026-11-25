import copy
import io
import os
import subprocess

import numpy as np
from PySide6.QtCore import QEvent, QSettings, Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import bambu, pipeline, preview3d, project, segment
from ..history import History, Snapshot
from ..params import LIMITS, Params
from .color_row import ColorRow
from .image_view import ImageView
from .view3d import View3D
from .worker import Task

PROJECT_FILTER = f"Projeto Img2Bambu (*{project.SUFFIX})"
TITLE = "Img2Bambu — imagem para 3MF multicor"
DEFAULT_MACHINE = "Bambu Lab A1 0.4 nozzle"
PRESETS = "Impressora", "Processo", "Filamento"
IMG_FILTER = "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITLE)
        self.resize(1300, 820)
        self.settings = QSettings("img2bambu", "img2bambu")
        self.pool = QThreadPool.globalInstance()
        self.params = Params()
        self.image_path = None
        self.image = None               # (name, file bytes as loaded), None before the first image
        self.project_path = None
        self.saved_state = None         # project.settings at the last save or opening
        self.kept_presets = "", "", ""  # names of the opened project while no presets are installed
        self.rgba = None
        self.analysis = None
        self.palette = None
        self.fresh_image = True
        self.rows = []
        self.req = 0
        # why: separate counter so 3D results never invalidate the 2D preview tagged with self.req
        self.req3d = 0
        self.dirty3d = False
        self.reframe3d = False
        self.busy_export = False
        self.last_project = None
        self.db = None
        self.pick_row = None
        self.history = History()
        self.detecting = False
        self.stale2d = False            # preview asked for while detecting
        self.undo_msg = None            # result of Ctrl+Z, kept in the status bar until the next change

        self.debounce = QTimer(self, singleShot=True, interval=350)
        self.debounce.timeout.connect(self.run_preview)

        split = QSplitter()
        self.tabs = QTabWidget()
        self.view_orig, self.view_prev = ImageView(), ImageView()
        self.tabs.addTab(self.view_prev, "Cores (prévia)")
        self.tabs.addTab(self.view_orig, "Original")
        self.view3d = View3D()
        self.tabs.addTab(self.view3d, "3D")
        self.tabs.currentChanged.connect(self.tab_changed)
        self.view_orig.picked.connect(lambda y, x: self.pick_from(self.view_orig, y, x))
        self.view_prev.picked.connect(lambda y, x: self.pick_from(self.view_prev, y, x))
        self.esc = QShortcut(QKeySequence(Qt.Key_Escape), self, self.cancel_pick)
        self.esc.setEnabled(False)
        split.addWidget(self.tabs)

        side = QWidget(); sl = QVBoxLayout(side)
        sl.addWidget(self._group_image())
        sl.addWidget(self._group_colors())
        sl.addWidget(self._group_dims())
        sl.addWidget(self._group_bambu())
        sl.addWidget(self._group_output())
        sl.addStretch()
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(side)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(570)
        split.addWidget(scroll)
        split.setStretchFactor(0, 3); split.setStretchFactor(1, 2)
        self.setCentralWidget(split)
        self.fields = {
            "Nº de cores": self.sp_n, "Filamentos": self.sp_fil, "Suavização": self.sp_smooth,
            "Detalhe mínimo": self.sp_detail, "Filtro reflexo (raio)": self.sp_streak,
            "Largura": self.sp_w, "Espessura da base": self.sp_base, "Relevo das cores": self.sp_relief,
        }
        for label, sp in self.fields.items():
            sp.valueChanged.connect(lambda _, label=label: self.record(label, key=label))
        self.param_fields = {
            "bg_tolerance": self.sp_tol, "n_colors": self.sp_n, "filaments": self.sp_fil, "smooth": self.sp_smooth,
            "min_detail_mm": self.sp_detail, "streak_radius_mm": self.sp_streak, "width_mm": self.sp_w,
            "base_mm": self.sp_base, "relief_mm": self.sp_relief,
        }
        self._menu()
        for signal in (self.cb_machine.currentTextChanged, self.cb_process.currentTextChanged,
                       self.cb_filament.currentTextChanged, self.ck_check.toggled, self.ed_name.textChanged):
            signal.connect(self.update_title)
        self.last = self.snapshot()
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
        for sp in self.findChildren(QAbstractSpinBox):
            sp.installEventFilter(self)
        self.statusBar().showMessage("Abra uma imagem para começar.")
        QTimer.singleShot(0, self.load_presets)

    # ---------- UI groups ----------
    def _menu(self):
        m = self.menuBar().addMenu("Arquivo")
        for text, keys, slot in (("Abrir projeto…", "Ctrl+O", self.open_project),
                                 ("Salvar projeto", "Ctrl+S", self.save_project),
                                 ("Salvar projeto como…", "Ctrl+Shift+S", self.save_project_as)):
            a = m.addAction(text)
            a.setShortcut(QKeySequence(keys))
            a.triggered.connect(lambda _, slot=slot: slot())

    def _group_image(self):
        g = QGroupBox("1. Imagem"); f = QFormLayout(g)
        row = QHBoxLayout()
        b = QPushButton("Abrir imagem…"); b.clicked.connect(self.open_image)
        self.lbl_file = QLabel("—"); self.lbl_file.setWordWrap(True)
        row.addWidget(b); row.addWidget(self.lbl_file, 1)
        f.addRow(row)
        self.cb_bg = QComboBox()
        self.cb_bg.addItem("Transparência (PNG com fundo transparente)", "alpha")
        self.cb_bg.addItem("Remover cor de fundo (a partir dos cantos)", "color")
        self.cb_bg.currentIndexChanged.connect(self.reanalyze)
        self.cb_bg.currentIndexChanged.connect(self.forget_history)
        f.addRow("Fundo:", self.cb_bg)
        self.sp_tol = QSpinBox(); self.sp_tol.setRange(*LIMITS["bg_tolerance"])
        self.sp_tol.setValue(self.params.bg_tolerance)
        self.sp_tol.valueChanged.connect(self.reanalyze)
        self.sp_tol.valueChanged.connect(self.forget_history)
        f.addRow("Tolerância do fundo:", self.sp_tol)
        return g

    def _group_colors(self):
        g = QGroupBox("2. Cores"); v = QVBoxLayout(g)
        f = QFormLayout()
        self.sp_n = QSpinBox(); self.sp_n.setRange(*LIMITS["n_colors"]); self.sp_n.setValue(self.params.n_colors)
        self.sp_n.setToolTip("Quantidade de cores detectadas automaticamente (AMS = 4 slots)")
        self.sp_n.valueChanged.connect(self.reanalyze)
        f.addRow("Nº de cores:", self.sp_n)
        self.sp_fil = QSpinBox(); self.sp_fil.setRange(*LIMITS["filaments"])
        self.sp_fil.setValue(self.params.filaments)
        self.sp_fil.setSpecialValueText("desligado")
        self.sp_fil.setToolTip("Quantos filamentos usar: as cores mais parecidas são mescladas até sobrar "
                               "esse número (desligado = não mesclar)")
        self.sp_fil.valueChanged.connect(self.reanalyze)
        f.addRow("Filamentos:", self.sp_fil)
        self.sp_smooth = QSpinBox(); self.sp_smooth.setRange(*LIMITS["smooth"])
        self.sp_smooth.setValue(self.params.smooth)
        self.sp_smooth.setToolTip("Achata degradês antes de detectar as cores (0 = desligado)")
        self.sp_smooth.valueChanged.connect(self.reanalyze)
        f.addRow("Suavização:", self.sp_smooth)
        self.sp_detail = self._dspin("min_detail_mm", 0.1, " mm")
        self.sp_detail.setToolTip("Detalhes menores que isso são removidos (bico 0.4 → ~0.5 mm)")
        f.addRow("Detalhe mínimo:", self.sp_detail)
        self.sp_streak = self._dspin("streak_radius_mm", 0.1, " mm")
        self.sp_streak.setToolTip("Raio mínimo de áreas mantidas nas cores com 'Filtro reflexo'")
        f.addRow("Filtro reflexo (raio):", self.sp_streak)
        self.ck_lines = QCheckBox("Proteger traços finos")
        self.ck_lines.setToolTip("Mantém os traços de pelo menos 0,42 mm de todas as cores, menos as com "
                                 "'Filtro reflexo' (para traços mais finos, marque 'Contorno' na cor)")
        self.ck_lines.setChecked(self.params.protect_lines)
        self.ck_lines.toggled.connect(self.lines_changed)
        f.addRow(self.ck_lines)
        v.addLayout(f)
        self.rows_box = QVBoxLayout(); v.addLayout(self.rows_box)
        self.base_group = QButtonGroup(self)
        self.base_group.idClicked.connect(self.set_base)
        self.lbl_colors = QLabel(""); self.lbl_colors.setWordWrap(True)
        v.addWidget(self.lbl_colors)
        return g

    def _group_dims(self):
        g = QGroupBox("3. Dimensões"); f = QFormLayout(g)
        self.sp_w = self._dspin("width_mm", 5, " mm")
        f.addRow("Largura:", self.sp_w)
        self.lbl_h = QLabel("—"); f.addRow("Altura (proporcional):", self.lbl_h)
        self.sp_base = self._dspin("base_mm", 0.5, " mm")
        f.addRow("Espessura da base:", self.sp_base)
        self.sp_relief = self._dspin("relief_mm", 0.2, " mm")
        f.addRow("Relevo das cores:", self.sp_relief)
        return g

    def _group_bambu(self):
        g = QGroupBox("4. Bambu Studio"); f = QFormLayout(g)
        row = QHBoxLayout()
        self.ed_exe = QLineEdit(self.settings.value("exe", "") or (bambu.find_exe() or ""))
        b = QPushButton("…"); b.setFixedWidth(30); b.clicked.connect(self.browse_exe)
        row.addWidget(self.ed_exe); row.addWidget(b)
        f.addRow("Executável:", row)
        self.cb_machine, self.cb_process, self.cb_filament = QComboBox(), QComboBox(), QComboBox()
        for cb in (self.cb_machine, self.cb_process, self.cb_filament):
            cb.setMaxVisibleItems(25)
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(18)
        self.cb_machine.currentTextChanged.connect(self.machine_changed)
        f.addRow("Impressora:", self.cb_machine)
        f.addRow("Processo:", self.cb_process)
        f.addRow("Filamento:", self.cb_filament)
        self.ck_check = QCheckBox("Verificar fatiando após gerar (+~20 s)")
        self.ck_check.setChecked(self.settings.value("check", "true") == "true")
        f.addRow(self.ck_check)
        return g

    def _group_output(self):
        g = QGroupBox("5. Gerar"); v = QVBoxLayout(g)
        f = QFormLayout()
        row = QHBoxLayout()
        self.ed_out = QLineEdit(); b = QPushButton("…"); b.setFixedWidth(30); b.clicked.connect(self.browse_out)
        row.addWidget(self.ed_out); row.addWidget(b)
        f.addRow("Pasta de saída:", row)
        self.ed_name = QLineEdit(); f.addRow("Nome do arquivo:", self.ed_name)
        v.addLayout(f)
        row = QHBoxLayout()
        self.bt_gen = QPushButton("Gerar 3MF"); self.bt_gen.setMinimumHeight(34)
        self.bt_gen.setStyleSheet("font-weight:bold;")
        self.bt_gen.clicked.connect(self.generate)
        self.bt_open = QPushButton("Abrir no Bambu Studio"); self.bt_open.clicked.connect(self.open_bambu)
        self.bt_dir = QPushButton("Abrir pasta"); self.bt_dir.clicked.connect(self.open_dir)
        self.bt_open.setEnabled(False)
        for b in (self.bt_gen, self.bt_open, self.bt_dir):
            row.addWidget(b)
        v.addLayout(row)
        self.progress = QProgressBar(); self.progress.setValue(0); v.addWidget(self.progress)
        self.log = QPlainTextEdit(readOnly=True); self.log.setMaximumHeight(140); v.addWidget(self.log)
        return g

    def _dspin(self, key, step, suffix):
        s = QDoubleSpinBox(); s.setRange(*LIMITS[key]); s.setValue(getattr(self.params, key))
        s.setSingleStep(step); s.setSuffix(suffix); s.setDecimals(2); s.valueChanged.connect(self.params_changed)
        return s

    # ---------- presets ----------
    def load_presets(self):
        self.db = bambu.PresetDB()
        if not self.db.ok:
            self.log_msg("Presets do Bambu Studio não encontrados: só STLs serão gerados.")
            self.view3d.set_bed(None)
            return
        self.cb_machine.blockSignals(True)
        self.cb_machine.addItems(self.db.machines())
        self.cb_machine.blockSignals(False)
        m = self.settings.value("machine", DEFAULT_MACHINE)
        i = self.cb_machine.findText(m)
        self.cb_machine.setCurrentIndex(i if i >= 0 else 0)
        self.machine_changed(self.cb_machine.currentText(), restore=True)

    def machine_changed(self, machine, restore=False):
        if not self.db or not machine:
            return
        self.view3d.set_bed(self.db.bed(machine))
        proc_def, fil_def = self.db.defaults(machine)
        for cb, items, default, key in (
            (self.cb_process, self.db.processes(machine), proc_def, "process"),
            (self.cb_filament, self.db.filaments(machine), fil_def, "filament"),
        ):
            cb.clear(); cb.addItems(items)
            want = self.settings.value(key) if restore else None
            i = cb.findText(want) if want else -1
            if i < 0:
                i = cb.findText(default or "")
            cb.setCurrentIndex(max(i, 0))

    # ---------- image / analysis ----------
    def open_image(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Abrir imagem", self.settings.value("dir", ""), IMG_FILTER)
        if not path:
            return
        self.settings.setValue("dir", os.path.dirname(path))
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.rgba = segment.load_image(io.BytesIO(data))
        except Exception as e:  # noqa: BLE001 — why: any decode error is shown to the user
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir a imagem:\n{e}")
            return
        self.image_path = path
        self.image = os.path.basename(path), data
        self.project_path = None
        self.fresh_image = True
        self.disarm()
        self.lbl_file.setText(os.path.basename(path))
        self.view_orig.set_image(self.rgba, refit=True)
        self.view_prev.fitted = False
        self.reframe3d = True
        self.ed_out.setText(os.path.join(os.path.dirname(path), "img2bambu_saida"))
        self.ed_name.setText(os.path.splitext(os.path.basename(path))[0])
        self.reanalyze()
        self.forget_history()

    def read_params(self):
        p = self.params
        p.background = self.cb_bg.currentData()
        p.bg_tolerance = self.sp_tol.value()
        p.n_colors = self.sp_n.value()
        p.filaments = self.sp_fil.value()
        p.smooth = self.sp_smooth.value()
        p.min_detail_mm = self.sp_detail.value()
        p.protect_lines = self.ck_lines.isChecked()
        p.streak_radius_mm = self.sp_streak.value()
        p.width_mm = self.sp_w.value()
        p.base_mm = self.sp_base.value()
        p.relief_mm = self.sp_relief.value()
        return copy.deepcopy(p)

    def reanalyze(self):
        if self.rgba is None:
            return
        self.req += 1
        self.detecting = True
        self.status("Detectando cores…")
        t = Task(self.req, segment.analyze, self.rgba, self.read_params())
        t.signals.done.connect(self.analysis_done)
        t.signals.failed.connect(self.task_failed)
        self.pool.start(t)

    def analysis_done(self, tag, an):
        if tag != self.req:
            return
        self.detecting = False
        keep = None if self.fresh_image else self.palette
        self.analysis, self.palette, self.fresh_image = an, segment.carry_over(keep, an.palette), False
        if an.note:
            self.log_msg(an.note)
        self.apply_auto_merge()
        self.last = self.snapshot()
        self.update_title()
        self.build_rows()
        self.run_preview()

    def apply_auto_merge(self):
        # why: carry_over may have marked rows edited, and edited rows must not be merged away
        n, k = self.params.filaments, len(self.palette.colors)
        left = segment.auto_merge(self.analysis, self.palette, n)
        if left > n > 0:
            self.log_msg(f"Mesclagem automática: só foi possível chegar a {left} filamentos "
                         f"({len(self.palette.edited)} cores editadas).")
        elif self.palette.merges:
            self.log_msg(f"Mesclagem automática: {k} cores → {left} filamento{'s' if left != 1 else ''}.")

    def build_rows(self):
        self.disarm()
        for r in self.rows:
            self.base_group.removeButton(r.base)
            r.setParent(None)
        self.rows = []
        for i in range(len(self.palette.colors)):
            r = ColorRow(i)
            self.base_group.addButton(r.base, i)
            r.sample.clicked.connect(lambda _, i=i: self.pick_color(i, "samples", "Cor na imagem"))
            r.drop.clicked.connect(lambda _, i=i: self.toggle_pick(i))
            r.swatch.clicked.connect(lambda _, i=i: self.pick_color(i, "colors", "Cor do filamento"))
            r.streak.toggled.connect(lambda on, i=i: self.set_streak(i, on))
            r.outline.toggled.connect(lambda on, i=i: self.set_outline(i, on))
            r.merge.currentIndexChanged.connect(lambda _, i=i: self.set_merge(i))
            self.rows_box.addWidget(r)
            self.rows.append(r)
        self.refresh_rows()

    def refresh_rows(self):
        pal = self.palette
        lab = segment.assign(self.analysis, pal)
        tot = max(1, int((lab >= 0).sum()))
        counts = np.bincount(lab[lab >= 0], minlength=len(pal.colors))
        for r in self.rows:
            r.refresh(pal)
            r.pct.setText(f"{100 * counts[r.idx] / tot:.0f}%")

    def show_count(self, masks):
        # why: counted from the masks export builds, so cleaned-away colors are not promised
        n = 1 + len(masks)
        warn = "  ⚠ mais que 4 cores = mais que um AMS." if n > 4 else ""
        self.lbl_colors.setText(f"{n} filamento(s) no projeto.{warn}")

    def set_base(self, i):
        self.palette.base_index = i
        self.palette_changed("Base")

    def set_streak(self, i, on):
        self.palette.set_streak(i, on)
        self.palette_changed("Filtro reflexo")

    def set_outline(self, i, on):
        self.palette.set_outline(i, on)
        self.palette_changed("Contorno")

    def set_merge(self, i):
        target = self.rows[i].merge.currentData()
        if not self.palette.merge(i, None if target is None or target < 0 else target):
            QMessageBox.warning(self, "Mesclar", "Essa combinação criaria um ciclo de mesclagem.")
        self.palette_changed("Mesclagem")

    def pick_color(self, i, field, title):
        values = getattr(self.palette, field)
        c = QColorDialog.getColor(QColor(*values[i]), self, title)
        if c.isValid():
            values[i] = (c.red(), c.green(), c.blue())
            self.palette.edited.add(i)
            self.palette_changed(title)

    def toggle_pick(self, i):
        if self.pick_row == i:
            self.cancel_pick()
            return
        self.pick_row = i
        for r in self.rows:
            r.drop.setChecked(r.idx == i)
        for v in (self.view_orig, self.view_prev):
            v.set_picking(True)
        self.esc.setEnabled(True)
        self.status(self.pick_hint())

    def pick_hint(self):
        return f"Clique na imagem para definir a cor na imagem da cor {self.pick_row + 1} (Esc cancela)."

    def disarm(self):
        self.pick_row = None
        for r in self.rows:
            r.drop.setChecked(False)
        for v in (self.view_orig, self.view_prev):
            v.set_picking(False)
        self.esc.setEnabled(False)

    def cancel_pick(self):
        if self.pick_row is None:
            return
        self.disarm()
        self.status("Conta-gotas cancelado.")

    def pick_from(self, view, y, x):
        if self.pick_row is None or self.analysis is None:
            return
        pm = view.item.pixmap()
        h, w = self.rgba.shape[:2] if view is self.view_orig else (pm.height(), pm.width())
        if not (0 <= y < h and 0 <= x < w):
            # why: the 5x5 window of a click just past the image edge would still reach the object
            self.status("Clique dentro do objeto.")
            return
        if view is self.view_orig:
            self.pick_at(y - self.analysis.offset[0], x - self.analysis.offset[1])
        else:
            self.pick_at(y // self.params.upsample, x // self.params.upsample)

    def pick_at(self, y, x):
        # invariant: (y, x) is a pixel of the cropped analysis image
        i = self.pick_row
        rgb = segment.sample_at(self.analysis, y, x)
        if rgb is None:
            self.status("Clique dentro do objeto.")
            return
        self.palette.samples[i] = rgb
        self.palette.edited.add(i)
        self.disarm()
        self.palette_changed("Cor na imagem")

    def palette_changed(self, label):
        self.record(label)
        self.refresh_rows()
        self.debounce.start()

    def lines_changed(self):
        self.record("Proteger traços finos")
        self.params_changed()

    def params_changed(self):
        if self.analysis is not None:
            h, w = self.analysis.sil.shape
            self.lbl_h.setText(f"{self.sp_w.value() * h / w:.1f} mm")
            self.debounce.start()

    def run_preview(self):
        if self.analysis is None:
            return
        h, w = self.analysis.sil.shape
        self.lbl_h.setText(f"{self.sp_w.value() * h / w:.1f} mm")
        if self.detecting:
            # why: taking a new tag here would discard the detection, which previews by itself when done
            self.stale2d = True
            return
        self.req += 1
        self.stale2d = False
        self.status("Atualizando prévia…")
        t = Task(self.req, pipeline.render, self.analysis, copy.deepcopy(self.palette), self.read_params())
        t.signals.done.connect(self.preview_done)
        t.signals.failed.connect(self.task_failed)
        self.pool.start(t)
        if self.tabs.currentWidget() is self.view3d:
            self.run_model()
        else:
            self.dirty3d = True

    def preview_done(self, tag, out):
        if tag != self.req:
            return
        self.view_prev.set_image(out[2])
        self.show_count(out[1])
        # why: a preview from an earlier pick must not hide the hint of the pick still armed
        self.status(self.pick_hint() if self.pick_row is not None
                    else self.undo_msg if self.undo_msg
                    else "Prévia pronta. Ajuste as cores ou clique em Gerar 3MF.")

    def tab_changed(self, i):
        if self.tabs.widget(i) is self.view3d and self.dirty3d and self.analysis is not None:
            self.run_model()

    def run_model(self):
        self.req3d += 1
        self.dirty3d = False
        t = Task(self.req3d, preview3d.build, self.analysis, copy.deepcopy(self.palette), self.read_params())
        t.signals.done.connect(self.model_done)
        t.signals.failed.connect(self.model_failed)
        self.pool.start(t)

    def model_done(self, tag, meshes):
        if tag != self.req3d:
            return
        self.view3d.set_parts(meshes, reframe=self.reframe3d)
        self.reframe3d = False

    def model_failed(self, tag, msg):
        if tag != self.req3d:
            return
        self.view3d.show_message(msg)
        self.log_msg(f"Erro: {msg}")

    # ---------- undo ----------
    def eventFilter(self, obj, e):
        # why: a spin box claims Ctrl+Z for its own text before the window shortcut sees it
        if e.type() == QEvent.ShortcutOverride and e.matches(QKeySequence.Undo):
            e.ignore()
            return True
        return super().eventFilter(obj, e)

    def snapshot(self):
        # why: until a new image is detected, palette and analysis still belong to the previous one
        pal, an = (None, None) if self.fresh_image else (copy.deepcopy(self.palette), self.analysis)
        values = [sp.value() for sp in self.fields.values()] + [self.ck_lines.isChecked()]
        return Snapshot(values, pal, an, self.detecting)

    def forget_history(self):
        self.history.clear()
        self.last = self.snapshot()
        self.undo_msg = None
        self.update_title()

    def record(self, label, key=None):
        before, self.last = self.last, self.snapshot()
        self.history.record(label, before, self.last, key)
        self.undo_msg = None
        self.update_title()

    def no_effect(self, label, st):
        # why: a run of a field back to its start still differs by the detection that ran meanwhile
        now = self.snapshot()
        return (not now.pending and st.values == now.values
                and (st.palette == now.palette or (st.pending and label in self.fields)))

    def undo(self):
        step = self.history.undo()
        while step is not None and self.no_effect(*step):
            step = self.history.undo()
        if step is None:
            self.undo_msg = "Nada para desfazer."
            self.status(self.undo_msg)
            return
        label, st = step
        self.undo_msg = f"Desfeito: {label}."
        for sp, v in zip(self.fields.values(), st.values[:-1], strict=True):
            sp.blockSignals(True); sp.setValue(v); sp.blockSignals(False)
        self.ck_lines.blockSignals(True); self.ck_lines.setChecked(st.values[-1]); self.ck_lines.blockSignals(False)
        self.read_params()
        self.debounce.stop()
        self.disarm()
        self.req += 1                  # why: drops a detection still running with the undone values
        self.detecting = False
        if st.palette is None:
            self.fresh_image = True
        else:
            self.palette, self.analysis = st.palette, st.analysis
            if len(self.rows) == len(self.palette.colors):
                self.refresh_rows()
            else:
                self.build_rows()
        if st.pending or st.palette is None:
            self.reanalyze()
        else:
            self.run_preview()
        self.last = self.snapshot()
        self.update_title()
        self.status(self.undo_msg)

    # ---------- project ----------
    def current_project(self):
        presets = [cb.currentText() for cb in (self.cb_machine, self.cb_process, self.cb_filament)]
        if not (self.db and self.db.ok):
            presets = self.kept_presets
        return project.Project(*self.image, self.read_params(), self.palette, self.analysis, *presets,
                               self.ck_check.isChecked(), self.ed_name.text())

    def unsaved(self):
        # why: without a project nobody asked to keep the work, so there is nothing to warn about
        return self.project_path is not None and project.settings(self.current_project()) != self.saved_state

    def update_title(self):
        if self.project_path is None:
            self.setWindowTitle(TITLE)
        else:
            mark = "*" if self.unsaved() else ""
            self.setWindowTitle(f"{os.path.basename(self.project_path)}{mark} — Img2Bambu")

    def confirm_discard(self):
        """False when the user wants to keep the current project, or saving it did not work."""
        if not self.unsaved():
            return True
        answer = self.ask(f"O projeto {os.path.basename(self.project_path)} tem alterações não salvas.",
                          "Salvar", "Descartar", "Cancelar")
        return self.save_project() if answer == "Salvar" else answer == "Descartar"

    def closeEvent(self, e):
        if self.confirm_discard():
            e.accept()
        else:
            e.ignore()

    def can_save(self):
        if self.image is None:
            QMessageBox.information(self, "Img2Bambu", "Abra uma imagem primeiro.")
        elif self.detecting:
            self.status("Aguarde a detecção de cores terminar para salvar.")
        elif self.fresh_image:
            QMessageBox.warning(self, "Img2Bambu", "As cores desta imagem não foram detectadas.")
        else:
            return True
        return False

    def save_project(self):
        if self.project_path is None:
            return self.save_project_as()
        return self.can_save() and self.write_project(self.project_path)

    def save_project_as(self):
        if not self.can_save():
            return False
        suggest = self.project_path or os.path.join(os.path.dirname(self.image_path or ""),
                                                    os.path.splitext(self.image[0])[0] + project.SUFFIX)
        path, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", suggest, PROJECT_FILTER)
        if not path:
            return False
        if not path.lower().endswith(project.SUFFIX):
            path += project.SUFFIX
            # why: the dialog only asked about the name without the suffix
            if os.path.exists(path) and self.ask(f"{os.path.basename(path)} já existe. Substituir?",
                                                 "Sim", "Não") != "Sim":
                return False
        return self.write_project(path)

    def write_project(self, path):
        try:
            project.save(path, self.current_project())
        except Exception as e:  # noqa: BLE001 — why: any failure to save is shown to the user
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar o projeto:\n{e}")
            return False
        self.project_path = path
        self.saved_state = project.settings(self.current_project())
        self.update_title()
        self.status(f"Projeto salvo: {os.path.basename(path)}.")
        return True

    def open_project(self):
        if not self.confirm_discard():
            return
        start = os.path.dirname(self.project_path or self.image_path or "") or self.settings.value("dir", "")
        path, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", start, PROJECT_FILTER)
        if not path:
            return
        try:
            p = project.load(path)
        except Exception as e:  # noqa: BLE001 — why: any failure to open is shown to the user
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir o projeto:\n{e}")
            return
        self.apply_project(path, p)

    def apply_project(self, path, p):
        self.debounce.stop()
        self.disarm()
        # why: drops a detection, a preview and a 3D model still running for the previous image
        self.req += 1
        self.req3d += 1
        self.detecting = self.stale2d = self.fresh_image = False
        self.reframe3d = True
        # invariant: signals stay blocked, or each control would start a detection over the restored palette
        for sp in self.param_fields.values():
            sp.blockSignals(True)
        self.cb_bg.blockSignals(True); self.ck_lines.blockSignals(True)
        for k, sp in self.param_fields.items():
            sp.setValue(getattr(p.params, k))
        self.cb_bg.setCurrentIndex(self.cb_bg.findData(p.params.background))
        self.ck_lines.setChecked(p.params.protect_lines)
        self.cb_bg.blockSignals(False); self.ck_lines.blockSignals(False)
        for sp in self.param_fields.values():
            sp.blockSignals(False)
        self.ck_check.setChecked(p.check)
        self.ed_name.setText(p.name)
        self.ed_out.setText(os.path.join(os.path.dirname(os.path.abspath(path)), "img2bambu_saida"))
        missing = self.apply_presets(p)
        self.rgba, self.image, self.image_path = p.rgba, (p.image_name, p.image), None
        self.palette, self.analysis = p.palette, p.analysis
        self.lbl_file.setText(p.image_name)
        self.view_orig.set_image(self.rgba, refit=True)
        self.view_prev.fitted = False
        self.read_params()
        self.build_rows()
        self.project_path = path
        self.saved_state = project.settings(self.current_project())
        self.forget_history()
        for n in p.notes:
            self.log_msg(f"⚠ {n}")
        self.run_preview()
        self.warn_presets(missing)

    def apply_presets(self, p):
        """Selects the project's presets; returns [(what, missing name, substitute or None)]."""
        want = p.machine, p.process, p.filament
        if not (self.db and self.db.ok):
            self.kept_presets = want
            return [(what, name, None) for what, name in zip(PRESETS, want, strict=True) if name]
        if not p.machine:
            return []
        i = self.cb_machine.findText(p.machine)
        if i < 0:
            i = max(0, self.cb_machine.findText(DEFAULT_MACHINE))
        self.cb_machine.blockSignals(True); self.cb_machine.setCurrentIndex(i); self.cb_machine.blockSignals(False)
        self.machine_changed(self.cb_machine.currentText())     # selects the defaults of the printer
        for cb, name in ((self.cb_process, p.process), (self.cb_filament, p.filament)):
            i = cb.findText(name)
            if i >= 0:
                cb.setCurrentIndex(i)
        got = (cb.currentText() for cb in (self.cb_machine, self.cb_process, self.cb_filament))
        return [(what, name, g) for what, name, g in zip(PRESETS, want, got, strict=True) if name and name != g]

    def warn_presets(self, missing):
        if not missing:
            return
        lines = [f"{what}: '{name}' → " + (f"'{sub}'" if sub else "nenhum" if sub == "" else "mantido no projeto")
                 for what, name, sub in missing]
        for line in lines:
            self.log_msg(f"⚠ Preset não instalado: {line}")
        QMessageBox.warning(self, "Presets não instalados",
                            "Este computador não tem estes presets do projeto:\n" + "\n".join(lines))

    def ask(self, text, *answers):
        """Text of the clicked button; the last answer is also the one of closing the dialog."""
        box = QMessageBox(QMessageBox.Question, "Img2Bambu", text, QMessageBox.NoButton, self)
        # why: Qt's standard buttons have English labels
        buttons = [box.addButton(a, QMessageBox.ActionRole) for a in answers]
        box.setDefaultButton(buttons[0])
        box.setEscapeButton(buttons[-1])
        box.exec()
        return next((a for a, b in zip(answers, buttons, strict=True) if b is box.clickedButton()), answers[-1])

    # ---------- export ----------
    def generate(self):
        if self.analysis is None:
            QMessageBox.information(self, "Img2Bambu", "Abra uma imagem primeiro.")
            return
        if self.busy_export:
            return
        outdir, name = self.ed_out.text().strip(), self.ed_name.text().strip()
        if not outdir or not name:
            QMessageBox.warning(self, "Img2Bambu", "Defina pasta de saída e nome do arquivo.")
            return
        exe = os.path.expanduser(self.ed_exe.text().strip())
        choice = None
        if exe and os.path.isfile(exe) and self.db and self.db.ok and self.cb_process.currentText() \
                and self.cb_filament.currentText():
            choice = pipeline.BambuChoice(exe, self.cb_machine.currentText(), self.cb_process.currentText(),
                                          self.cb_filament.currentText(), self.ck_check.isChecked())
        for k, v in (("exe", exe), ("machine", self.cb_machine.currentText()),
                     ("process", self.cb_process.currentText()), ("filament", self.cb_filament.currentText()),
                     ("check", "true" if self.ck_check.isChecked() else "false")):
            self.settings.setValue(k, v)
        self.busy_export = True
        self.bt_gen.setEnabled(False)
        self.progress.setValue(0)
        self.log_msg(f"Gerando '{name}'…")
        t = Task(0, pipeline.export, self.analysis, copy.deepcopy(self.palette), self.read_params(),
                 outdir, name, choice, self.db, with_progress=True)
        t.signals.progress.connect(lambda p, m: (self.progress.setValue(p), self.status(m)))
        t.signals.done.connect(self.export_done)
        t.signals.failed.connect(self.export_failed)
        self.pool.start(t)

    def export_done(self, _tag, res):
        self.busy_export = False
        self.bt_gen.setEnabled(True)
        for s in res.stls:
            self.log_msg(f"STL: {s}")
        if res.project:
            self.last_project = res.project
            self.bt_open.setEnabled(True)
            self.log_msg(f"Projeto: {res.project}")
        if res.check:
            c = res.check
            self.log_msg(f"Verificação: {c.get('changes')} trocas de filamento, "
                         f"cores {', '.join(c.get('colours', []))}, tempo estimado {c.get('time') or '?'}.")
        for w in res.warnings:
            self.log_msg(f"⚠ {w}")
        self.status("Concluído.")

    def export_failed(self, _tag, msg):
        self.busy_export = False
        self.bt_gen.setEnabled(True)
        self.progress.setValue(0)
        self.log_msg(f"Erro: {msg}")
        QMessageBox.critical(self, "Erro ao gerar", msg)

    def task_failed(self, tag, msg):
        if tag == self.req:
            self.log_msg(f"Erro: {msg}")
            self.status("Erro.")
            if self.detecting:
                self.detecting = False
                self.last = self.snapshot()
                if self.stale2d:
                    self.run_preview()

    # ---------- misc ----------
    def browse_exe(self):
        p, _ = QFileDialog.getOpenFileName(self, "Bambu Studio" if bambu.is_linux() else "bambu-studio.exe",
                                           self.ed_exe.text(),
                                           "Todos (*)" if bambu.is_linux() else "Executável (*.exe)")
        if p:
            self.ed_exe.setText(p)

    def browse_out(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta de saída", self.ed_out.text())
        if p:
            self.ed_out.setText(p)

    def open_bambu(self):
        exe = os.path.expanduser(self.ed_exe.text().strip())
        if self.last_project and os.path.isfile(exe):
            subprocess.Popen([exe, self.last_project])

    def open_dir(self):
        d = self.ed_out.text().strip()
        if d and os.path.isdir(d):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(d)))

    def status(self, msg):
        self.statusBar().showMessage(msg)

    def log_msg(self, msg):
        self.log.appendPlainText(msg)
