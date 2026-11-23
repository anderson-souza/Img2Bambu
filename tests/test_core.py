import json
import os
import zipfile

import numpy as np
import pytest

from img2bambu import bambu, export3mf, geometry, pipeline, segment
from img2bambu.params import Params

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEE = os.path.join(ROOT, "..", "new abelha", "Mascote Abelha com Placa ABELHÃO.png")


def synthetic(alpha=True):
    """Black disc with a yellow square and a white bar, on transparent (or white) background."""
    h = w = 400
    img = np.zeros((h, w, 4), np.uint8)
    yy, xx = np.mgrid[:h, :w]
    disc = (yy - 200) ** 2 + (xx - 200) ** 2 < 180 ** 2
    img[disc] = (20, 20, 20, 255)
    img[120:220, 120:220] = (250, 210, 0, 255)
    img[260:300, 100:300] = (240, 240, 240, 255)
    if not alpha:
        img[~disc] = (255, 255, 255, 255)
    return img


@pytest.mark.parametrize("alpha", [True, False])
def test_segment_three_colors(alpha):
    p = Params(width_mm=100, n_colors=3)
    an = segment.analyze(synthetic(alpha), p)
    assert bool(an.note) == (not alpha)
    assert an.sil.shape == (360, 360) or abs(an.sil.shape[0] - 360) <= 2
    base = an.palette.colors[an.palette.base_index]
    assert max(base) < 60, f"base should be the dark ring color, got {base}"
    sil_m, masks = segment.build_masks(an, an.palette, p)
    assert len(masks) == 2
    for m in masks.values():
        assert not (m & ~sil_m.astype(bool)).any()
    a, b = masks.values()
    assert not (a & b).any(), "raised color masks must be disjoint"


def test_parts_watertight_and_heights():
    p = Params(width_mm=100, base_mm=8, relief_mm=1.2)
    an = segment.analyze(synthetic(), p)
    sil_m, masks = segment.build_masks(an, an.palette, p)
    parts = geometry.build_parts(sil_m, masks, an.palette, p)
    assert len(parts) == 3
    assert all(pt.mesh.is_watertight for pt in parts)
    assert parts[0].mesh.bounds[1][2] == pytest.approx(8)
    assert parts[0].mesh.extents[0] == pytest.approx(100, abs=0.5)
    for pt in parts[1:]:
        assert pt.mesh.bounds[0][2] == pytest.approx(8)
        assert pt.mesh.bounds[1][2] == pytest.approx(9.2)


def test_merge_reduces_parts():
    p = Params(width_mm=100)
    an = segment.analyze(synthetic(), p)
    pal = an.palette
    others = [i for i in range(3) if i != pal.base_index]
    pal.merges[others[1]] = others[0]
    sil_m, masks = segment.build_masks(an, pal, p)
    assert list(masks) == [others[0]]


def test_streak_filter_drops_thin_lines():
    img = synthetic()
    img[60:63, 150:250] = (245, 245, 245, 255)       # ~0.75 mm wide streak at 100 mm width
    p = Params(width_mm=100, streak_radius_mm=1.0)
    an = segment.analyze(img, p)
    white = [i for i, c in enumerate(an.palette.colors) if min(c) > 200][0]
    assert white in an.palette.streak
    _, masks = segment.build_masks(an, an.palette, p)
    up = p.upsample
    assert not masks[white][int(50 / 400 * 360) * up:int(70 / 400 * 360) * up].any()


def _fake_cli_project(path, n_fil):
    settings = {"filament_settings_id": ["X"] * n_fil, "filament_colour": ["#00AE42"],
                "filament_type": ["PLA"], "nozzle_temperature": ["220"], "layer_height": "0.2",
                "flush_volumes_matrix": ["0"] * 16, "flush_volumes_vector": ["140"] * 8}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Metadata/project_settings.config", json.dumps(settings))
        z.writestr("3D/3dmodel.model", "<model/>")


