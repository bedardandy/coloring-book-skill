"""Deterministic layout validation for charlib pages.

charlib embeds semantic metadata (data-face / data-sky / data-ground /
data-hand / data-el="figure" / data-mat / data-chrome) into the SVG it emits.
This module parses that SVG, expands every nested G()/GM() transform into a
world-space affine matrix, and runs EXACT ARITHMETIC versions of the numeric
rules that reference/drawing-guide.md previously asked models to eyeball:

  border_clearance   every element >= CLEARANCE px inside the border rect
  scene_span         connected scene mass spans >=55% of page height
                     (data-sky tokens excluded — a corner sun + high cloud
                     must NOT make the arithmetic pass)
  figure_size        figures >= MIN_FIG_H px tall; faces r >= MIN_FACE_R
  caption_band       no art intrudes into the caption band (y > CAPTION_Y)
  title_band         no art intrudes into the title zone (y < TITLE_Y)
  text_fit           text width estimated from DejaVu metrics must fit the
                     page with margin (the 0.55x/0.62x rule, computed)
  head_clearance     no foreign element inside a face's 1.3r kill radius
                     (heads draw LAST and silently cover props)
  hand_arm           hand circles must OVERLAP some line endpoint (a 2px gap
                     reads as a floating bubble); line ends stopping just
                     outside a hand are flagged as near-misses
  ground_tangency    wheels tagged data-ground sit tangent to their line
  sliver_gap         near-parallel lines closer than the ~11px uncolorable
                     gap floor (3-4mm at 100dpi)
  mat_swallow        a later knockout mat fully covering an earlier element
                     (the documented "dog's halo ate the mound" failure)
  float_noise        leftover long decimals (should be impossible post-serialize)

Usage:
    from validate import validate_svg, validate_file, full_qa, lint_book
    report = validate_file("pages/05-search.svg")
    if not report["ok"]: ...

Severity: HIGH = ship-blocker (erased art, collision, floating wheel);
MED = likely-visible craft violation; LOW = polish/lint.
CLI: `python -m lib.validate pages/*.svg` exits 1 on any HIGH finding.
"""
import math
import re
import sys
import xml.etree.ElementTree as ET

W, H = 850, 1100
BORDER_INSET = 28          # page()/spage() border rect inset
CLEARANCE = 12             # guide rule: keep elements >=12px inside the border
SPAN_TOP = 450             # guide rule: connected mass top <=450 ...
SPAN_BOTTOM = 900          # ... and bottom >=900 (>=55% of page height)
MIN_FIG_H = 180            # main figures >=180px tall
MIN_FACE_R = 28.0          # faces r>=28 or trait features crowd
CAPTION_Y = 1000           # caption band starts ~y1000 ("keep art above it")
TITLE_Y = 145              # title baseline+underline zone
HEAD_KILL = 1.3            # prop clearance radius multiplier (head+hair)
SLIVER_GAP = 11.0          # ~3-4mm parallel-line gap floor @100dpi
GROUND_TOL = 2.0           # wheel tangency tolerance (px)
TEXT_W_REGULAR = 0.55      # DejaVu Sans avg advance per char (per drawing-guide)
TEXT_W_BOLD = 0.62

_SVG_NS = "{http://www.w3.org/2000/svg}"
_SHAPE_TAGS = ("path", "circle", "ellipse", "rect", "line",
               "polygon", "polyline")
_TRANSFORM_RE = re.compile(r"(translate|rotate|scale)\(\s*([^)]*)\)")
_NUM_TOKEN_RE = re.compile(r"-?\d+(?:\.\d+)?")


# ------------------------------------------------------------------ geometry
def _mat(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0):
    return [a, b, c, d, e, f]


def _mmul(m1, m2):
    """m1 * m2 (apply m2 first, then m1)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return [
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    ]


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _parse_transform(s):
    """Parse the translate/rotate/scale grammar charlib's G()/GM() emit."""
    m = _mat()
    if not s:
        return m
    for name, args in _TRANSFORM_RE.findall(s):
        vals = [float(v) for v in _NUM_TOKEN_RE.findall(args)]
        if name == "translate":
            t = _mat(e=vals[0], f=vals[1] if len(vals) > 1 else 0.0)
            m = _mmul(m, t)
        elif name == "scale":
            sx = vals[0]
            sy = vals[1] if len(vals) > 1 else vals[0]
            m = _mmul(m, _mat(a=sx, d=sy))
        elif name == "rotate":
            ang = math.radians(vals[0])
            ca, sa = math.cos(ang), math.sin(ang)
            rm = _mat(a=ca, b=sa, c=-sa, d=ca)
            if len(vals) == 3:  # rotate(a cx cy)
                m = _mmul(m, _mat(e=vals[1], f=vals[2]))
                m = _mmul(m, rm)
                m = _mmul(m, _mat(e=-vals[1], f=-vals[2]))
            else:
                m = _mmul(m, rm)
    return m


