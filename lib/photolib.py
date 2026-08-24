"""photolib — turn photographs into coloring-book-compatible outlines.

The splintering problem (raw edge maps shatter into fragments, doubled
edges, and texture splatter) is attacked in layers:

  1. edge-preserving pre-filter (bilateral) kills sensor noise
  2. style="clean": adaptive-threshold ink  |  style="sketch": flow-based
     XDoG (DoG along an edge-tangent field — strokes FOLLOW the subject
     instead of pixel gradients)
  3. morphological close bridges small gaps; open + component filter
     deletes specks and short fragments
  4. vectorize: contours -> RDP simplify -> optional H/V angle snap
     (segments within SNAP_DEG of horizontal/vertical are squared up —
     cars/houses read crisp) -> charlib smooth_path averaging for organic
     runs -> two-tier strokes with WHITE-FILL layering (big shapes first,
     knock out what's behind — same doctrine as charlib helpers)
  5. closed QA loop: validate_svg + qa_page on the OUTPUT; sliver/region
     counts nudge the soft-rule parameters (<= 3 rounds); final params are
     written into the page as data-policy for reproducibility

Subject understanding is a soft-rule fallback chain (all local):
  Haar frontal face (ships with OpenCV) -> GrabCut around a center rect
  -> center-prior saliency -> whole-image. The label picks a POLICY:
  per-class parameters (thresholds, simplify epsilon, angle snapping,
  protected regions) that bias — never hard-gate — the trace.

All processing is local; every stage is deterministic (fixed iteration
counts, no randomness). Photos of real people stay on disk: the pipeline
extracts LINE ART only, never likeness shading.

CLI:
    python -m lib.photolib photo.jpg -o page.svg [--style sketch]
        [--detail medium] [--fragment out_fragment.svg]
"""
import math
import os
import re
import sys
import tempfile

import cv2
import numpy as np

try:
    from charlib import P, G, spage, smooth_path, matted, _f, W, H
except ImportError:  # `python -m lib.photolib` — put lib/ on the path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from charlib import P, G, spage, smooth_path, matted, _f, W, H

# ---------------------------------------------------------------- constants
ART_BAND = (60, 170, 790, 990)     # x0, y0, x1, y1 — where the trace lives
SNAP_DEG = 7.0                     # segments within this of H/V get squared
CORNER_DEG = 24.0                  # turns sharper than this are corners
MIN_STROKE_LEN = 26.0              # image-px: shorter fragments are splinters
MIN_COMPONENT = 20                 # ink component area below = speck
QA_MAX_ROUNDS = 3

# soft-rule policies per subject label; QA may adjust within bounds
POLICIES = {
    "face":     dict(edge_c=13, block=25, simplify=1.4, snap_hv=False,
                     protect_face=True, max_strokes=300),
    "person":   dict(edge_c=12, block=27, simplify=1.7, snap_hv=False,
                     protect_face=True, max_strokes=280),
    "vehicle":  dict(edge_c=12, block=29, simplify=2.0, snap_hv=True,
                     protect_face=False, max_strokes=200),
    "building": dict(edge_c=13, block=31, simplify=2.2, snap_hv=True,
                     protect_face=False, max_strokes=180),
    "animal":   dict(edge_c=11, block=27, simplify=1.8, snap_hv=False,
                     protect_face=True, max_strokes=240),
    "plant":    dict(edge_c=10, block=29, simplify=2.0, snap_hv=False,
                     protect_face=False, max_strokes=200),
    "generic":  dict(edge_c=11, block=29, simplify=1.8, snap_hv=False,
                     protect_face=False, max_strokes=240),
}
DETAIL_MULT = {"low": 1.7, "medium": 1.0, "high": 0.65}


# ---------------------------------------------------------------- ingestion
def load_photo(path, max_dim=1600):
    """EXIF-rotate, load, downscale, return (gray uint8, BGR)."""
    from PIL import Image, ImageOps
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > max_dim:
        s = max_dim / max(w, h)
        im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return gray, bgr


