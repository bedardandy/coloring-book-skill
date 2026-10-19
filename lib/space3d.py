"""space3d — one-point perspective for charlib pages: a pinhole Camera, a
depth-sorted Stage, and perspective line-art primitives (rooms, receding
paths, boxes, tables, rows, floor grids) that stay colorable.

Flat pages put every figure on one ground line. With a Camera, depth is a
NUMBER: a figure's page position, scale and ground contact all follow from
its world (x, z), so "Max in front, Lily behind the table, the house far
away" is consistent by construction:

    from space3d import Camera, Stage, room_box
    cam = Camera()                                   # horizon y520, VP x425
    st = Stage(cam)
    st.add(lambda: kid_stand(T1), x=-150, z=820, name="Max")
    st.add_table(x=60, z=1000, w=260, d=200, h=100, name="table")
    st.add(lambda: kid_stand(T2), x=60, z=1300, name="Lily")
    svg = spage("Playroom", room_box(cam) + st.render())

WORLD UNITS are charlib figure units: a kid_stand is ~250 tall, so a world
height Hw drawn at depth z is Hw * scale_at(z) page px. Axes: x lateral
(0 = the camera axis, + = page right), y up (0 = the ground), z depth
(z > 0 in front of the camera; larger = farther). The camera looks along +z
with a level optical axis, so every line parallel to z converges on ONE
vanishing point (vp_x, horizon_y) and fronto-parallel shapes stay
undistorted — exactly the one-point perspective of a picture-book interior.

PROJECTION (exact; f = focal length in page px, eye_h = camera height):
    f     = near_scale * near_z
    eye_h = (near_ground_y - horizon_y) / near_scale
    px    = vp_x + f * x / z
    py    = horizon_y + f * (eye_h - y) / z
    scale_at(z) = f / z       (so doubling z halves the size)
A charlib fragment drawn at the feet-origin convention and placed with
G(px, py, frag, scale_at(z)) is the EXACT projection of a flat cut-out
standing at depth z: local (lx, ly) maps to world (x + lx, -ly, z).

COLORABILITY RULES baked into every primitive (see reference/spatial-guide.md):
- Converging lines get closer than lib/validate.py's SLIVER_GAP (11px) near
  the vanishing point and leave uncolorable slivers. Every primitive stops
  converging lines — and fades out detail rows — at the depth where their
  PERPENDICULAR spacing drops below CONVERGE_GAP (14px). Box faces, top
  slabs and back table legs thinner than that are omitted.
- Everything is clipped to SAFE: >= 12px inside the border rect (x 28-822,
  y 28-1072), out of the title zone (y < 145) and the caption band (y > 1000).
- White fills, back to front: primitives draw their own far faces first;
  Stage sorts placed items FAR TO NEAR (painter's algorithm), wraps each in
  matted(), and draws each item's short ground contact line AFTER its
  matted art (a mat halo otherwise dashes the ground under feet).

VALIDATION HOOKS: every Stage item is wrapped in
<g data-depth="z" data-depth-name=... data-depth-scale=... data-depth-ground=...>
(solids add data-depth-far); lib/validate.py's depth_order check reads them
(farther-but-bigger, farther-but-lower, farther-painted-over-nearer).

GAZE: look_toward(x_from, x_to) / Stage.gaze(a, b) return a yaw in [-1, 1]
(+ = toward page right) for the parametric face's `look` trait:
kid_stand(dict(t, look=v)). Pass a CALLABLE to Stage.add so the value is
computed at render time, once every item is placed.

All placement is arithmetic — never random — so output is byte-deterministic.
"""
import math
from xml.sax.saxutils import escape as _xml_escape

from charlib import (W, SW, DETAIL_SW, LINE, C, P, G, GM, matted,
                     smooth_path, _cr_to_bez, _f)
from charlib import window as _window
from scenes import SCENE_GROUND

HORIZON_Y = 520            # default page y of the horizon (eye level)
NEAR_Z = 800               # default foreground depth (world units)
NEAR_SCALE = 1.3           # G() scale at NEAR_Z (three-layer recipe foreground)
CONVERGE_GAP = 14.0        # stop converging lines below this perpendicular
                           # spacing (validator SLIVER_GAP is 11px)
SAFE = (42, 152, 808, 988)  # x0, y0, x1, y1 drawable clip rect: >=12px inside
                           # the border (+2px), below the title zone (145),
                           # above the caption band (1000)
LOOK_SPAN = 300.0          # lateral world distance that maps to a full |look|=1
BANDS = {                  # three-layer recipe as multiples of near_z
    "foreground": (1.0, 1.2),
    "midground": (1.35, 2.0),
    "background": (2.25, 5.0),
}


