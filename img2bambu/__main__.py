import argparse
import os
import sys

from PIL import UnidentifiedImageError

from . import bambu, pipeline, segment
from .params import LIMITS, Params, hex_color


def _choices(key):
    lo, hi = LIMITS[key]
    return {"choices": range(lo, hi + 1), "metavar": f"{lo}-{hi}"}


def _mm(key):
    lo, hi = LIMITS[key]

    def parse(text):
        try:
            v = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"número inválido: {text!r}") from None
        if not lo <= v <= hi:   # why: also rejects nan
            raise argparse.ArgumentTypeError(f"{text} fora do intervalo {lo:g}-{hi:g} mm")
        return v
    return {"type": parse, "metavar": f"{lo:g}-{hi:g}"}


def _message(e, image):
    if isinstance(e, UnidentifiedImageError):
        return f"arquivo não é uma imagem reconhecida: {image}"
    if isinstance(e, FileNotFoundError):
        return f"arquivo não encontrado: {e.filename or image}"
    if isinstance(e, OSError):
        return f"falha ao acessar {e.filename or image}: {e.strerror or e}"
    return str(e)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="img2bambu", description="Imagem -> projeto 3MF multicor Bambu Studio")
    ap.add_argument("image")
    ap.add_argument("--out", default=None)
    ap.add_argument("--width", default=150.0, **_mm("width_mm"))
    ap.add_argument("--base", default=10.0, **_mm("base_mm"))
    ap.add_argument("--relief", default=1.0, **_mm("relief_mm"))
    ap.add_argument("--colors", type=int, default=3, **_choices("n_colors"))
    ap.add_argument("--smooth", type=int, default=0, **_choices("smooth"),
                    help="suavização (mean-shift) antes de detectar as cores; 0 = desligado")
    ap.add_argument("--filaments", type=int, default=0, **_choices("filaments"),
                    help="mesclar as cores mais parecidas até sobrar esse número; 0 = desligado")
    ap.add_argument("--printer", default="Bambu Lab A1 0.4 nozzle")
    ap.add_argument("--process", default=None)
    ap.add_argument("--filament", default=None)
    ap.add_argument("--check", action="store_true", help="fatiar para verificar trocas de filamento")
    ap.add_argument("--stl-only", action="store_true")
    a = ap.parse_args(argv)

    params = Params(width_mm=a.width, base_mm=a.base, relief_mm=a.relief, n_colors=a.colors, smooth=a.smooth,
                    filaments=a.filaments)
    try:
        an = segment.analyze(a.image, params)
    except (OSError, ValueError) as e:   # why: UnidentifiedImageError is an OSError
        print("Erro:", _message(e, a.image), file=sys.stderr)
        return 1
    if an.note:
        print(an.note)
    pal = an.palette
    print("Paleta:", [hex_color(c) for c in pal.colors], "base:", pal.base_index)
    if pal.merges:
        m = len(pal.active())
        print(f"Mesclagem automática: {len(pal.colors)} cores → {m} filamento{'s' if m != 1 else ''}.")
        for i in sorted(pal.merges):
            print(f"Mesclada: {hex_color(pal.colors[i])} → {hex_color(pal.colors[pal.resolve(i)])}")
    outdir = a.out or os.path.join(os.path.dirname(os.path.abspath(a.image)), "img2bambu_saida")
    name = os.path.splitext(os.path.basename(a.image))[0]

    choice, db = None, None
    exe = None if a.stl_only else bambu.find_exe()
    if exe:
        db = bambu.PresetDB()
        if not db.ok:
            print("Presets do Bambu Studio não encontrados: só STLs serão gerados. Abra o Bambu Studio uma vez.")
    if db and db.ok:
        proc, fil = db.defaults(a.printer)
        proc, fil = a.process or proc, a.filament or fil
        for opt, kind, preset in (("printer", "machine", a.printer), ("process", "process", proc),
                                  ("filament", "filament", fil)):
            if preset not in db.raw[kind]:
                ap.error(f"preset não instalado: {preset}. Informe outro com --{opt}." if preset else
                         f"a impressora '{a.printer}' não tem preset padrão. Informe um com --{opt}.")
        choice = pipeline.BambuChoice(exe, a.printer, proc, fil, a.check)
    try:
        res = pipeline.export(an, an.palette, params, outdir, name, choice, db,
                              progress=lambda p, m: print(f"[{p:3d}%] {m}"))
    except (RuntimeError, OSError, ValueError) as e:
        print("Erro:", _message(e, a.image), file=sys.stderr)
        return 1
    for s in res.stls:
        print("STL:", s)
    if res.project:
        print("Projeto:", res.project)
    if res.check:
        print("Verificação:", res.check)
    for w in res.warnings:
        print("Aviso:", w)
    for e in res.errors:
        print("Erro:", e, file=sys.stderr)
    return 1 if res.errors else 0


if __name__ == "__main__":
    sys.exit(main())
