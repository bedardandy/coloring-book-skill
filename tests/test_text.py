"""Page text as Andika glyph paths (charlib.text_path / TXT / wrap_width)
and the validator's handling of <g data-text="1"> runs."""
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

import charlib
import validate as V
from charlib import (C, G, W, TXT, otext, page, spage, text_path, text_width,
                     wrap_width, wrap_words, CAPTION_MAX_W, kid_stand)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_NS = "{http://www.w3.org/2000/svg}"
CAPTION = ("Max and Lily looked under the bed, behind the couch, and inside "
           "the toy box, but Button was nowhere to be found!")


def _page():
    body = G(425, 900, kid_stand({"outfit": "tee", "hair": "bob"}), 1.4)
    return spage("Where Is Button?", body, num=4, caption=CAPTION)


def _runs(svg):
    root = ET.fromstring(svg)
    return [g for g in root.iter(_NS + "g") if g.get("data-text") == "1"]


def _adv_px(s, size):
    F = charlib._letters()
    return sum(F["letters"][c]["adv"] for c in s) * size / F["upem"]


# ---------------------------------------------------------------- (a) determinism
def test_same_page_builds_byte_identical():
    assert _page() == _page()


def test_page_byte_identical_across_fresh_processes():
    """Fresh interpreters (different hash seeds, cold glyph cache) must emit
    the same bytes — nothing host- or run-dependent leaks into the SVG."""
    code = ("import sys; sys.path.insert(0, 'lib'); import charlib as c; "
            "sys.stdout.write(c.spage('Zoë & José', c.C(400, 500, 60), num=3, "
            "caption='A caption long enough to wrap onto a second measured "
            "line of Andika glyph outlines, with ñ and é.'))")
    outs = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONIOENCODING="utf-8")
        outs.append(subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                   env=env, capture_output=True,
                                   check=True).stdout)
    assert outs[0] == outs[1] and b'data-text="1"' in outs[0]


def test_rendered_png_byte_identical():
    cairosvg = pytest.importorskip("cairosvg")
    svg = _page().encode()
    a = cairosvg.svg2png(bytestring=svg, output_width=340)
    b = cairosvg.svg2png(bytestring=svg, output_width=340)
    assert a == b


def test_letters_json_matches_build_tool(tmp_path):
    """lib/letters.json is exactly what tools/build_font.py produces
    (needs the build-only deps: pip install -r requirements-dev.txt)."""
    pytest.importorskip("fontTools")
    pytest.importorskip("pathops")
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import build_font
    finally:
        sys.path.pop(0)
    out = tmp_path / "letters.json"
    build_font.main(build_font.DEFAULT_TTF, str(out))
    with open(os.path.join(ROOT, "lib", "letters.json"), "rb") as fh:
        assert out.read_bytes() == fh.read()


def test_glyph_paths_absolute_mlqcz_only():
    """validate.py pairs path numbers even/odd for bboxes — H/V/relative
    commands in the glyph data would silently misalign that."""
    for ch, g in charlib._letters()["letters"].items():
        assert set(re.sub(r"[-0-9. ]", "", g["d"])) <= set("MLQCZ"), ch


# ---------------------------------------------------------------- (b) no <text>
def test_default_page_has_no_text_element():
    svg = _page()
    assert "<text" not in svg
    runs = _runs(svg)
    assert len(runs) >= 4          # title + 2 caption lines + page number
    labels = [g.get("aria-label") for g in runs]
    assert "Where Is Button?" in labels and "4" in labels
    for g in runs:
        assert g.get("data-w") and g.get("data-size")
        assert all(ch.tag == _NS + "path" for ch in g)


# ---------------------------------------------------------------- (c) measured width
def test_measured_width_is_sum_of_advances():
    s = "Where Is Button?"
    assert text_width(s, 42) == pytest.approx(_adv_px(s, 42))
    g = ET.fromstring(text_path(425, 100, s, 42))
    assert float(g.get("data-w")) == pytest.approx(_adv_px(s, 42), abs=0.05)
    # anchor math: middle centres the advance box on x
    assert float(g.get("data-x0")) == pytest.approx(425 - _adv_px(s, 42) / 2,
                                                    abs=0.05)
    start = ET.fromstring(text_path(100, 100, s, 42, anchor="start"))
    end = ET.fromstring(text_path(700, 100, s, 42, anchor="end"))
    assert float(start.get("data-x0")) == 100
    assert float(end.get("data-x0")) == pytest.approx(700 - _adv_px(s, 42),
                                                      abs=0.05)
    # one glyph path per inked character, pen advanced by real advances
    assert len(g) == len(s.replace(" ", ""))