# ---------------------------------------------------------------- camera
class Camera:
    """One-point-perspective pinhole camera on the 850x1100 page.

    horizon_y      page y of the horizon / eye level (vanishing point y)
    vp_x           page x of the vanishing point (camera axis)
    near_z         foreground depth (world units; see BANDS)
    near_ground_y  page y where the ground at z=near_z lands (default
                   scenes.SCENE_GROUND = 940, the kits' ground line)
    near_scale     G() scale of a figure standing at near_z (default 1.3:
                   kid_stand ~326px, the recipe's foreground size)

    Derived: f (focal length, page px) and eye_h (camera height, world
    units; the default camera's eye is ~323 units up — 1.3 kid heights, so
    the horizon sits above the foreground kid's head)."""

    def __init__(self, horizon_y=HORIZON_Y, vp_x=W / 2, near_z=NEAR_Z,
                 near_ground_y=SCENE_GROUND, near_scale=NEAR_SCALE):
        if near_ground_y <= horizon_y:
            raise ValueError("near_ground_y must lie below the horizon "
                             "(the camera stands above the ground)")
        if near_z <= 0 or near_scale <= 0:
            raise ValueError("near_z and near_scale must be positive")
        self.horizon_y = float(horizon_y)
        self.vp_x = float(vp_x)
        self.near_z = float(near_z)
        self.near_ground_y = float(near_ground_y)
        self.near_scale = float(near_scale)
        self.f = self.near_scale * self.near_z
        self.eye_h = (self.near_ground_y - self.horizon_y) / self.near_scale

    def __repr__(self):
        return (f"Camera(horizon_y={self.horizon_y:g}, vp_x={self.vp_x:g}, "
                f"near_z={self.near_z:g}, near_ground_y={self.near_ground_y:g}, "
                f"near_scale={self.near_scale:g})")

    def scale_at(self, z):
        """G() scale of a figure at depth z (f / z)."""
        if z <= 0:
            raise ValueError(f"z={z} is behind the camera (need z > 0)")
        return self.f / z

    def project(self, x, y, z):
        """World (x, y, z) -> page (px, py)."""
        s = self.scale_at(z)
        return (self.vp_x + s * x, self.horizon_y + s * (self.eye_h - y))

    def ground_point(self, x, z):
        """Page point of the ground (y=0) at world (x, z)."""
        return self.project(x, 0.0, z)

    def place(self, x, z, y=0.0):
        """(px, feet_py, scale) for G(px, feet_py, fragment, scale): a
        feet-origin fragment standing at world (x, z), raised y units
        (y > 0: on a table top / shelf)."""
        px, py = self.project(x, y, z)
        return px, py, self.scale_at(z)

    def z_for_ground_y(self, py):
        """Inverse of the ground projection: the depth whose ground lands on
        page row py (must lie below the horizon)."""
        if py <= self.horizon_y:
            raise ValueError(f"page y={py} is at/above the horizon "
                             f"({self.horizon_y:g}): no ground there")
        return self.f * self.eye_h / (py - self.horizon_y)

    def x_for_page_x(self, px, z):
        """Inverse lateral projection: world x that lands on page px at z."""
        return (px - self.vp_x) * z / self.f

    def unproject_ground(self, px, py):
        """Page point below the horizon -> the world ground point (x, z)."""
        z = self.z_for_ground_y(py)
        return self.x_for_page_x(px, z), z

    def band(self, name):
        """(z_near, z_far) of a three-layer band: foreground / midground /
        background (BANDS, scaled by near_z)."""
        a, b = BANDS[name]
        return a * self.near_z, b * self.near_z

    def converge_z(self, off_a, off_b, gap=CONVERGE_GAP):
        """Depth beyond which two depth-parallel lines get closer than
        `gap` page px. Each line is given by its offset (x, y) from the
        camera axis in world units (a ground line at lateral x is (x, 0); a
        wall line at height y on the wall x=hw is (hw, y)). Exact: both lines
        pass through the VP, and the perpendicular distance from a point of
        one (at depth z) to the other is f*|cross(oa, ob)| / (z*|o|) — taking
        the larger |o| keeps it conservative for oblique lines."""
        ax, ay = off_a[0], self.eye_h - off_a[1]
        bx, by = off_b[0], self.eye_h - off_b[1]
        cross = abs(ax * by - ay * bx)
        norm = max(math.hypot(ax, ay), math.hypot(bx, by))
        if cross == 0 or norm == 0:
            return 0.0
        return self.f * cross / (gap * norm)


