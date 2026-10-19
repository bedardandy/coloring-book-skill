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


# ---------------------------------------------------------------- faces, hints, feature protection
FACE_KEYS = {"eye_l", "eye_r", "nose", "mouth_l", "mouth_r"}


@pytest.fixture(scope="module")
def face_photo(tmp_path_factory):
    p = tmp_path_factory.mktemp("face") / "face_features.png"
    cv2.imwrite(str(p), photolib.synthetic_photo("face_features"))
    return str(p)


@pytest.fixture(scope="module")
def face_traces(face_photo):
    """The portrait fixture traced with its hints, protect_face on / off."""
    hints = photolib.synthetic_face_hints()
    return {pf: photolib.photo_to_svg(face_photo, qa=False, hints=hints,
                                      protect_face=pf)
            for pf in (True, False)}


def test_detect_faces_full_dict_contract(face_photo):
    """YuNet fires on the portrait fixture: the dict shape is a contract
    (charlib.traits_from_landmarks consumes it), _l/_r are IMAGE-left/right,
    and _detect_faces still returns the same boxes as tuples."""
    gray, bgr = photolib.load_photo(face_photo)
    full = photolib.detect_faces_full(gray, bgr)
    assert len(full) == 1
    f = full[0]
    assert {"box", "score", "landmarks"} <= set(f)
    assert set(f["landmarks"]) == FACE_KEYS
    x, y, w, h = f["box"]
    for px, py in f["landmarks"].values():
        assert x <= px <= x + w and y <= py <= y + h
    lm = f["landmarks"]
    assert lm["eye_l"][0] < lm["eye_r"][0] and lm["mouth_l"][0] < lm["mouth_r"][0]
    assert lm["eye_l"][1] < lm["nose"][1] < lm["mouth_l"][1]
    assert 0.0 < f["score"] <= 1.0
    assert photolib._detect_faces(gray, bgr) == [tuple(f["box"])]
    # landmarks land near the fixture's known geometry (within 0.2 IOD)
    truth = photolib.synthetic_face_truth()[0]["landmarks"]
    iod = truth["eye_r"][0] - truth["eye_l"][0]
    for k in ("eye_l", "eye_r", "nose"):
        assert np.hypot(lm[k][0] - truth[k][0], lm[k][1] - truth[k][1]) < 0.2 * iod


def test_no_faces_on_existing_fixtures(fixtures):
    for p in fixtures.values():
        gray, bgr = photolib.load_photo(p)
        assert photolib.detect_faces_full(gray, bgr) == []


def test_face_landmarks_hint_overrides_detection(face_photo):
    faces = photolib.face_landmarks(face_photo, photolib.synthetic_face_hints())
    assert len(faces) == 1                       # the hint replaced YuNet's face
    f = faces[0]
    assert f["source"] == "hint" and f["features"] == ["glasses", "mole"]
    assert "mole" in f["feature_boxes"]
    assert f["landmarks"] == photolib.synthetic_face_truth()[0]["landmarks"]


def test_parse_hints_px_norm_and_image_size():
    shape = (640, 640)
    px = photolib.parse_hints(photolib.synthetic_face_hints(units="px"), shape)
    nm = photolib.parse_hints(photolib.synthetic_face_hints(units="norm"), shape)
    for k in FACE_KEYS:
        a, b = px["faces"][0]["landmarks"][k], nm["faces"][0]["landmarks"][k]
        assert abs(a[0] - b[0]) < 0.6 and abs(a[1] - b[1]) < 0.6
    # px coordinates refer to the ORIGINAL photo (or image_size): a 1280px
    # original traced at 640 halves them
    big = photolib.parse_hints({"subject_box": [200, 100, 600, 800]}, shape,
                               photo_size=(1280, 1280))
    assert big["subject_box"] == (100.0, 50.0, 300.0, 400.0)
    sized = photolib.parse_hints({"image_size": [320, 320],
                                  "keep": [[10, 10, 20, 20]]}, shape)
    assert sized["keep"] == [(20.0, 20.0, 40.0, 40.0)]
    # a box-only face gets canonical landmarks inside its box
    f = photolib.parse_hints({"faces": [{"box": [100, 100, 200, 240]}]},
                             shape)["faces"][0]
    assert set(f["landmarks"]) == FACE_KEYS
    assert f["landmarks"]["eye_l"][0] < f["landmarks"]["eye_r"][0]
    # subject-left given as eye_l by mistake is re-ordered by x
    sw = photolib.parse_hints({"faces": [{"box": [100, 100, 200, 240],
                                          "landmarks": {"eye_l": [250, 200],
                                                        "eye_r": [150, 200]}}]},
                              shape)["faces"][0]["landmarks"]
    assert sw["eye_l"] == (150.0, 200.0)