def test_bold_is_fake_bold_stroke_same_width():
    bold = text_path(0, 0, "Hi", 40, anchor="start")
    reg = text_path(0, 0, "Hi", 40, anchor="start", weight="normal")
    assert "stroke=" in bold and "stroke=" not in reg
    sw = float(re.search(r'stroke-width="([0-9.]+)"', bold).group(1))
    k = 40 / charlib._letters()["upem"]
    assert sw * k == pytest.approx(40 * charlib.BOLD_STROKE, abs=0.01)
    assert ET.fromstring(bold).get("data-w") == ET.fromstring(reg).get("data-w")


# ---------------------------------------------------------------- (d) wrapping
@pytest.mark.parametrize("max_w", [120, 300, CAPTION_MAX_W])
@pytest.mark.parametrize("size", [22, 24])
def test_wrap_never_exceeds_width_nor_empty(max_w, size):
    texts = [CAPTION, "Hi", "   spaced    out   words   ",
             "Supercalifragilisticexpialidocious and a very long "
             "Wolfeschlegelsteinhausenbergerdorff surname",
             "Zoë, José & Niño — “Hooray!” … • ok"]
    for t in texts:
        lines = wrap_width(t, max_w, size)
        assert lines, t
        for ln in lines:
            assert ln and ln.strip() == ln
            assert text_width(ln, size) <= max_w + 1e-9, (ln, max_w)
        # no characters lost or invented
        assert "".join("".join(lines).split()) == "".join(t.split())


def test_wrap_words_legacy_maxchars_still_works():
    lines = wrap_words(CAPTION, 30)
    assert all(len(ln) <= 30 for ln in lines) and len(lines) >= 3


def test_page_caption_lines_fit_measured_width():
    for build in (lambda: page("T", C(400, 500, 60), caption=CAPTION, num=2),
                  _page):
        caps = [g for g in _runs(build()) if g.get("data-size") in ("22", "24")
                and len(g.get("aria-label")) > 3]
        assert len(caps) >= 2
        for g in caps:
            assert float(g.get("data-w")) <= CAPTION_MAX_W


def test_short_caption_single_line_24px_in_page():
    runs = _runs(page("T", C(400, 500, 60), caption="Hello there."))
    assert any(g.get("aria-label") == "Hello there." and
               g.get("data-size") == "24" for g in runs)


# ---------------------------------------------------------------- (e) validator
def test_validator_excludes_text_runs_from_art():
    # art: one small circle; text: big non-chrome labels high and low. If
    # glyph paths counted as scene mass the span check would pass.
    body = (C(425, 550, 50) + TXT(425, 180, "HIGH ABOVE", 60)
            + TXT(425, 990, "LOW BELOW", 60))
    rep = V.validate_svg(spage("T", body))
    span = [f for f in rep["findings"] if f["check"] == "scene_span"]
    assert span and span[0]["severity"] == "HIGH"
    assert "100px" in span[0]["msg"]           # the circle alone
    # nor are they art in the caption/title bands
    assert not [f for f in rep["findings"]
                if f["check"] in ("caption_band", "title_band",
                                  "border_clearance")]


def test_validator_items_flag_text():
    root = ET.fromstring(_page())
    runs = []
    items, _, _ = V._collect(root, runs)
    glyphs = [it for it in items if it.text]
    assert glyphs and all(it.tag == "path" for it in glyphs)
    assert len(runs) >= 4 and sum(len(r.items) for r in runs) == len(glyphs)


def test_text_fit_flags_overwide_title_high_with_exact_width():
    title = "The Most Tremendously Enormous Adventure Ever"
    rep = V.validate_svg(spage(title, C(425, 600, 300)))
    hits = [f for f in rep["findings"] if f["check"] == "text_fit"]
    assert hits and hits[0]["severity"] == "HIGH"
    assert "measured" in hits[0]["msg"]
    assert f"{text_width(title, 42):.0f}px" in hits[0]["msg"]


def test_text_fit_passes_normal_page():
    rep = V.validate_svg(_page())
    assert not [f for f in rep["findings"] if f["check"] == "text_fit"]


def test_text_fit_uses_world_transform_for_nested_runs():
    # a 300px-wide label inside a group translated near the right edge
    lab = TXT(0, 0, "Wide label text here", 30, anchor="start")
    rep = V.validate_svg(spage("T", C(425, 600, 300) + G(700, 500, lab)))
    assert any(f["check"] == "text_fit" and f["severity"] == "HIGH"
               for f in rep["findings"])


