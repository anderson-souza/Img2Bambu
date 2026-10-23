"""Drives the GUI without dialogs: python tests/gui_smoke.py <image> <outdir> <screenshot.png>"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from img2bambu import segment  # noqa: E402
from img2bambu.gui.main_window import MainWindow  # noqa: E402

img, outdir, shot = sys.argv[1:4]
app = QApplication(sys.argv)
w = MainWindow(); w.show()
state = {"step": 0, "ticks": 0}


def tick():
    state["ticks"] += 1
    if state["ticks"] > 600:
        print("TIMEOUT at step", state["step"]); app.exit(2); return
    s = state["step"]
    if s == 0 and w.db is not None:
        w.rgba = segment.load_image(img); w.image_path = img
        w.view_orig.set_image(w.rgba, refit=True)
        w.ed_out.setText(outdir); w.ed_name.setText("gui_test")
        w.ck_check.setChecked(True)
        w.reanalyze(); state["step"] = 1
    elif s == 1 and w.analysis is not None and "Prévia pronta" in w.statusBar().currentMessage():
        print("palette", [r.swatch.styleSheet() for r in w.rows], "machine", w.cb_machine.currentText(),
              "process", w.cb_process.currentText(), "filament", w.cb_filament.currentText())
        w.tabs.setCurrentWidget(w.view3d); state["step"] = 2
    elif s == 2 and w.view3d.part_count() > 0:
        print("3D part_count", w.view3d.part_count(), "info", w.view3d.info_text().replace("\n", " | "))
        w.generate(); state["step"] = 3
    elif s == 3 and not w.busy_export:
        print("LOG:\n" + w.log.toPlainText())
        w.grab().save(shot)
        app.exit(0 if w.last_project else 1)


t = QTimer(); t.timeout.connect(tick); t.start(100)
sys.exit(app.exec())