@pytest.mark.parametrize("bad, words", [
    ({"subjct_box": [1, 2, 3, 4]}, "unknown key"),
    ({"units": "inches"}, "units"),
    ({"label": "dragon"}, "not a policy"),
    ({"subject_box": [1, 2, 3]}, "[x, y, w, h]"),
    ({"subject_box": [10, 10, -5, 20]}, "> 0"),
    ({"subject_box": [5000, 10, 50, 50]}, "outside"),
    ({"subject_box": [0.1, 0.2, 0.5, 0.5]}, "looks normalized"),
    ({"units": "norm", "keep": [[0.1, 0.2, 1.5, 0.5]]}, "0-1"),
    ({"drop": "fence"}, "list"),
    ({"faces": {"box": [1, 1, 5, 5]}}, "list"),
    ({"faces": [{"landmarks": {}}]}, "box"),
    ({"faces": [{"box": [100, 100, 80, 80],
                 "landmarks": {"left_eye": [120, 130]}}]}, "eye_l"),
    ({"faces": [{"box": [100, 100, 80, 80], "features": ["mole"]}]}, "needs a box"),
    ({"faces": [{"box": [100, 100, 80, 80], "score": 3}]}, "[0, 1]"),
    ({"faces": [{"box": [100, 100, 80, 80], "landmarks": {"nose": ["a", 1]}}]},
     "number"),
    ("not-a-dict-or-file.json", "hints file"),
])
def test_parse_hints_rejects_malformed(bad, words):
    with pytest.raises(photolib.HintError) as e:
        photolib.parse_hints(bad, (640, 640))
    assert words in str(e.value)


def test_hints_absent_or_empty_change_nothing(fixtures):
    base = photolib.photo_to_svg(fixtures["animal"], qa=False)
    assert photolib.photo_to_svg(fixtures["animal"], qa=False, hints={},
                                 backends={}) == base
    assert "data-fidelity" not in base


def test_hint_label_and_subject_box(fixtures):
    svg = photolib.photo_to_svg(fixtures["animal"], qa=False,
                                hints={"label": "building"})
    assert 'data-policy="building"' in svg
    gray, bgr = photolib.load_photo(fixtures["animal"])
    mask, label, meta = photolib.detect_subject(
        gray, bgr, hints={"subject_box": [100, 120, 440, 330]})
    assert meta["detector"] == "hint-box" and mask is not None
    ys, xs = np.nonzero(mask)
    assert xs.min() >= 95 and ys.min() >= 115          # GrabCut stays in the rect


def _art_points(svg):
    import re
    body = re.sub(r'<g data-ground="1">.*?</g>', "", svg, flags=re.S)
    body = re.sub(r'<path [^>]*data-knockout="1"/>', "", body)
    art = body[body.index("data-policy"):]
    art = art[:art.index("<g data-chrome")] if "<g data-chrome" in art else art
    return [(float(a), float(b)) for d in re.findall(r' d="([^"]+)"', art)
            for a, b in zip(*[iter(re.findall(r"-?\d+\.?\d*", d))] * 2)]


def test_drop_and_keep_boxes(tmp_path):
    """drop boxes erase traced ink; keep boxes survive the background drop
    (the fence of the clutter test is kept when the hints say so)."""
    img = photolib.synthetic_photo("animal")
    for x in range(40, 200, 24):
        cv2.line(img, (x, 20), (x, 150), (60, 50, 45), 3)
    p = str(tmp_path / "fence.png")
    cv2.imwrite(p, img)
    s, ox, oy = photolib._page_fit(640, 640)

    def in_box(svg, box):
        x, y, w, h = box
        return [(px, py) for px, py in _art_points(svg)
                if ox + x * s <= px <= ox + (x + w) * s
                and oy + y * s <= py <= oy + (y + h) * s]
    fence = [30, 10, 180, 150]
    assert not in_box(photolib.photo_to_svg(p, qa=False), fence)
    kept = photolib.photo_to_svg(p, qa=False, hints={"keep": [fence]})
    assert len(in_box(kept, fence)) >= 4
    eye = [470, 240, 50, 40]                             # the animal's light eye
    base = photolib.photo_to_svg(p, qa=False)
    dropped = photolib.photo_to_svg(p, qa=False, hints={"drop": [eye]})
    assert base != dropped
    inner = [eye[0] + 8, eye[1] + 8, eye[2] - 16, eye[3] - 16]
    assert not in_box(dropped, inner)


