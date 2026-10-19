"""space3d: camera math, Stage ordering + tags, colorable perspective
primitives, and the validator's depth_order check."""
import math
import re
import xml.etree.ElementTree as ET

import pytest

import space3d as S
import validate as V
from charlib import (G, C, LINE, spage, kid_stand, dog_sit, tree_round,
                     tree_pine, house, matted)
from scenes import SCENE_GROUND

T1 = {"hair": "pigtails", "outfit": "dress"}
T2 = {"hair": "buzz", "outfit": "tee"}


def _put(cam, x, z, frag):
    """G()-place a feet-origin fragment at world (x, z) without a Stage."""
    px, py, s = cam.place(x, z)
    return G(px, py, frag, s)


def _checks(rep, check):
    return [f for f in rep["findings"] if f["check"] == check]


def _clean(svg, **kw):
    """No HIGH, no sliver_gap, nothing in the title zone or caption band.
    Primitive-only pages pass require_span=False: thin receding lines carry
    no scene mass, so they are colorability fixtures, not composed scenes."""
    ET.fromstring(svg)
    rep = V.validate_svg(svg, **kw)
    highs = [f for f in rep["findings"] if f["severity"] == "HIGH"]
    assert not highs, highs
    for check in ("sliver_gap", "title_band", "caption_band",
                  "border_clearance", "depth_order"):
        assert not _checks(rep, check), _checks(rep, check)
    return rep


# ---------------------------------------------------------------- camera math
def test_camera_defaults_match_three_layer_recipe():
    cam = S.Camera()
    assert cam.place(0, cam.near_z) == (425.0, SCENE_GROUND, 1.3)
    assert cam.f == pytest.approx(1.3 * 800)
    assert cam.eye_h == pytest.approx((940 - 520) / 1.3)


def test_scale_halves_when_z_doubles():
    cam = S.Camera()
    for z in (500, 800, 1300, 2600):
        assert cam.scale_at(2 * z) == pytest.approx(cam.scale_at(z) / 2)
    # page offsets from the vanishing point halve too
    px1, py1 = cam.project(200, 0, 1000)
    px2, py2 = cam.project(200, 0, 2000)
    assert px2 - cam.vp_x == pytest.approx((px1 - cam.vp_x) / 2)
    assert py2 - cam.horizon_y == pytest.approx((py1 - cam.horizon_y) / 2)


def test_eye_level_projects_onto_the_horizon():
    cam = S.Camera(horizon_y=480, vp_x=400)
    for z in (300, 900, 5000):
        assert cam.project(123, cam.eye_h, z)[1] == pytest.approx(480)
    # the far ground approaches (never reaches) the horizon
    assert 480 < cam.ground_point(0, 1e7)[1] < 480.1


@pytest.mark.parametrize("cam", [S.Camera(), S.Camera(horizon_y=430,
                                 vp_x=380, near_z=600, near_ground_y=960,
                                 near_scale=1.45)])
def test_round_trips(cam):
    for x, z in ((-300, 700), (0, 1000), (250, 3100)):
        px, py = cam.ground_point(x, z)
        assert cam.z_for_ground_y(py) == pytest.approx(z)
        assert cam.x_for_page_x(px, z) == pytest.approx(x)
        ux, uz = cam.unproject_ground(px, py)
        assert (ux, uz) == (pytest.approx(x), pytest.approx(z))
    assert cam.z_for_ground_y(cam.near_ground_y) == pytest.approx(cam.near_z)


def test_g_placement_is_the_exact_projection():
    """A feet-origin fragment placed with G(*place(x, z)) maps local
    (lx, ly) onto the world point (x + lx, -ly, z)."""
    cam = S.Camera()
    x, z = -140, 1250
    px, py, s = cam.place(x, z)
    m = V._parse_transform(G(px, py, "", s).split('"')[1])
    for lx, ly in ((0, 0), (37, -188), (-60, -250)):
        wx, wy = V._apply(m, lx, ly)
        ex, ey = cam.project(x + lx, -ly, z)
        assert wx == pytest.approx(ex, abs=0.06)
        assert wy == pytest.approx(ey, abs=0.06)


def test_camera_rejects_impossible_input():
    cam = S.Camera()
    with pytest.raises(ValueError):
        cam.project(0, 0, 0)
    with pytest.raises(ValueError):
        cam.z_for_ground_y(cam.horizon_y - 5)
    with pytest.raises(ValueError):
        S.Camera(horizon_y=900, near_ground_y=800)


