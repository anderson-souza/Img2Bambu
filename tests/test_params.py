import pytest
from PIL import Image
from test_core import synthetic

from img2bambu import __main__ as cli
from img2bambu import bambu
from img2bambu.params import LIMITS, Palette, Params


def palette(**kw):
    return Palette([(0, 0, 0), (100, 100, 100), (200, 200, 200)], **kw)


def test_defaults_are_inside_the_limits():
    for key, (lo, hi) in LIMITS.items():
        assert lo <= getattr(Params(), key) <= hi


def test_streak_and_outline_exclude_each_other():
    p = palette(streak={1})
    p.set_outline(1, True)
    assert (p.streak, p.outline) == (set(), {1})
    p.set_streak(1, True)
    assert (p.streak, p.outline) == ({1}, set())
    p.set_outline(1, False)
    assert (p.streak, p.outline) == ({1}, set())


def test_merge_moves_the_base_and_undoing_keeps_it():
    p = palette(base_index=0)
    assert p.merge(0, 2)
    assert (p.merges, p.base_index) == ({0: 2}, 2)
    assert p.merge(0, None)
    assert (p.merges, p.base_index) == ({}, 2)


@pytest.mark.parametrize("merges", [{1: 0}, {1: 0, 0: 2}])
def test_merge_refuses_a_cycle(merges):
    p = palette(base_index=2, merges=dict(merges))
    label = 2 if 0 in merges else 0
    assert not p.merge(label, 1)
    assert (p.merges, p.base_index) == (merges, 2)


def test_merge_refusing_a_cycle_keeps_the_previous_target():
    p = palette(base_index=2, merges={0: 2, 1: 0})
    assert not p.merge(0, 1)
    assert p.merges == {0: 2, 1: 0}


@pytest.mark.parametrize("bad", ["1", "9"])
def test_cli_colors_out_of_range_exits_2(monkeypatch, capsys, bad):
    monkeypatch.setattr(cli.segment, "analyze", lambda *a: pytest.fail("analyzed"))
    with pytest.raises(SystemExit) as e:
        cli.main(["missing.png", "--colors", bad])
    assert e.value.code == 2
    assert "--colors" in capsys.readouterr().err


@pytest.fixture
def run(monkeypatch, tmp_path):
    db = bambu.PresetDB(root=str(tmp_path / "none"))
    db.raw = {"machine": {"M": ("m.json", {"default_print_profile": "P", "default_filament_profile": ["F"]}),
                          "Bare": ("b.json", {})},
              "process": {"P": ("p.json", {})}, "filament": {"F": ("f.json", {}), "G": ("g.json", {})}}
    monkeypatch.setattr(cli.bambu, "PresetDB", lambda: db)
    monkeypatch.setattr(cli.bambu, "find_exe", lambda: "bambu-studio")
    Image.fromarray(synthetic()).save(tmp_path / "t.png")
    choices = []

    def export(an, pal, params, outdir, name, choice, *a, **kw):
        assert name == "t"
        choices.append((choice.machine, choice.process, choice.filament))
        return cli.pipeline.Result(stls=[])
    monkeypatch.setattr(cli.pipeline, "export", export)

    def go(*args):
        cli.main([str(tmp_path / "t.png"), *args])
        return choices
    go.db, go.choices = db, choices
    return go


def test_cli_uses_defaults_and_overrides(run):
    run("--printer", "M")
    assert run("--printer", "M", "--filament", "G") == [("M", "P", "F"), ("M", "P", "G")]


@pytest.mark.parametrize("args, said", [
    (["--printer", "X"], "não instalado: X. Informe outro com --printer"),
    (["--printer", "Bare"], "'Bare' não tem preset padrão. Informe um com --process"),
    (["--printer", "M", "--process", "X"], "não instalado: X. Informe outro com --process"),
    (["--printer", "M", "--filament", "X"], "não instalado: X. Informe outro com --filament"),
])
def test_cli_refuses_missing_presets_before_exporting(run, capsys, args, said):
    with pytest.raises(SystemExit) as e:
        run(*args)
    assert e.value.code == 2 and run.choices == []
    assert said in capsys.readouterr().err


def test_cli_refuses_a_default_filament_that_is_not_installed(run, capsys):
    del run.db.raw["filament"]["F"]
    with pytest.raises(SystemExit):
        run("--printer", "M")
    assert run.choices == [] and "não instalado: F" in capsys.readouterr().err
    assert run("--printer", "M", "--filament", "G") == [("M", "P", "G")]