def test_protection_zones_cover_features():
    faces = photolib.synthetic_face_truth()
    z = photolib.protection_zones(faces, (640, 640))
    lm = faces[0]["landmarks"]
    for k in FACE_KEYS:
        assert z[int(lm[k][1]), int(lm[k][0])] == 255
    mid = ((lm["eye_l"][0] + lm["eye_r"][0]) / 2, lm["eye_l"][1])
    assert z[int(mid[1]), int(mid[0])] == 255             # glasses bridge (declared)
    assert z[600, 50] == 0 and 0.01 < z.mean() / 255 < 0.15
    assert photolib.protection_zones([], (64, 64)) is None


def test_feature_fidelity_metric():
    faces = photolib.synthetic_face_truth()
    s, ox, oy = photolib._page_fit(640, 640)
    ex, ey = faces[0]["landmarks"]["eye_l"]
    dot = photolib.P(f"M {ox + ex * s:.1f} {oy + ey * s:.1f} L "
                     f"{ox + ex * s + 2:.1f} {oy + ey * s:.1f}", 3.6)
    r = photolib.feature_fidelity([dot], faces, (640, 640))
    assert r["faces"][0]["features"]["eye_l"]["hit"]
    assert r["hits"] == 1 and r["total"] == 7           # 5 landmarks + glasses + mole
    assert r["score"] == round(1 / 7, 3) and "face0.nose" in r["missing"]
    assert photolib.feature_fidelity([], faces, (640, 640))["score"] == 0.0
    assert photolib.feature_fidelity([dot], [], (640, 640))["score"] is None
    # knockout fills never count as ink
    ko = dot.replace('fill="none" stroke="black"', 'fill="white" stroke="none"')
    assert photolib.feature_fidelity([ko], faces, (640, 640))["hits"] == 0


def test_protect_face_improves_feature_fidelity(face_traces):
    """The point of protect_face: on a portrait with known landmarks, eyes,
    nostrils and the mole survive with protection and are lost without it,
    while mottled skin still drops (stroke count stays sane)."""
    truth = photolib.synthetic_face_truth()
    on = photolib.feature_fidelity(face_traces[True], truth, (640, 640))
    off = photolib.feature_fidelity(face_traces[False], truth, (640, 640))
    assert on["score"] >= 0.85, on["missing"]
    assert on["score"] - off["score"] >= 0.3, (on["missing"], off["missing"])
    assert "face0.nose" in off["missing"] and "face0.nose" not in on["missing"]
    strokes_on = face_traces[True].count("<path")
    assert strokes_on - face_traces[False].count("<path") <= 12
    # recorded on the page for the integrator / CLI
    assert photolib.read_fidelity(face_traces[True]) == pytest.approx(on["score"], abs=0.01)
    rep = validate_svg(face_traces[True], require_span=False)
    assert not [f for f in rep["findings"] if f["severity"] == "HIGH"]


