import os
import shutil
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from . import bambu, export3mf, geometry, segment, tower
from .params import Palette, Params, hex_color


@dataclass
class BambuChoice:
    exe: str
    machine: str
    process: str
    filament: str
    check: bool = False


@dataclass
class Result:
    stls: list
    project: str = ""
    preview: str = ""
    check: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def render(an, palette: Palette, params: Params):
    sil_m, masks = segment.build_masks(an, palette, params)
    return sil_m, masks, segment.preview(sil_m, masks, palette)


def model(an, palette: Palette, params: Params):
    return geometry.build_parts(*segment.build_masks(an, palette, params), palette, params)


def export(an, palette: Palette, params: Params, outdir, basename, choice: BambuChoice = None,
           db: bambu.PresetDB = None, progress=lambda pct, msg: None):
    os.makedirs(outdir, exist_ok=True)
    if choice and choice.exe and bambu.is_flatpak(choice.exe) and not bambu.sandbox_sees(outdir):
        raise RuntimeError(f"O Bambu Studio (Flatpak) não acessa a pasta de saída: {outdir}. "
                           "Escolha uma dentro da sua pasta pessoal.")
    progress(5, "Separando cores…")
    sil_m, masks, prev = render(an, palette, params)
    progress(30, "Gerando malhas 3D…")
    parts = geometry.build_parts(sil_m, masks, palette, params)
    res = Result(stls=[])
    progress(55, "Salvando STLs…")
    res.stls = export3mf.write_stls(parts, outdir, basename)
    res.preview = os.path.join(outdir, f"{basename}_preview.png")
    Image.fromarray(prev).save(res.preview)
    colors = [hex_color(p.color) for p in parts]
    if len(parts) > 4:
        res.warnings.append(f"{len(parts)} cores: mais que um AMS (4 slots).")
    if not choice or not choice.exe:
        res.warnings.append("Projeto Bambu não gerado (Bambu Studio ausente ou desativado): apenas STLs.")
        progress(100, "Concluído (somente STLs).")
        return res
    db = db or bambu.PresetDB()
    work = bambu.work_dir()
    try:
        _export_bambu(parts, colors, outdir, basename, choice, db, work, res, progress)
    finally:
        # why: unlike /tmp, ~/.cache is never emptied by the system
        if bambu.is_linux():
            shutil.rmtree(work, ignore_errors=True)
    progress(100, "Concluído.")
    return res


def _place_tower(parts, choice, db, res):
    proc = db.resolve("process", choice.process)
    bed = db.bed(choice.machine)
    if len(parts) < 2 or bed is None or str(proc.get("enable_prime_tower")) != "1":
        return None
    size = tower.side(len(parts), float(proc["layer_height"]), float(proc.get("prime_volume", 45)))
    pos = tower.place(bed, db.bed_exclude(choice.machine),
                      tower.footprint(parts[0].mesh, db.bed_center(choice.machine)), size)
    if pos is None:
        res.warnings.append(f"Sem espaço na mesa para a torre de purga (cerca de {size + 2 * tower.BRIM:.0f} mm de "
                            "lado): o fatiamento pode falhar. Reduza a peça ou mova a torre no Bambu Studio.")
    return pos


def _export_bambu(parts, colors, outdir, basename, choice, db, work, res, progress):
    bed = db.bed(choice.machine)
    bounds = np.array([p.mesh.bounds for p in parts])
    size = np.round(bounds[:, 1].max(axis=0) - bounds[:, 0].min(axis=0), 3)
    if bed and not bambu.fits(size, bed):
        res.errors.append(f"Modelo maior que a mesa: {' × '.join(f'{v:.1f}' for v in size)} mm.")
    minimal = os.path.join(work, "minimal.3mf")
    export3mf.write_minimal_3mf(parts, minimal, basename, db.bed_center(choice.machine))
    progress(65, "Criando projeto no Bambu Studio…")
    res.project = os.path.join(outdir, f"{basename}.3mf")
    bambu.export_project(choice.exe, db, minimal, res.project, choice.machine, choice.process,
                         choice.filament, colors, _place_tower(parts, choice, db, res), workdir=work)
    if choice.check:
        progress(80, "Verificando (fatiando)…")
        res.check = bambu.slice_check(choice.exe, res.project, workdir=os.path.join(work, "slice"))
        res.warnings += [f"Verificação: {w}" for w in res.check["warnings"]]
        if not res.check["ok"]:
            res.errors.append(f"Verificação: o fatiamento falhou: {res.check['error']}")
        elif len(parts) > 1 and not res.check["changes"]:
            res.errors.append("Verificação: fatiamento sem trocas de filamento.")
