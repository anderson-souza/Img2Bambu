# PyInstaller spec — build with: pyinstaller --noconfirm img2bambu.spec
import re

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("trimesh") + [("img2bambu/gui/view3d.qml", "img2bambu/gui")]
hidden = collect_submodules("trimesh.exchange") + ["mapbox_earcut", "shapely"]
# why: GUI never uses these heavy optional deps; excluding them keeps the bundle small
excludes = ["matplotlib", "scipy", "sklearn", "pandas", "IPython", "tkinter", "manifold3d", "pytest"]

a = Analysis(["app.py"], pathex=["."], datas=datas, hiddenimports=hidden, excludes=excludes)
# why: PySide6 QtQuick/QtQml hooks pull every Qt module (WebEngine alone ~200 MB); view3d.qml only loads
# QtQml, QtQuick, QtQuick3D and QtQuick3D.Helpers (traced with QML_IMPORT_TRACE + loaded-DLL list)
unused_qt = re.compile(
    r"Qt6Web|QtWeb|Qt63D|Qt3D|Charts|Graphs|DataVisualization|Location|Positioning|Multimedia"
    r"|SpatialAudio|Quick3DPhysics|Quick3D/Physics|Quick3DParticle|Quick3D/Particle|Quick3DXr|Quick3D/Xr"
    r"|QuickControls2|QuickTemplates2|QuickDialogs2|QuickNativeStyle|QtQuick/(Controls|Templates|Dialogs|NativeStyle)"
    r"|LabsStyleKit|VirtualKeyboard(Qml|Settings)|QtQuick/VirtualKeyboard|qml/Qt5Compat|qmltooling"
    r"|RemoteObjects|Scxml|StateMachine|Sensors|TextToSpeech|Qt6Test|QuickTest|QtTest|PdfQuick|QtQuick/Pdf"
    r"|QuickParticles|QtQuick/Particles|Quick3DEffects|Quick3D/Effects|Quick3DAsset|Quick3D/AssetUtils"
    r"|Quick3D/(designer|MaterialEditor|lightmapviewer)")
a.binaries = [e for e in a.binaries if not unused_qt.search(e[0].replace("\\", "/"))]
a.datas = [e for e in a.datas if not unused_qt.search(e[0].replace("\\", "/"))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Img2Bambu", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Img2Bambu")
