import argparse
import os
import sys

from . import bambu, pipeline, segment
from .params import Params, hex_color


def main(argv=None):
    ap = argparse.ArgumentParser(prog="img2bambu", description="Imagem -> projeto 3MF multicor Bambu Studio")
    ap.add_argument("image")
    ap.add_argument("--out", default=None)
    ap.add_argument("--width", type=float, default=150.0)
    ap.add_argument("--base", type=float, default=10.0)
    ap.add_argument("--relief", type=float, default=1.0)
    ap.add_argument("--colors", type=int, default=3)
    ap.add_argument("--smooth", type=int, default=0, choices=range(6), metavar="0-5",
                    help="suavização (mean-shift) antes de detectar as cores; 0 = desligado")
    ap.add_argument("--filaments", type=int, default=0, choices=range(9), metavar="0-8",
                    help="mesclar as cores mais parecidas até sobrar esse número; 0 = desligado")
    ap.add_argument("--printer", default="Bambu Lab A1 0.4 nozzle")
    ap.add_argument("--process", default=None)
    ap.add_argument("--filament", default=None)
    ap.add_argument("--check", action="store_true", help="fatiar para verificar trocas de filamento")
    ap.add_argument("--stl-only", action="store_true")
    a = ap.parse_args(argv)

    params = Params(width_mm=a.width, base_mm=a.base, relief_mm=a.relief, n_colors=a.colors, smooth=a.smooth,
                    filaments=a.filaments)
    an = segment.analyze(a.image, params)
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
        choice = pipeline.BambuChoice(exe, a.printer, a.process or proc, a.filament or fil, a.check)
    res = pipeline.export(an, an.palette, params, outdir, name, choice, db,
                          progress=lambda p, m: print(f"[{p:3d}%] {m}"))
    for s in res.stls:
        print("STL:", s)
    if res.project:
        print("Projeto:", res.project)
    if res.check:
        print("Verificação:", res.check)
    for w in res.warnings:
        print("Aviso:", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
