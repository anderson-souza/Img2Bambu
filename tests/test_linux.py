import os
import subprocess

import pytest
from test_core import synthetic

from img2bambu import __main__ as cli
from img2bambu import bambu, pipeline, segment
from img2bambu.params import Params

FLATPAK = bambu.FLATPAK_ID
PRESETS = ("BambuStudio", "system", "BBL")


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return str(path)


@pytest.fixture
def linux(monkeypatch, tmp_path):
    """Linux with an empty home, no bambu-studio on PATH and no Flatpak."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(bambu.sys, "platform", "linux")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(bambu, "FLATPAK_SYSTEM_BIN", str(tmp_path / "sys"))
    monkeypatch.setattr(bambu.shutil, "which", lambda name: None)
    return home


def test_find_exe_order(linux, monkeypatch, tmp_path):
    assert bambu.find_exe() is None
    system = touch(tmp_path / "sys" / FLATPAK)
    assert bambu.find_exe() == system
    user = touch(linux / ".local" / "share" / "flatpak" / "exports" / "bin" / FLATPAK)
    assert os.path.samefile(bambu.find_exe(), user)
    native = touch(tmp_path / "bin" / "bambu-studio")
    monkeypatch.setattr(bambu.shutil, "which", lambda name: native if name == "bambu-studio" else None)
    assert bambu.find_exe() == native


def test_presets_prefer_flatpak(linux):
    native = linux.joinpath(".config", *PRESETS)
    assert not bambu.PresetDB().ok
    native.mkdir(parents=True)
    assert os.path.samefile(bambu.presets_root(), native)
    flatpak = linux.joinpath(".var", "app", FLATPAK, "config", *PRESETS)
    flatpak.mkdir(parents=True)
    assert os.path.samefile(bambu.presets_root(), flatpak)


def test_windows_locations_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(bambu.sys, "platform", "win32")
    monkeypatch.setattr(bambu.shutil, "which", lambda name: None)
    monkeypatch.setitem(__import__("sys").modules, "winreg", None)
    for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.setenv(v, str(tmp_path / "none"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(bambu.tempfile, "tempdir", str(tmp_path))
    exe = touch(tmp_path / "pf" / "Bambu Studio" / "bambu-studio.exe")
    assert bambu.find_exe() == exe
    assert bambu.presets_root() == os.path.join(str(tmp_path / "appdata"), *PRESETS)
    assert os.path.dirname(bambu.work_dir()) == str(tmp_path)


@pytest.mark.parametrize("fail", [False, True])
def test_work_files_in_cache_and_removed(linux, monkeypatch, tmp_path, fail):
    seen = []

    def fake_export(exe, db, minimal, out, *args, workdir):
        assert os.path.isfile(minimal)
        seen.append(workdir)
        if fail:
            raise RuntimeError("boom")

    monkeypatch.setattr(bambu, "export_project", fake_export)
    p = Params(width_mm=40)
    an = segment.analyze(synthetic(), p)
    choice = pipeline.BambuChoice("bambu-studio", "m", "p", "f")

    def run():
        return pipeline.export(an, an.palette, p, str(tmp_path / "out"), "t", choice, bambu.PresetDB())

    if fail:
        with pytest.raises(RuntimeError, match="boom"):
            run()
    else:
        assert run().project.endswith("t.3mf")
    cache = linux / ".cache" / "img2bambu"
    assert os.path.samefile(os.path.dirname(seen[0]), cache)
    assert list(cache.iterdir()) == []


def export_with(monkeypatch, outdir, exe, code):
    """Exports with a fake `flatpak` exiting with `code`; returns the probe commands that ran."""
    ran = []

    def fake_run(args, **kw):
        ran.append(args)
        assert os.path.isfile(args[-1]) and os.path.samefile(os.path.dirname(args[-1]), outdir)
        return subprocess.CompletedProcess(args, code)

    monkeypatch.setattr(bambu.subprocess, "run", fake_run)
    monkeypatch.setattr(bambu, "export_project", lambda *a, **k: None)
    p = Params(width_mm=40)
    an = segment.analyze(synthetic(), p)
    choice = pipeline.BambuChoice(exe, "m", "p", "f") if exe else None
    pipeline.export(an, an.palette, p, str(outdir), "t", choice, bambu.PresetDB())
    return ran


def test_flatpak_refuses_unseen_folder(linux, monkeypatch, tmp_path):
    exe, out = touch(tmp_path / "sys" / FLATPAK), tmp_path / "out"
    with pytest.raises(RuntimeError) as e:
        export_with(monkeypatch, out, exe, 1)
    assert str(e.value) == (f"O Bambu Studio (Flatpak) não acessa a pasta de saída: {out}. "
                            "Escolha uma dentro da sua pasta pessoal.")
    assert list(out.iterdir()) == []


def test_flatpak_accepts_seen_folder(linux, monkeypatch, tmp_path):
    out = tmp_path / "out"
    ran = export_with(monkeypatch, out, touch(tmp_path / "sys" / FLATPAK), 0)
    assert [r[:-1] for r in ran] == [["flatpak", "run", "--command=test", FLATPAK, "-r"]]
    assert sorted(f.suffix for f in out.iterdir()) == [".png", ".stl", ".stl", ".stl"]


@pytest.mark.parametrize("native", [True, False])
def test_no_folder_check_without_flatpak(linux, monkeypatch, tmp_path, native):
    exe = touch(tmp_path / "bin" / "bambu-studio") if native else None
    assert export_with(monkeypatch, tmp_path / "out", exe, 1) == []


def test_system_flatpak_location():
    assert bambu.FLATPAK_SYSTEM_BIN == "/var/lib/flatpak/exports/bin"


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlink_to_flatpak_is_flatpak(linux, tmp_path):
    link = tmp_path / "bambu-studio"
    link.symlink_to(touch(tmp_path / "sys" / FLATPAK))
    assert bambu.is_flatpak(str(link))


def test_probe_failure_is_explained(linux, monkeypatch, tmp_path):
    def missing(*a, **k):
        raise FileNotFoundError("flatpak")
    monkeypatch.setattr(bambu.subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="Não foi possível consultar o Flatpak"):
        bambu.sandbox_sees(str(tmp_path))


def test_windows_keeps_work_files_and_slices_inside(monkeypatch, tmp_path):
    dirs = []
    monkeypatch.setattr(bambu.sys, "platform", "win32")
    monkeypatch.setattr(bambu.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(bambu, "export_project", lambda *a, workdir: dirs.append(workdir))
    monkeypatch.setattr(bambu, "slice_check", lambda *a, workdir: dirs.append(workdir) or {"changes": 1})
    p = Params(width_mm=40)
    an = segment.analyze(synthetic(), p)
    choice = pipeline.BambuChoice("bambu-studio.exe", "m", "p", "f", check=True)
    pipeline.export(an, an.palette, p, str(tmp_path / "out"), "t", choice, bambu.PresetDB(root=str(tmp_path)))
    assert os.path.isfile(os.path.join(dirs[0], "minimal.3mf"))
    assert dirs[1] == os.path.join(dirs[0], "slice")


def test_cli_without_presets_writes_stls(linux, monkeypatch, tmp_path, capsys):
    from PIL import Image
    Image.fromarray(synthetic()).save(tmp_path / "t.png")
    touch(tmp_path / "sys" / FLATPAK)
    assert cli.main([str(tmp_path / "t.png"), "--width", "40", "--out", str(tmp_path / "out")]) == 0
    assert "Presets do Bambu Studio não encontrados" in capsys.readouterr().out
    assert len(list((tmp_path / "out").glob("*.stl"))) == 3
