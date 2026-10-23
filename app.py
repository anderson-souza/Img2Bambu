import os
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        # why: windowed (console=False) builds have no stdout; IMG2BAMBU_LOG lets the CLI mode report anyway
        if sys.stdout is None or os.environ.get("IMG2BAMBU_LOG"):
            log = open(os.environ.get("IMG2BAMBU_LOG", os.devnull), "w", encoding="utf-8")
            sys.stdout = sys.stderr = log
        from img2bambu.__main__ import main as cli_main
        return cli_main(sys.argv[2:])

    from PySide6.QtWidgets import QApplication
    from img2bambu.gui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName("Img2Bambu")
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