def test_converge_z_is_the_exact_gap_depth():
    """At converge_z the perpendicular distance between the two projected
    depth-parallel lines equals the gap."""
    cam = S.Camera()
    for oa, ob in (((100, 0), (220, 0)), ((-380, 0), (-250, 0)),
                   ((380, 300), (380, 420))):
        z = cam.converge_z(oa, ob, gap=14)
        a0, a1 = cam.project(oa[0], oa[1], z), cam.project(oa[0], oa[1], 2 * z)
        b = cam.project(ob[0], ob[1], z)
        ux, uy = a1[0] - a0[0], a1[1] - a0[1]
        d = abs(ux * (b[1] - a0[1]) - uy * (b[0] - a0[0])) / math.hypot(ux, uy)
        assert d >= 14 - 1e-6
        assert d < 14 * 1.6        # conservative, but not wildly so


def test_bands_scale_with_near_z():
    cam = S.Camera(near_z=1000)
    assert cam.band("foreground") == (1000, 1200)
    assert cam.band("background")[0] > cam.band("midground")[1]


def test_look_toward():
    assert S.look_toward(0, 0) == 0
    assert S.look_toward(-150, 60) > 0          # target to page right
    assert S.look_toward(60, -150) < 0
    assert S.look_toward(0, 5000) == 1.0
    assert S.look_toward(0, -5000) == -1.0


# ---------------------------------------------------------------- stage
def _stage():
    cam = S.Camera()
    st = S.Stage(cam)
    st.add(lambda: kid_stand(T2, "wave"), x=-170, z=830, name="Max")
    st.add(lambda: house(0, 0, w=240), x=150, z=3200, name="house",
           contact=False)
    st.add(lambda: kid_stand(T1, "wave_high"), x=60, z=1300, name="Lily")
    st.add_table(x=60, z=1020, w=250, d=190, h=80, name="table")
    st.add(lambda: dog_sit({"coat": "spots"}), x=230, z=880, name="dog",
           flip=True)
    return cam, st


def test_stage_orders_far_to_near():
    _cam, st = _stage()
    assert st.order() == ["house", "Lily", "table", "dog", "Max"]


def test_stage_tags_and_mats():
    cam, st = _stage()
    body = st.render()
    root = ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg">' + body
                         + "</svg>")
    groups = [g for g in root if g.get("data-depth") is not None]
    assert [g.get("data-depth-name") for g in groups] == st.order()
    zs = [float(g.get("data-depth")) for g in groups]
    assert zs == sorted(zs, reverse=True)
    for g in groups:
        z = float(g.get("data-depth"))
        assert float(g.get("data-depth-ground")) == pytest.approx(
            cam.ground_point(0, z)[1], abs=0.06)
        if g.get("data-depth-far") is None:           # billboard
            assert float(g.get("data-depth-scale")) == pytest.approx(
                cam.scale_at(z), abs=0.0051)
        # every item is matted: its mat copy is the FIRST thing drawn
        assert 'data-mat="1"' in ET.tostring(g, encoding="unicode")
    # the contact line comes AFTER the matted art inside its group
    maxg = next(g for g in groups if g.get("data-depth-name") == "Max")
    kids = list(maxg)
    assert kids[-1].tag.endswith("line")
    assert float(kids[-1].get("y1")) == pytest.approx(
        cam.ground_point(-170, 830)[1], abs=0.06)


def test_stage_contact_off_and_numeric():
    cam = S.Camera()
    st = S.Stage(cam)
    st.add(tree_round(0, 0, h=200), x=0, z=1000, name="a", contact=False)
    st.add(tree_round(0, 0, h=200), x=0, z=1200, name="b", contact=50)
    body = st.render()
    a = body[body.index('data-depth-name="a"'):]
    assert "<line" not in a                           # a is drawn last
    b = body[body.index('data-depth-name="b"'):body.index('data-depth-name="a"')]
    m = re.findall(r'<line x1="([\d.]+)" y1="[\d.]+" x2="([\d.]+)"', b)[-1]
    assert float(m[1]) - float(m[0]) == pytest.approx(
        100 * cam.scale_at(1200), abs=0.2)


def test_stage_callables_run_at_render_time_and_gaze():
    cam = S.Camera()
    st = S.Stage(cam)
    seen = []

    def lily():
        seen.append(st.gaze("Lily", "Max"))
        return kid_stand(T1)

    st.add(lily, x=200, z=1000, name="Lily")
    st.add(kid_stand(T2), x=-100, z=900, name="Max")  # added AFTER the callable
    assert seen == []
    st.render()
    assert seen == [S.look_toward(200, -100)] and seen[0] < 0


