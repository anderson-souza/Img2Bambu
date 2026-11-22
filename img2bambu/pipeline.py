import os
import tempfile
from dataclasses import dataclass, field

from PIL import Image

from . import bambu, export3mf, geometry, segment
from .params import Params, Palette, hex_color


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


def render(an, palette: Palette, params: Params):
    sil_m, masks = segment.build_masks(an, palette, params)
    return sil_m, masks, segment.preview(sil_m, masks, palette)


def model(an, palette: Palette, params: Params):
    return geometry.build_parts(*segment.build_masks(an, palette, params), palette, params)


def export(an, palette: Palette, params: Params, outdir, basename, choice: BambuChoice = None,
           db: bambu.PresetDB = None, progress=lambda pct, msg: None):
    os.makedirs(outdir, exist_ok=True)
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
    work = tempfile.mkdtemp(prefix="img2bambu_")
    minimal = os.path.join(work, "minimal.3mf")
    export3mf.write_minimal_3mf(parts, minimal, basename, db.bed_center(choice.machine))
    progress(65, "Criando projeto no Bambu Studio…")
    res.project = os.path.join(outdir, f"{basename}.3mf")
    bambu.export_project(choice.exe, db, minimal, res.project, choice.machine, choice.process,
                         choice.filament, colors, workdir=work)
    if choice.check:
        progress(80, "Verificando (fatiando)…")
        res.check = bambu.slice_check(choice.exe, res.project, workdir=os.path.join(work, "slice"))
        if len(parts) > 1 and not res.check.get("changes"):
            res.warnings.append("Verificação: fatiamento sem trocas de filamento.")
    progress(100, "Concluído.")
    return res
