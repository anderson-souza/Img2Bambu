import numpy as np
import pytest

from img2bambu import geometry, pipeline, segment
from img2bambu.params import Params
from test_core import synthetic


def test_model_matches_export_parts():
    p = Params()
    an = segment.analyze(synthetic(), p)
    ref = geometry.build_parts(*segment.build_masks(an, an.palette, p), an.palette, p)
    got = pipeline.model(an, an.palette, p)
    assert len(got) == len(ref) == 3
    for g, r in zip(got, ref):
        assert g.name == r.name
        assert tuple(g.color) == tuple(r.color)
        assert np.allclose(g.mesh.bounds, r.mesh.bounds)


def test_model_z_bounds_follow_base_and_relief():
    p = Params(base_mm=3.0, relief_mm=2.0)
    an = segment.analyze(synthetic(), p)
    base, *colors = pipeline.model(an, an.palette, p)
    assert base.mesh.bounds[:, 2] == pytest.approx([0.0, 3.0])
    assert colors
    for pt in colors:
        assert pt.mesh.bounds[:, 2] == pytest.approx([3.0, 5.0])


def test_model_all_merged_is_base_only():
    p = Params()
    an = segment.analyze(synthetic(), p)
    pal = an.palette
    for i in range(len(pal.colors)):
        if i != pal.base_index:
            pal.merges[i] = pal.base_index
    parts = pipeline.model(an, pal, p)
    assert len(parts) == 1
    assert parts[0].name.startswith("Base ")


def test_model_empty_silhouette_raises():
    p = Params()
    an = segment.analyze(synthetic(), p)
    an.sil[:] = False
    with pytest.raises(ValueError, match="^Silhueta vazia após limpeza.$"):
        pipeline.model(an, an.palette, p)