def _local_bbox(el):
    """Conservative local bbox of an element, or None if not measurable.

    Paths use ALL coordinate numbers paired even/odd — valid because charlib
    only emits absolute M/L/Q/C/Z commands. Control points make path boxes a
    slight superset of the true curve extent (conservative = safe here)."""
    tag = el.tag.replace(_SVG_NS, "")
    g = el.get
    try:
        if tag == "circle":
            cx, cy, r = float(g("cx")), float(g("cy")), float(g("r"))
            return (cx - r, cy - r, cx + r, cy + r)
        if tag == "ellipse":
            cx, cy = float(g("cx")), float(g("cy"))
            rx, ry = float(g("rx")), float(g("ry"))
            return (cx - rx, cy - ry, cx + rx, cy + ry)
        if tag == "rect":
            x, y = float(g("x", 0)), float(g("y", 0))
            w_, h_ = float(g("width")), float(g("height"))
            return (x, y, x + w_, y + h_)
        if tag == "line":
            x1, y1, x2, y2 = (float(g(k)) for k in ("x1", "y1", "x2", "y2"))
            return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if tag in ("polygon", "polyline"):
            nums = [float(v) for v in _NUM_TOKEN_RE.findall(g("points", ""))]
            xs, ys = nums[0::2], nums[1::2]
            return (min(xs), min(ys), max(xs), max(ys))
        if tag == "path":
            nums = [float(v) for v in _NUM_TOKEN_RE.findall(g("d", ""))]
            xs, ys = nums[0::2], nums[1::2]
            if not xs or not ys:
                return None
            return (min(xs), min(ys), max(xs), max(ys))
    except (TypeError, ValueError):
        return None
    return None