def test_lint_book_ignores_text_runs_for_complexity():
    a = spage("A", C(400, 500, 60))
    b = spage("A much longer title here", C(400, 500, 60),
              caption="plus a caption with many glyphs")
    counts = V.lint_book([a, b])["element_counts"]
    assert counts[0] == counts[1]


# ---------------------------------------------------------------- (f) accents / missing
def test_accented_characters_render():
    F = charlib._letters()["letters"]
    out = text_path(425, 300, "é ñ", 40)
    for ch in "éñ":
        assert ch in F and F[ch]["d"] in out
    assert len(ET.fromstring(out)) == 2


def test_accent_fallback_to_base_letter():
    # U+1EA1 (a with dot below) is not baked; NFKD base "a" stands in
    assert "ạ" not in charlib._letters()["letters"]
    assert text_width("Bạ", 30) == pytest.approx(text_width("Ba", 30))


def test_missing_glyph_skipped_with_one_time_warning():
    charlib._TEXT_WARNED.clear()
    with pytest.warns(UserWarning, match="U\\+2713"):
        out = text_path(425, 300, "A✓B", 40)
    ET.fromstring(out)
    assert len(ET.fromstring(out)) == 2
    assert text_width("A✓B", 40) == pytest.approx(text_width("AB", 40))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")      # second use: no new warning
        text_path(425, 300, "✓", 40)


def test_attribute_escaping_in_labels():
    out = text_path(10, 10, 'Say "hi" & <wave>', 20)
    g = ET.fromstring(out)
    assert g.get("aria-label") == 'Say "hi" & <wave>'
    ET.fromstring(charlib.word('A"B&', 400, 400))   # data-word/data-letter


# ---------------------------------------------------------------- (g) legacy switch
def test_text_mode_font_restores_text_elements(monkeypatch):
    monkeypatch.setattr(charlib, "TEXT_MODE", "font")
    svg = spage("Title", C(400, 500, 60), num=3, caption=CAPTION)
    assert "<text" in svg and 'font-family="DejaVu Sans"' in svg
    assert 'data-text="1"' not in svg
    assert otext(400, 400, "MAX", 150).startswith("<text")
    # legacy char-count wrap in font mode
    assert svg.count("<text") == 1 + len(wrap_words(CAPTION, 54)) + 1


def test_otext_routes_to_colorable_word():
    out = otext(W / 2, 400, "MAX", 150, 4)
    assert "<text" not in out and 'data-word="MAX"' in out
    assert out.count('fill="white"') == 3
    start = otext(100, 400, "MAX", 150, 4, anchor="start")
    assert float(ET.fromstring(start).get("data-x0")) == pytest.approx(100, abs=0.1)


# ---------------------------------------------------------------- hollow letters
# (letter / word / banner / name_trace_page / otext): dilated body, overlap-
# free outlines, open counters, dashed trace band. Raster checks render the
# page band y in [_Y0, _Y0 + _BH) at 4x, so widths resolve to 0.25px.
_SC, _Y0, _BH = 4, 380, 260


def _mask(frag):
    """Boolean ink mask (dark pixels) of a fragment on white; row r is page
    y = _Y0 + r / _SC, column c is page x = c / _SC."""
    cairosvg = pytest.importorskip("cairosvg")
    import io
    import numpy as np
    from PIL import Image
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{_BH}" '
           f'viewBox="0 {_Y0} {W} {_BH}"><rect y="{_Y0}" width="{W}" '
           f'height="{_BH}" fill="white"/>{frag}</svg>')
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=W * _SC)
    return np.array(Image.open(io.BytesIO(png)).convert("L")) < 128


def _row_runs(row):
    out, cur, n = [], bool(row[0]), 0
    for v in row:
        if bool(v) == cur:
            n += 1
        else:
            out.append((cur, n))
            cur, n = bool(v), 1
    out.append((cur, n))
    return out


def _stem(size, sw=4, ch="I"):
    """(outer stem width, colorable channel) in px across a hollow stem."""
    m = _mask(charlib.word(ch, 425, 600, size=size, sw=sw))
    r = _row_runs(m[int((600 - size * 0.33 - _Y0) * _SC)])
    first = next(i for i, (v, _n) in enumerate(r) if v)
    b = [i for i, (v, _n) in enumerate(r) if v][:2]
    assert b[0] == first and len(b) == 2, r
    outer = sum(n for _v, n in r[b[0]:b[1] + 1]) / _SC
    channel = sum(n for _v, n in r[b[0] + 1:b[1]]) / _SC
    return outer, channel


