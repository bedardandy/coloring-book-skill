import math

import pytest

import charlib
from charlib import (C, DOT, E, G, GM, LINE, P, TXT, W, H, banner, cloud,
                     kid_stand, dog, cat_sitting, letter, limb, matted,
                     page, spage, sparkle, sun, word, word_width,
                     name_trace_page)


# ---------------------------------------------------------------- primitives
def test_txt_escapes_xml():
    out = TXT(10, 10, "Tom & <Jerry>")
    assert "&amp;" in out and "&lt;" in out and "&gt;" in out
    import xml.etree.ElementTree as ET
    ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{out}</svg>')


def test_no_float_noise_in_primitives():
    out = C(1.00000001, 2.55000004, 3.0) + LINE(0.123456, 0, 5, 5)
    assert "000001" not in out and "12345" not in out.replace("0.1 ", "")


def test_meta_attrs_render():
    out = C(0, 0, 5, 4, "white", face="0,0,5", sky="1")
    assert 'data-face="0,0,5"' in out and 'data-sky="1"' in out


def test_pages_are_wellformed_and_chrome_tagged():
    import xml.etree.ElementTree as ET
    svg = spage("Title", C(400, 500, 50), caption="Hello.", num=3)
    root = ET.fromstring(svg)
    assert svg.count('data-chrome="1"') >= 3  # bg rect + border + chrome group


def test_page_output_deterministic():
    body = G(300, 800, kid_stand({"outfit": "tee"}))
    assert page("A", body) == page("A", body)


def test_matted_wraps_mat_group_and_scales_pad():
    inner = C(0, 0, 20)
    out = matted(inner, pad=9, scale=0.5)
    assert 'data-mat="1"' in out
    assert 'data-pad="18.0"' in out  # 9 / 0.5 — local pad doubles
    # visual pad stays 9: mat strokes thickened by 18 at scale 0.5


def test_gm_mirrors_x_only():
    out = GM(100, 100, C(0, 0, 5))
    assert "scale(-1" in out or "scale(-1.0" in out


# ---------------------------------------------------------------- figures
@pytest.mark.parametrize("pose", ["wave", "up", "down", "hold"])
@pytest.mark.parametrize("outfit", ["tee", "dress"])
def test_kid_stand_all_poses_parse(pose, outfit):
    import xml.etree.ElementTree as ET
    t = {"hair": "bob", "glasses": True, "freckles": True, "outfit": outfit}
    svg = f'<svg xmlns="http://www.w3.org/2000/svg">{kid_stand(t, pose)}</svg>'
    ET.fromstring(svg)
    assert 'data-el="figure"' in svg
    assert svg.count('data-hand="1"') == 2


def test_kid_hand_positions_stable():
    """Prop anchors depend on exact hand centers (e.g. hold_teddy redraws)."""
    svg = kid_stand({"outfit": "tee"}, "wave")
    for token in ('cx="-54"', 'cx="55"', 'cy="-94"', 'cy="-186"'):
        assert token in svg, token


def test_legacy_toggle_binds_names():
    charlib.use_legacy_figures(True)
    try:
        assert charlib.kid_stand is charlib._legacy_kid_stand
        assert charlib.dog is charlib._legacy_dog
    finally:
        charlib.use_legacy_figures(False)
    assert charlib.kid_stand is charlib._smooth_kid_stand
    assert charlib.dog is charlib._smooth_dog


def test_animals_parse_with_traits():
    import xml.etree.ElementTree as ET
    for frag in (dog({"coat": "spots"}), dog({"coat": "patch"}),
                 dog({"floppy_ears": False}), cat_sitting({"coat": "stripes"})):
        ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{frag}</svg>')
        assert 'data-el="figure"' in frag


def test_limb_taper_outline_has_hand_when_asked():
    seg = limb((-18, -140), (-40, -110), (-46, -100), hand_r=8)
    assert 'data-hand="1"' in seg
    bare = limb((-18, -140), (-40, -110), (-46, -100))
    assert 'data-hand' not in bare


# ---------------------------------------------------------------- letters
def test_letters_loaded_full_alphabet():
    data = charlib._letters()
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert ch in data["letters"], ch
    for ch in "abcdefghijklmnopqrstuvwxyz":
        assert ch in data["letters"], ch


def test_letter_trace_vs_colorable():
    a = letter("A", 0, 0)
    assert 'fill="white"' in a and "dasharray" not in a
    b = letter("A", 0, 0, style="trace")
    assert 'fill="none"' in b and "dasharray" in b


def test_word_width_monotonic():
    w1 = word_width("MAX", size=100)
    w2 = word_width("MAXIMILIAN", size=100)
    assert 0 < w1 < w2


def test_banner_fits_its_text():
    from charlib import word_width
    text = "HOORAY"
    size = 64
    bw = word_width(text, size) + 2 * 28
    svg = banner(text, 500, size=size)
    # ribbon width equals computed width; both under the printable width
    assert bw < W - 80
    assert f'width="{bw:.1f}"' in svg or f'width="{bw:.0f}"' in svg


def test_name_trace_page_validates_clean():
    from validate import validate_svg
    rep = validate_svg(name_trace_page(["Harper", "Max"]))
    assert rep["ok"], rep["findings"]


# ---------------------------------------------------------------- motifs/sky tags
def test_sky_tokens_tagged():
    assert 'data-sky="1"' in sun(100, 100)
    assert 'data-sky="1"' in cloud(100, 100, 30)
    assert 'data-sky="1"' in sparkle(100, 100)


def test_wheel_ground_tagged():
    from charlib import _wheel
    out = _wheel(100, 900, 24)
    assert 'data-ground="900"' in out
