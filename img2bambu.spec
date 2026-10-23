# PyInstaller spec — build with: pyinstaller --noconfirm img2bambu.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("trimesh") + [("img2bambu/gui/view3d.qml", "img2bambu/gui")]
hidden = collect_submodules("trimesh.exchange") + ["mapbox_earcut", "shapely"]
# why: GUI never uses these heavy optional deps; excluding them keeps the bundle small
excludes = ["matplotlib", "scipy", "sklearn", "pandas", "IPython", "tkinter", "manifold3d", "pytest"]

a = Analysis(["app.py"], pathex=["."], datas=datas, hiddenimports=hidden, excludes=excludes)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Img2Bambu", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Img2Bambu")