def _world_bbox(el, m):
    lb = _local_bbox(el)
    if lb is None:
        return None
    x0, y0, x1, y1 = lb
    pts = [_apply(m, x0, y0), _apply(m, x1, y0),
           _apply(m, x0, y1), _apply(m, x1, y1)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _inflate(bb, pad):
    return (bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad)


def _contains(outer, inner, tol=0.5):
    return (outer[0] <= inner[0] + tol and outer[1] <= inner[1] + tol
            and outer[2] >= inner[2] - tol and outer[3] >= inner[3] - tol)


def _intersects(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _disk_hits_bbox(cx, cy, r, bb):
    nx = min(max(cx, bb[0]), bb[2])
    ny = min(max(cy, bb[1]), bb[3])
    return (cx - nx) ** 2 + (cy - ny) ** 2 <= r * r


# ------------------------------------------------------------------ collection
class _El:
    __slots__ = ("el", "tag", "m", "wbbox", "figure", "chrome",
                 "in_mat", "mat_owner", "idx")

    def __init__(self, el, m, figure, chrome, in_mat, mat_owner, idx):
        self.el = el
        self.tag = el.tag.replace(_SVG_NS, "")
        self.m = m
        self.figure = figure      # nearest ancestor g[data-el] node, or None
        self.chrome = chrome      # inside data-chrome group
        self.in_mat = in_mat      # inside a knockout-mat copy (invisible)
        self.mat_owner = mat_owner
        self.idx = idx            # document order among collected items
        self.wbbox = None


class _Mat:
    __slots__ = ("node", "m", "pad", "boxes")

    def __init__(self, node, m, pad):
        self.node = node
        self.m = m
        self.pad = pad
        self.boxes = []


def _collect(root):
    """Single document-order walk. Returns (visible_items, mats_in_order, layout)."""
    items, mats = [], []
    layouts = set()
    counter = [0]

    def walk(node, m, figure, chrome, in_mat, mat_owner):
        tag = node.tag.replace(_SVG_NS, "")
        if tag == "svg":
            for child in node:
                walk(child, m, figure, chrome, in_mat, mat_owner)
            return
        if tag == "g":
            lay = node.get("data-layout")
            if lay:
                layouts.add(lay)
            nm = _mmul(m, _parse_transform(node.get("transform")))
            nfig = figure if node.get("data-el") is None else node
            nchrome = chrome or (node.get("data-chrome") == "1")
            nin_mat, nowner = in_mat, mat_owner
            if node.get("data-mat") == "1" and not in_mat:
                mt = _Mat(node, nm, float(node.get("data-pad") or 9))
                mats.append(mt)
                nin_mat, nowner = True, mt
            for child in node:
                walk(child, nm, nfig, nchrome, nin_mat, nowner)
            return
        if tag in _SHAPE_TAGS or tag == "text":
            nm = _mmul(m, _parse_transform(node.get("transform")))
            nchrome = chrome or (node.get("data-chrome") == "1")
            it = _El(node, nm, figure, nchrome, in_mat, mat_owner, counter[0])
            counter[0] += 1
            items.append(it)
            if in_mat and mat_owner is not None and tag != "text":
                wb = _world_bbox(node, nm)
                if wb:
                    mat_owner.boxes.append(wb)

    walk(root, _mat(), None, False, False, None)
    for it in items:
        if not it.in_mat:
            it.wbbox = _world_bbox(it.el, it.m)
    return items, mats, layouts


def _faces(items):
    """World-space face circles from data-face attrs, with document order."""
    out = []
    for it in items:
        raw = it.el.get("data-face")
        if not raw:
            continue
        cx, cy, r = (float(v) for v in raw.split(","))
        wx, wy = _apply(it.m, cx, cy)
        det = abs(it.m[0] * it.m[3] - it.m[1] * it.m[2])
        scale = math.sqrt(det) if det else 1.0
        out.append((wx, wy, r * scale, it.figure, it.idx))
    return out


def _hands(items):
    out = []
    for it in items:
        if it.el.get("data-hand") != "1":
            continue
        wb = _world_bbox(it.el, it.m)
        if wb:
            out.append(((wb[0] + wb[2]) / 2, (wb[1] + wb[3]) / 2,
                        (wb[2] - wb[0]) / 2, it.figure))
    return out


def _line_endpoints(items):
    eps = []
    path_pts = []  # (all coord pairs per path) — closed limb outlines reach
    for it in items:  # the wrist mid-path, so endpoints alone miss them
        if it.chrome or it.in_mat:
            continue
        try:
            if it.tag == "line":
                p1 = _apply(it.m, float(it.el.get("x1")), float(it.el.get("y1")))
                p2 = _apply(it.m, float(it.el.get("x2")), float(it.el.get("y2")))
                eps.append((p1, it))
                eps.append((p2, it))
            elif it.tag == "path":
                nums = [float(v) for v in
                        _NUM_TOKEN_RE.findall(it.el.get("d", ""))]
                if len(nums) < 4:
                    continue
                pts = [_apply(it.m, nums[i], nums[i + 1])
                       for i in range(0, len(nums) - 1, 2)]
                eps.append((pts[0], it))
                eps.append((pts[-1], it))
                path_pts.append((pts, it))
        except (TypeError, ValueError):
            continue
    return eps, path_pts


# ------------------------------------------------------------------ checks
def validate_svg(svg_str, *, clearance=CLEARANCE, span_top=SPAN_TOP,
                 span_bottom=SPAN_BOTTOM, min_fig_h=MIN_FIG_H,
                 min_face_r=MIN_FACE_R, caption_y=CAPTION_Y, title_y=TITLE_Y,
                 require_span=True):
    """Validate one serialized page SVG. Returns a report dict:
    {ok, findings: [{severity, check, msg}], counts}."""
    findings = []

    def add(sev, check, msg):
        findings.append({"severity": sev, "check": check, "msg": msg})

    root = ET.fromstring(svg_str)
    items, mats, layouts = _collect(root)
    is_activity = "activity" in layouts
    is_vignette = "vignette" in layouts
    visible = [it for it in items if not it.in_mat]
    inner_border = (BORDER_INSET + clearance, BORDER_INSET + clearance,
                    W - BORDER_INSET - clearance, H - BORDER_INSET - clearance)

    # ---- border clearance --------------------------------------------------
    for it in visible:
        if it.chrome or it.tag == "text" or not it.wbbox:
            continue
        bb = it.wbbox
        if (bb[0] < inner_border[0] or bb[1] < inner_border[1]
                or bb[2] > inner_border[2] or bb[3] > inner_border[3]):
            add("HIGH", "border_clearance",
                f"{it.tag} at {[round(v) for v in bb]} crosses the "
                f"{clearance}px interior margin {list(inner_border)}")

    # ---- scene span (sky tokens excluded) ----------------------------------
    mass = [it.wbbox for it in visible
            if not it.chrome and it.tag != "text"
            and it.el.get("data-sky") != "1" and it.wbbox]
    if mass and require_span:
        top = min(b[1] for b in mass)
        bot = max(b[3] for b in mass)
        span = bot - top
        need = 0.55 * H
        if span < need:
            if is_activity or "creative" in layouts:
                add("LOW", "scene_span",
                    f"scene mass spans {span:.0f}px (fine for an "
                    f"data-layout=activity page)")
            else:
                add("HIGH", "scene_span",
                    f"scene mass spans {span:.0f}px ({top:.0f}..{bot:.0f}); "
                    f"need >= {need:.0f}px — add midground anchors, not sky "
                    f"tokens")
        else:
            if top > span_top:
                add("MED", "scene_span",
                    f"scene top y={top:.0f} (want <= {span_top}): bottom-crammed")
            if bot < span_bottom:
                add("MED", "scene_span",
                    f"scene bottom y={bot:.0f} (want >= {span_bottom}): "
                    f"scene floats above the caption band")

    # ---- figure size & faces -------------------------------------------------
    figs = {}
    for it in visible:
        if it.figure is not None and it.wbbox:
            k = id(it.figure)
            cur = figs.get(k)
            figs[k] = it.wbbox if cur is None else (
                min(cur[0], it.wbbox[0]), min(cur[1], it.wbbox[1]),
                max(cur[2], it.wbbox[2]), max(cur[3], it.wbbox[3]))
    if figs:
        # the rule gates the page's MAIN figure (the tallest); secondary
        # background characters may legitimately be smaller
        tallest = max(b[3] - b[1] for b in figs.values())
        if tallest < min_fig_h:
            sev = "MED" if (is_activity or is_vignette) else "HIGH"
            add(sev, "figure_size",
                f"largest figure spans {tallest:.0f}px tall (min {min_fig_h}) "
                f"— place the subject larger with G(x, y, kid, s)")
    for fx, fy, fr, _own, _fidx in _faces(visible):
        if fr < min_face_r:
            add("MED", "figure_size",
                f"face r={fr:.0f} below {min_face_r} — trait features crowd")

    # ---- caption / title bands ------------------------------------------------
    for it in visible:
        if it.chrome or it.tag == "text" or not it.wbbox:
            continue
        if it.wbbox[3] > caption_y:
            add("HIGH", "caption_band",
                f"{it.tag} bottom reaches y={it.wbbox[3]:.0f} into the caption "
                f"band (> {caption_y})")
        if it.wbbox[1] < title_y and it.el.get("data-sky") != "1":
            add("MED", "title_band",
                f"{it.tag} top at y={it.wbbox[1]:.0f} intrudes into the title "
                f"zone (< {title_y})")

    # ---- text fit ---------------------------------------------------------------
    for it in visible:
        if it.tag != "text":
            continue
        el = it.el
        txt = "".join(el.itertext())
        if not txt.strip():
            continue
        size = float(el.get("font-size") or 40)
        weight = el.get("font-weight") or "normal"
        factor = TEXT_W_BOLD if weight == "bold" else TEXT_W_REGULAR
        est = len(txt) * factor * size
        ax = float(el.get("x"))
        anchor = el.get("text-anchor") or "start"
        if anchor == "middle":
            left, right = ax - est / 2, ax + est / 2
        elif anchor == "end":
            left, right = ax - est, ax
        else:
            left, right = ax, ax + est
        if left < inner_border[0] or right > inner_border[2]:
            add("HIGH", "text_fit",
                f"text '{txt[:26]}' est {est:.0f}px wide overflows the page "
                f"(spans {left:.0f}..{right:.0f}, limit "
                f"{inner_border[0]}..{inner_border[2]})")
        y = float(el.get("y"))
        if not it.chrome and (y > H - BORDER_INSET or y < BORDER_INSET + 20):
            add("MED", "text_fit", f"text baseline y={y:.0f} outside safe area")

    # ---- head clearance ----------------------------------------------------------
    # Two real failure modes, checked separately:
    #   (a) a small foreign element FULLY inside the kill disk gets silently
    #       covered when the white-filled head draws last (the documented
    #       raised-hand/gift-prop bug);
    #   (b) anything drawn AFTER the face that reaches the face circle itself
    #       paints over facial features.
    # Large shapes merely PASSING behind a head (fences, furniture, rugs) are
    # normal depth layering and must not fire.
    for fx, fy, fr, owner, fidx in _faces(visible):
        kill_r = fr * HEAD_KILL
        for it in visible:
            if it.chrome or it.el.get("data-sky") == "1" or not it.wbbox:
                continue
            if it.figure is owner:
                continue     # own hair/glasses legitimately live there
            if it.el.get("data-face"):
                continue
            bb = it.wbbox
            corners = [(bb[0], bb[1]), (bb[2], bb[1]),
                       (bb[0], bb[3]), (bb[2], bb[3])]
            fully_in = all(math.hypot(px - fx, py - fy) <= kill_r
                           for px, py in corners)
            small = max(bb[2] - bb[0], bb[3] - bb[1]) <= 1.6 * kill_r
            if fully_in and small:
                add("HIGH", "head_clearance",
                    f"{it.tag} at {[round(v) for v in bb]} sits fully inside "
                    f"face ({fx:.0f},{fy:.0f}) kill radius — the white head "
                    f"drawn LAST will erase it")
                continue
            if it.idx > fidx:   # drawn after the face: MIGHT paint over features
                near = math.hypot(
                    min(max(fx, bb[0]), bb[2]) - fx,
                    min(max(fy, bb[1]), bb[3]) - fy) <= fr
                if near:
                    add("MED", "head_clearance",
                        f"{it.tag} at {[round(v) for v in bb]} draws AFTER "
                        f"face ({fx:.0f},{fy:.0f}) and reaches it — verify on "
                        f"tile crops that facial features stay readable")

    # ---- hands overlap arm/rope ends ----------------------------------------------
    endpoints, path_pts = _line_endpoints(visible)
    # white-filled closed shapes: a line end hidden INSIDE one is attached to
    # that object (e.g. arms ending behind a held teddy's body), not floating.
    # Chrome/page-background shapes excluded (they contain everything).
    solid_boxes = [
        it.wbbox for it in visible
        if it.wbbox and not it.chrome and it.el.get("fill") == "white"
        and it.tag in ("circle", "ellipse", "rect", "path", "polygon")
        and (it.wbbox[2] - it.wbbox[0]) < W * 0.5
        and (it.wbbox[3] - it.wbbox[1]) < H * 0.5]
    for hx, hy, hr, hfig in _hands(visible):
        overlapped = False
        for (px, py), src in endpoints:
            d = math.hypot(px - hx, py - hy)
            if d <= hr * 0.95:
                overlapped = True
                continue
            if hr * 1.05 < d <= hr * 3.0 and src.figure is hfig:
                inside_solid = any(bb[0] - 1 <= px <= bb[2] + 1
                                   and bb[1] - 1 <= py <= bb[3] + 1
                                   for bb in solid_boxes)
                if not inside_solid:
                    add("MED", "hand_arm",
                        f"line end stops {d - hr:.0f}px short of hand circle "
                        f"({hx:.0f},{hy:.0f}) — reads as a floating bubble")
        if not overlapped:
            # closed limb outlines reach the wrist mid-path — scan their
            # coordinates, not just endpoints
            for pts, src in path_pts:
                if any(math.hypot(px - hx, py - hy) <= hr * 0.95
                       for px, py in pts):
                    overlapped = True
                    break
        if not overlapped:
            add("LOW", "hand_arm",
                f"hand circle ({hx:.0f},{hy:.0f}) overlaps no line end — "
                f"prop/leash may be detached")

    # ---- ground tangency ------------------------------------------------------------
    for it in visible:
        gy = it.el.get("data-ground")
        if gy is None:
            continue
        try:
            cx, cy, r = (float(it.el.get(k)) for k in ("cx", "cy", "r"))
            err = abs((cy + r) - float(gy))
        except (TypeError, ValueError):
            continue
        if err > GROUND_TOL:
            sev = "HIGH" if err > 6 else "MED"
            add(sev, "ground_tangency",
                f"wheel at x={cx:.0f} floats/sinks {err:.0f}px off ground y={gy}")

    # ---- parallel-line slivers --------------------------------------------------------
    lines = []
    for it in visible:
        if it.tag != "line" or it.chrome or not it.wbbox:
            continue
        try:
            p1 = _apply(it.m, float(it.el.get("x1")), float(it.el.get("y1")))
            p2 = _apply(it.m, float(it.el.get("x2")), float(it.el.get("y2")))
        except (TypeError, ValueError):
            continue
        lines.append((p1, p2, it))
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            (a1, a2, ea), (b1, b2, eb) = lines[i], lines[j]
            if ea.figure is not None and ea.figure is eb.figure:
                continue  # intentional detail pairs within one figure
            va = (a2[0] - a1[0], a2[1] - a1[1])
            vb = (b2[0] - b1[0], b2[1] - b1[1])
            na, nb = math.hypot(*va), math.hypot(*vb)
            if na < 8 or nb < 8:
                continue
            ang = abs(math.degrees(math.asin(
                min(1.0, abs(va[0] * vb[1] - va[1] * vb[0]) / (na * nb)))))
            if ang > 10:
                continue
            ux, uy = va[0] / na, va[1] / na
            nx_, ny_ = -uy, ux
            d = abs((b1[0] - a1[0]) * nx_ + (b1[1] - a1[1]) * ny_)
            if d > SLIVER_GAP or d < 0.5:
                continue
            ta = sorted((0.0,
                         (b1[0] - a1[0]) * ux + (b1[1] - a1[1]) * uy,
                         (b2[0] - a1[0]) * ux + (b2[1] - a1[1]) * uy))
            overlap = min(ta[2], na) - max(ta[1], 0)
            if overlap < max(24, 0.4 * min(na, nb)):
                continue
            add("LOW", "sliver_gap",
                f"near-parallel lines {d:.1f}px apart over {overlap:.0f}px — "
                f"under the {SLIVER_GAP:.0f}px colorable-gap floor")

    # ---- mat swallow ---------------------------------------------------------
    # A mat's inflated extent fully covering an earlier element is only a BUG
    # when the halo alone did the killing: if the earlier element does not
    # intersect the mat's actual art (its un-inflated boxes), it was erased by
    # white padding — never hidden behind foreground shapes. Elements under the
    # art itself are legitimately occluded background (correct depth order).
    earlier = []  # world bboxes of visible art drawn before each mat
    mat_ids = {id(mt.node): mt for mt in mats}
    seen_msgs = set()
    seq = []

    def order(node, in_mat):
        tag = node.tag.replace(_SVG_NS, "")
        if tag == "svg":
            for ch in node:
                order(ch, in_mat)
        elif tag == "g":
            im = in_mat or (node.get("data-mat") == "1")
            if im and not in_mat:
                seq.append(("mat", node))
            for ch in node:
                order(ch, im)
        elif tag in _SHAPE_TAGS:
            seq.append(("el", node, in_mat))

    order(root, False)
    bbmap = {}
    for it in visible:
        if it.wbbox:
            bbmap[id(it.el)] = it.wbbox
    for ev in seq:
        if ev[0] == "el":
            if not ev[2]:
                bb = bbmap.get(id(ev[1]))
                if bb is not None:
                    earlier.append(bb)
        else:
            mt = mat_ids.get(id(ev[1]))
            if mt is None or not mt.boxes:
                continue
            # data-pad is the LOCAL pad (page-pad / placement scale); recover
            # the on-page visual halo width from the mat's matrix
            det = abs(mt.m[0] * mt.m[3] - mt.m[1] * mt.m[2])
            mscale = math.sqrt(det) if det else 1.0
            xs0 = min(b[0] for b in mt.boxes)
            ys0 = min(b[1] for b in mt.boxes)
            xs1 = max(b[2] for b in mt.boxes)
            ys1 = max(b[3] for b in mt.boxes)
            art = (xs0, ys0, xs1, ys1)
            ext = _inflate(art, mt.pad * mscale / 2 + 1)
            # per-shape halo coverage: the mat whites out only near ACTUAL
            # shapes, not the corners of their union bbox — so the element
            # must be covered by individual shape-boxes inflated by the halo
            halo_boxes = [_inflate(b, mt.pad * mscale / 2 + 1) for b in mt.boxes]

            def _covered(pt):
                return any(r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]
                           for r in halo_boxes)

            for bb in earlier:
                if not _contains(ext, bb, tol=0.5):
                    continue
                x0_, y0_, x1_, y1_ = bb
                samples = [(x0_, y0_), (x1_, y0_), (x0_, y1_), (x1_, y1_),
                           ((x0_+x1_)/2, y0_), ((x0_+x1_)/2, y1_),
                           (x0_, (y0_+y1_)/2), (x1_, (y0_+y1_)/2),
                           ((x0_+x1_)/2, (y0_+y1_)/2)]
                if not all(_covered(p) for p in samples):
                    continue
                cx_, cy_ = (x0_ + x1_) / 2, (y0_ + y1_) / 2
                center_under_art = any(a[0] <= cx_ <= a[2] and a[1] <= cy_ <= a[3]
                                       for a in mt.boxes)
                if not center_under_art:
                    msg = (f"knockout-mat HALO fully erases an earlier element "
                           f"at {[round(v) for v in bb]} — draw the cluster as "
                           f"ONE matted() group or add ~2x-pad clearance")
                    if msg not in seen_msgs:
                        seen_msgs.add(msg)
                        add("HIGH", "mat_swallow", msg)

    # ---- float noise lint ------------------------------------------------------------------
    for m_ in re.finditer(r'([a-zA-Z-]+)="(-?\d+\.\d{3,})"', svg_str):
        add("LOW", "float_noise",
            f"attribute {m_.group(1)}='{m_.group(2)}' has excess decimals")
    # relative path commands make bbox pairing approximate — charlib emits
    # absolute geometry only; flag stragglers so bboxes stay trustworthy
    for el_ in root.iter():
        d_ = el_.get("d") if hasattr(el_, "get") else None
        if d_ and re.search(r"[a-z]", re.sub(r"[^a-zA-Z]", "", d_)):
            add("LOW", "relative_path",
                "path uses relative commands — bbox approximate; charlib "
                "convention is absolute commands only")

    counts = {"HIGH": 0, "MED": 0, "LOW": 0}
    for f_ in findings:
        counts[f_["severity"]] += 1
    return {"ok": counts["HIGH"] == 0, "findings": findings, "counts": counts}


# ------------------------------------------------------------------ file/book API
def validate_file(path, **kw):
    with open(path, encoding="utf-8") as fh:
        return validate_svg(fh.read(), **kw)


def full_qa(svg_path, **kw):
    """Deterministic layout validation + raster colorability/print QA."""
    rep = validate_file(svg_path, **kw)
    try:
        try:
            from charlib import qa_page
        except ImportError:
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from charlib import qa_page
        rep["raster"] = qa_page(svg_path)
    except Exception as exc:  # raster stack optional
        rep["raster"] = {"error": str(exc)}
    return rep


def lint_book(page_svgs, density_mean_tol=6):
    """Cross-page coherence checks over a list of serialized page SVGs:
    duplicate pages, density pacing (no 3+ consecutive busy pages)."""
    findings = []
    seen = {}

    def complexity(svg):
        return len(re.findall(
            rf"<(?:{'|'.join(_SHAPE_TAGS)})[\s>]", svg))

    normalized = [re.sub(r"\s+", " ", s_) for s_ in page_svgs]
    for i, s_ in enumerate(normalized):
        if s_ in seen:
            findings.append({"severity": "HIGH", "check": "duplicate_page",
                             "msg": f"page {i + 1} duplicates page {seen[s_] + 1}"})
        else:
            seen[s_] = i

    counts = [complexity(s_) for s_ in normalized]
    mean = sum(counts) / len(counts) if counts else 0.0
    run = 0
    for i, c in enumerate(counts):
        busy = c > mean + density_mean_tol
        run = run + 1 if busy else 0
        if run >= 3:
            findings.append({
                "severity": "MED", "check": "density_pacing",
                "msg": f"pages {i - 1}-{i + 1}: 3+ consecutive busy pages "
                       f"(elements {counts[max(0, i - 2):i + 1]}, "
                       f"book mean {mean:.0f})"})
            run = 0
    return {"ok": not any(f_["severity"] == "HIGH" for f_ in findings),
            "findings": findings, "element_counts": counts}


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        sys.exit(2)
    bad = 0
    for pth in paths:
        rep = validate_file(pth)
        print(f"== {pth}: {'OK' if rep['ok'] else 'FAIL'} {rep['counts']}")
        for f_ in rep["findings"]:
            print(f"   [{f_['severity']}] {f_['check']}: {f_['msg']}")
        bad += rep["counts"]["HIGH"]
    sys.exit(1 if bad else 0)
