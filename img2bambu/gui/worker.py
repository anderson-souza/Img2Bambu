import traceback

from PySide6.QtCore import QObject, QRunnable, Signal


class Signals(QObject):
    done = Signal(int, object)
    failed = Signal(int, str)
    progress = Signal(int, str)


class Task(QRunnable):
    """Runs fn(progress=...) in the thread pool; `tag` lets the UI discard stale results."""

    def __init__(self, tag, fn, *args, with_progress=False, **kwargs):
        super().__init__()
        self.tag, self.fn, self.args, self.kwargs = tag, fn, args, kwargs
        self.with_progress = with_progress
        self.signals = Signals()

    def run(self):
        try:
            if self.with_progress:
                self.kwargs["progress"] = lambda p, m: self.signals.progress.emit(int(p), m)
            out = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001 — why: any failure must reach the UI instead of killing the thread
            traceback.print_exc()
            self.signals.failed.emit(self.tag, str(e) or e.__class__.__name__)
            return
        self.signals.done.emit(self.tag, out)