def test_stage_billboard_beside_a_solid_draws_after_it():
    """A kid standing beside a box on its camera-facing side (within its
    depth span) is IN FRONT of the box's visible side face."""
    st = S.Stage(S.Camera())
    st.add_box(x=270, z=1100, w=150, d=300, h=110, name="box")
    st.add(kid_stand(T2), x=120, z=1250, name="kid")
    assert st.order() == ["box", "kid"]
    # ...but a kid on the box's FAR side (hidden face) stays behind it
    st2 = S.Stage(S.Camera())
    st2.add_box(x=270, z=1100, w=150, d=300, h=110, name="box")
    st2.add(kid_stand(T2), x=420, z=1250, name="kid")
    assert st2.order() == ["kid", "box"]


def test_stage_item_resting_on_a_solid_draws_after_it():
    st = S.Stage(S.Camera())
    st.add(C(0, -20, 20, 4, "white"), x=0, z=1100, y=80, name="ball",
           contact=False)
    st.add_table(x=0, z=1000, w=250, d=200, h=80, name="table")
    assert st.order() == ["table", "ball"]


def test_stage_add_row_and_determinism():
    def build():
        cam = S.Camera()
        st = S.Stage(cam)
        st.add_row(lambda i: tree_pine(0, 0, h=260), 300, 1300, 4000, 6,
                   name="pine")
        st.add(kid_stand(T2), x=-100, z=850, name="kid")
        return st
    a, b = build(), build()
    assert a.render() == b.render()
    names = a.order()
    assert names[-1] == "kid" and names[0].startswith("pine")
    assert len(names) >= 3


def test_stage_page_validates_clean():
    cam, st = _stage()
    svg = spage("Depth", S.room_box(cam, height=640, door=True) + st.render())
    rep = _clean(svg)
    assert rep["depth"]["groups"] == 5
    assert rep["depth"]["order"] == st.order()
    assert rep["depth"]["inversions"] == 0
    assert rep["depth"]["scale_conflicts"] == 0


# ---------------------------------------------------------------- primitives
@pytest.mark.parametrize("kw", [
    {},
    {"floor": "tiles", "ceiling": False, "window": False, "door": True},
    {"height": 300, "boards": 9, "z_back": 3200},        # dollhouse, far wall
    {"width": 600, "boards": 14, "z_back": 4500, "floor": "tiles",
     "tile_depth": 90},                                    # dense: fade-out
    {"window": (-150, 200, 180, 150), "door": (200, 150, 330)},
])
def test_room_box_is_colorable(kw):
    cam = S.Camera()
    body = S.room_box(cam, **kw)
    svg = spage("Room", body + G(425, SCENE_GROUND, kid_stand(T2), 1.3))
    _clean(svg, require_span=False)


def test_room_box_lines_stay_in_safe_rect():
    cam = S.Camera(horizon_y=420)
    body = S.room_box(cam, width=900, height=900, floor="tiles")
    x0, y0, x1, y1 = S.SAFE
    for m in re.finditer(r'<line x1="([-\d.]+)" y1="([-\d.]+)" '
                         r'x2="([-\d.]+)" y2="([-\d.]+)"', body):
        a, b, c, d = (float(v) for v in m.groups())
        assert x0 - 0.1 <= min(a, c) and max(a, c) <= x1 + 0.1
        assert y0 - 0.1 <= min(b, d) and max(b, d) <= y1 + 0.1


def test_room_boards_stop_before_they_crowd():
    """Dense boards toward a far back wall stop where they would come
    closer than CONVERGE_GAP; none reaches the back wall."""
    cam = S.Camera()
    body = S.room_box(cam, width=600, boards=14, z_back=4500, window=False,
                      ceiling=False)
    back_y = cam.ground_point(0, 4500)[1]
    lines = [tuple(float(v) for v in m.groups()) for m in re.finditer(
        r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)" '
        r'stroke="black" stroke-width="3.2', body)]
    assert lines
    assert all(min(l[1], l[3]) > back_y + 5 for l in lines)


@pytest.mark.parametrize("curve,dashes", [(0, False), (90, True), (-60, True)])
def test_path_recede_is_colorable(curve, dashes):
    cam = S.Camera()
    body = S.path_recede(cam, 0, 180, 600, 6000, curve=curve, dashes=dashes)
    svg = spage("Path", LINE(50, cam.horizon_y, 800, cam.horizon_y, 4) + body
                + G(260, SCENE_GROUND, kid_stand(T2), 1.3))
    _clean(svg, require_span=False)