def look_toward(x_from, x_to, span=LOOK_SPAN):
    """Head yaw for a figure at world x_from looking at x_to, in [-1, 1]
    (+ = toward page right, 0 = facing the reader). Pass it as the face
    trait `look`: kid_stand(dict(t, look=look_toward(-150, 60)))."""
    if span <= 0:
        raise ValueError("span must be positive")
    v = max(-1.0, min(1.0, (x_to - x_from) / float(span)))
    return round(v, 2)


# ---------------------------------------------------------------- clipping
def _clip_seg(p, q, rect=SAFE):
    """Liang-Barsky: segment p-q clipped to rect, or None if outside."""
    x0, y0, x1, y1 = rect
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]),
                   (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return None
            continue
        r = qq / pp
        if pp < 0:
            if r > t1:
                return None
            t0 = max(t0, r)
        else:
            if r < t0:
                return None
            t1 = min(t1, r)
    if t1 - t0 <= 1e-9:
        return None
    return ((p[0] + t0 * dx, p[1] + t0 * dy), (p[0] + t1 * dx, p[1] + t1 * dy))


def _cline(p, q, sw, rect=SAFE, min_len=6.0):
    """LINE from page p to q, clipped to rect ("" when nothing is left).
    Receding lines pass their NEAR end as p: validate.py's sliver_gap
    measures a pair's gap at the second line's first endpoint, and the near
    end lies inside the pair's real overlap (the far end of a longer line
    can reach past where its shorter neighbour stopped)."""
    seg = _clip_seg(p, q, rect)
    if seg is None:
        return ""
    (ax, ay), (bx, by) = seg
    if math.hypot(bx - ax, by - ay) < min_len:
        return ""
    return LINE(ax, ay, bx, by, sw)


def _clamp_pt(p, rect=SAFE):
    return (min(max(p[0], rect[0]), rect[2]), min(max(p[1], rect[1]), rect[3]))


def _poly(pts, sw, fill="white"):
    """Closed straight-edged polygon (white-filled face)."""
    d = f"M {_f(pts[0][0])} {_f(pts[0][1])} " + " ".join(
        f"L {_f(x)} {_f(y)}" for x, y in pts[1:]) + " Z"
    return P(d, sw, fill)


def _near_z(cam, rect=SAFE):
    """A depth near enough that receding lines from the back of a scene are
    certain to leave the page before reaching it (lines are clipped)."""
    return min(cam.near_z * 0.25, cam.z_for_ground_y(rect[3] + 400))


# ---------------------------------------------------------------- room interior
def room_box(cam, width=760, z_back=2000, height=520, *, ceiling=True,
             floor="boards", boards=6, tile_depth=160, window=True,
             door=False, sw=4.5, detail_sw=DETAIL_SW, rect=SAFE):
    """One-point-perspective interior, drawn as the page BACKGROUND (call it
    before Stage.render()). The room spans x in [-width/2, width/2], floor
    y=0, back wall at z_back; its open front faces the camera and every
    receding edge is clipped to `rect`.

    ceiling=True draws the back wall's top edge and the two ceiling corner
    lines (they rise toward the page corners when height > cam.eye_h);
    False runs the back-wall corners up to the clip top (open-topped set).
    floor: "boards" (n=boards lines receding to the VP), "tiles" (boards +
    cross rows every tile_depth units), or None. window: True (default
    placement), False, or (x_center, y_bottom, w, h) in world units on the
    back wall; door: True/False or (x_center, w, h). Converging board lines
    stop where their spacing drops below CONVERGE_GAP; tile rows closer
    than that are skipped (fade-out), so no sliver regions are created."""
    hw = width / 2.0
    zo = _near_z(cam, rect)
    out = []
    bl, br = cam.project(-hw, 0, z_back), cam.project(hw, 0, z_back)
    tl, tr = cam.project(-hw, height, z_back), cam.project(hw, height, z_back)
    # floor: drawn first so the structural edges lie on top
    if floor in ("boards", "tiles"):
        n = max(1, int(boards))
        xs = [-hw + width * k / n for k in range(n + 1)]
        for k in range(1, n):
            zf = min(z_back, cam.converge_z((xs[k - 1], 0), (xs[k], 0)),
                     cam.converge_z((xs[k], 0), (xs[k + 1], 0)))
            if zf <= zo:
                continue
            out.append(_cline(cam.ground_point(xs[k], zo),
                              cam.ground_point(xs[k], zf), detail_sw, rect))
        if floor == "tiles" and tile_depth > 0:
            prev_y = bl[1]
            z = z_back - tile_depth
            while z > zo:
                y = cam.ground_point(0, z)[1]
                if y > rect[3]:
                    break
                if y - prev_y >= CONVERGE_GAP:
                    out.append(_cline(cam.ground_point(-hw, z),
                                      cam.ground_point(hw, z), detail_sw, rect))
                    prev_y = y
                z -= tile_depth
    # receding floor/wall edges, then the back wall on top of them
    out.append(_cline(cam.ground_point(-hw, zo), bl, sw, rect))
    out.append(_cline(cam.ground_point(hw, zo), br, sw, rect))
    if ceiling:
        out.append(_cline(cam.project(-hw, height, zo), tl, sw, rect))
        out.append(_cline(cam.project(hw, height, zo), tr, sw, rect))
        out.append(_cline(tl, tr, sw, rect))
        top_l, top_r = tl, tr
    else:
        top_l, top_r = (tl[0], rect[1]), (tr[0], rect[1])
    out.append(_cline(bl, br, sw, rect))
    out.append(_cline(bl, top_l, sw, rect))
    out.append(_cline(br, top_r, sw, rect))
    # back-wall features: the wall is fronto-parallel, so a world rectangle
    # on it projects to an undistorted page rectangle
    k = cam.scale_at(z_back)
    if window:
        wx, wy, ww, wh = ((-0.2 * width if door else 0.0, 0.36 * height,
                           0.3 * width, 0.34 * height)
                          if window is True else window)
        px0, py1 = cam.project(wx - ww / 2, wy, z_back)
        out.append(_window(px0, py1 - wh * k, ww * k, wh * k))
    if door:
        dx, dw, dh = ((0.28 * width, 0.2 * width, 0.66 * height)
                      if door is True else door)
        px0, py1 = cam.project(dx - dw / 2, 0, z_back)
        # square corners: the door's sill lies ON the wall-base line, and
        # rounded bottom corners would leave two wedge slivers there
        px1, py0 = px0 + dw * k, py1 - dh * k
        out.append(_poly([(px0, py1), (px0, py0), (px1, py0), (px1, py1)],
                         sw, "white"))
        out.append(C(px0 + dw * k * 0.8, py1 - dh * k * 0.48,
                     max(4.0, 7 * k), 3, "white"))
    return "".join(out)


def wall_quad(cam, x, z0, z1, y0, y1, *, sw=4.5, fill="white", inset=0.0):
    """A rectangle on a SIDE wall (the plane at lateral x, e.g. -width/2 of
    a room_box) spanning depths z0..z1 and heights y0..y1: a picture, side
    window, door or shelf in perspective. inset > 0 adds an inner frame
    whose band is `inset` PAGE px wide at its thinnest (raised to
    CONVERGE_GAP): a world-unit inset along depth foreshortens to a sliver
    at the far edge, so the inner depths are solved on the page. Returns ""
    when the quad itself would be a sliver (its near and far edges, or its
    top and bottom edges at the far end, closer than CONVERGE_GAP)."""
    def quad(za, zb, ya, yb):
        pa, pb = cam.project(x, ya, za), cam.project(x, ya, zb)
        qa, qb = cam.project(x, yb, za), cam.project(x, yb, zb)
        if (abs(pa[0] - pb[0]) < CONVERGE_GAP
                or abs(pb[1] - qb[1]) < CONVERGE_GAP):
            return None
        return [pa, pb, qb, qa]

    outer = quad(z0, z1, y0, y1)
    if outer is None:
        return ""
    out = [_poly(outer, sw, fill)]
    if inset > 0 and x != 0:
        band = max(float(inset), CONVERGE_GAP)
        px0, px1 = outer[0][0], outer[1][0]
        step = band if px1 > px0 else -band
        za = cam.f * x / (px0 + step - cam.vp_x)       # page x -> depth on
        zb = cam.f * x / (px1 - step - cam.vp_x)       # the wall plane
        if z0 < za < zb < z1:
            yi = band / cam.scale_at(zb)               # thinnest at the far end
            inner = (quad(za, zb, y0 + yi, y1 - yi)
                     if y1 - y0 > 2 * yi else None)
            if inner is not None:
                out.append(_poly(inner, max(2.5, sw - 1.5), fill))
    return "".join(out)


# ---------------------------------------------------------------- ground primitives
def ground_grid(cam, x0, x1, z0, z1, dx=100, dz=150, sw=DETAIL_SW, rect=SAFE):
    """Floor tiles / garden plots: depth lines every dx (converging on the
    VP) and cross rows every dz between z0 (near) and z1 (far), outline
    included. Depth lines stop where neighbours get closer than
    CONVERGE_GAP; cross rows closer than that are skipped (fade-out)."""
    n = max(1, int(round((x1 - x0) / float(dx))))
    xs = [x0 + (x1 - x0) * k / n for k in range(n + 1)]
    out = []
    for k, x in enumerate(xs):
        stop = z1
        if k > 0:
            stop = min(stop, cam.converge_z((xs[k - 1], 0), (x, 0)))
        if k < n:
            stop = min(stop, cam.converge_z((x, 0), (xs[k + 1], 0)))
        if stop > z0:
            out.append(_cline(cam.ground_point(x, z0),
                              cam.ground_point(x, stop), sw, rect))
    m = max(1, int(round((z1 - z0) / float(dz))))
    prev_y = None
    for j in range(m, -1, -1):              # far row first
        z = z0 + (z1 - z0) * j / m
        y = cam.ground_point(0, z)[1]
        if prev_y is not None and y - prev_y < CONVERGE_GAP:
            continue
        out.append(_cline(cam.ground_point(x0, z), cam.ground_point(x1, z),
                          sw, rect))
        prev_y = y
    return "".join(out)


def ground_ellipse(cam, x, z, rx, rz, sw=4, fill="white", n=24):
    """A ground-plane ellipse (rug, pond, puddle, sandpit) centred at world
    (x, z) with lateral radius rx and depth radius rz, projected exactly
    (sampled) and drawn as one smooth closed white-filled curve."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append(cam.ground_point(x + rx * math.cos(a), z + rz * math.sin(a)))
    return smooth_path(pts, sw=sw, fill=fill, closed=True)


def _cr_d(pts):
    """Catmull-Rom path data THROUGH pts (no leading M)."""
    d = ""
    for p1, c1, c2, p2 in _cr_to_bez([(float(a), float(b)) for a, b in pts],
                                     False):
        d += (f"C {_f(c1[0])} {_f(c1[1])} {_f(c2[0])} {_f(c2[1])} "
              f"{_f(p2[0])} {_f(p2[1])} ")
    return d


def path_recede(cam, x, width, z0, z1, curve=0.0, *, sw=4.5, dashes=False,
                samples=18, rect=SAFE):
    """A path or road of constant world `width` running from depth z0
    (near) to z1 (far) around lateral x, narrowing toward the horizon.
    curve bends it sideways by curve*sin(pi*t) world units (t = 0 near, 1
    far): a winding garden path. Returns ONE closed white-filled shape (it
    knocks out ground lines/hills drawn before it), so draw it over the
    background and under the Stage.

    The far end is capped where the edges' perpendicular spacing would
    drop below CONVERGE_GAP (an uncolorable sliver otherwise); the near end
    is cut at the clip bottom. Edges are clamped into `rect` laterally.
    dashes=True adds centre dashes that fade out where they'd crowd the
    edges."""
    z_near = max(z0, cam.z_for_ground_y(rect[3]))
    if z_near >= z1:
        raise ValueError("path lies entirely below the clip rect")

    def cx_at(z):
        t = (z - z0) / float(z1 - z0)
        return x + curve * math.sin(math.pi * t)

    # far stop: both edge offsets as depth-parallel ground lines
    z_far = z1
    for i in range(samples + 1):
        z = z_near * (z1 / z_near) ** (i / samples)
        c = cx_at(z)
        if z > cam.converge_z((c - width / 2, 0), (c + width / 2, 0)):
            z_far = min(z_far, z)
            break
    z_far = min(z_far, cam.converge_z((cx_at(z_far) - width / 2, 0),
                                      (cx_at(z_far) + width / 2, 0)))
    if z_far <= z_near:
        return ""
    zs = [z_near * (z_far / z_near) ** (i / samples) for i in range(samples + 1)]
    left = [_clamp_pt(cam.ground_point(cx_at(z) - width / 2, z), rect) for z in zs]
    right = [_clamp_pt(cam.ground_point(cx_at(z) + width / 2, z), rect) for z in zs]
    d = (f"M {_f(left[0][0])} {_f(left[0][1])} " + _cr_d(left)
         + f"L {_f(right[-1][0])} {_f(right[-1][1])} " + _cr_d(right[::-1]) + "Z")
    out = [P(d, sw, "white")]
    if dashes:
        dash, gap = width * 0.6, width * 0.5
        z = z_near + gap / 2
        z_stop = min(z_far, cam.converge_z((0, 0), (width / 2, 0)))
        while z + dash < z_stop:
            a = cam.ground_point(cx_at(z), z)
            b = cam.ground_point(cx_at(z + dash), z + dash)
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 10:
                break
            out.append(_cline(a, b, 3.5, rect))
            z += dash + gap
    return "".join(out)


# ---------------------------------------------------------------- solids
def box3d(cam, x, z, w, d, h, *, base=0.0, sw=SW, fill="white", top=True,
          sides=True):
    """Extruded box in perspective — blocks, crates, beds, counters,
    buildings. Footprint centred on lateral x, front face at depth z,
    extending d units away, h tall, bottom at height `base` (0 = on the
    ground). Only VISIBLE faces are drawn, far first (top, side, then the
    fronto-parallel front face): the top shows when base + h < cam.eye_h,
    the left side when the box sits right of the camera axis (and vice
    versa). A face thinner than CONVERGE_GAP on the page is omitted rather
    than drawn as an uncolorable sliver."""
    x0, x1 = x - w / 2.0, x + w / 2.0
    y0, y1 = base, base + h
    zf = z + d
    fbl, fbr = cam.project(x0, y0, z), cam.project(x1, y0, z)
    ftl, ftr = cam.project(x0, y1, z), cam.project(x1, y1, z)
    btl, btr = cam.project(x0, y1, zf), cam.project(x1, y1, zf)
    bbl, bbr = cam.project(x0, y0, zf), cam.project(x1, y0, zf)
    out = []
    if top and y1 < cam.eye_h and ftl[1] - btl[1] >= CONVERGE_GAP:
        out.append(_poly([ftl, ftr, btr, btl], sw, fill))
    if sides:
        if x0 > 0 and ftl[0] - btl[0] >= CONVERGE_GAP:
            out.append(_poly([fbl, ftl, btl, bbl], sw, fill))
        if x1 < 0 and btr[0] - ftr[0] >= CONVERGE_GAP:
            out.append(_poly([fbr, ftr, btr, bbr], sw, fill))
    out.append(_poly([fbl, fbr, ftr, ftl], sw, fill))
    return "".join(out)


def table3d(cam, x, z, w, d, h, *, top_t=14, leg=14, sw=SW):
    """Table in perspective: four legs + a top slab (box3d) at height h.
    Back legs draw first and are dropped when they would sit closer than
    CONVERGE_GAP to a front leg (a sliver between the two outlines); the
    slab draws last so it caps the legs. Figures BEHIND the table (z >
    z + d) show their upper body over it — "Lily behind the table"."""
    inset = leg * 0.9
    lx = (x - w / 2 + inset + leg / 2, x + w / 2 - inset - leg / 2)
    z_front, z_back = z + inset, z + d - inset - leg
    lw = leg * cam.scale_at(z_front)
    out = []
    for zl in (z_back, z_front):                    # back pair first
        for cxl in lx:
            if zl == z_back:
                fx = cam.project(cxl, 0, z_front)[0]
                bx = cam.project(cxl, 0, z_back)[0]
                if abs(fx - bx) < lw + CONVERGE_GAP:
                    continue                        # hidden behind its twin
            out.append(box3d(cam, cxl, zl, leg, leg, h - top_t, sw=sw - 0.5,
                             top=False))
    out.append(box3d(cam, x, z, w, d, top_t, base=h - top_t, sw=sw))
    return "".join(out)


# ---------------------------------------------------------------- rows
def _row_slots(cam, x, z0, z1, n, min_gap=CONVERGE_GAP, min_scale=0.2):
    """[(i, x, z)] for n items evenly spaced in depth from z0 to z1 (x may
    be a number or a callable(i) -> x), NEAR first, dropping items smaller
    than min_scale or whose ground point crowds the last kept one by less
    than min_gap page px (fade-out)."""
    slots, last_y = [], None
    for i in range(n):
        z = z0 + (z1 - z0) * (i / (n - 1) if n > 1 else 0.0)
        if cam.scale_at(z) < min_scale:
            continue
        xi = x(i) if callable(x) else x
        y = cam.ground_point(xi, z)[1]
        if last_y is not None and abs(last_y - y) < min_gap:
            continue
        slots.append((i, xi, z))
        last_y = y
    return slots


def receding_row(cam, make, x, z0, z1, n, *, min_gap=CONVERGE_GAP,
                 min_scale=0.2, mat=False, pad=9):
    """n copies of make(i) (a feet-origin fragment: trees, fence posts,
    lampposts) evenly spaced in depth from z0 (near) to z1 (far) at lateral
    x (a number, or callable(i) -> x for zig-zags). Each is placed with the
    exact perspective scale and drawn FAR TO NEAR. Items whose ground
    points crowd closer than min_gap page px, or smaller than min_scale, are
    dropped (fade-out). For rows that must interleave with figures, use
    Stage.add_row instead (one depth group per item)."""
    out = []
    for i, xi, z in reversed(_row_slots(cam, x, z0, z1, n, min_gap,
                                        min_scale)):
        px, py, s = cam.place(xi, z)
        frag = make(i)
        out.append(G(px, py, matted(frag, pad, scale=s) if mat else frag, s))
    return "".join(out)


# ---------------------------------------------------------------- stage
def _bottom_span(frag):
    """x-range of the parts of a fragment that touch its bottom (the feet,
    a trunk, wheels): elements whose bbox bottom lies in the lowest 10% of
    the fragment's height. None for an empty fragment."""
    import xml.etree.ElementTree as _ET
    import validate as _v
    root = _ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg">' + frag
                          + "</svg>")
    items, _m, _l = _v._collect(root)
    boxes = [it.wbbox for it in items
             if not it.in_mat and not it.text and it.wbbox is not None]
    if not boxes:
        return None
    y0 = min(b[1] for b in boxes)
    y1 = max(b[3] for b in boxes)
    cut = y1 - 0.10 * max(1e-6, y1 - y0)
    low = [b for b in boxes if b[3] >= cut]
    return min(b[0] for b in low), max(b[2] for b in low)


