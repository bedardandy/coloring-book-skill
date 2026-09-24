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
    bw = word_width(text, size, tracking=size * 0.08) + 2 * 28
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


# ---------------------------------------------------------------- fragment geometry
def test_fragment_bbox_tight_transformed_and_mat_free():
    from charlib import fragment_bbox, heart
    # circle + stroke: r=10 grown by half the 4px stroke
    assert fragment_bbox(C(0, 0, 10, 4)) == (-12, -12, 12, 12)
    assert fragment_bbox(C(0, 0, 10, 4), stroke=False) == (-10, -10, 10, 10)
    # nested G() scale/translate expanded to world space
    bb = fragment_bbox(G(100, 50, C(0, 0, 10, 0), 2.0))
    assert bb == (80, 30, 120, 70)
    # knockout mats are invisible: the matted copy must not grow the box
    assert fragment_bbox(matted(C(0, 0, 10, 4), pad=20)) == (-12, -12, 12, 12)
    # curves are sampled ON the curve: a heart's C-handles reach 1.4s but
    # the lobes only ~0.9s, so the box must be well inside the handles
    x0, _y0, x1, _y1 = fragment_bbox(heart(0, 0, 50, 0))
    assert 40 < x1 < 60 and -60 < x0 < -40
    assert fragment_bbox("") is None


def test_fit_fragment_centres_and_keeps_stroke_weight():
    from charlib import fit_fragment, fragment_bbox
    placed = fit_fragment(C(0, 0, 10, 4), 300, 400, 200, 200)
    x0, y0, x1, y1 = fragment_bbox(placed)
    assert abs((x0 + x1) / 2 - 300) < 1 and abs((y0 + y1) / 2 - 400) < 1
    assert abs((x1 - x0) - 200) < 12          # fitted (stroke kept ~4px)
    assert 'stroke-width="0.408"' in placed      # 4 / k(=196/20) restroked
    # anchor="bottom": geometry stands ON (cx, cy) — grids of grounded items
    stood = fit_fragment(C(0, 0, 10, 4), 300, 400, 200, 200, anchor="bottom")
    assert abs(fragment_bbox(stood, stroke=False)[3] - 400) < 0.5


def test_sticker_sheet_motifs_fill_their_cells():
    import re
    from charlib import sticker_sheet, fragment_bbox, star, heart
    svg = sticker_sheet([star(0, 0, 30, 4, "white"), heart(0, 0, 26, 4, "white")])
    cells = re.findall(r'<rect x="([0-9.]+)" y="([0-9.]+)" width="([0-9.]+)" '
                       r'height="[0-9.]+" rx="12"', svg)
    assert cells and all(float(c[2]) + 16 >= 200 for c in cells)   # cells >=200
    for frag in re.findall(r'(<g transform="translate[^"]*scale\([^)]*\)">.*?</g>)', svg):
        x0, y0, x1, y1 = fragment_bbox(frag)
        assert max(x1 - x0, y1 - y0) >= 0.6 * 200


def test_symmetry_page_motif_fills_the_page_width():
    import re
    import xml.etree.ElementTree as ET
    from charlib import symmetry_page, fragment_bbox
    for motif in ("butterfly", "heart", "star", "flower", "face"):
        svg = symmetry_page(motif, caption="Draw the other half!")
        root = ET.fromstring(svg)
        # the solid (left-clipped) half: measure its unclipped geometry
        solid = "".join(ET.tostring(el, encoding="unicode") for el in root.iter()
                        if el.get("clip-path") == "url(#symL)")
        solid = re.sub(r' xmlns:ns0="[^"]*"|ns0:', "", solid)
        g = re.search(r'<g transform="translate\(([0-9.]+),([0-9.]+)\)', svg)
        bb = fragment_bbox(f'<g transform="translate({g.group(1)},{g.group(2)})">{solid}</g>')
        width = 2 * (float(g.group(1)) - bb[0])        # solid half mirrored
        assert 0.52 * W <= width <= 0.68 * W, (motif, width)
        assert bb[1] >= 150 and bb[3] <= 1000, (motif, bb)


def test_bubbles_speaker_top_tail_ends_above_the_head():
    import re
    from charlib import speech_bubble, thought_bubble, fragment_bbox
    for tail in ("down", "left", "right"):
        frag = speech_bubble(tail=tail, speaker_top=(400, 500))
        # the tail triangle's apex is the only vertex at the tip y
        tail_path = re.findall(r'<path d="M [^"]*L ([0-9.]+) ([0-9.]+) L', frag)[0]
        tx, ty = float(tail_path[0]), float(tail_path[1])
        assert (tx, ty) == (400, 480), (tail, tx, ty)
        # the balloon sits entirely above the tip — never over the head
        assert fragment_bbox(frag)[3] <= 480 + 3, tail
    tb = thought_bubble(speaker_top=(400, 500))
    assert fragment_bbox(tb, stroke=False)[3] <= 480.5   # last puff ends 20px above
    # legacy positional call unchanged
    assert speech_bubble(200, 300).startswith('<rect x="95.0" y="250.0"')


def test_finish_page_object_straddles_axis_and_fills_width():
    import re
    from charlib import finish_page, fragment_bbox
    for kind in ("house", "rocket", "butterfly", "face"):
        svg = finish_page(kind)
        g = re.search(r'<g transform="translate\(([0-9.]+),([0-9.]+)\)[^"]*">', svg)
        ax = float(g.group(1))
        # the solid copy (first placed group) must straddle the mirror axis
        # so the dashed right-half ghost actually has something to show
        body = svg[g.start():svg.index("</g>", g.start()) + 4]
        x0, y0, x1, y1 = fragment_bbox(body)
        assert x0 < ax - 150 and x1 > ax + 150, (kind, x0, x1, ax)
        assert x1 - x0 >= 0.5 * W and y0 >= 150 and y1 <= 1000, kind
