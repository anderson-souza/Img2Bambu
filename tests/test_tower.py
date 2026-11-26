import json
import zipfile

import pytest
from shapely.geometry import Point, box
from test_core import _fake_cli_project, preset_db, synthetic

from img2bambu import bambu, geometry, pipeline, segment, tower
from img2bambu.params import Params

BED = (0, 0, 256, 256, 256)
MINI = (0, 0, 180, 180, 180)


def area(pos, size):
    b = tower.BRIM
    return box(pos[0] - b, pos[1] - b, pos[0] + size + b, pos[1] + size + b)


# measured on Bambu Studio 2.9.1 gcode: far edge of the tower, brim included, from its position
@pytest.mark.parametrize("n,layer,far", [(2, .2, 27.2), (3, .2, 34.9), (4, .2, 41.5), (6, .2, 52.0),
                                         (3, .08, 50.0), (3, .28, 31.7), (8, .2, 61.3)])
def test_side_covers_measured_tower(n, layer, far):
    assert far - .5 <= tower.side(n, layer) + tower.BRIM <= far + 5


def test_default_is_kept_when_it_fits():
    assert tower.place(BED, [], box(78, 78, 178, 178), tower.side(3, .2)) == tower.DEFAULT


@pytest.mark.parametrize("bed,n,part", [(MINI, 3, box(60, 60, 120, 120)), (BED, 4, box(78, 78, 178, 178)),
                                        (BED, 3, box(0, 210, 100, 256)),
                                        (BED, 3, Point(128, 128).buffer(105))])
def test_moved_tower_is_on_the_bed_and_clear_of_the_part(bed, n, part):
    size = tower.side(n, .2)
    pos = tower.place(bed, [], part, size)
    assert box(*bed[:4]).buffer(1e-3).contains(area(pos, size))
    assert area(pos, size).distance(part) >= tower.CLEARANCE - .1


def test_no_room():
    assert tower.place(MINI, [], box(15, 15, 165, 165), tower.side(3, .2)) is None
    assert tower.place((0, 0, 30, 30, 30), [], Point(15, 15).buffer(1), tower.side(3, .2)) is None


def test_excluded_corner_is_avoided():
    part, size = box(45, 0, 256, 256), 30
    free = tower.place(BED, [], part.union(box(0, 60, 256, 256)), size)
    assert free is not None
    assert tower.place(BED, [(0, 0), (18, 0), (18, 28), (0, 28)], part.union(box(0, 60, 256, 256)), size) is None


def test_patch_writes_position(tmp_path):
    src, dst = str(tmp_path / "a.3mf"), str(tmp_path / "b.3mf")
    _fake_cli_project(src, 2)
    bambu.patch_project(src, dst, ["#000000", "#FFFFFF"], (), (15.0, 140.0))
    with zipfile.ZipFile(dst) as z:
        d = json.loads(z.read("Metadata/project_settings.config"))
    assert (d["wipe_tower_x"], d["wipe_tower_y"]) == (["15.0"], ["140.0"])


@pytest.mark.parametrize("width,enabled,moved,warned", [(60, "1", True, False), (170, "1", False, True),
                                                        (170, "0", False, False)])
def test_export_places_or_warns(tmp_path, monkeypatch, width, enabled, moved, warned):
    preset_db(tmp_path, "machine", {"name": "M", "instantiation": "true", "printable_height": "180",
                                    "printable_area": ["0x0", "180x0", "180x180", "0x180"]})
    db = preset_db(tmp_path, "process", {"name": "P", "layer_height": "0.2", "enable_prime_tower": enabled})
    seen = []
    monkeypatch.setattr(bambu, "export_project", lambda *a, **k: seen.append(a[8]))
    p = Params(width_mm=width)
    an = segment.analyze(synthetic(), p)
    # why: a square part leaves no free corner
    sil, masks = segment.build_masks(an, an.palette, p)
    sil[:] = True
    parts = geometry.build_parts(sil, masks, an.palette, p)
    monkeypatch.setattr(pipeline.geometry, "build_parts", lambda *a: parts)
    res = pipeline.export(an, an.palette, p, str(tmp_path / "o"), "t", pipeline.BambuChoice("exe", "M", "P", "F"), db)
    assert (seen[0] is not None) == moved
    assert any("torre" in w for w in res.warnings) == warned