def test_patch_project_expands_arrays(tmp_path):
    src, dst = str(tmp_path / "a.3mf"), str(tmp_path / "b.3mf")
    _fake_cli_project(src, 3)
    bambu.patch_project(src, dst, ["#000000", "#FFFF00", "#FFFFFF"], {"nozzle_temperature"})
    with zipfile.ZipFile(dst) as z:
        d = json.loads(z.read("Metadata/project_settings.config"))
        assert z.read("3D/3dmodel.model") == b"<model/>"
    assert d["filament_colour"] == ["#000000", "#FFFF00", "#FFFFFF"]
    assert d["filament_type"] == ["PLA"] * 3
    assert d["nozzle_temperature"] == ["220"] * 3
    assert d["layer_height"] == "0.2"
    assert len(d["flush_volumes_matrix"]) == 9 and d["flush_volumes_matrix"][0] == "0"
    assert len(d["flush_volumes_vector"]) == 6


def test_patch_project_rejects_wrong_count(tmp_path):
    src = str(tmp_path / "a.3mf")
    _fake_cli_project(src, 1)
    with pytest.raises(RuntimeError):
        bambu.patch_project(src, str(tmp_path / "b.3mf"), ["#000000", "#FFFFFF"])


def test_minimal_3mf_assigns_extruders(tmp_path):
    p = Params(width_mm=60)
    an = segment.analyze(synthetic(), p)
    parts = geometry.build_parts(*segment.build_masks(an, an.palette, p), an.palette, p)
    out = export3mf.write_minimal_3mf(parts, str(tmp_path / "m.3mf"), "Teste & <x>")
    with zipfile.ZipFile(out) as z:
        cfg = z.read("Metadata/model_settings.config").decode()
        model = z.read("3D/3dmodel.model").decode()
    assert 'name="Application"' not in model
    for i in (1, 2, 3):
        assert f'<metadata key="extruder" value="{i}"/>' in cfg


@pytest.mark.slow
@pytest.mark.skipif(not (bambu.find_exe() and os.path.isfile(BEE)), reason="needs Bambu Studio + bee image")
def test_bee_end_to_end(tmp_path):
    p = Params(width_mm=150)
    an = segment.analyze(BEE, p)
    db = bambu.PresetDB()
    m = "Bambu Lab A1 0.4 nozzle"
    proc, fil = db.defaults(m)
    choice = pipeline.BambuChoice(bambu.find_exe(), m, proc, fil, check=True)
    res = pipeline.export(an, an.palette, p, str(tmp_path), "abelha", choice, db)
    assert len(res.stls) == 3 and os.path.isfile(res.project)
    assert res.check["changes"] > 0
    assert len(res.check["colours"]) == 3


SAGE, GREEN, PATCH = (215, 213, 179), (171, 171, 107), (180, 178, 120)


def sage_green():
    """Dark disc; left half sage, right half green, with a sage-ish-green patch inside the green half."""
    img = synthetic()
    img[60:340, 60:200] = (*SAGE, 255)
    img[60:340, 200:340] = (*GREEN, 255)
    img[150:250, 240:300] = (*PATCH, 255)
    return img


def _row_of(an, color):
    return min(range(len(an.palette.colors)),
               key=lambda i: sum((a - b) ** 2 for a, b in zip(an.palette.colors[i], color, strict=True)))


def test_analysis_initial_samples_and_filaments():
    an = segment.analyze(sage_green(), Params(width_mm=100, n_colors=3))
    pal = an.palette
    assert len(pal.samples) == len(pal.colors) == 3
    assert pal.edited == set()
    sage = _row_of(an, SAGE)
    assert pal.colors[sage] == SAGE                                  # filament = cluster median
    assert max(abs(a - b) for a, b in zip(pal.samples[sage], SAGE, strict=True)) <= 3   # sample = cluster center


def test_initial_sample_is_cluster_center_not_median():
    img = sage_green()
    img[60:140, 200:340] = (*PATCH, 255)          # ~44% of the green+patch cluster: median != mean
    an = segment.analyze(img, Params(width_mm=100, n_colors=3))
    green = _row_of(an, GREEN)
    assert an.palette.colors[green] == GREEN
    lab = an.lab[an.labels[an.sil] == green].mean(0)
    mean_rgb = segment._to_rgb(lab[None, :])[0]
    assert max(abs(a - b) for a, b in zip(an.palette.samples[green], mean_rgb, strict=True)) <= 1
    assert an.palette.samples[green] != GREEN


