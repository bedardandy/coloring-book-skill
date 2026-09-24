import math
import xml.etree.ElementTree as ET

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


# ---------------------------------------------------------------- span + mass
# Ownership: scene_span owns the scene's vertical EXTENT (HIGH: a strip on the
# ground line, or a floating scene); mass_distribution owns WHERE the ink
# sits inside it (MED: hollow middle). Calibration (showcase + fixtures):
#   extent  strip fixture 246px (22%)  <  SPAN_MIN 330  <  photo/beach/recipe
#           pages 407-444px (37-40%)
#   ratio   hourglass pages <= 0.30  <  MID_RATIO 0.40  <  recipe pages >= 0.49
import importlib.util  # noqa: E402
import os  # noqa: E402

import scenes  # noqa: E402

T_KID = {"hair": "pigtails", "outfit": "dress"}
SG = scenes.SCENE_GROUND


def _mass_findings(rep, kind=None):
    hits = [f for f in rep["findings"] if f["check"] == "mass_distribution"]
    if kind == "hollow":
        hits = [f for f in hits if "hollow middle" in f["msg"]]
    return hits


def _span(rep, sev=None):
    return [f for f in rep["findings"] if f["check"] == "scene_span"
            and (sev is None or f["severity"] == sev)]


def _ratio(rep):
    b = rep["mass"]["bands"]
    return b["mid"] / max(b["top"], b["bottom"])


def bottom_crammed_body():
    """The documented first-draft failure: kit + one 1.0 kid on the ground."""
    from charlib import kid_stand
    return scenes.scene_meadow() + G(430, SG, kid_stand(T_KID, "wave"), 1.0)


def three_layer_recipe_body():
    """drawing-guide recipe: kit background + midground tree whose top
    reaches y~500 + foreground kid at 1.3 on the declared ground line."""
    from charlib import kid_stand, tree_round
    return (scenes.scene_meadow(midground=False) +
            tree_round(595, SG - 4, h=455) +
            G(330, SG, kid_stand(T_KID, "wave"), 1.3))


def hourglass_body():
    """Props up top, a 1.0 kid strip on the ground, nothing between: the
    extent passes, the distribution does not."""
    from charlib import hot_air_balloon
    return bottom_crammed_body() + G(640, 330, hot_air_balloon(0, 0), 0.85)


def test_strip_page_is_scene_span_high():
    rep = V.validate_svg(svg_of(bottom_crammed_body()))
    assert not rep["ok"]
    high = _span(rep, "HIGH")
    assert high and "strip on the ground line" in high[0]["msg"]
    assert rep["span"]["px"] < V.SPAN_MIN - 60          # calibration margin
    # the sun (disc AND rays) is sky: it no longer reaches the span's top
    assert rep["span"]["raw_top"] > 600
    # one failure, one owner: mass_distribution stands down
    assert rep["mass"]["skip"] == "scene_span HIGH already fired"
    assert not _mass_findings(rep)


def test_three_layer_recipe_passes_both_checks():
    rep = V.validate_svg(svg_of(three_layer_recipe_body()))
    assert rep["ok"], rep["findings"]
    assert not _span(rep), _span(rep)                    # no finding at all
    assert not _mass_findings(rep), _mass_findings(rep)
    assert rep["mass"]["judged"]
    assert rep["span"]["px"] >= V.SPAN_MIN + 60         # calibration margin
    assert _ratio(rep) >= 0.54


def test_hourglass_page_flags_hollow_middle():
    rep = V.validate_svg(svg_of(hourglass_body()))
    assert rep["ok"]                       # MED only: CI keeps passing
    assert not _span(rep, "HIGH")
    hollow = _mass_findings(rep, "hollow")
    assert hollow and hollow[0]["severity"] == "MED"
    msg = hollow[0]["msg"]
    assert "middle band" in msg and "bottom band" in msg and "%" in msg
    assert "midground anchor" in msg and "kid_stand 1.2-1.5" in msg
    b = rep["mass"]["bands"]
    assert b["mid"] < 5 and b["bottom"] > 20
    assert _ratio(rep) <= 0.30             # calibration gap, low side


def test_span_and_mass_report_shape():
    rep = V.validate_svg(svg_of(three_layer_recipe_body()))
    m = rep["mass"]
    assert set(m["bands"]) == {"top", "mid", "bottom"}
    assert m["edges"] == [145, 430, 715, 1000]
    assert all(0 <= v <= 100 for v in m["bands"].values())
    assert m["skip"] is None
    assert set(rep["span"]) == {"top", "bottom", "px", "raw_top"}
    assert rep["span"]["px"] == rep["span"]["bottom"] - rep["span"]["top"]