def test_path_recede_far_cap_is_wide_enough():
    cam = S.Camera()
    body = S.path_recede(cam, 0, 120, 600, 1e6)
    pts = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?",
                                        body.split('d="')[1].split('"')[0])]
    ys = pts[1::2]
    top = min(ys)
    assert top > cam.horizon_y                 # never reaches the horizon
    far_z = cam.z_for_ground_y(top)
    assert 120 * cam.scale_at(far_z) >= S.CONVERGE_GAP - 0.5


@pytest.mark.parametrize("x,z,w,d,h", [
    (250, 1100, 150, 160, 110),       # right of axis: left side + top
    (-260, 1000, 180, 200, 140),      # left of axis: right side + top
    (0, 1200, 300, 150, 90),          # straddling: no side face
    (60, 2600, 200, 60, 300),         # tall + far: thin faces omitted
])
def test_box3d_is_colorable(x, z, w, d, h):
    cam = S.Camera()
    svg = spage("Box", S.box3d(cam, x, z, w, d, h)
                + G(425, SCENE_GROUND, kid_stand(T2), 1.3))
    _clean(svg, require_span=False)


def test_box3d_draws_only_visible_faces():
    cam = S.Camera()
    n = lambda s: s.count("<path")
    assert n(S.box3d(cam, 250, 1100, 150, 160, 110)) == 3     # front+side+top
    assert n(S.box3d(cam, 0, 1100, 150, 160, 110)) == 2       # front+top
    assert n(S.box3d(cam, 0, 1100, 150, 160, 400)) == 1       # above eye: front
    assert n(S.box3d(cam, 250, 3000, 150, 30, 110)) == 1      # slivers omitted


def test_table_and_wall_quad_and_ellipse_are_colorable():
    cam = S.Camera()
    body = (S.room_box(cam, height=640) +
            S.wall_quad(cam, -380, 1050, 1450, 300, 450, inset=16) +
            S.wall_quad(cam, 380, 1100, 1700, 0, 380) +
            S.ground_ellipse(cam, -40, 1150, 260, 170) +
            S.table3d(cam, 60, 1020, 250, 190, 80) +
            S.table3d(cam, -250, 1500, 160, 160, 90))
    _clean(spage("Room", body + G(170, SCENE_GROUND, kid_stand(T2), 1.3)))


def test_wall_quad_inner_frame_band_is_page_sized():
    cam = S.Camera()
    frag = S.wall_quad(cam, -380, 1050, 1450, 300, 450, inset=16)
    polys = re.findall(r'd="([^"]+)"', frag)
    assert len(polys) == 2
    outer, inner = ([tuple(map(float, p)) for p in
                     re.findall(r"(-?[\d.]+) (-?[\d.]+)", d_)] for d_ in polys)
    # far edges (larger x on the left wall) at least 16px apart
    assert max(p[0] for p in outer) - max(p[0] for p in inner) >= 15.9
    assert min(p[0] for p in inner) - min(p[0] for p in outer) >= 15.9


def test_receding_row_and_ground_grid_are_colorable():
    cam = S.Camera()
    body = (S.ground_grid(cam, -300, 300, 900, 5000, dx=100, dz=150) +
            S.receding_row(cam, lambda i: tree_pine(0, 0, h=240), 330, 1300,
                           5000, 8) +
            G(260, SCENE_GROUND, kid_stand(T2), 1.3))
    rep = _clean(spage("Grid", body), require_span=False)
    # rows fade out: far items crowding < CONVERGE_GAP are dropped
    slots = S._row_slots(cam, 330, 1300, 5000, 8)
    ys = [cam.ground_point(x, z)[1] for _i, x, z in slots]
    assert all(a - b >= S.CONVERGE_GAP for a, b in zip(ys, ys[1:]))
    assert len(slots) < 8
    assert rep["counts"]["HIGH"] == 0


# ---------------------------------------------------------------- depth_order check
def _grp(z, name, frag, scale=None, ground=None, far=None):
    attrs = f'data-depth="{z}" data-depth-name="{name}"'
    if scale is not None:
        attrs += f' data-depth-scale="{scale}"'
    if ground is not None:
        attrs += f' data-depth-ground="{ground}"'
    if far is not None:
        attrs += f' data-depth-far="{far}"'
    return f"<g {attrs}>{frag}</g>"


