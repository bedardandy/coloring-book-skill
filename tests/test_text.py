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
    xs = [float(v) for v in re.findall(r'translate\(([-0-9.]+),', start)]
    assert min(xs) == pytest.approx(100, abs=0.1)
