import math

import pytest

import validate as V
from charlib import C, G, LINE, P, spage, sun, cloud, matted, dog_sit


def svg_of(body):
    return spage("T", body)


# ---------------------------------------------------------------- transform math
def test_parse_transform_translate_scale():
    m = V._parse_transform("translate(10,20) scale(2)")
    assert V._apply(m, 3, 4) == (16, 28)


def test_parse_transform_mirror():
    m = V._parse_transform("translate(100,0) scale(-1,1)")
    assert V._apply(m, 30, 5) == (70, 5)


def test_parse_transform_rotate():
    m = V._parse_transform("rotate(90)")
    x, y = V._apply(m, 10, 0)
    assert abs(x) < 1e-9 and abs(y - 10) < 1e-9


# ---------------------------------------------------------------- each rule fires
def _first(rep, check):
    hits = [f for f in rep["findings"] if f["check"] == check]
    return hits[0] if hits else None


def test_border_clearance_fires():
    rep = V.validate_svg(svg_of(G(810, 900, __import__("charlib").house(0, 0))))
    f = _first(rep, "border_clearance")
    assert f and f["severity"] == "HIGH"


def test_scene_span_ignores_sky_tokens():
    small = C(400, 500, 40) + sun(120, 120) + cloud(650, 150, 30)
    rep = V.validate_svg(svg_of(small))
    f = _first(rep, "scene_span")
    assert f and f["severity"] == "HIGH"


def test_figure_size_fires_on_tiny_subject():
    from charlib import kid_stand
    body = G(400, 700, kid_stand({"outfit": "tee"}), 0.35) + C(150, 300, 90)
    rep = V.validate_svg(svg_of(body))
    f = _first(rep, "figure_size")
    assert f and f["severity"] == "HIGH"


def test_caption_band_fires():
    rep = V.validate_svg(spage("T", C(400, 1030, 60)), require_span=False)
    f = _first(rep, "caption_band")
    assert f and f["severity"] == "HIGH"


def test_text_fit_fires():
    base = spage("T", C(400, 500, 40))
    long_text = "word " * 20
    injected = base.replace(
        "</svg>",
        '<text x="425" y="600" font-size="24" font-weight="normal" '
        f'text-anchor="middle">{long_text}</text></svg>')
    rep = V.validate_svg(injected)
    f = _first(rep, "text_fit")
    assert f and f["severity"] == "HIGH"


def test_head_clearance_fully_swallowed_prop():
    kid = G(300, 800, __import__("charlib").kid_stand({"outfit": "dress"}), 1.2)
    stray = G(330, 560, C(0, 0, 8))  # inside the head kill disk
    rep = V.validate_svg(svg_of(kid + stray))
    f = _first(rep, "head_clearance")
    assert f and f["severity"] == "HIGH"
    assert "fully inside" in f["msg"] or "kill radius" in f["msg"]


def test_hand_arm_gap_fires():
    fig = ('<g data-el="figure">' + P("M -18 -142 L -34 -110", 5) +
           C(-46, -100, 8, 4, "white", hand="1") +
           C(0, -188, 37, 5, "white", face="0,-188,37") + "</g>")
    rep = V.validate_svg(svg_of(G(400, 800, fig, 1.2)))
    f = [x for x in rep["findings"]
         if x["check"] == "hand_arm" and "short of" in x["msg"]]
    assert f and f[0]["severity"] == "MED"


def test_hand_arm_attached_passes():
    fig = ('<g data-el="figure">' + P("M -18 -142 L -42 -104", 5) +
           C(-46, -100, 8, 4, "white", hand="1") +
           C(0, -188, 37, 5, "white", face="0,-188,37") + "</g>")
    rep = V.validate_svg(svg_of(G(400, 800, fig, 1.2)))
    near = [x for x in rep["findings"]
            if x["check"] == "hand_arm" and "short of" in x["msg"]]
    assert not near


def test_ground_tangency_fires():
    wheel = ('<circle cx="300" cy="840" r="24" fill="white" stroke="black" '
             'stroke-width="5" data-ground="900"/>')
    rep = V.validate_svg(svg_of(wheel + C(600, 400, 120)))
    f = _first(rep, "ground_tangency")
    assert f and f["severity"] == "HIGH"


def test_sliver_gap_fires():
    body = LINE(200, 400, 600, 400, 4) + LINE(200, 406, 600, 406, 4)
    body += C(750, 850, 80)
    rep = V.validate_svg(svg_of(body))
    f = _first(rep, "sliver_gap")
    assert f is not None


def test_mat_swallow_halo_only_kill():
    pebble = C(354, 938, 6, 3, "white")
    pack = G(430, 950, matted(dog_sit({"coat": "plain"}), pad=44), 1.0)
    rep = V.validate_svg(svg_of(pebble + pack))
    f = _first(rep, "mat_swallow")
    assert f and f["severity"] == "HIGH"


def test_legit_depth_occlusion_not_flagged():
    """An element hidden BEHIND mat art (center under art boxes) is normal."""
    rug = C(430, 905, 60, 4, "white")   # fully under where the dog will stand
    pack = G(430, 950, matted(dog_sit({"coat": "plain"})), 1.0)
    rep = V.validate_svg(svg_of(rug + pack + C(120, 350, 90)))
    f = _first(rep, "mat_swallow")
    assert f is None


# ---------------------------------------------------------------- layout relaxations
def test_activity_layout_relaxes_span():
    sparse = C(400, 500, 40)
    strict = V.validate_svg(svg_of(sparse))
    assert _first(strict, "scene_span") is not None
    relaxed = V.validate_svg(
        spage("T", '<g data-layout="activity">' + sparse + "</g>"))
    f = _first(relaxed, "scene_span")
    assert f is None or f["severity"] == "LOW"


def test_vignette_layout_downgrades_figure_size():
    from charlib import kid_stand
    body = G(400, 700, kid_stand({"outfit": "tee"}), 0.42) + C(150, 320, 90)
    relaxed = V.validate_svg(
        spage("T", '<g data-layout="vignette">' + body + "</g>"))
    f = _first(relaxed, "figure_size")
    assert f is None or f["severity"] == "MED"


# ---------------------------------------------------------------- book lint
def test_lint_book_duplicates_and_pacing():
    a = spage("A", C(400, 500, 60))
    b = spage("B", C(400, 520, 60) + LINE(100, 100, 700, 100))
    rep = V.lint_book([a, a, b])
    dup = [f for f in rep["findings"] if f["check"] == "duplicate_page"]
    assert dup and dup[0]["severity"] == "HIGH"


def test_good_page_passes_clean():
    from charlib import kid_stand, tree_round, grass_tuft, house
    body = (G(190, 950, house(0, 0)) +
            G(430, 950, tree_round(0, 0, h=640)) +
            G(620, 950, kid_stand({"outfit": "tee"}, "wave"), 1.0) +
            G(760, 950, grass_tuft(0, 0)))
    rep = V.validate_svg(spage("Park", body))
    assert rep["ok"], [f for f in rep["findings"] if f["severity"] == "HIGH"]