def _face_lineart(scale=2, eye_shift=0.0):
    """A clean line drawing of the portrait fixture (what an image model
    asked to 'redraw as a coloring page' returns), at scale x the photo's
    resolution. eye_shift (x IOD) moves the eyes down: identity drift."""
    f = photolib.synthetic_face_truth()[0]
    lm = {k: (v[0] * scale, v[1] * scale) for k, v in f["landmarks"].items()}
    iod = lm["eye_r"][0] - lm["eye_l"][0]
    n = 640 * scale
    img = np.full((n, n), 255, np.uint8)
    t = 3 * scale

    def q(p):
        return (int(round(p[0])), int(round(p[1])))
    cv2.ellipse(img, (n // 2, int(0.505 * n)), (int(0.165 * n), int(0.205 * n)),
                0, 0, 360, 0, t)
    dy = eye_shift * iod
    for k in ("eye_l", "eye_r"):
        c = (lm[k][0], lm[k][1] + dy)
        cv2.ellipse(img, q(c), (int(0.3 * iod), int(0.14 * iod)), 0, 0, 360, 0, t)
        cv2.circle(img, q(c), int(0.08 * iod), 0, -1)
        cv2.ellipse(img, q(c), (int(0.55 * iod), int(0.4 * iod)), 0, 0, 360, 0, t)
    cv2.line(img, q((lm["eye_l"][0] + 0.55 * iod, lm["eye_l"][1] + dy)),
             q((lm["eye_r"][0] - 0.55 * iod, lm["eye_r"][1] + dy)), 0, t)
    nx, ny = lm["nose"]
    for sx in (-1, 1):
        cv2.circle(img, q((nx + sx * 0.12 * iod, ny)), int(0.05 * iod), 0, -1)
    mc = ((lm["mouth_l"][0] + lm["mouth_r"][0]) / 2, lm["mouth_l"][1] - 0.05 * iod)
    cv2.ellipse(img, q(mc), (int((lm["mouth_r"][0] - lm["mouth_l"][0]) / 2),
                             int(0.12 * iod)), 0, 10, 170, 0, t)
    mb = f["feature_boxes"]["mole"]
    cv2.circle(img, q(((mb[0] + mb[2] / 2) * scale, (mb[1] + mb[3] / 2) * scale)),
               int(0.05 * iod), 0, -1)
    return img


def test_trace_lineart_standalone():
    """A synthetic line drawing alone: thresholded, centreline-traced (a
    thick drawn line becomes ONE stroke), stroke-tiered, valid page."""
    img = np.full((600, 600), 255, np.uint8)
    cv2.circle(img, (300, 300), 200, 0, 9)
    cv2.line(img, (200, 260), (400, 260), 0, 7)
    cv2.circle(img, (300, 360), 14, 0, -1)
    svg = photolib.trace_lineart(img, title="Lines")
    ET.fromstring(svg)
    art = svg[svg.index("data-policy"):svg.index("<g data-chrome")]
    assert 2 <= art.count("<path") <= 5
    rep = validate_svg(svg, require_span=False)
    assert not [f for f in rep["findings"] if f["severity"] == "HIGH"]
    assert "data-fidelity" not in svg                     # no faces, no metric
    with pytest.raises(ValueError, match="photo"):
        photolib.photo_to_svg(None)


def test_trace_lineart_aligned_and_identity_drift(face_photo):
    """Line art from a 'generative model' at 2x the photo's resolution is
    aligned onto the photo: landmarks come from the photo + hints, so a
    faithful redraw scores high and a redraw with moved eyes falls below
    FIDELITY_MIN (reject / re-generate)."""
    hints = photolib.synthetic_face_hints()
    good = photolib.trace_lineart(_face_lineart(), photo=face_photo, hints=hints,
                                  qa=False)
    drift = photolib.trace_lineart(_face_lineart(eye_shift=0.9), photo=face_photo,
                                   hints=hints, qa=False)
    assert photolib.read_fidelity(good) >= photolib.FIDELITY_MIN
    assert photolib.read_fidelity(drift) < photolib.FIDELITY_MIN
    assert "face0.eye_l" in drift
    with pytest.raises(ValueError, match="aspect"):
        photolib.trace_lineart(np.full((300, 600), 255, np.uint8), photo=face_photo)
    frag = photolib.trace_lineart(_face_lineart(), photo=face_photo, fragment=True)
    assert 'data-el="photo-trace"' in frag


def test_cli_hints_prints_fidelity(face_photo, tmp_path):
    import json
    hp = tmp_path / "hints.json"
    hp.write_text(json.dumps(photolib.synthetic_face_hints()))
    out = tmp_path / "page.svg"
    r = subprocess.run([sys.executable, "-m", "lib.photolib", face_photo,
                        "-o", str(out), "--hints", str(hp)],
                       capture_output=True, text=True, timeout=300, cwd=REPO)
    assert r.returncode == 0, r.stderr
    assert "feature fidelity" in r.stdout
    hp.write_text(json.dumps({"faces": [{"box": [1, 2, 3]}]}))
    r = subprocess.run([sys.executable, "-m", "lib.photolib", face_photo,
                        "-o", str(out), "--hints", str(hp)],
                       capture_output=True, text=True, timeout=300, cwd=REPO)
    assert r.returncode == 2 and "bad hints" in r.stderr
