import json
import os
import subprocess

import pytest
from test_core import preset_db, synthetic

from img2bambu import __main__ as cli
from img2bambu import bambu, pipeline, segment
from img2bambu.params import Params

OK = {"ok": True, "changes": 3, "colours": [], "time": "", "error": "", "warnings": []}


def fake_cli(monkeypatch, result):
    def run(exe, args, timeout=900):
        out = args[args.index("--outputdir") + 1]
        # why: the real CLI leaves no result.json when it fails and the folder does not exist
        if result is not None and os.path.isdir(out):
            with open(os.path.join(out, "result.json"), "w", encoding="utf-8") as f:
                f.write(result if isinstance(result, str) else json.dumps(result))
    monkeypatch.setattr(bambu, "_run", run)


def test_slice_check_reports_reason_and_warnings(tmp_path, monkeypatch):
    fake_cli(monkeypatch, {"return_code": -104, "error_string": " G-code fora ",
                           "sliced_plates": [{"filament_change_times": 2, "warning_message": "cuidado"}]})
    r = bambu.slice_check("exe", "p.3mf", str(tmp_path / "missing" / "slice"))
    assert (r["ok"], r["error"], r["warnings"], r["changes"]) == (False, "G-code fora", ["cuidado"], 2)


def test_slice_check_success_has_no_error(tmp_path, monkeypatch):
    fake_cli(monkeypatch, {"return_code": 0, "error_string": "Success.", "sliced_plates": [{}]})
    r = bambu.slice_check("exe", "p.3mf", str(tmp_path / "s"))
    assert r["ok"] and r["error"] == "" and r["warnings"] == []


@pytest.mark.parametrize("result", [None, "{broken"])
def test_slice_check_without_result_fails_with_reason(tmp_path, monkeypatch, result):
    fake_cli(monkeypatch, result)
    r = bambu.slice_check("exe", "p.3mf", str(tmp_path / "s"))
    assert not r["ok"] and "não informou" in r["error"]


def test_slice_check_timeout(tmp_path, monkeypatch):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired("exe", 1)
    monkeypatch.setattr(bambu, "_run", slow)
    r = bambu.slice_check("exe", "p.3mf", str(tmp_path / "s"))
    assert not r["ok"] and "demorou" in r["error"]


@pytest.mark.parametrize("width,check,error", [
    (60, OK, None), (60, {**OK, "ok": False, "error": "motivo"}, "motivo"), (60, {**OK, "changes": 0}, "sem trocas"),
    (60, {**OK, "ok": False, "changes": 0, "error": "motivo"}, "motivo"), (300, OK, "maior que a mesa")])
def test_export_collects_errors_and_keeps_project(tmp_path, monkeypatch, width, check, error):
    db = preset_db(tmp_path, "machine", {"name": "M", "printable_area": ["0x0", "256x0", "256x256", "0x256"],
                                         "printable_height": "256"})
    monkeypatch.setattr(bambu, "export_project", lambda *a, **k: None)
    monkeypatch.setattr(bambu, "slice_check", lambda *a, **k: check)
    p = Params(width_mm=width)
    an = segment.analyze(synthetic(), p)
    res = pipeline.export(an, an.palette, p, str(tmp_path / "o"), "t",
                          pipeline.BambuChoice("exe", "M", "P", "F", True), db)
    assert res.project.endswith("t.3mf")
    assert len(res.errors) == (1 if error else 0) and all(error in e for e in res.errors)


@pytest.mark.parametrize("errors,code", [([], 0), (["motivo"], 1)])
def test_cli_exit_code(tmp_path, monkeypatch, capsys, errors, code):
    from PIL import Image
    Image.fromarray(synthetic()).save(tmp_path / "t.png")
    monkeypatch.setattr(pipeline, "export",
                        lambda *a, **k: pipeline.Result(stls=[], project="x.3mf", errors=errors))
    assert cli.main([str(tmp_path / "t.png"), "--stl-only"]) == code
    cap = capsys.readouterr()
    assert "Projeto: x.3mf" in cap.out and ("Erro: motivo" in cap.err) == bool(errors)


def test_cli_export_failure_is_not_a_traceback(tmp_path, monkeypatch, capsys):
    from PIL import Image
    Image.fromarray(synthetic()).save(tmp_path / "t.png")

    def boom(*a, **k):
        raise RuntimeError("sem projeto")
    monkeypatch.setattr(pipeline, "export", boom)
    assert cli.main([str(tmp_path / "t.png"), "--stl-only"]) == 1
    assert "Erro: sem projeto" in capsys.readouterr().err