class _Item:
    __slots__ = ("kind", "art", "x", "y", "z", "z_far", "x0", "x1", "top",
                 "name", "mat", "contact", "flip", "idx")


class Stage:
    """Depth-sorted scene graph over a Camera.

    add() billboards: a fragment (or a zero-argument callable returning one,
    evaluated at render time) drawn at the charlib FEET-ORIGIN convention
    (kid_stand, dog_sit, tree_round(0, 0, ...)), stood at world (x, z) with
    the exact perspective scale. add_box()/add_table()/add_solid() take
    page-space perspective solids with a depth extent.

    render() draws everything FAR TO NEAR (painter's algorithm; a billboard
    beside a solid on its camera-facing side, or resting on top of it, draws
    after it), each item wrapped in matted() and in
    <g data-depth="z" data-depth-name=... data-depth-scale=...
       data-depth-ground=...>
    (solids add data-depth-far), with each billboard's short ground contact
    line drawn AFTER its matted art. lib/validate.py's depth_order check
    reads those tags."""

    def __init__(self, cam, pad=9, contact_sw=4.0):
        self.cam = cam
        self.pad = pad
        self.contact_sw = contact_sw
        self.items = []

    def _push(self, it):
        it.idx = len(self.items)
        if it.name is None:
            it.name = f"item{it.idx + 1}"
        self.items.append(it)
        return self

    def add(self, art, x, z, name=None, mat=True, contact=True, y=0.0,
            flip=False):
        """Stand a feet-origin fragment (or callable) at world (x, z); y > 0
        raises it onto a surface. flip=True mirrors it (GM). contact: True
        (auto width from the fragment's feet), a half-width in world units,
        or False. Returns the stage (chainable)."""
        if z <= 0:
            raise ValueError(f"z={z} is behind the camera")
        it = _Item()
        it.kind, it.art, it.x, it.y, it.z = "bill", art, float(x), float(y), float(z)
        it.z_far, it.x0, it.x1, it.top = float(z), float(x), float(x), None
        it.name, it.mat, it.contact, it.flip = name, mat, contact, flip
        return self._push(it)

    def add_solid(self, art, z, z_far=None, x0=None, x1=None, top=None,
                  name=None, mat=True):
        """A page-space perspective fragment (already projected, e.g. from
        box3d) occupying depths z..z_far and world x0..x1, top units tall
        (for the "resting on it" ordering rule)."""
        it = _Item()
        it.kind, it.art, it.z = "solid", art, float(z)
        it.z_far = float(z if z_far is None else z_far)
        it.x0 = float(x0) if x0 is not None else -math.inf
        it.x1 = float(x1) if x1 is not None else math.inf
        it.x, it.y, it.top = None, 0.0, top
        it.name, it.mat, it.contact, it.flip = name, mat, False, False
        return self._push(it)

    def add_box(self, x, z, w, d, h, name=None, mat=True, **kw):
        """box3d(cam, x, z, w, d, h, **kw) as a depth-sorted solid."""
        return self.add_solid(lambda: box3d(self.cam, x, z, w, d, h, **kw),
                              z, z + d, x - w / 2, x + w / 2, h, name, mat)

    def add_table(self, x, z, w, d, h, name=None, mat=True, **kw):
        """table3d(cam, x, z, w, d, h, **kw) as a depth-sorted solid."""
        return self.add_solid(lambda: table3d(self.cam, x, z, w, d, h, **kw),
                              z, z + d, x - w / 2, x + w / 2, h, name, mat)

    def add_row(self, make, x, z0, z1, n, name="row", mat=True, contact=False,
                min_gap=CONVERGE_GAP, min_scale=0.2):
        """receding_row as individual billboards (each make(i) gets its own
        depth group, so a figure can stand between two trees)."""
        for i, xi, z in _row_slots(self.cam, x, z0, z1, n, min_gap, min_scale):
            self.add((lambda i=i: make(i)), xi, z, name=f"{name}{i + 1}",
                     mat=mat, contact=contact)
        return self

    def gaze(self, src, dst, span=LOOK_SPAN):
        """look_toward() between two named billboards (call inside a
        callable passed to add(), so it runs at render time)."""
        a = next(it for it in self.items if it.name == src)
        b = next(it for it in self.items if it.name == dst)
        return look_toward(a.x if a.x is not None else (a.x0 + a.x1) / 2,
                           b.x if b.x is not None else (b.x0 + b.x1) / 2, span)

    # ---- ordering
    @staticmethod
    def _solid_first(s, b):
        """True when billboard b must draw AFTER solid s although their
        depth ranges overlap: b stands beside s on the camera-facing side
        (whose visible side face would otherwise paint over it), or b rests
        on/above s's top."""
        if not (s.z <= b.z <= s.z_far):
            return False
        if s.top is not None and b.y >= s.top * 0.98 and s.x0 <= b.x <= s.x1:
            return True
        if s.x0 >= 0 and b.x < s.x0:
            return True
        if s.x1 <= 0 and b.x > s.x1:
            return True
        return False

    def _order(self):
        """Kahn topological sort: hard edges for strictly-behind pairs and
        the solid/billboard rule; among free items, the FARTHEST near-z goes
        first (ties: insertion order). Deterministic."""
        items = self.items
        n = len(items)
        after = [set() for _ in range(n)]       # i must draw before each j
        indeg = [0] * n
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                a, b = items[i], items[j]
                first = a.z > b.z_far
                if not first and a.kind == "solid" and b.kind == "bill":
                    first = self._solid_first(a, b)
                if first and j not in after[i]:
                    after[i].add(j)
                    indeg[j] += 1
        done, out = set(), []
        while len(out) < n:
            free = [k for k in range(n) if k not in done and indeg[k] == 0]
            if not free:                         # cycle: fall back to depth
                free = [k for k in range(n) if k not in done]
            k = min(free, key=lambda q: (-items[q].z, items[q].idx))
            done.add(k)
            out.append(items[k])
            for j in after[k]:
                indeg[j] -= 1
        return out

    def order(self):
        """Item names in draw order (far to near)."""
        return [it.name for it in self._order()]

    # ---- output
    def _contact(self, it, frag, px, py, s):
        if not it.contact:
            return ""
        if it.contact is True:
            span = _bottom_span(frag)
            if span is None:
                return ""
            a, b = span
            if it.flip:
                a, b = -b, -a
            half = (b - a) / 2 * s + 12
            mid = px + (a + b) / 2 * s
        else:
            half, mid = float(it.contact) * s, px
        sw = max(3.0, min(self.contact_sw, self.contact_sw * s))
        return LINE(mid - half, py, mid + half, py, sw)

    def render(self):
        """Body string: every item far to near, tagged and matted."""
        cam = self.cam
        out = []
        for it in self._order():
            frag = it.art() if callable(it.art) else it.art
            name = _xml_escape(str(it.name), {'"': "&quot;"})
            if it.kind == "bill":
                px, py, s = cam.place(it.x, it.z, it.y)
                inner = matted(frag, self.pad, scale=s) if it.mat else frag
                body = (GM if it.flip else G)(px, py, inner, s)
                body += self._contact(it, frag, px, py, s)
                gy = cam.ground_point(it.x, it.z)[1]
                attrs = (f'data-depth="{_f(it.z)}" data-depth-name="{name}" '
                         f'data-depth-scale="{round(s, 2):g}" '
                         f'data-depth-ground="{_f(gy)}" data-depth-x="{_f(it.x)}"')
            else:
                body = matted(frag, self.pad) if it.mat else frag
                gx = 0.0 if math.isinf(it.x0) or math.isinf(it.x1) \
                    else (it.x0 + it.x1) / 2
                gy = cam.ground_point(gx, it.z)[1]
                attrs = (f'data-depth="{_f(it.z)}" data-depth-far="{_f(it.z_far)}" '
                         f'data-depth-name="{name}" data-depth-ground="{_f(gy)}"')
            out.append(f"<g {attrs}>{body}</g>")
        return "".join(out)
