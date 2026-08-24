"""Photo -> coloring-outline pipeline tests. All fixtures are synthetic
(deterministic) — no personal photos in the repo."""
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import pytest

from charlib import spage
import photolib
from validate import validate_svg

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    d = tmp_path_factory.mktemp("photos")
    out = {}
    for kind in ("animal", "house", "car"):
        p = d / f"{kind}.png"
        cv2.imwrite(str(p), photolib.synthetic_photo(kind))
        out[kind] = str(p)
    return out


# ---------------------------------------------------------------- fixtures
def test_synthetic_photo_deterministic():
    a = photolib.synthetic_photo("animal")
    b = photolib.synthetic_photo("animal")
    assert np.array_equal(a, b)


def test_load_photo_exif_and_scale(tmp_path):
    from PIL import Image
    p = tmp_path / "big.png"
    Image.new("RGB", (3000, 1500), (128, 128, 128)).save(p)
    gray, _ = photolib.load_photo(str(p), max_dim=800)
    assert max(gray.shape) <= 800


# ---------------------------------------------------------------- detection
def test_detect_subject_returns_chain(fixtures):
    gray, bgr = photolib.load_photo(fixtures["animal"])
    mask, label, meta = photolib.detect_subject(gray, bgr)
    assert label in photolib.POLICIES
    assert mask is None or mask.shape == gray.shape


def test_policies_cover_core_subjects():
    for label in ("face", "person", "vehicle", "building", "animal",
                  "plant", "generic"):
        assert label in photolib.POLICIES
        pol = photolib.POLICIES[label]
        assert "edge_c" in pol and "simplify" in pol and "max_strokes" in pol


# ---------------------------------------------------------------- pipeline
@pytest.mark.parametrize("kind", ["animal", "house", "car"])
def test_photo_to_svg_validates_clean(fixtures, kind):
    svg = photolib.photo_to_svg(fixtures[kind], title=kind.title())
    ET.fromstring(svg)
    rep = validate_svg(svg, require_span=False)
    highs = [f for f in rep["findings"] if f["severity"] == "HIGH"]
    assert not highs, highs
    q = photolib._qa_report(svg)["raster"]
    assert q["print_safe"]
    # colorability: a good trace keeps slivers in the production baseline
    assert q["sliver_count"] <= 70


def test_sketch_style_produces_lines(fixtures):
    svg = photolib.photo_to_svg(fixtures["animal"], style="sketch")
    q = photolib._qa_report(svg)["raster"]
    assert q["regions"] >= 3


def test_determinism(fixtures):
    a = photolib.photo_to_svg(fixtures["car"], title="T")
    b = photolib.photo_to_svg(fixtures["car"], title="T")
    assert a == b


def test_detail_levels_change_output(fixtures):
    low = photolib.photo_to_svg(fixtures["animal"], detail="low")
    high = photolib.photo_to_svg(fixtures["animal"], detail="high")
    assert low != high


def test_no_splinter_explosion(fixtures):
    """The anti-splinter doctrine: stroke count stays in a sane band."""
    svg = photolib.photo_to_svg(fixtures["animal"])
    strokes = svg.count("<path")
    assert 2 <= strokes <= photolib.POLICIES["generic"]["max_strokes"] + 8


# ---------------------------------------------------------------- integration
def test_fragment_is_placeable_and_anchored(fixtures):
    import re
    frag = photolib.photo_to_fragment(fixtures["car"])
    assert 'data-el="photo-trace"' in frag
    m = re.search(r'translate\((-?\d+\.?\d*),(-?\d+\.?\d*)\)', frag)
    assert m, "fragment must carry its feet-anchor translate"
    bcx, bcy = float(m.group(1)), float(m.group(2))
    # local origin = ink bottom-centre: the lowest PATH point maps to y ~= 0
    paths = re.findall(r'<path d="([^"]+)"', frag)
    assert paths
    lowest = max(max(float(v) for v in re.findall(r"-?\d+\.?\d*", d)[1::2])
                 for d in paths)
    assert abs(lowest + bcy) <= 3.0


def test_composite_page_validates(fixtures):
    import scenes
    svg = photolib.composite_page(
        fixtures["animal"], scenes.scene_meadow(), scenes.SCENE_GROUND,
        x=580, scale=0.95, title="Friends", caption="Hello friend.")
    rep = validate_svg(svg, require_span=False)
    highs = [f for f in rep["findings"] if f["severity"] == "HIGH"]
    assert not highs, highs


def test_cli(fixtures, tmp_path):
    out = tmp_path / "page.svg"
    r = subprocess.run(
        [sys.executable, "-m", "lib.photolib", fixtures["car"],
         "-o", str(out), "--title", "CLI"],
        capture_output=True, text=True, timeout=300, cwd=REPO)
    assert r.returncode == 0, r.stderr
    assert out.exists()
    ET.fromstring(out.read_text())
