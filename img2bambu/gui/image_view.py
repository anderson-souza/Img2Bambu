import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


def to_pixmap(arr):
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    fmt = QImage.Format_RGBA8888 if arr.shape[2] == 4 else QImage.Format_RGB888
    return QPixmap.fromImage(QImage(arr.data, w, h, arr.strides[0], fmt).copy())


class ImageView(QGraphicsView):
    picked = Signal(int, int)       # (y, x) pixel of the shown image

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.item = QGraphicsPixmapItem()
        self.scene().addItem(self.item)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#d0d0d0"))
        self.fitted = False
        self.picking = False

    def set_picking(self, on):
        self.picking = on
        self.setDragMode(QGraphicsView.NoDrag if on else QGraphicsView.ScrollHandDrag)
        if on:
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.viewport().unsetCursor()

    def mousePressEvent(self, e):
        if self.picking and e.button() == Qt.LeftButton:
            p = self.mapToScene(e.position().toPoint())
            self.picked.emit(int(np.floor(p.y())), int(np.floor(p.x())))
            e.accept()
            return
        super().mousePressEvent(e)

    def set_image(self, arr, refit=False):
        self.item.setPixmap(to_pixmap(arr))
        self.scene().setSceneRect(self.item.boundingRect())
        if refit or not self.fitted:
            self.fitInView(self.item, Qt.KeepAspectRatio)
            self.fitted = True

    def wheelEvent(self, e):
        f = 1.2 if e.angleDelta().y() > 0 else 1 / 1.2
        self.scale(f, f)

    def mouseDoubleClickEvent(self, e):
        self.fitInView(self.item, Qt.KeepAspectRatio)
