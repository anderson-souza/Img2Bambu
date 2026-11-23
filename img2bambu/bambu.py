import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

EXE_NAME = "bambu-studio.exe"
FLATPAK_ID = "com.bambulab.BambuStudio"
FLATPAK_SYSTEM_BIN = "/var/lib/flatpak/exports/bin"
FLUSH_DEFAULT = "280"
FLUSH_VECTOR_DEFAULT = "140"


def is_linux():
    return sys.platform.startswith("linux")


def find_exe():
    if is_linux():
        cands = [shutil.which("bambu-studio") or "",
                 os.path.join(os.path.expanduser("~"), ".local/share/flatpak/exports/bin", FLATPAK_ID),
                 os.path.join(FLATPAK_SYSTEM_BIN, FLATPAK_ID)]
        return next((c for c in cands if c and os.path.isfile(c)), None)
    cands = [os.path.join(os.environ.get(v, ""), "Bambu Studio", EXE_NAME)
             for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    try:
        import winreg
        key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\bambu-studio.exe"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, key) as k:
                    cands.insert(0, winreg.QueryValue(k, None))
            except OSError:
                pass
    except ImportError:
        pass
    cands.append(shutil.which(EXE_NAME) or "")
    return next((c for c in cands if c and os.path.isfile(c)), None)


def presets_root():
    if is_linux():
        home = os.path.expanduser("~")
        roots = [os.path.join(home, d, "BambuStudio", "system", "BBL")
                 for d in (f".var/app/{FLATPAK_ID}/config", ".config")]
        return next((r for r in roots if os.path.isdir(r)), roots[-1])
    return os.path.join(os.environ.get("APPDATA", ""), "BambuStudio", "system", "BBL")


def is_flatpak(exe):
    return is_linux() and os.path.basename(os.path.realpath(exe)) == FLATPAK_ID


def sandbox_sees(folder):
    """Asks the Flatpak sandbox itself, so permission overrides are respected."""
    # hazard: the sandbox has its own /tmp, so the folder may exist there with other contents; test a file instead
    with tempfile.NamedTemporaryFile(prefix=".img2bambu_", dir=folder) as f:
        r = _run("flatpak", ["run", "--command=test", FLATPAK_ID, "-r", os.path.abspath(f.name)], timeout=60)
    return r.returncode == 0


def work_dir():
    if not is_linux():
        return tempfile.mkdtemp(prefix="img2bambu_")
    # hazard: the Flatpak sandbox has a private /tmp, so files there are invisible to the CLI
    root = os.path.join(os.path.expanduser("~"), ".cache", "img2bambu")
    os.makedirs(root, exist_ok=True)
    return tempfile.mkdtemp(prefix="img2bambu_", dir=root)


class PresetDB:
    """Instantiable system presets of the installed Bambu Studio (user presets are not loadable by CLI)."""

    def __init__(self, root=None):
        self.root = root or presets_root()
        self.raw = {"machine": {}, "process": {}, "filament": {}}
        self._cache = {}
        for kind in self.raw:
            for p in glob.glob(os.path.join(self.root, kind, "*.json")):
                try:
                    with open(p, encoding="utf-8") as f:
                        d = json.load(f)
                except (OSError, ValueError):
                    continue
                if "name" in d:
                    self.raw[kind][d["name"]] = (p, d)

    @property
    def ok(self):
        return bool(self.raw["machine"])

    def _inst(self, kind):
        return sorted(n for n, (_, d) in self.raw[kind].items() if d.get("instantiation") == "true")

    def machines(self):
        return self._inst("machine")

    def _compatible(self, kind, machine):
        out = []
        for n in self._inst(kind):
            comp = self.resolve(kind, n).get("compatible_printers") or []
            if machine in comp:
                out.append(n)
        return out

    def processes(self, machine):
        return self._compatible("process", machine)

    def filaments(self, machine):
        return self._compatible("filament", machine)

    def path(self, kind, name):
        return self.raw[kind][name][0]

    def resolve(self, kind, name):
        key = (kind, name)
        if key not in self._cache:
            self._cache[key] = self._resolve(kind, name)
        return self._cache[key]

    def _resolve(self, kind, name):
        chain, seen = [], set()
        while name and name in self.raw[kind] and name not in seen:
            seen.add(name)
            d = self.raw[kind][name][1]
            chain.append(d)
            name = d.get("inherits")
        merged = {}
        for d in reversed(chain):
            merged.update(d)
        return merged

    def defaults(self, machine):
        m = self.resolve("machine", machine)
        fil = (m.get("default_filament_profile") or [None])[0]
        return m.get("default_print_profile"), fil

    def bed(self, machine):
        m = self.resolve("machine", machine)
        try:
            pts = [tuple(float(v) for v in a.split("x")) for a in m.get("printable_area") or []]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            area = min(xs), min(ys), max(xs), max(ys)
        except (ValueError, IndexError, AttributeError):
            return None
        try:
            height = float(m["printable_height"])
        except (KeyError, TypeError, ValueError):
            height = None
        return (*area, height)

    def bed_center(self, machine):
        b = self.bed(machine)
        if b is None:
            return 128.0, 128.0
        return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _run(exe, args, timeout=900):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # hazard: CLI often exits with 0xC0000005 after finishing successfully; callers check output files instead
    return subprocess.run([exe] + args, capture_output=True, timeout=timeout, creationflags=flags)


def export_project(exe, db, minimal_3mf, out_path, machine, process, filament, colors, workdir=None):
    n = len(colors)
    work = workdir or tempfile.mkdtemp(prefix="img2bambu_")
    raw = os.path.join(work, "cli_export.3mf")
    if os.path.exists(raw):
        os.remove(raw)
    fpath = db.path("filament", filament)
    _run(exe, ["--load-settings", f"{db.path('machine', machine)};{db.path('process', process)}",
               "--load-filaments", ";".join([fpath] * n),
               "--outputdir", work, "--export-3mf", os.path.basename(raw), minimal_3mf])
    if not os.path.isfile(raw):
        raise RuntimeError("Bambu Studio CLI não gerou o projeto 3MF.")
    filament_keys = set(db.resolve("filament", filament))
    patch_project(raw, out_path, colors, filament_keys)
    return out_path


def patch_project(src, dst, colors, filament_keys=()):
    """CLI export leaves per-filament arrays at length 1; GUI then rejects the config. Expand to N."""
    n = len(colors)
    with zipfile.ZipFile(src) as zin:
        d = json.loads(zin.read("Metadata/project_settings.config"))
        if len(d.get("filament_settings_id", [])) != n:
            raise RuntimeError(f"Projeto exportado com {len(d.get('filament_settings_id', []))} filamentos, "
                               f"esperado {n}.")
        for k, v in d.items():
            if isinstance(v, list) and len(v) == 1 and (k in filament_keys or k.startswith("filament_")):
                d[k] = v * n
        d["filament_colour"] = list(colors)
        if "filament_multi_colour" in d:
            d["filament_multi_colour"] = list(colors)
        # invariant: flush matrix is n*n with zero diagonal, vector is 2*n
        d["flush_volumes_matrix"] = ["0" if r == c else FLUSH_DEFAULT for r in range(n) for c in range(n)]
        d["flush_volumes_vector"] = [FLUSH_VECTOR_DEFAULT] * (2 * n)
        tmp = dst + ".tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "Metadata/project_settings.config":
                    data = json.dumps(d, indent=4).encode()
                z.writestr(info, data)
    os.replace(tmp, dst)
    return dst


def slice_check(exe, project, workdir=None):
    """Slice with the project's embedded config only; returns summary dict."""
    work = workdir or tempfile.mkdtemp(prefix="img2bambu_slice_")
    res_path = os.path.join(work, "result.json")
    for f in (res_path, os.path.join(work, "plate_1.gcode")):
        if os.path.exists(f):
            os.remove(f)
    _run(exe, ["--slice", "0", "--outputdir", work, project])
    if not os.path.isfile(res_path):
        raise RuntimeError("Fatiamento de verificação falhou (sem result.json).")
    with open(res_path, encoding="utf-8") as f:
        r = json.load(f)
    plate = (r.get("sliced_plates") or [{}])[0]
    out = {"ok": r.get("return_code") == 0, "changes": plate.get("filament_change_times", 0),
           "colours": [], "time": ""}
    gcode = os.path.join(work, "plate_1.gcode")
    if os.path.isfile(gcode):
        with open(gcode, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if line.startswith("; filament_colour ="):
                    out["colours"] = line.split("=", 1)[1].strip().split(";")
                elif line.startswith("; model printing time:"):
                    out["time"] = line.split("total estimated time:")[-1].strip()
                if i > 4000 and out["time"] and out["colours"]:
                    break
    return out