def test_sample_edit_pulls_pixels_filament_edit_does_not():
    p = Params(width_mm=100, n_colors=3)
    an = segment.analyze(sage_green(), p)
    pal = an.palette
    sage, green = _row_of(an, SAGE), _row_of(an, GREEN)
    y, x = 200 - 20, 270 - 20                    # patch pixel, in the cropped frame (crop offset 20)
    assert segment.assign(an, pal)[y, x] == green
    pal.samples[sage] = PATCH
    labels = segment.assign(an, pal)
    assert labels[y, x] == sage
    assert labels[100, 100] == sage and labels[100, 260] == green
    pal.colors[sage] = (255, 255, 255)
    assert (segment.assign(an, pal) == labels).all()
    sil_m, masks, prev = pipeline.render(an, pal, p)
    up = p.upsample
    assert tuple(prev[y * up, x * up]) == (255, 255, 255)


def test_unedited_rows_keep_kmeans_split():
    rng = np.random.default_rng(1)
    img = sage_green()
    noise = rng.integers(-25, 26, img[..., :3].shape)
    img[..., :3] = np.clip(img[..., :3].astype(int) + noise, 0, 255).astype(np.uint8)
    an = segment.analyze(img, Params(width_mm=100, n_colors=4))
    pal = an.palette
    assert segment.assign(an, pal) is an.labels
    pal.samples[0] = tuple(pal.samples[0])          # same value re-entered: still unedited
    assert (segment.assign(an, pal) == an.labels).all()
    far = 3
    pal.samples[far] = (0, 0, 255)                  # pure blue: nothing in the image is near it
    labels = segment.assign(an, pal)
    kept = (an.labels >= 0) & (an.labels != far)
    # why: edited palettes use rounded RGB samples, so only boundary pixels may move
    assert (labels[kept] == an.labels[kept]).mean() > 0.99
    assert not (labels == far).any()


def test_criterion_example_pixel_goes_to_nearest_sample():
    img = sage_green()
    img[100:110, 100:110] = (214, 212, 178, 255)
    an = segment.analyze(img, Params(width_mm=100, n_colors=3))
    pal = an.palette
    sage, green = _row_of(an, SAGE), _row_of(an, GREEN)
    pal.samples[sage], pal.samples[green] = SAGE, GREEN
    pal.colors[sage] = (255, 255, 255)
    assert segment.assign(an, pal)[105 - 20, 105 - 20] == sage


def test_equal_samples_tie_goes_to_lower_index():
    an = segment.analyze(sage_green(), Params(width_mm=100, n_colors=3))
    pal = an.palette
    sage, green = _row_of(an, SAGE), _row_of(an, GREEN)
    lo, hi = sorted((sage, green))
    pal.samples[hi] = tuple(pal.samples[lo])
    labels = segment.assign(an, pal)
    assert not (labels == hi).any()
    assert (labels[an.labels == hi] == lo).all()


def test_export_uses_filament_not_sample(tmp_path, monkeypatch):
    p = Params(width_mm=100, n_colors=3)
    an = segment.analyze(sage_green(), p)
    pal = an.palette
    sage = _row_of(an, SAGE)
    pal.samples[sage] = PATCH
    pal.colors[sage] = (255, 255, 255)
    seen = {}
    monkeypatch.setattr(bambu, "export_project", lambda *a, **k: seen.setdefault("colors", a[7]))

    class DB:
        def bed_center(self, m):
            return (128.0, 128.0)
    choice = pipeline.BambuChoice("bambu-studio", "M", "P", "F")
    res = pipeline.export(an, pal, p, str(tmp_path), "t", choice, DB())
    expected = [bambu_hex(pal.colors[i]) for i in [pal.base_index] + [i for i in range(3) if i != pal.base_index]]
    assert sorted(seen["colors"]) == sorted(expected)
    assert "#FFFFFF" in seen["colors"] and bambu_hex(PATCH) not in seen["colors"]
    from PIL import Image
    prev = np.array(Image.open(res.preview))
    up = p.upsample
    assert tuple(prev[180 * up, 250 * up][:3]) == (255, 255, 255)


def bambu_hex(c):
    from img2bambu.params import hex_color
    return hex_color(c)