def test_depth_order_fires_on_painted_over_inversion():
    cam = S.Camera()
    near = _put(cam, 0, 900, kid_stand(T2))
    far = _put(cam, 40, 1300, kid_stand(T1))
    # far group drawn AFTER the near one, overlapping it
    body = (_grp(900, "near", matted(near)) + _grp(1300, "far", matted(far)))
    rep = V.validate_svg(spage("T", body))
    hits = _checks(rep, "depth_order")
    assert hits and all(f["severity"] == "MED" for f in hits)
    assert any("farther object painted over nearer one" in f["msg"]
               for f in hits)
    assert rep["depth"]["inversions"] == 1
    # the correct order is silent
    ok = V.validate_svg(spage("T", _grp(1300, "far", matted(far))
                              + _grp(900, "near", matted(near))))
    assert not _checks(ok, "depth_order")


def test_depth_order_ignores_non_overlapping_inversions():
    cam = S.Camera()
    near = _put(cam, -250, 900, kid_stand(T2))
    far = _put(cam, 300, 1300, kid_stand(T1))
    rep = V.validate_svg(spage("T", _grp(900, "near", near)
                               + _grp(1300, "far", far)))
    assert not _checks(rep, "depth_order")


def test_depth_order_fires_on_scale_and_ground_conflicts():
    cam = S.Camera()
    # declared scales: the farther kid is drawn BIGGER
    near = G(*cam.place(-200, 900)[:2], kid_stand(T2), 1.0)
    far = G(*cam.place(200, 1300)[:2], kid_stand(T1), 1.3)
    rep = V.validate_svg(spage("T", _grp(1300, "far", far, scale=1.3)
                               + _grp(900, "near", near, scale=1.0)))
    hits = _checks(rep, "depth_order")
    assert any("larger than nearer" in f["msg"] for f in hits)
    # measured ground (no tag): the farther kid stands LOWER on the page
    near = G(-150 + 425, 800, kid_stand(T2), 1.0)
    far = G(150 + 425, 900, kid_stand(T1), 0.9)
    rep = V.validate_svg(spage("T", _grp(1300, "far", far)
                               + _grp(900, "near", near)))
    hits = _checks(rep, "depth_order")
    assert any("lower on the page" in f["msg"] for f in hits)
    assert all(f["severity"] == "MED" for f in hits)
    assert rep["depth"]["scale_conflicts"] >= 1


def test_depth_order_respects_depth_extent_of_solids():
    """A kid inside a solid's depth span (beside it) drawn after it is not
    an inversion; one wholly behind it is."""
    cam = S.Camera()
    box = S.box3d(cam, 270, 1100, 150, 300, 110)
    kid = _put(cam, 170, 1250, kid_stand(T2))
    rep = V.validate_svg(spage("T", _grp(1100, "box", box, far=1400)
                               + _grp(1250, "kid", kid)))
    assert not [f for f in _checks(rep, "depth_order")
                if "painted over" in f["msg"]]
    kid2 = _put(cam, 240, 1500, kid_stand(T2))
    rep = V.validate_svg(spage("T", _grp(1100, "box", box, far=1400)
                               + _grp(1500, "kid", kid2)))
    assert [f for f in _checks(rep, "depth_order") if "painted over" in f["msg"]]


def test_pages_without_depth_groups_have_no_depth_report():
    rep = V.validate_svg(spage("T", G(425, 940, kid_stand(T2), 1.3)))
    assert "depth" not in rep
    assert not _checks(rep, "depth_order")


def test_head_clearance_exempts_farther_depth_art():
    """A small far object behind a nearer head is correct occlusion inside
    depth groups; the same geometry without depth tags still fires."""
    cam = S.Camera()
    px, py, s = cam.place(-100, 850)
    hx, hy = px, py - 188 * s              # tee kid's head centre
    trunk = C(hx + 6, hy + 4, 8, 4, "white")
    kid = G(px, py, kid_stand(T2), s)
    tagged = _grp(3000, "far", trunk) + _grp(850, "kid", kid)
    rep = V.validate_svg(spage("T", tagged), require_span=False)
    assert not [f for f in _checks(rep, "head_clearance")
                if f["severity"] == "HIGH"]
    plain = V.validate_svg(spage("T", trunk + kid), require_span=False)
    assert [f for f in _checks(plain, "head_clearance")
            if f["severity"] == "HIGH"]
