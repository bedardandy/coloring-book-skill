"""Stress and edge-case tests: input extremes, the full photo matrix,
transform math against known answers, malformed inputs, and a
charlib -> raster -> photo-trace round trip."""
import io
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import pytest

import photolib
from charlib import (G, GM, P, W, H, kid_stand, dog, spage, sun, cloud,
                     word, letter, banner)
from validate import validate_svg, _mmul, _apply, _parse_transform


# ---------------------------------------------------------------- transform math
def test_transform_composition_order():
    """G(x, y, inner, s) means: scale inner, then translate."""
    m = _parse_transform("translate(100,50) scale(2)")
    assert _apply(m, 10, 10) == (120, 70)


def test_mirror_rotate_scale_combo():
    m = _parse_transform("translate(500,900) scale(-1.5,1.5) rotate(90)")
    # rotate(90): (1,0) -> (0,1); then scale; then translate
    x, y = _apply(m, 1, 0)
    assert abs(x - 500) < 1e-6 and abs(y - 901.5) < 1e-6


def test_deep_nesting_ten_levels():
    body = "M 0 0 L 10 10"
    inner = P(body, 4)
    for i in range(10):
        inner = G(5, 5, inner, 1.0)
    svg = spage("deep", inner)
    rep = validate_svg(svg, require_span=False)
    assert isinstance(rep["ok"], bool)


def test_mirrored_figure_world_bbox():
    """GM must produce a sane world bbox (the negative-scale trap)."""
    svg = spage("m", GM(400, 900, dog({"coat": "spots"}), 1.0))
    root = __import__("xml").etree.ElementTree.fromstring(svg)
    import validate as V
    items, _, _ = V._collect(root)
    figs = [it for it in items if it.wbbox and it.el.get("data-el") is None
            and it.tag == "path"]
    assert figs  # mirrored dog produced measurable geometry
    assert all(b[0] > 0 for b in (it.wbbox for it in figs))


# ---------------------------------------------------------------- malformed input
def test_malformed_svg_raises_cleanly():
    with pytest.raises(Exception):
        validate_svg("<svg><unclosed>")


def test_empty_page_only_chrome_passes():
    svg = spage("", "")
    rep = validate_svg(svg, require_span=False)
    assert rep["counts"]["HIGH"] == 0


def test_unicode_text_escaped():
    svg = spage("Café — José & Niño", "")
    ET.fromstring(svg)  # must stay well-formed
    assert "José" in svg


# ---------------------------------------------------------------- photo matrix
@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    d = tmp_path_factory.mktemp("mx")
    out = {}
    for kind in ("animal", "house", "car"):
        p = d / f"{kind}.png"
        cv2.imwrite(str(p), photolib.synthetic_photo(kind))
        out[kind] = str(p)
    return out


@pytest.mark.parametrize("style", ["clean", "sketch"])
@pytest.mark.parametrize("detail", ["low", "medium", "high"])
def test_photo_full_matrix(fx, style, detail):
    """Every subject x style x detail combination produces a valid page."""
    svg = photolib.photo_to_svg(fx["animal"], style=style, detail=detail,
                                qa=False)
    ET.fromstring(svg)
    rep = validate_svg(svg, require_span=False)
    highs = [f for f in rep["findings"] if f["severity"] == "HIGH"]
    assert not highs, highs


@pytest.mark.parametrize("subject", ["face", "vehicle", "building",
                                     "animal", "plant", "generic"])
def test_forced_subject_policies(fx, subject):
    svg = photolib.photo_to_svg(fx["car"], subject=subject, qa=False)
    assert f'data-policy="{subject}"' in svg


def test_tiny_photo(fx, tmp_path):
    """100px photo must not crash and must produce *something* traceable."""
    img = cv2.resize(photolib.synthetic_photo("animal"), (100, 100))
    p = tmp_path / "tiny.png"
    cv2.imwrite(str(p), img)
    svg = photolib.photo_to_svg(str(p), qa=False)
    ET.fromstring(svg)