def _pal(samples, edited=()):
    from img2bambu.params import Palette
    return Palette(colors=[(9, 9, i) for i in range(len(samples))], samples=list(samples), edited=set(edited))


DARK, PINK, LIGHT = (90, 90, 55), (220, 140, 150), (240, 240, 230)


def test_carry_over_follows_color_not_position():
    old = _pal([DARK, PINK, GREEN, LIGHT], {1})
    old.colors[1] = (255, 0, 128)
    # k-means at N=5 re-sorted: pink-ish now sits at index 2
    new = segment.carry_over(old, _pal([DARK, (130, 130, 85), (215, 145, 152), GREEN, LIGHT]))
    assert new.colors[2] == (255, 0, 128) and new.samples[2] == PINK
    assert new.edited == {2}
    assert [new.colors[i] for i in (0, 1, 3, 4)] == [(9, 9, i) for i in (0, 1, 3, 4)]


def test_carry_over_no_row_reused_and_extras_dropped():
    old = _pal([DARK, PINK, GREEN, LIGHT], {0, 1, 3})
    new = segment.carry_over(old, _pal([(100, 95, 60), (230, 235, 225)]))
    assert new.samples == [DARK, LIGHT]                  # the two closest pairs; pink dropped
    assert new.edited == {0, 1}


def test_carry_over_without_edits_is_fresh():
    fresh = _pal([DARK, PINK])
    assert segment.carry_over(None, fresh) is fresh
    assert segment.carry_over(_pal([LIGHT]), fresh).samples == [DARK, PINK]


def _sg_analysis(img=None):
    img = sage_green() if img is None else img
    an = segment.analyze(img, Params(width_mm=100, n_colors=3))
    ys, xs = np.nonzero(img[..., 3] > 128)
    assert an.offset == (ys.min(), xs.min())
    return an


def test_sample_at_uniform_area():
    an = _sg_analysis()
    oy, ox = an.offset
    assert segment.sample_at(an, 200 - oy, 270 - ox) == PATCH


def test_sample_at_means_a_mixed_window():
    an = _sg_analysis()
    oy, ox = an.offset
    # why: window x 198..202 = 2 sage columns + 3 green columns, 10 + 15 pixels
    assert segment.sample_at(an, 100 - oy, 200 - ox) == (189, 188, 136)


def test_sample_at_ignores_background_pixels():
    img = sage_green()
    img[img[..., 3] == 0] = (255, 255, 255, 0)       # bright transparent background
    an = _sg_analysis(img)
    oy, ox = an.offset
    y = 30 - oy                                      # disc edge above the colored areas (they start at y=60)
    x = int(np.argmax(an.sil[y]))                    # first disc pixel of that row
    win = an.sil[y - 2:y + 3, x - 2:x + 3]
    assert 0 < win.sum() < 25
    assert segment.sample_at(an, y, x) == (20, 20, 20)


