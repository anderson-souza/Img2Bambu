import os
import re
import zipfile
from xml.sax.saxutils import escape, quoteattr


def safe_name(s):
    return re.sub(r"[^\w\-]+", "_", s).strip("_") or "parte"


def write_stls(parts, outdir, basename):
    paths = []
    for i, p in enumerate(parts, 1):
        path = os.path.join(outdir, f"{basename}_{i}_{safe_name(p.name)}.stl")
        p.mesh.export(path)
        paths.append(path)
    return paths


def _mesh_xml(mesh, oid):
    v = "".join(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in mesh.vertices)
    t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.faces)
    return f'<object id="{oid}" type="model"><mesh><vertices>{v}</vertices><triangles>{t}</triangles></mesh></object>\n'


def write_minimal_3mf(parts, path, title, bed_center=(128.0, 128.0)):
    """One object, one part per color, part i -> filament i+1.

    hazard: no `Application` metadata — Bambu Studio CLI crashes loading a file that claims to be
    a Bambu project without project_settings. The GUI ignores this file's config; it is only CLI input.
    """
    lo = parts[0].mesh.bounds[0]
    hi = parts[0].mesh.bounds[1]
    tx, ty = bed_center[0] - (lo[0] + hi[0]) / 2, bed_center[1] - (lo[1] + hi[1]) / 2
    n = len(parts)
    ident = "1 0 0 0 1 0 0 0 1 0 0 0"
    model = ['<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">\n'
             '<metadata name="BambuStudio:3mfVersion">1</metadata>\n'
             f'<metadata name="Title">{escape(title)}</metadata>\n<resources>\n']
    model += [_mesh_xml(p.mesh, i) for i, p in enumerate(parts, 1)]
    model.append(f'<object id="{n + 1}" type="model"><components>' +
                 "".join(f'<component objectid="{i}" transform="{ident}"/>' for i in range(1, n + 1)) +
                 '</components></object>\n</resources>\n')
    model.append(f'<build><item objectid="{n + 1}" transform="1 0 0 0 1 0 0 0 1 {tx:.3f} {ty:.3f} 0" '
                 'printable="1"/></build>\n</model>\n')

    cfg = [f'<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <object id="{n + 1}">\n'
           f'    <metadata key="name" value={quoteattr(title)}/>\n    <metadata key="extruder" value="1"/>\n']
    for i, p in enumerate(parts, 1):
        cfg.append(f'    <part id="{i}" subtype="normal_part">\n'
                   f'      <metadata key="name" value={quoteattr(p.name)}/>\n'
                   f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                   f'      <metadata key="extruder" value="{i}"/>\n    </part>\n')
    cfg.append('  </object>\n</config>\n')

    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", "".join(model))
        z.writestr("Metadata/model_settings.config", "".join(cfg))
    return path
