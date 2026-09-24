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
        x=560, scale=0.95, title="Friends", caption="Hello friend.")
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


# ---------------------------------------------------------------- centreline + background drop
PHOTOS = os.path.join(REPO, "assets", "photos")


def _band_ink(size=400):
    """A thick open arc (an edge BAND) plus a solid disk (a BLOB)."""
    ink = np.zeros((size, size), np.uint8)
    cv2.ellipse(ink, (size // 2, size // 2), (140, 100), 0, 200, 340, 255, 14)
    cv2.circle(ink, (size // 2, int(size * 0.72)), 22, 255, -1)
    return ink


def test_thin_gives_one_pixel_centreline():
    ink = _band_ink()
    sk = photolib._thin(ink)
    assert sk.dtype == np.uint8 and sk.max() == 1
    # every skeleton pixel lies on the ink, and the band (14px wide, ~370px
    # long) collapses to roughly one pixel per unit length
    assert np.all(ink[sk == 1] > 0)
    band_only = ink.copy()
    cv2.circle(band_only, (200, 288), 30, 0, -1)
    n_band = int(photolib._thin(band_only).sum())
    assert 300 <= n_band <= 480, n_band


def test_skeleton_polylines_walks_one_open_branch():
    ink = _band_ink()
    cv2.circle(ink, (200, 288), 30, 0, -1)               # band only
    polys = photolib._skeleton_polylines(
        photolib._prune(photolib._thin(ink), photolib.SPUR_LEN))
    assert len(polys) == 1
    pts, closed, ends = polys[0]
    assert not closed and ends == 0
    assert photolib._poly_len(pts) > 300


def test_vectorize_traces_band_once_and_outlines_blob():
    """The double-contour fix: a thick band yields ONE stroke (its
    centreline), not both of its sides; a solid disk is outlined."""
    ink = _band_ink()
    gray = np.full(ink.shape, 200, np.uint8)
    gray[ink > 0] = 30                                    # blob is dark
    els = photolib.vectorize(ink, policy=photolib.POLICIES["generic"],
                             gray=gray)
    assert len(els) == 2, els
    closed = [e for e in els if 'Z"' in e]
    assert len(closed) == 1                               # the disk outline
    open_ = [e for e in els if 'Z"' not in e][0]
    # the band's stroke runs once along the arc: its extent matches the
    # arc's, and its control polygon is not ~2x the arc length
    ext = photolib._elements_extent([open_])
    assert ext[2] - ext[0] > 150 * photolib._page_fit(400, 400)[0]
    assert photolib._elements_length([open_]) < 1.5 * 370 * photolib._page_fit(400, 400)[0]


def test_background_drop_removes_clutter_outside_subject(tmp_path):
    """Fence boards and grass outside the dilated subject mask are dropped
    for single-subject (animal/generic/plant) policies; a ground contact
    line is added."""
    img = photolib.synthetic_photo("animal")
    h, w = img.shape[:2]
    for x in range(40, 200, 24):                           # "fence" top-left
        cv2.line(img, (x, 20), (x, 150), (60, 50, 45), 3)
    p = tmp_path / "cluttered.png"
    cv2.imwrite(str(p), img)
    svg = photolib.photo_to_svg(str(p), qa=False)
    assert 'data-ground="1"' in svg
    gray, bgr = photolib.load_photo(str(p))
    mask, label, meta = photolib.detect_subject(gray, bgr)
    assert photolib.POLICIES[label]["bg"] == "drop"
    assert photolib._mask_usable(mask, meta)
    # no traced coordinate lands in the fence region (page coords)
    s, ox, oy = photolib._page_fit(w, h)
    import re
    body = re.sub(r'<g data-ground="1">.*?</g>', "", svg, flags=re.S)
    art = body[body.index("data-policy"):]
    xs_ys = [(float(a), float(b)) for d in re.findall(r' d="([^"]+)"', art)
             for a, b in zip(*[iter(re.findall(r"-?\d+\.?\d*", d))] * 2)]
    fence = [(x, y) for x, y in xs_ys
             if ox + 30 * s <= x <= ox + 210 * s and oy + 10 * s <= y <= oy + 160 * s]
    assert not fence, fence[:5]


def test_fragment_has_no_ground_line(fixtures):
    frag = photolib.photo_to_fragment(fixtures["animal"])
    assert 'data-ground="1"' not in frag


def test_mask_usable_rejects_frame_filling_masks():
    m = np.zeros((100, 100), np.uint8)
    m[5:95, 5:95] = 255                                    # 81% of the frame
    assert not photolib._mask_usable(m)
    m = np.zeros((100, 100), np.uint8)
    m[30:70, 30:70] = 255                                  # framed subject
    assert photolib._mask_usable(m)
    m[:, :25] = 255                                        # spills over the border
    assert not photolib._mask_usable(m)


def test_grabcut_is_reproducible_across_calls(fixtures):
    gray, bgr = photolib.load_photo(fixtures["animal"])
    a = photolib._grabcut(bgr)
    cv2.setRNGSeed(12345)                                  # disturb OpenCV's RNG
    photolib._grabcut(cv2.flip(bgr, 1))
    b = photolib._grabcut(bgr)
    assert a is not None and np.array_equal(a, b)


@pytest.mark.skipif(not os.path.exists(os.path.join(PHOTOS, "teddy.jpg")),
                    reason="sample photo not present")
def test_real_photo_traces_deterministically():
    """The open-licensed sample photo (assets/photos/, attribution in
    CREDITS.md): a real JPEG round-trips through the full pipeline to a
    byte-identical page, validates, and the subject mask is a silhouette."""
    p = os.path.join(PHOTOS, "teddy.jpg")
    a = photolib.photo_to_svg(p, qa=False, title="Teddy")
    b = photolib.photo_to_svg(p, qa=False, title="Teddy")
    assert a == b
    ET.fromstring(a)
    rep = validate_svg(a, require_span=False)
    assert not [f for f in rep["findings"] if f["severity"] == "HIGH"]
    gray, bgr = photolib.load_photo(p)
    mask, label, meta = photolib.detect_subject(gray, bgr)
    assert mask is not None and 0.05 < meta["mask_frac"] < 0.7