def test_big_figure_alone_does_not_fill_the_middle():
    from charlib import kid_stand
    body = scenes.scene_meadow() + G(430, SG, kid_stand(T_KID, "wave"), 1.4)
    rep = V.validate_svg(svg_of(body))
    assert not _span(rep, "HIGH")          # one 351px figure clears the floor
    hollow = _mass_findings(rep, "hollow")
    assert hollow
    # figure is already foreground-sized, so the advice is the anchor only
    assert "already foreground-sized" in hollow[0]["msg"]


def test_thin_prop_cannot_carry_the_span():
    """A lone pole reaching y=300 used to satisfy the span arithmetic; rows
    with a single stroke carry no mass, so the strip is still a strip."""
    from charlib import LINE as L
    pole = L(700, SG, 700, 300, 5)
    rep = V.validate_svg(svg_of(bottom_crammed_body() + pole))
    high = _span(rep, "HIGH")
    assert high and "thin stroke reaching y=300" in high[0]["msg"]
    assert rep["span"]["raw_top"] == 300 and rep["span"]["top"] > 600
    # a real (if small) object up there is mass: the span passes and the
    # hollow middle becomes mass_distribution's MED
    flag = P("M 700 300 L 760 322 L 700 344 Z", 4, "white")
    rep = V.validate_svg(svg_of(bottom_crammed_body() + pole + flag))
    assert not _span(rep, "HIGH") and _mass_findings(rep, "hollow")


def test_old_kit_street_strip_is_high():
    """pre-recomposition showcase 08: skyline to y~560 + a 0.9 bus. Its
    extent passed only on the sun's rays."""
    from charlib import school_bus, ROAD_H
    body = scenes.scene_street() + G(
        400, SG - 120 + ROAD_H, school_bus(0, 0, w=190), 0.9)
    rep = V.validate_svg(svg_of(body))
    assert _span(rep, "HIGH")


def test_old_kit_beach_strip_is_high():
    """pre-recomposition showcase 09: kit + one 1.0 kid on the sand."""
    from charlib import kid_stand
    body = scenes.scene_beach() + G(
        300, scenes.BEACH_GROUND, kid_stand({"hair": "buzz", "outfit": "tee"},
                                            "up"), 1.0)
    rep = V.validate_svg(svg_of(body))
    assert _span(rep, "HIGH")


def test_floating_scene_bottom_is_high():
    from charlib import kid_stand, tree_round
    body = G(330, 840, kid_stand(T_KID, "wave"), 1.3) + tree_round(
        595, 836, h=455)
    rep = V.validate_svg(svg_of(body))
    assert any("floats" in f["msg"] for f in _span(rep, "HIGH"))


def test_sky_motifs_tagged_in_every_part():
    import re
    from charlib import sun, moon, shooting_star, cloud, sparkle, star_field
    for frag in (sun(200, 250), moon(200, 250, r=40), shooting_star(200, 250),
                 cloud(200, 250, 30), sparkle(200, 250),
                 star_field(60, 170, 790, 600, n=9)):
        shapes = re.findall(r"<(?:circle|ellipse|line|path|polygon|rect)\b[^>]*>",
                            frag)
        assert shapes and all('data-sky="1"' in sh for sh in shapes), frag[:80]


def test_sky_decoration_colliding_with_title_is_flagged():
    from charlib import sun
    rep = V.validate_svg(spage("A Long Page Title", sun(560, 100) +
                               three_layer_recipe_body()))
    hits = [f for f in rep["findings"] if f["check"] == "title_band"
            and "sky decoration" in f["msg"]]
    assert hits and hits[0]["severity"] == "MED"
    # the kit sun at y=225 clears the title ink
    rep = V.validate_svg(svg_of(three_layer_recipe_body()))
    assert not [f for f in rep["findings"] if f["check"] == "title_band"]


def test_unfilled_outline_is_not_mass():
    """A big hollow outline (door frame) in the middle band must not
    masquerade as midground; the same shape filled white does count."""
    base = bottom_crammed_body()
    door = "M 600 900 L 600 440 L 740 440 L 740 900"
    hollow_door = P(door, 5)                          # fill="none"
    solid_door = P(door + " Z", 5, "white")
    r_hollow = V.validate_svg(svg_of(base + hollow_door))
    r_solid = V.validate_svg(svg_of(base + solid_door))
    assert r_hollow["mass"]["bands"]["mid"] < 5
    assert _mass_findings(r_hollow, "hollow")
    assert r_solid["mass"]["bands"]["mid"] > r_hollow["mass"]["bands"]["mid"] + 5


def test_flatten_path_uses_curve_not_control_point():
    # open hill arc: control point at y=700, real crest at y=820
    polys = V._flatten_path("M 100 940 Q 300 700 500 940")
    ys = [p[1] for p in polys[0]]
    assert abs(min(ys) - 820) < 1.0