# ---------------------------------------------------------------- subject detection
_YUNET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                      "assets", "models", "face_detection_yunet_2023mar.onnx")


def _detect_faces(gray, bgr=None):
    """YuNet face detection (Apache-2.0 model bundled in assets/models).
    Returns [x, y, w, h] list. OpenCV 5 removed Haar cascades; YuNet is the
    supported detector and runs fully local."""
    if not os.path.exists(_YUNET):
        return []
    bgr = bgr if bgr is not None else cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    h, w = bgr.shape[:2]
    try:
        det = cv2.FaceDetectorYN.create(_YUNET, "", (w, h),
                                        score_threshold=0.55)
        det.setInputSize((w, h))
        _ret, faces = det.detect(bgr)
    except cv2.error:
        return []
    out = []
    if faces is not None:
        for f in faces:
            x, y, fw, fh = f[0], f[1], f[2], f[3]
            if fw >= w / 16:
                out.append((int(x), int(y), int(fw), int(fh)))
    return out


def detect_subject(gray, bgr=None):
    """Soft-rule fallback chain, all local. Returns
    (subject_mask or None, label, meta dict)."""
    h, w = gray.shape
    meta = {}

    # 1) YuNet face detection (bundled Apache-2.0 model)
    faces = _detect_faces(gray, bgr)
    if len(faces):
        meta["faces"] = faces
        x0 = max(0, min(f[0] for f in faces) - w // 12)
        y0 = max(0, min(f[1] for f in faces) - h // 12)
        x1 = min(w, max(f[0] + f[2] for f in faces) + w // 12)
        y1 = min(h, max(f[1] + f[3] for f in faces) + int(h * 0.35))
        mask = _grabcut(gray, (x0, y0, x1 - x0, y1 - y0))
        return mask, ("face" if _big_single_face(faces, w, h) else "person"), meta

    # 2) GrabCut around a center rect (subject usually near center)
    rect = (int(w * 0.14), int(h * 0.10), int(w * 0.72), int(h * 0.80))
    mask = _grabcut(gray, rect)
    if mask is not None and 0.04 < mask.mean() / 255 < 0.92:
        return mask, _heuristic_label(gray, mask, meta), meta

    # 3) center-prior saliency on gradient magnitude
    grad = cv2.Sobel(cv2.GaussianBlur(gray, (5, 5), 0), cv2.CV_32F, 1, 1)
    mag = np.linalg.norm(grad, axis=0) if grad.ndim == 3 else np.abs(grad)
    mag = mag / (mag.max() + 1e-6)
    yy, xx = np.mgrid[0:h, 0:w]
    prior = np.exp(-(((xx / w - 0.5) ** 2) + ((yy / h - 0.5) ** 2)) * 4.0)
    sal = (mag * 0.6 + prior * 0.4)
    m = (sal > np.percentile(sal, 72)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    meta["detector"] = "saliency"
    return m, _heuristic_label(gray, m, meta), meta


def _big_single_face(faces, w, h):
    return len(faces) == 1 and faces[0][2] > w * 0.12


def _grabcut(gray, rect):
    """GrabCut with a center rect seed; None on failure/empty."""
    try:
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        mask = np.zeros(gray.shape, np.uint8)
        cv2.grabCut(img, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
        m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
                     255, 0).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        if m.mean() < 1 or m.mean() > 250:
            return None
        return m
    except cv2.error:
        return None


def _heuristic_label(gray, mask, meta):
    """Soft heuristics: line density -> building; roundness -> generic."""
    edges = cv2.Canny(gray, 80, 160)
    density = float(edges.mean()) / 255.0
    meta["edge_density"] = round(density, 3)
    if density > 0.16:
        return "building"
    return "generic"


# ---------------------------------------------------------------- ink extraction
def extract_ink(gray, style="clean", policy=None, subject_mask=None,
                detail="medium"):
    """Binary ink mask (255 = line) from a grayscale photo."""
    policy = policy or POLICIES["generic"]
    mult = DETAIL_MULT.get(detail, 1.0)
    smooth = cv2.bilateralFilter(gray, 7, 45, 45)

    if style == "sketch":
        ink = _flow_dog(smooth, policy)
    else:
        block = max(9, int(policy["block"] * mult) // 2 * 2 + 1)
        c = max(3.0, policy["edge_c"] * mult)
        ink = cv2.adaptiveThreshold(smooth, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, block, c)
        # dual scale: a wide-block pass catches low-contrast boundaries the
        # fine pass misses (union, then the desplinter stage cleans up)
        wblock = block * 3 + (1 if (block * 3) % 2 == 0 else 0)
        ink2 = cv2.adaptiveThreshold(smooth, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, wblock,
                                     max(2.0, c * 0.6))
        ink = cv2.bitwise_or(ink, ink2)
        # soften flat-area noise via Otsu ceiling — but never clear more than
        # 55% of the ink (guard against killing whole subjects on dark photos)
        otsu, _ = cv2.threshold(smooth, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ceiling = (smooth > otsu + 55)
        if ceiling.mean() < 0.55:
            ink[ceiling] = 0

    ink = _desplinter(ink, mult)
    if subject_mask is not None:
        ink = _focus_subject(ink, subject_mask, mult)
    return ink


def _desplinter(ink, mult):
    """Morphological anti-splinter: bridge gaps, delete specks/short runs."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, k, iterations=2)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, k)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    keep = np.zeros_like(ink)
    min_area = MIN_COMPONENT * (1.5 if mult > 1.2 else 1.0)
    for i in range(1, n):
        x, y, w_, h_, area = stats[i]
        if area >= min_area and max(w_, h_) >= 5:
            keep[labels == i] = 255
    return keep


def _focus_subject(ink, subject_mask, mult):
    """Soft rule: background ink thinned (thicker threshold), subject kept —
    implemented as extra erosion of ink OUTSIDE the subject mask."""
    bg = cv2.bitwise_and(ink, cv2.bitwise_not(subject_mask))
    bg = cv2.erode(bg, np.ones((2, 2), np.uint8), iterations=1)
    fg = cv2.bitwise_and(ink, subject_mask)
    return cv2.bitwise_or(fg, bg)


def _flow_dog(gray, policy, sigma=1.4, tau=1.0, iters=2,
              offsets=(-4, -2, 0, 2, 4)):
    """Simplified coherent-line-drawing. DoG ridge = wider-Gaussian minus
    narrower (positive at dark-line centres on light surround); summed along
    an edge-tangent-flow field so strokes FOLLOW the subject instead of
    fragmenting on pixel noise. Deterministic (fixed iterations)."""
    g1 = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), sigma)
    g2 = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), sigma * 1.6)
    dog = g2 - tau * g1                      # +ridge on dark/light boundaries

    # edge tangent flow from the structure tensor
    gx = cv2.Sobel(g1, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g1, cv2.CV_32F, 0, 1, ksize=3)
    tx, ty = -gy, gx
    norm = np.sqrt(tx * tx + ty * ty) + 1e-6
    tx, ty = tx / norm, ty / norm
    for _ in range(iters):  # smooth the tangent field along itself
        map_x = (np.arange(gray.shape[1])[None, :] + tx * 2.0).astype(np.float32)
        map_y = (np.arange(gray.shape[0])[:, None] + ty * 2.0).astype(np.float32)
        tx2 = cv2.remap(tx, map_x, map_y, cv2.INTER_LINEAR)
        ty2 = cv2.remap(ty, map_x, map_y, cv2.INTER_LINEAR)
        keep = (tx * tx2 + ty * ty2) >= 0
        tx = np.where(keep, tx2, -tx2)
        ty = np.where(keep, ty2, -ty2)

    def _sample(src, dx, dy):
        mx = (np.arange(gray.shape[1])[None, :] + dx).astype(np.float32)
        my = (np.arange(gray.shape[0])[:, None] + dy).astype(np.float32)
        return cv2.remap(src, mx, my, cv2.INTER_LINEAR)

    center = np.zeros_like(dog)
    for off in offsets:                       # average ALONG the tangent
        center += _sample(dog, tx * off, ty * off)
    center /= len(offsets)

    surround = np.zeros_like(dog)
    for off in offsets:                       # suppress perpendicular surround
        for perp in (-2.5, 2.5):
            surround += _sample(dog, tx * off - ty * perp, ty * off + tx * perp)
    surround /= len(offsets) * 2

    # adaptive ridge threshold: soft/blurry photos have weak ridges, crisp
    # ones strong — scale with the image's own ridge distribution
    pos = center[center > 0]
    thr = max(1.0, float(np.percentile(pos, 88)) * 1.15) if pos.size else 9e9
    line = np.where((center > thr) & (center > 1.25 * surround + 0.3),
                    255, 0).astype(np.uint8)
    line = cv2.morphologyEx(line, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return line


# ---------------------------------------------------------------- vectorization
def _smooth_contour(cnt, k=7):
    """Circular moving average over contour points — the 'solid line
    averaging' pass: removes pixel-scale wobble before simplification."""
    n = len(cnt)
    if n < k + 2:
        return cnt
    pts = cnt.reshape(-1, 2).astype(np.float32)
    pad = np.vstack([pts[-k:], pts, pts[:k]])
    kernel = np.ones(k, np.float32) / k
    sm = np.vstack([np.convolve(pad[:, 0], kernel, "valid"),
                    np.convolve(pad[:, 1], kernel, "valid")]).T
    return sm.reshape(-1, 1, 2).astype(np.int32)


def _snap_polyline(pts, snap_deg=SNAP_DEG):
    """Angle detection: square up near-horizontal/vertical segments."""
    pts = [list(p) for p in pts]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        dx, dy = x1 - x0, y1 - y0
        ang = abs(math.degrees(math.atan2(dy, dx))) % 180
        if min(ang, 180 - ang) <= snap_deg:          # near-horizontal
            avg = (y0 + y1) / 2
            pts[i][1] = pts[i + 1][1] = avg
        elif abs(ang - 90) <= snap_deg:               # near-vertical
            avg = (x0 + x1) / 2
            pts[i][0] = pts[i + 1][0] = avg
    return [(p[0], p[1]) for p in pts]


def _page_fit(iw, ih):
    """Fit transform image px -> art-band page px (aspect preserved)."""
    bx0, by0, bx1, by1 = ART_BAND
    s = min((bx1 - bx0) / iw, (by1 - by0) / ih)
    ox = bx0 + ((bx1 - bx0) - iw * s) / 2
    oy = by0 + ((by1 - by0) - ih * s) / 2
    return s, ox, oy


def vectorize(ink, policy=None, detail="medium", subject_mask=None):
    """Ink mask -> ordered list of SVG path elements in PAGE coordinates.

    White-fill layering: big closed shapes first (fill white — knocks out
    what's behind, same doctrine as charlib), thin strokes after (fill none).
    """
    policy = policy or POLICIES["generic"]
    mult = DETAIL_MULT.get(detail, 1.0)
    ih, iw = ink.shape
    s, ox, oy = _page_fit(iw, ih)
    eps = max(1.0, policy["simplify"] * mult)
    max_strokes = policy["max_strokes"]

    contours, hier = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    entries = []
    areas_by_idx = {i: cv2.contourArea(c) for i, c in enumerate(contours)}
    for i, cnt in enumerate(contours):
        # anti-double-line: a thick stroke traces as outer contour + inner
        # hole; skip holes that just shadow their parent (keep genuine large
        # openings like a window hole in a filled silhouette)
        parent = hier[0][i][3] if hier is not None else -1
        if parent != -1:
            pa = areas_by_idx.get(parent, 0)
            if pa <= 0 or areas_by_idx[i] > 0.25 * pa:
                continue
        perim = cv2.arcLength(cnt, True)
        if perim < MIN_STROKE_LEN:
            continue                                   # splinter fragment
        area = cv2.contourArea(cnt)
        if area < 16:
            continue
        thickness = 2.0 * area / (perim + 1e-6)
        approx = cv2.approxPolyDP(_smooth_contour(cnt, k=7), eps, True)
        pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
        if len(pts) < 3:
            continue
        if policy["snap_hv"]:
            pts = _snap_polyline(pts + [pts[0]])[:-1]
        cx, cy = float(cnt[:, 0, 0].mean()), float(cnt[:, 0, 1].mean())
        in_subject = 1.0
        if subject_mask is not None:
            sx, sy = int(min(iw - 1, cx)), int(min(ih - 1, cy))
            in_subject = 1.0 if subject_mask[sy, sx] else 0.0
        entries.append(dict(pts=pts, area=area, perim=perim,
                            thickness=thickness, subj=in_subject, cx=cx, cy=cy))

    # keep the richest strokes, drop the tail (soft max_strokes rule)
    entries.sort(key=lambda e: -(e["area"] * math.log1p(e["perim"])))
    entries = entries[:max_strokes]

    shapes = sorted((e for e in entries if e["thickness"] >= 5.5),
                    key=lambda e: -e["area"])
    strokes = [e for e in entries if e["thickness"] < 5.5]

    def to_page(pts):
        return [((x * s + ox), (y * s + oy)) for x, y in pts]

    out = []
    for j, e in enumerate(shapes):
        # ONLY the largest silhouette gets a white fill (knockout for
        # compositing); filling every thick blob erased interior detail
        pp = to_page(e["pts"])
        sw = 4.6 if e["subj"] else 3.4
        fill = "white" if j == 0 else "none"
        if policy["snap_hv"]:
            d = "M " + " L ".join(f"{_f(a)} {_f(b)}" for a, b in pp) + " Z"
            out.append(P(d, sw, fill))
        else:
            out.append(smooth_path(pp, sw=sw, closed=True, fill=fill))
    for e in strokes:                                   # detail strokes
        pp = to_page(e["pts"])
        sw = 3.6 if e["subj"] else 2.6
        if policy["snap_hv"]:
            d = "M " + " L ".join(f"{_f(a)} {_f(b)}" for a, b in pp)
            out.append(P(d, sw))
        else:
            out.append(smooth_path(pp, sw=sw))
    return out


# ---------------------------------------------------------------- QA loop
def _qa_report(svg_str):
    """validate_svg + qa_page (via a temp file for the raster stage)."""
    import validate
    rep = validate.validate_svg(svg_str, require_span=False)
    rep["raster"] = None
    try:
        from charlib import qa_page
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
            fh.write(svg_str)
            tmp = fh.name
        try:
            rep["raster"] = qa_page(tmp)
        finally:
            os.unlink(tmp)
    except Exception:
        pass
    return rep


def _qa_adjust(policy, params, rep):
    """Soft-rule controller: nudge thresholds from QA findings."""
    r = rep.get("raster") or {}
    slivers = r.get("sliver_count", 0)
    changed = False
    if slivers > 70 and params["edge_c"] < 20:
        params["edge_c"] += 2
        params["simplify"] *= 1.15
        changed = True
    if rep["counts"]["LOW"] > 40 and params["edge_c"] < 20:
        params["edge_c"] += 1
        changed = True
    if r.get("regions", 0) and r.get("regions") < 25 and params["edge_c"] > 6:
        params["edge_c"] -= 2
        params["simplify"] *= 0.9
        changed = True
    if rep["counts"]["HIGH"] and params["simplify"] < 6.0:
        params["simplify"] *= 1.25
        changed = True
    return changed


def _assemble(elements, title, caption, policy_name, params, layout=None):
    meta = (f'<g data-policy="{policy_name}" '
            f'data-params="edge_c={params["edge_c"]:.0f};simplify={params["simplify"]:.1f}">'
            + "".join(elements) + "</g>")
    return spage(title, meta, caption=caption, layout=layout)


def spage_wrap(elements, title, caption, policy_name, params, layout=None):
    return _assemble(elements, title, caption, policy_name, params, layout)


# ---------------------------------------------------------------- public API
def photo_to_svg(photo_path, *, style="clean", subject="auto", detail="medium",
                 title=None, caption=None, max_dim=1600, qa=True,
                 layout=None):
    """Photo file -> standalone coloring page SVG string. layout="creative"
    marks open-composition pages (e.g. sketch traces) for the validator."""
    elements, label, params, _ink = _trace(
        photo_path, style, subject, detail, max_dim)
    if qa:
        for _ in range(QA_MAX_ROUNDS):
            svg = _assemble(elements, title, caption, label, params, layout)
            rep = _qa_report(svg)
            if rep["ok"] and (rep["raster"] is None
                              or rep["raster"]["sliver_count"] <= 70):
                break
            if not _qa_adjust(POLICIES[label], params, rep):
                break
            elements, label2, params, _ink = _trace(
                photo_path, style, subject, detail, max_dim, overrides=params)
            label = label2
    return spage_wrap(elements, title, caption, label, params, layout)


def photo_to_fragment(photo_path, *, style="clean", subject="auto",
                      detail="medium", max_dim=1600, pad=20):
    """Photo -> G()-placeable charlib fragment. Local origin = the traced
    ink's BOTTOM-CENTRE (same feet-anchor convention as every charlib
    helper): G(x, ground_y, fragment, s) stands the subject on a ground
    line. Reusable like any library asset."""
    elements, _label, _params, ink = _trace(photo_path, style, subject,
                                            detail, max_dim)
    ih, iw = ink.shape
    s, ox, oy = _page_fit(iw, ih)
    # anchor on the component that TOUCHES the lowest ink pixel — whatever
    # reaches lowest is what "stands" (largest-area can be background texture)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    if n > 1:
        ys_all, xs_all = np.nonzero(ink)
        low_label = int(labels[ys_all.max(), xs_all[ys_all.argmax()]])
        bx, by, bw, bh = (stats[low_label, 0], stats[low_label, 1],
                          stats[low_label, 2], stats[low_label, 3])
        bcx = ox + (bx + bw / 2) * s
        bcy = oy + (by + bh) * s
    else:
        bcx, bcy = (ART_BAND[0] + ART_BAND[2]) / 2, (ART_BAND[1] + ART_BAND[3]) / 2
    return (f'<g data-el="photo-trace" '
            f'transform="translate({_f(-bcx)},{_f(-bcy)})">'
            + "".join(elements) + "</g>")


def composite_page(photo_path, scene_body, ground_y, *, x=425, scale=1.0,
                   style="clean", detail="medium", title="My Photo Page",
                   caption=None, num=None):
    """Traced photo subject matted onto a scene kit body beside charlib
    art. The fragment self-anchors at its ink bottom-centre, so it stands
    ON ground_y at (x, ground_y) like any charlib figure."""
    frag = photo_to_fragment(photo_path, style=style, detail=detail)
    body = scene_body + G(x, ground_y, matted(frag, scale=scale), scale)
    return spage(title, body, caption=caption, num=num)


def _trace(photo_path, style, subject, detail, max_dim, overrides=None):
    gray, bgr = load_photo(photo_path, max_dim)
    mask, label, _meta = (detect_subject(gray, bgr) if subject == "auto"
                          else (None,
                                subject if subject in POLICIES else "generic",
                                {}))
    policy = dict(POLICIES.get(label, POLICIES["generic"]))
    if overrides:
        policy.update({k: v for k, v in overrides.items()
                       if k in policy})
    ink = extract_ink(gray, style=style, policy=policy,
                      subject_mask=mask, detail=detail)
    elements = vectorize(ink, policy=policy, detail=detail,
                         subject_mask=mask)
    return elements, label, policy, ink


# ---------------------------------------------------------------- test fixture
def synthetic_photo(kind="animal", size=640):
    """Deterministic photo-like fixture (soft gradients + shapes + grain)
    for tests/showcase — stands in for a real photograph."""
    rng = np.random.default_rng(42)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    base = 135 + 32 * np.sin(xx / size * 2.2) * np.cos(yy / size * 1.7)
    img = np.dstack([base] * 3)
    if kind == "animal":
        cv2.ellipse(img, (size // 2, int(size * 0.58)), (int(size * 0.30),
                    int(size * 0.20)), 0, 0, 360, (70, 60, 55), -1)
        cv2.circle(img, (int(size * 0.72), int(size * 0.42)),
                   int(size * 0.13), (70, 60, 55), -1)
        cv2.ellipse(img, (int(size * 0.60), int(size * 0.30)),
                    (int(size * 0.045), int(size * 0.11)), 25, 0, 360,
                    (70, 60, 55), -1)
        cv2.circle(img, (int(size * 0.76), int(size * 0.40)),
                   int(size * 0.02), (230, 230, 230), -1)
    elif kind == "house":
        pts = np.array([[size * 0.2, size * 0.75], [size * 0.2, size * 0.45],
                        [size * 0.5, size * 0.25], [size * 0.8, size * 0.45],
                        [size * 0.8, size * 0.75]], np.int32)
        cv2.fillPoly(img, [pts], (90, 80, 150))
        cv2.rectangle(img, (int(size * 0.44), int(size * 0.55)),
                      (int(size * 0.56), size * 3 // 4), (60, 50, 40), -1)
    else:  # car
        cv2.rectangle(img, (int(size * 0.15), int(size * 0.5)),
                      (int(size * 0.85), int(size * 0.68)), (50, 60, 140), -1)
        pts = np.array([[size * 0.28, size * 0.5], [size * 0.38, size * 0.36],
                        [size * 0.62, size * 0.36], [size * 0.74, size * 0.5]],
                       np.int32)
        cv2.fillPoly(img, [pts], (50, 60, 140))
        cv2.circle(img, (int(size * 0.30), int(size * 0.68)),
                   int(size * 0.06), (30, 30, 30), -1)
        cv2.circle(img, (int(size * 0.70), int(size * 0.68)),
                   int(size * 0.06), (30, 30, 30), -1)
    # soft shadow + sensor grain
    img = cv2.GaussianBlur(img, (0, 0), 3)
    grain = rng.normal(0, 6, img.shape).astype(np.float32)
    return np.clip(img + grain, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- CLI
def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="photolib")
    ap.add_argument("photo")
    ap.add_argument("-o", "--out", default="photo-page.svg")
    ap.add_argument("--style", choices=("clean", "sketch"), default="clean")
    ap.add_argument("--subject", default="auto")
    ap.add_argument("--detail", choices=("low", "medium", "high"),
                    default="medium")
    ap.add_argument("--title", default=None)
    ap.add_argument("--fragment", default=None,
                    help="also write a G()-placeable fragment SVG body")
    a = ap.parse_args(argv)
    svg = photo_to_svg(a.photo, style=a.style, subject=a.subject,
                       detail=a.detail, title=a.title)
    with open(a.out, "w") as fh:
        fh.write(svg)
    print("wrote", a.out)
    if a.fragment:
        with open(a.fragment, "w") as fh:
            fh.write(photo_to_fragment(a.photo, style=a.style,
                                       detail=a.detail))
        print("wrote", a.fragment)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