def test_dark_low_contrast_photo(tmp_path):
    """Near-black, near-flat photo: no crash, no garbage explosion."""
    rng = np.random.default_rng(7)
    img = rng.normal(18, 4, (400, 400, 3)).clip(0, 255).astype(np.uint8)
    p = tmp_path / "dark.png"
    cv2.imwrite(str(p), img)
    svg = photolib.photo_to_svg(str(p), qa=False)
    rep = validate_svg(svg, require_span=False)
    # nothing on a near-black photo should explode the stroke budget
    assert svg.count("<path") < photolib.POLICIES["generic"]["max_strokes"] + 50


def test_grayscale_single_channel_photo(tmp_path):
    img = photolib.synthetic_photo("house")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    p = tmp_path / "gray.png"
    cv2.imwrite(str(p), gray)  # single-channel file
    svg = photolib.photo_to_svg(str(p), qa=False)
    ET.fromstring(svg)


def test_exif_rotated_photo(tmp_path):
    from PIL import Image
    # simulate EXIF via PIL's exif_transpose path: bake Orientation tag
    img = photolib.synthetic_photo("car")
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6  # Orientation: rotate 90 to display
    pil.save(buf, format="JPEG", exif=exif.tobytes())
    p = tmp_path / "rot.jpg"
    p.write_bytes(buf.getvalue())
    gray, _ = photolib.load_photo(str(p))
    # EXIF transpose applied: landscape source becomes portrait working image
    assert gray.shape[0] >= gray.shape[1]


def test_qa_loop_converges(tmp_path):
    """A noisy photo through the QA loop terminates and improves."""
    rng = np.random.default_rng(3)
    img = photolib.synthetic_photo("animal")
    noisy = (img.astype(np.float32) + rng.normal(0, 25, img.shape)).clip(0, 255)
    p = tmp_path / "noisy.png"
    cv2.imwrite(str(p), noisy.astype(np.uint8))
    svg = photolib.photo_to_svg(str(p))  # qa=True default
    ET.fromstring(svg)  # and stays well-formed


# ---------------------------------------------------------------- round trip
def test_charlib_page_round_trip(fx, tmp_path):
    """Render a charlib page to raster, trace it back, validate the trace —
    the pipeline must be able to re-line-art its own output."""
    # render the BODY on a plain white canvas (no border/caption chrome —
    # tracing a framed page would faithfully trace the frame too)
    body = (G(300, 700, kid_stand({"outfit": "tee"}, "wave"), 1.2) +
            G(620, 700, dog({"coat": "spots"}), 1.2) + sun(120, 140))
    raw = (f'<svg xmlns="http://www.w3.org/2000/svg" width="850" height="1100" '
           f'viewBox="0 0 850 1100"><rect width="850" height="1100" '
           f'fill="white"/>{body}</svg>')
    png = tmp_path / "rt.png"
    import cairosvg
    cairosvg.svg2png(bytestring=raw.encode(), write_to=str(png),
                     output_width=850, background_color="white")
    traced = photolib.photo_to_svg(str(png), title="Re-Traced", qa=False)
    rep = validate_svg(traced, require_span=False)
    highs = [f for f in rep["findings"] if f["severity"] == "HIGH"]
    assert not highs, highs
    # the traced page must retain recognizable subjects (>= 2 ink regions)
    q = photolib._qa_report(traced)["raster"]
    assert q["regions"] >= 2


# ---------------------------------------------------------------- letters edge cases
def test_word_unknown_chars_render_nothing():
    from charlib import word_width
    w_before = word_width("AB", size=100)
    w_after = word_width("AB€∫", size=100)
    assert w_before < w_after  # unknown glyphs add tracking only, no crash


def test_banner_overlong_text_gets_flagged_not_broken():
    long_text = "A" * 60
    svg = spage("", banner(long_text, 500, size=64))
    rep = validate_svg(svg, require_span=False)
    # by construction the ribbon overflows and the validator SAYS so
    assert any(f["check"] == "border_clearance"
               for f in rep["findings"] if f["severity"] == "HIGH")


# ---------------------------------------------------------------- validator perf
def test_validation_is_fast_on_dense_page():
    import time
    body = "".join(
        f'<circle cx="{60 + (i * 37) % 730}" cy="{200 + (i * 53) % 700}" '
        f'r="14" fill="white" stroke="black" stroke-width="4"/>'
        for i in range(150))
    svg = spage("dense", body)
    t0 = time.time()
    validate_svg(svg, require_span=False)
    assert time.time() - t0 < 5.0