def test_sample_at_outside_object_is_none():
    an = _sg_analysis()
    assert not an.sil[0:5, 0:5].any()
    assert segment.sample_at(an, 2, 2) is None                       # crop corner, background only
    assert segment.sample_at(an, -10, -10) is None                   # left of / above the crop
    h, w = an.sil.shape
    assert segment.sample_at(an, h + 10, w // 2) is None             # below the crop


def gradient_noise():
    """Opaque disc on transparent black: left-to-right two-color gradient plus speckle noise."""
    h = w = 200
    img = np.zeros((h, w, 4), np.uint8)
    yy, xx = np.mgrid[:h, :w]
    disc = (yy - 100) ** 2 + (xx - 100) ** 2 < 95 ** 2
    t = (xx / (w - 1))[..., None]
    rgb = (1 - t) * np.array([220, 140, 150]) + t * np.array([110, 160, 90])
    rgb += np.random.default_rng(1).normal(0, 12, rgb.shape)
    img[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    img[..., 3] = disc * 255
    img[~disc, :3] = 0
    return img


def _components(an):
    import cv2
    return sum(cv2.connectedComponents((an.labels == i).astype(np.uint8), connectivity=8)[0] - 1
               for i in range(len(an.palette.colors)))


def test_smooth_defaults_off():
    assert Params().smooth == 0


def test_smooth_zero_is_todays_analysis():
    img = gradient_noise()
    an = segment.analyze(img, Params(n_colors=3, smooth=0))
    sil, _ = segment.silhouette(img, Params())
    rgba, sil, _ = segment._crop(img, sil)
    labels, colors, centers, lab = segment.kmeans_palette(rgba, sil, 3)
    assert np.array_equal(an.labels, labels) and np.array_equal(an.lab, lab)
    assert np.array_equal(an.centers, centers) and an.palette.colors == colors
    assert list(an.samples) == segment._to_rgb(centers)


@pytest.mark.parametrize("level,sp,sr", [(1, 4, 8), (3, 12, 24), (5, 20, 40)])
def test_smooth_level_sets_mean_shift_strength(monkeypatch, level, sp, sr):
    import cv2
    seen, real = [], cv2.pyrMeanShiftFiltering

    def spy(rgb, a, b):
        out = real(rgb, a, b)
        seen.append((a, b, out))
        return out
    monkeypatch.setattr(segment.cv2, "pyrMeanShiftFiltering", spy)
    an = segment.analyze(gradient_noise(), Params(n_colors=3, smooth=level))
    ((a, b, out),) = seen
    assert (a, b) == (sp, sr)
    assert np.array_equal(an.lab, segment._to_lab(out[an.sil]))      # clustering ran on the filtered pixels


def test_smooth_reduces_islands():
    img = gradient_noise()
    base = _components(segment.analyze(img, Params(n_colors=3, smooth=0)))
    for level in (1, 3):
        assert _components(segment.analyze(img, Params(n_colors=3, smooth=level))) < base


def test_smooth_ignores_rgb_of_transparent_pixels():
    img = np.zeros((120, 120, 4), np.uint8)
    yy, xx = np.mgrid[:120, :120]
    disc = (yy - 60) ** 2 + (xx - 60) ** 2 < 50 ** 2
    img[disc] = (235, 235, 225, 255)                                  # light edge next to the background
    img[40:80, 40:80] = (200, 90, 110, 255)
    white = img.copy()
    white[~disc] = (255, 255, 255, 0)
    p = Params(n_colors=2, smooth=3)
    a, b = segment.analyze(img, p), segment.analyze(white, p)
    assert np.array_equal(a.labels, b.labels)
    assert a.palette.colors == b.palette.colors
    light = _row_of(a, (235, 235, 225))
    assert (a.labels[a.sil] == light).sum() == (disc.sum() - 1600)    # no dark ring at the edge


def test_smooth_keeps_original_image_for_eyedropper():
    img = gradient_noise()
    an = segment.analyze(img, Params(n_colors=3, smooth=3))
    oy, ox = an.offset
    assert np.array_equal(an.rgba, img[oy:oy + an.sil.shape[0], ox:ox + an.sil.shape[1]])
    y, x = 100 - oy, 100 - ox
    want = tuple(int(v) for v in np.round(img[98:103, 98:103, :3].astype(float).mean((0, 1))))
    assert segment.sample_at(an, y, x) == want


def _cli(monkeypatch, tmp_path, *extra):
    from PIL import Image

    from img2bambu import __main__ as cli
    img = tmp_path / "g.png"
    Image.fromarray(synthetic()).save(img)
    seen, real = [], segment.analyze
    monkeypatch.setattr(cli.segment, "analyze", lambda path, p: (seen.append(p.smooth), real(path, p))[1])
    assert cli.main([str(img), "--stl-only", "--out", str(tmp_path / "out"), *extra]) == 0
    return seen


def test_cli_smooth_flag(monkeypatch, tmp_path):
    assert _cli(monkeypatch, tmp_path, "--smooth", "5") == [5]


def test_cli_smooth_defaults_to_zero(monkeypatch, tmp_path):
    assert _cli(monkeypatch, tmp_path) == [0]


@pytest.mark.parametrize("bad", ["6", "-1", "1.5", "x"])
def test_cli_smooth_out_of_range_exits_2(monkeypatch, capsys, bad):
    from img2bambu import __main__ as cli
    called = []
    monkeypatch.setattr(cli.segment, "load_image", lambda *a: called.append(a))
    monkeypatch.setattr(cli.segment, "analyze", lambda *a: called.append(a))
    with pytest.raises(SystemExit) as e:
        cli.main(["missing.png", "--smooth", bad])
    assert e.value.code == 2 and called == []
    assert "--smooth" in capsys.readouterr().err


def stripes(tones):
    """1000x50 horizontal stripes on a transparent border; tones = [(L, a, b) real LAB, share %], dark -> light."""
    rows = []
    for (L, a, b), pct in tones:
        rgb = segment._to_rgb(np.array([[L * 255 / 100, a + 128, b + 128]], np.float32))[0]
        rows += [rgb] * (pct * 10)
    img = np.zeros((len(rows) + 20, 70, 4), np.uint8)
    img[10:-10, 10:-10, :3] = np.array(rows, np.uint8)[:, None, :]
    img[10:-10, 10:-10, 3] = 255
    return img


def _acyclic(pal):
    act = set(pal.active())
    return all(pal.resolve(i) in act for i in range(len(pal.colors)))


def test_filaments_defaults_off():
    assert Params().filaments == 0


def test_filaments_zero_is_todays_analysis():
    img = sage_green()
    an = segment.analyze(img, Params(n_colors=4))
    sil, _ = segment.silhouette(img, Params())
    rgba, sil, _ = segment._crop(img, sil)
    labels, colors, centers, _ = segment.kmeans_palette(rgba, sil, 4)
    assert an.palette.merges == {}
    assert an.palette.base_index == segment.suggest_base(labels, sil, 4) == an.base
    assert np.array_equal(an.labels, labels) and an.palette.colors == colors
    assert an.palette.samples == segment._to_rgb(centers)


EIGHT = [((10 + 11 * i, 0, 0), 12 if i < 4 else 13) for i in range(8)]


@pytest.mark.parametrize("n,merged", [(8, 0), (9, 0), (7, 1), (0, 0)])
def test_filaments_at_or_above_rows_merges_nothing(n, merged):
    an = segment.analyze(stripes(EIGHT), Params(n_colors=8, filaments=n))
    assert len(an.palette.colors) == 8
    assert len(an.palette.merges) == merged


@pytest.mark.parametrize("m", range(1, 8))
def test_filaments_leaves_exactly_m_active(m):
    pal = segment.analyze(stripes(EIGHT), Params(n_colors=8, filaments=m)).palette
    assert len(pal.active()) == m
    assert _acyclic(pal)
    assert pal.base_index in pal.active()


def test_closest_pair_merges_into_larger():
    # A 40%, A' (ΔE 5 from A) 10%, B 50%
    an = segment.analyze(stripes([((40, 0, 0), 40), ((45, 0, 0), 10), ((80, 0, 0), 50)]),
                         Params(n_colors=3, filaments=2))
    assert an.palette.merges == {1: 0}


def test_small_distinct_color_survives_close_large_ones_merge():
    # C 30% and C' 30% close; D 2% far from all; E 38% far
    tones = [((20, 0, 0), 30), ((26, 0, 0), 30), ((55, 60, 0), 2), ((85, 0, 0), 38)]
    pal = segment.analyze(stripes(tones), Params(n_colors=4, filaments=3)).palette
    assert pal.merges == {1: 0}                 # equal shares -> lower label survives
    assert 2 in pal.active()


def test_group_centroid_is_share_weighted():
    # after X(49%)+Y(1%) merge, the weighted centroid stays near X (L≈10.4): Z is closer to Q (37) than
    # to the group (≈41.6), so Z+Q merge; an unweighted centroid (L=20, 32 away) would take Z instead
    tones = [((10, 0, 0), 49), ((30, 0, 0), 1), ((52, 0, 0), 25), ((89, 0, 0), 25)]
    pal = segment.analyze(stripes(tones), Params(n_colors=4, filaments=2)).palette
    assert pal.merges == {1: 0, 3: 2}


def test_merged_base_moves_to_survivor():
    # disc L40 with a thin L44 outline (the suggested base) and a light L80 square
    gray = [segment._to_rgb(np.array([[L * 255 / 100, 128, 128]], np.float32))[0] for L in (40, 44, 80)]
    img = np.zeros((300, 300, 4), np.uint8)
    yy, xx = np.mgrid[:300, :300]
    r2 = (yy - 150) ** 2 + (xx - 150) ** 2
    img[r2 < 140 ** 2] = (*gray[1], 255)
    img[r2 < 134 ** 2] = (*gray[0], 255)
    img[100:200, 100:200] = (*gray[2], 255)
    an = segment.analyze(img, Params(n_colors=3, filaments=2))
    assert an.base == 1
    assert an.palette.merges == {1: 0}
    assert an.palette.base_index == 0 and 0 in an.palette.active()


def test_auto_merge_is_deterministic():
    p = Params(n_colors=6, filaments=3)
    a, b = segment.analyze(sage_green(), p), segment.analyze(sage_green(), p)
    assert a.palette.merges == b.palette.merges and a.palette.base_index == b.palette.base_index
    assert _acyclic(a.palette)


def test_distance_is_cielab_not_opencv_scaled():
    # A–B differ by ΔL 10 (ΔE 10); A–C by Δa 20 (ΔE 20). OpenCV's 8-bit L (×2.55) would make A–B 25.5
    tones = [((50, 0, 0), 40), ((50, 20, 0), 30), ((60, 0, 0), 30)]
    an = segment.analyze(stripes(tones), Params(n_colors=3, filaments=2))
    a, c, b = (_row_of(an, segment._to_rgb(np.array([[L * 2.55, x + 128, y + 128]], np.float32))[0])
               for (L, x, y), _ in tones)
    assert an.palette.merges == {b: a}


def test_edited_row_absorbs_instead_of_being_merged():
    an = segment.analyze(stripes([((50, 0, 0), 5), ((55, 0, 0), 40), ((90, 0, 0), 55)]), Params(n_colors=3))
    an.palette.edited = {0}                     # X 5% edited, closest to the unedited Y 40%
    assert segment.auto_merge(an, an.palette, 2) == 2
    assert an.palette.merges == {1: 0} and 0 in an.palette.active()


def test_pair_of_edited_rows_is_skipped():
    an = segment.analyze(stripes([((50, 0, 0), 20), ((54, 0, 0), 20), ((70, 0, 0), 60)]), Params(n_colors=3))
    an.palette.edited = {0, 1}                  # A–B (ΔE 4) is the closest pair but both are edited
    assert segment.auto_merge(an, an.palette, 2) == 2
    assert an.palette.merges == {2: 1}          # next closest: B–C; B survives because it is edited


def test_runs_out_of_allowed_pairs_with_more_edited_rows_than_filaments():
    an = segment.analyze(stripes(EIGHT), Params(n_colors=8))
    edited = {0, 2, 4, 6, 7}
    an.palette.edited = set(edited)
    assert segment.auto_merge(an, an.palette, 4) == 5
    assert set(an.palette.active()) == edited
    assert _acyclic(an.palette)


def test_rerun_starts_from_suggested_base():
    an = segment.analyze(stripes(EIGHT), Params(n_colors=8, filaments=1))
    assert segment.auto_merge(an, an.palette, 0) == 8
    assert an.palette.merges == {} and an.palette.base_index == an.base


def _cli_fil(monkeypatch, tmp_path, capsys, *extra):
    from PIL import Image

    from img2bambu import __main__ as cli
    img = tmp_path / "sg.png"
    Image.fromarray(sage_green()).save(img)
    seen, real = [], segment.analyze
    monkeypatch.setattr(cli.segment, "analyze", lambda path, p: (seen.append(p.filaments), real(path, p))[1])
    assert cli.main([str(img), "--stl-only", "--colors", "4", "--out", str(tmp_path / "out"), *extra]) == 0
    out = capsys.readouterr().out.splitlines()
    return seen, out, [line for line in out if line.startswith("STL:")]


def test_cli_filaments_flag_merges_and_prints(monkeypatch, tmp_path, capsys):
    seen, out, stls = _cli_fil(monkeypatch, tmp_path, capsys, "--filaments", "3")
    assert seen == [3]
    i = next(k for k, line in enumerate(out) if line.startswith("Paleta:"))
    assert out[i + 1] == "Mesclagem automática: 4 cores → 3 filamentos."
    an = segment.analyze(sage_green(), Params(n_colors=4))
    from img2bambu.params import hex_color
    assert out[i + 2] == f"Mesclada: {hex_color(_color(an, PATCH))} → {hex_color(_color(an, GREEN))}"
    assert not out[i + 3].startswith("Mesclada:")
    assert len(stls) == 3                       # base + sage + green; the patch went into green


def _color(an, rgb):
    return an.palette.colors[_row_of(an, rgb)]


def test_cli_filaments_defaults_to_zero(monkeypatch, tmp_path, capsys):
    seen, out, stls = _cli_fil(monkeypatch, tmp_path, capsys)
    assert seen == [0] and len(stls) == 4
    assert not any(line.startswith(("Mesclagem", "Mesclada")) for line in out)


def test_cli_filaments_8_accepted(monkeypatch, tmp_path, capsys):
    assert _cli_fil(monkeypatch, tmp_path, capsys, "--filaments", "8")[0] == [8]


@pytest.mark.parametrize("bad", ["9", "-1", "2.5", "x"])
def test_cli_filaments_out_of_range_exits_2(monkeypatch, capsys, bad):
    from img2bambu import __main__ as cli
    called = []
    monkeypatch.setattr(cli.segment, "load_image", lambda *a: called.append(a))
    monkeypatch.setattr(cli.segment, "analyze", lambda *a: called.append(a))
    with pytest.raises(SystemExit) as e:
        cli.main(["missing.png", "--filaments", bad])
    assert e.value.code == 2 and called == []
    assert "--filaments" in capsys.readouterr().err


def test_distance_ignores_area():
    # C 40% and C' 40% are ΔE 6 apart; D 2% is ΔE 15 from C'. Plain distance merges C+C'; an
    # area-weighted (Ward) cost, 6·√20 ≈ 27 vs 15·√(80/42) ≈ 21, would fold the small D in first
    tones = [((20, 0, 0), 40), ((26, 0, 0), 40), ((41, 0, 0), 2), ((85, 0, 0), 18)]
    pal = segment.analyze(stripes(tones), Params(n_colors=4, filaments=3)).palette
    assert pal.merges == {1: 0}


def _cv_lab(L):
    return [L * 255 / 100, 128, 128]


def test_unedited_rows_are_compared_by_kmeans_centers():
    an = segment.analyze(stripes([((30, 0, 0), 30), ((50, 0, 0), 30), ((70, 0, 0), 40)]), Params(n_colors=3))
    an.centers = np.array([_cv_lab(30), _cv_lab(60), _cv_lab(65)], np.float32)   # samples still say 30/50/70
    segment.auto_merge(an, an.palette, 2)
    assert an.palette.merges == {1: 2}          # centers decide (B–C 5), not samples (A–B = B–C = 20)


def test_edited_sample_switches_to_samples():
    an = segment.analyze(stripes([((30, 0, 0), 30), ((50, 0, 0), 30), ((70, 0, 0), 40)]), Params(n_colors=3))
    an.centers = np.array([_cv_lab(30), _cv_lab(60), _cv_lab(65)], np.float32)
    an.palette.samples[0] = segment._to_rgb(np.array([_cv_lab(45)], np.float32))[0]
    segment.auto_merge(an, an.palette, 2)
    assert an.palette.merges == {1: 0}          # samples decide (A 45 – B 50, equal shares); centers: B–C


def test_equal_distances_merge_the_lower_pair():
    an = segment.analyze(stripes([((30, 0, 0), 30), ((50, 0, 0), 30), ((70, 0, 0), 40)]), Params(n_colors=3))
    an.centers = np.array([_cv_lab(30), _cv_lab(50), _cv_lab(70)], np.float32)    # A–B == B–C exactly
    segment.auto_merge(an, an.palette, 2)
    assert an.palette.merges == {1: 0}          # pair (0, 1) before (1, 2); equal shares -> lower survives


def test_cli_one_filament_prints_singular(monkeypatch, tmp_path, capsys):
    _, out, stls = _cli_fil(monkeypatch, tmp_path, capsys, "--filaments", "1")
    assert "Mesclagem automática: 4 cores → 1 filamento." in out
    assert sum(line.startswith("Mesclada:") for line in out) == 3 and len(stls) == 1
