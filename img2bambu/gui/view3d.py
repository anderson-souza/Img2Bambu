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

    def _node(self, name):
        return self._root().findChild(QObject, name)

    def _place(self):
        """Centre the model's bbox on the bed centre (origin without bed), like the export does."""
        tx = ty = 0.0
        if self.bed is not None:
            x0, y0, x1, y1, _ = self.bed
            tx, ty = (x0 + x1) / 2, (y0 + y1) / 2
        if self.meshes:
            lo = [min(m.lo[i] for m in self.meshes) for i in range(2)]
            hi = [max(m.hi[i] for m in self.meshes) for i in range(2)]
            self._node("model").setProperty(
                "position", QVector3D(tx - (lo[0] + hi[0]) / 2, ty - (lo[1] + hi[1]) / 2, 0))
            self.info.setText(preview3d.describe(self.meshes, self.bed))

    def set_parts(self, meshes, reframe):
        if not self.ok:
            return
        self.meshes = list(meshes)
        self.geos = [MeshGeometry(m) for m in self.meshes]
        self._root().setProperty("parts", [{"geometry": g, "color": QColor(*m.color)}
                                           for g, m in zip(self.geos, self.meshes, strict=True)])
        self._place()
        if reframe and self.meshes:
            self._reframe()

    def _reframe(self):
        off = self._node("model").property("position")
        lo = [min(m.lo[i] for m in self.meshes) for i in range(3)]
        hi = [max(m.hi[i] for m in self.meshes) for i in range(3)]
        cx, cy, cz = [(a + b) / 2 for a, b in zip(lo, hi, strict=True)]
        # invariant: the container's -90° X rotation maps model (x, y, z) to scene (x, z, -y)
        self._node("orbit").setProperty(
            "position", QVector3D(cx + off.x(), cz + off.z(), -(cy + off.y())))
        self._node("orbit").setProperty("eulerRotation", QVector3D(-35, 0, 0))
        self._node("camera").setProperty("z", 2 * max(b - a for a, b in zip(lo, hi, strict=True)))

    def set_bed(self, bed):
        self.bed = bed
        if not self.ok:
            return
        old = self._node("model").property("position")
        node = self._node("bed")
        node.setProperty("visible", bed is not None)
        if bed is not None:
            x0, y0, x1, y1, _ = bed
            # invariant: #Rectangle is 100×100 units centred on its origin; z just below the base avoids z-fighting
            node.setProperty("scale", QVector3D((x1 - x0) / 100, (y1 - y0) / 100, 1))
            node.setProperty("position", QVector3D((x0 + x1) / 2, (y0 + y1) / 2, -0.01))
        self._place()
        # why: the orbit origin follows the model so a printer change does not push it off-screen
        d = self._node("model").property("position") - old
        orbit = self._node("orbit")
        orbit.setProperty("position", orbit.property("position") + QVector3D(d.x(), d.z(), -d.y()))

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