def _bbox_of(d):
    return V._local_bbox(ET.fromstring(
        f'<path xmlns="http://www.w3.org/2000/svg" d="{d}"/>'))


def test_bbox_reads_h_v_and_relative_commands():
    # H/V take ONE number; even/odd pairing used to misread (or drop) them
    assert _bbox_of("M 10 10 H 50 V 80") == (10, 10, 50, 80)
    assert _bbox_of("m 10 10 h 40 v 70 h -40 z") == (10, 10, 50, 80)
    # relative curves are offsets from the current point
    bb = _bbox_of("M 100 100 c 0 -40 60 -40 60 0 l 0 20")
    assert bb[0] == 100 and bb[2] == 160 and abs(bb[1] - 70) < 0.5
    assert bb[3] == 120
    # smooth curves reflect the previous control point
    bb = _bbox_of("M 0 100 Q 50 0 100 100 T 200 100")
    assert abs(bb[1] - 50) < 0.5 and abs(bb[3] - 150) < 0.5
    # arcs are sampled on the curve: a sweep=1 semicircle bulges UP (y-down)
    bb = _bbox_of("M 0 0 a 5 5 0 0 1 10 0")
    assert abs(bb[1] + 5) < 0.1 and bb[3] == 0


def test_border_clearance_sees_h_commands():
    # the H segment runs past the right margin; the old parser dropped it
    rep = V.validate_svg(svg_of(P("M 700 500 H 815", 5) +
                                three_layer_recipe_body()))
    f = _first(rep, "border_clearance")
    assert f and f["severity"] == "HIGH"


@pytest.mark.parametrize("layout", ["activity", "vignette", "creative"])
def test_mass_distribution_layout_opt_outs(layout):
    body = '<g data-layout="%s">' % layout + bottom_crammed_body() + "</g>"
    rep = V.validate_svg(spage("T", body))
    assert not _mass_findings(rep)
    assert rep["mass"]["judged"] is False
    assert rep["mass"]["skip"] == f"layout={layout}"
    assert rep["mass"]["bands"]["bottom"] > 20      # still measured


def test_mass_distribution_spage_layout_kwarg_opt_out():
    rep = V.validate_svg(spage("T", bottom_crammed_body(), layout="activity"))
    assert not _mass_findings(rep)


def test_require_span_false_skips_mass_distribution():
    rep = V.validate_svg(svg_of(bottom_crammed_body()), require_span=False)
    assert not _mass_findings(rep)
    assert rep["mass"]["skip"] == "require_span=False"


def _harper_module():
    path = os.path.join(os.path.dirname(__file__), "..", "examples",
                        "where-is-button", "make_book.py")
    spec = importlib.util.spec_from_file_location("_harper_book", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("page", ["03-intro", "04-problem",
                                  "05-search-bedroom", "06-search-living",
                                  "07-find-activity", "08-solve",
                                  "09-celebrate"])
def test_harper_story_pages_flag_hollow_middle(page):
    """Calibration anchors: the bundled example's story pages keep ~1.0-scale
    kids on the floor line under wall decor — visibly hollow middles. If
    make_book.py is recomposed per the three-layer recipe to clear these
    MEDs, drop the fixed pages from this list (that is the point of it)."""
    fn = dict(_harper_module().BUILDERS)[page]
    rep = V.validate_svg(fn())
    assert rep["ok"]
    assert _mass_findings(rep, "hollow"), rep["mass"]
    assert _ratio(rep) <= 0.30


def test_harper_opt_out_pages_not_judged():
    builders = dict(_harper_module().BUILDERS)
    for page in ("02-names", "10-back-cover"):
        rep = V.validate_svg(builders[page]())
        assert not _mass_findings(rep), page


def test_head_clearance_ignores_details_of_background_objects():
    # a building's windows hidden behind a foreground kid's head are normal
    # depth layering (street scenes), not a swallowed prop
    from charlib import rrect, kid_stand, matted
    building = rrect(240, 480, 200, 300, 3, 4, "white") + "".join(
        rrect(254 + 26 * i, 500 + 26 * j, 14, 14, 2, 2.5, "white")
        for i in range(7) for j in range(10))
    kid = matted(G(330, 800, kid_stand({"outfit": "tee"}), 1.2))
    rep = V.validate_svg(svg_of(building + kid))
    assert not [f for f in rep["findings"]
                if f["check"] == "head_clearance" and f["severity"] == "HIGH"]
    # ...but a standalone prop at the face is still the documented bug
    prop = G(330, 580, rrect(-7, -7, 14, 14, 2, 2.5, "white"))
    rep = V.validate_svg(svg_of(prop + kid))
    assert _first(rep, "head_clearance")["severity"] == "HIGH"