@pytest.mark.parametrize("ch", list("MXYKWN"))
def test_overlap_free_glyphs_are_single_contours(ch):
    """build_font.py unions Andika's overlapping strokes: one contour each
    (A keeps exactly outer + counter)."""
    d = charlib._letters()["letters"][ch]["d"]
    assert d.count("M") == 1, ch
    assert charlib._letters()["letters"]["A"]["d"].count("M") == 2


@pytest.mark.parametrize("ch", list("MXYAKWN"))
def test_hollow_interior_has_no_stray_lines(ch):
    """Raster: inside the colorable body (glyph dilated by D - sw, minus a
    2px anti-alias margin and minus the counter bands) there is no ink —
    overlapping source contours would draw lines through it."""
    np = pytest.importorskip("numpy")
    from scipy import ndimage
    size, sw = 120, 4
    D = charlib._hollow_dilation(size, sw, None)
    k = size / charlib._letters()["upem"]
    hollow = _mask(charlib.letter(ch, 300, 600, size=size, sw=sw))
    tr = (f'transform="translate({300 + D / 2},600) '
          f'scale({k},{-k})"')
    ink = [d for dp, _a, d in charlib._glyph_contours(ch) if dp % 2 == 0]
    holes = [d for dp, _a, d in charlib._glyph_contours(ch) if dp % 2]
    body = _mask(f'<g {tr}><path d="{"".join(ink)}" fill="black" '
                 f'stroke="black" stroke-width="{2 * (D - sw) / k}" '
                 f'stroke-linejoin="round"/></g>')
    if holes:   # counters + their centred band are legitimately not body
        hole = _mask(f'<g {tr}><path d="{"".join(holes)}" fill="black" '
                     f'stroke="black" stroke-width="{sw / k}"/></g>')
        body &= ~hole
    core = ndimage.binary_erosion(body, iterations=2 * _SC)
    assert core.sum() > 1000
    assert int((hollow & core).sum()) == 0


def test_hollow_stem_meets_thickness_and_channel_floors():
    outer120, ch120 = _stem(120)
    outer64, _ch64 = _stem(64)
    assert outer120 >= 26 and outer64 >= 14
    assert ch120 >= 12          # drawing-guide colorability floor (~3x3 mm)
    # legacy thin outline (body=0) was the ~7px-channel defect at this size
    m = _mask(charlib.word("I", 425, 600, size=120, body=0))
    r = _row_runs(m[int((600 - 120 * 0.33 - _Y0) * _SC)])
    b = [i for i, (v, _n) in enumerate(r) if v][:2]
    assert sum(n for _v, n in r[b[0] + 1:b[1]]) / _SC < 10 < ch120


@pytest.mark.parametrize("size", [64, 120])
@pytest.mark.parametrize("ch,holes", [("A", 1), ("B", 2), ("O", 1), ("R", 1)])
def test_hollow_counters_stay_open(ch, holes, size):
    """White regions of a hollow glyph: page outside + the colorable body +
    one per counter. A dilation that closed a counter would merge it away."""
    from scipy import ndimage
    frag = charlib.letter(ch, 300, 600, size=size)
    assert 'fill-rule="nonzero"' in frag
    white = ~_mask(frag)
    lab, n = ndimage.label(white)
    sizes = ndimage.sum(white, lab, range(1, n + 1))
    regions = int((sizes > 4 * _SC * _SC).sum())     # ignore AA specks
    assert regions == 2 + holes, (ch, size, regions)


def test_trace_style_band_is_dashed():
    frag = charlib.letter("L", 300, 600, size=150, style="trace")
    assert "stroke-dasharray" in frag
    k = 150 / charlib._letters()["upem"]
    arr = re.search(r'stroke="white"[^>]*stroke-dasharray="([0-9. ]+)"', frag)
    gap, dash = (float(v) * k for v in arr.group(1).split())
    assert (dash, gap) == pytest.approx(charlib.TRACE_DASH, abs=0.1)
    # raster: walking down the band along the L's left edge (2px inside the
    # outer edge) alternates ink and paper
    np = pytest.importorskip("numpy")
    m = _mask(frag)
    x = int(np.nonzero(m.any(axis=0))[0].min() + 2 * _SC)
    col = m[int((470 - _Y0) * _SC):int((580 - _Y0) * _SC), x]
    flips = sum(1 for a, b in zip(col, col[1:]) if a != b)
    assert flips >= 8 and 0.3 < col.mean() < 0.8, (flips, col.mean())


