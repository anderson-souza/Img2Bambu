import os

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QColor, QVector3D
from PySide6.QtQuick3D import QQuick3DGeometry
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .. import preview3d

QML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "view3d.qml")
EMPTY = "Abra uma imagem para ver o modelo 3D."
UNAVAILABLE = "Visualização 3D indisponível"


class MeshGeometry(QQuick3DGeometry):
    def __init__(self, md):
        super().__init__()
        self.setVertexData(md.vertices)
        self.setStride(24)
        self.setBounds(QVector3D(*md.lo), QVector3D(*md.hi))
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        A = QQuick3DGeometry.Attribute
        self.addAttribute(A.Semantic.PositionSemantic, 0, A.ComponentType.F32Type)
        self.addAttribute(A.Semantic.NormalSemantic, 12, A.ComponentType.F32Type)


class View3D(QWidget):
    """Qt Quick 3D view of MeshData parts plus an info line; does no geometry work."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.meshes, self.geos, self.bed = [], [], None
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.quick = QQuickWidget()
        self.quick.setResizeMode(QQuickWidget.SizeRootObjectToView)
        # invariant: a connected slot stops Qt Quick from terminating the app on GPU/context failure
        self.quick.sceneGraphError.connect(lambda err, msg: self._fail(msg))
        self.quick.setSource(QUrl.fromLocalFile(QML))
        self.info = QLabel(EMPTY); self.info.setWordWrap(True)
        self.ok = self.quick.status() == QQuickWidget.Ready
        lay.addWidget(self.quick, 1)
        lay.addWidget(self.info)
        if not self.ok:
            self._fail("; ".join(e.toString() for e in self.quick.errors()) or self.quick.status().name)

    def _fail(self, msg):
        self.ok = False
        if self._root() is not None:
            self._root().setProperty("parts", [])
        self.meshes, self.geos = [], []
        self.quick.hide()
        self.info.setText(f"{UNAVAILABLE}: {msg}")

    def _root(self):
        return self.quick.rootObject()

    def set_parts(self, meshes, reframe):
        if not self.ok:
            return
        self.meshes = list(meshes)
        self.geos = [MeshGeometry(m) for m in self.meshes]
        self._root().setProperty("parts", [{"geometry": g, "color": QColor(*m.color)}
                                           for g, m in zip(self.geos, self.meshes)])
        self.info.setText(preview3d.describe(self.meshes, self.bed))

    def show_message(self, text):
        if not self.ok:
            return
        self.meshes = []
        self._root().setProperty("parts", [])
        self.geos = []
        self.info.setText(text)

    def part_count(self):
        if not self.ok:
            return 0
        return self._root().findChild(QObject, "parts").property("count")

    def info_text(self):
        return self.info.text()