def test_hollow_extent_is_exact_for_validator_and_data_w():
    """data-bleed makes validate's bbox the DILATED ink (within AA), and
    the word's data-x0/data-w span contains it."""
    np = pytest.importorskip("numpy")
    frag = charlib.word("MAXO", 425, 600, size=120)
    items, _, _ = V._collect(ET.fromstring(
        f'<svg xmlns="http://www.w3.org/2000/svg">{frag}</svg>'))
    bbs = [it.wbbox for it in items if it.wbbox]
    vb = (min(b[0] for b in bbs), min(b[1] for b in bbs),
          max(b[2] for b in bbs), max(b[3] for b in bbs))
    ys, xs = np.nonzero(_mask(frag))
    rb = (xs.min() / _SC, ys.min() / _SC + _Y0, (xs.max() + 1) / _SC,
          (ys.max() + 1) / _SC + _Y0)
    assert all(abs(a - b) < 1.0 for a, b in zip(vb, rb)), (vb, rb)
    g = ET.fromstring(frag)
    x0, w = float(g.get("data-x0")), float(g.get("data-w"))
    assert x0 <= rb[0] and rb[2] <= x0 + w
    assert w == pytest.approx(charlib.word_width("MAXO", 120), abs=0.05)


def test_hollow_body_zero_is_legacy_outline():
    out = charlib.letter("A", 0, 0, body=0)
    assert out.startswith("<path") and "data-bleed" not in out


def test_name_trace_page_rows_clear_guidelines():
    """Dashed hollow letters sit BETWEEN the ruled lines (no line runs
    along a letter edge) and the page still validates."""
    svg = charlib.name_trace_page(["Harper", "Max", "Lily"])
    rep = V.validate_svg(svg)
    assert rep["ok"], rep["findings"]
    root = ET.fromstring(svg)
    items, _, _ = V._collect(root)
    ns = "{http://www.w3.org/2000/svg}"
    words = [g for g in root.iter(ns + "g") if g.get("data-word")]
    assert [g.get("data-word") for g in words] == ["HARPER", "MAX", "LILY"]
    lines = sorted({round(float(el.get("y1")), 1) for el in root.iter(ns + "line")
                    if el.get("y1") == el.get("y2") and float(el.get("y1")) > 200})
    for g in words:
        ids = {id(e) for e in g.iter()}
        ink = [it.wbbox for it in items if id(it.el) in ids and it.wbbox]
        top, bot = min(b[1] for b in ink), max(b[3] for b in ink)
        # nearest ruled lines above and below the word
        assert any(top - 8 < y < top - 3 for y in lines), (top, lines)
        assert any(bot + 3 < y < bot + 8 for y in lines), (bot, lines)


# ---------------------------------------------------------------- page number vs caption
def _caption_y(svg, text):
    import re
    m = re.search(r'<g data-text="1"[^>]*data-y="(\d+)"[^>]*aria-label="' + re.escape(text), svg)
    assert m, text
    return int(m.group(1))


def test_page_number_lifts_a_wide_one_line_caption():
    """A wide single-line caption shares the number's baseline and reads as
    part of it ("2 Hello, barn!..."): the caption block lifts by one line."""
    from charlib import spage, page, W, text_width, CAPTION_MAX_W
    wide = "Hello, barn! Nora feeds the baby goat. Pip says hello to everyone."
    assert text_width(wide, 22) <= CAPTION_MAX_W          # really one line
    svg = spage("T", "", num=2, caption=wide)
    assert _caption_y(svg, wide) == 1030 and _caption_y(svg, "2") == 1058
    # legacy page(): same rule on its own baselines
    svg2 = page("T", "", num=2, caption=wide)
    assert _caption_y(svg2, wide) == 1100 - 48 - 27


def test_page_number_leaves_a_short_caption_alone():
    from charlib import spage
    svg = spage("T", "", num=2, caption="Grow, flower, grow!")
    assert _caption_y(svg, "Grow, flower, grow!") == 1058


def test_public_pose_parts_match_internal_builders():
    import charlib
    t = {"hair": "pigtails", "outfit": "dress"}
    assert charlib.kid_top(t) == charlib._kid_top(t)
    assert charlib.arm((0, -150), (40, -90)) == charlib._arm((0, -150), (40, -90))
