"""photolib — turn photographs into coloring-book-compatible outlines.

The splintering problem (raw edge maps shatter into fragments, doubled
edges, and texture splatter) is attacked in layers:

  1. edge-preserving pre-filter (bilateral) kills sensor noise
  2. style="clean": adaptive-threshold ink  |  style="sketch": flow-based
     XDoG (DoG along an edge-tangent field — strokes FOLLOW the subject
     instead of pixel gradients)
  3. morphological close bridges small gaps; open + component filter
     deletes specks and short fragments
  4. background suppression: for single-subject policies (animal, plant,
     generic) ink outside the DILATED subject mask is dropped outright and
     a ground contact line is drawn under the subject; other policies keep
     the soft rule (background ink thinned, not removed)
  5. vectorize: every ink component is classified as a RIBBON (an edge
     band) or a BLOB (a solid dark patch — eye, nose, window). Ribbons are
     thinned to their CENTRELINE (Zhang-Suen) and walked into polylines, so
     a thick edge band yields ONE stroke instead of both of its sides;
     blobs are outlined. Then RDP simplify -> optional H/V angle snap
     (segments within SNAP_DEG of horizontal/vertical are squared up —
     cars/houses read crisp) -> charlib smooth_path averaging -> two-tier
     strokes (silhouette 4.6 / interior 3.6 / background 2.6) with a
     white-fill knockout on the largest closed silhouette
  6. closed QA loop: validate_svg + qa_page on the OUTPUT; sliver/region
     counts nudge the soft-rule parameters (<= 3 rounds); final params are
     written into the page as data-policy for reproducibility

Subject understanding is a soft-rule fallback chain (all local):
  YuNet face detection (bundled model) -> colour GrabCut seeded by a thin
  border ring (the subject may fill the frame) -> center-prior saliency ->
  whole-image. The label picks a POLICY: per-class parameters (thresholds,
  simplify epsilon, angle snapping, background mode) that bias — never
  hard-gate — the trace.

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
GRABCUT_WORK = 640                 # GrabCut runs on a <=640px copy (fast, deterministic)
GRABCUT_MARGIN = 0.025             # border ring seeded as background (subject may fill the frame)
DROP_MASK_FRAC = (0.05, 0.70)      # subject-area window in which a mask is trusted for bg drop
DROP_BORDER_TOUCH = 0.30           # >30% of the frame border inside the mask = not a single subject
BLOB_ELONGATION = 3.0              # perimeter/(4*inscribed radius) below this = solid blob
BLOB_DARK_RATIO = 0.55             # interior blob kept if darker than 55% of the subject median
BLOB_LARGE_FRAC = 0.02             # ...or if it covers >=2% of the subject area
SPUR_LEN = 12.0                    # skeleton branch ending free, shorter than this = thinning spur
TEXTURE_RATIO = 3.5                # open interior structure longer than 3.5x its extent = texture
WIDE_INTERIOR_C = 1.5              # clean style: wide-block threshold x this INSIDE a dropped subject
BLOB_INK_RATIO = 0.35              # a blob near the silhouette must be this dark (nose) to survive
BLOB_MIN_RADIUS = 0.004            # blob inscribed radius below this x image size = dot, dropped
INTERIOR_FLOOR = 0.03              # drop mode: line structure inside the subject >= 3% of image size
RING_FLOOR = 0.05                  # drop mode: structure on the silhouette ring >= 5% (grass is shorter)
FEET_BAND = 0.08                   # bottom 8% of the subject: ring tightened to the mask (ground clutter)
FEET_RADIUS = 7                    # ...to this many px (keeps the paw outline band, not the grass)
SW_SILHOUETTE, SW_SUBJECT, SW_BACKGROUND = 4.6, 3.6, 2.6
SKETCH_MIN_LENGTH = 400.0          # page px of traced line below which sketch falls back to clean

# soft-rule policies per subject label; QA may adjust within bounds.
# bg="drop": ink outside the dilated subject mask is removed (single-subject
# photos); bg="soft": background ink is thinned but kept (scenes, people,
# buildings — where the mask is a hint, not a silhouette).
POLICIES = {
    "face":     dict(edge_c=13, block=25, simplify=1.4, snap_hv=False,
                     protect_face=True, max_strokes=300, bg="soft"),
    "person":   dict(edge_c=12, block=27, simplify=1.7, snap_hv=False,
                     protect_face=True, max_strokes=280, bg="soft"),
    "vehicle":  dict(edge_c=12, block=29, simplify=2.0, snap_hv=True,
                     protect_face=False, max_strokes=200, bg="soft"),
    "building": dict(edge_c=13, block=31, simplify=2.2, snap_hv=True,
                     protect_face=False, max_strokes=180, bg="soft"),
    "animal":   dict(edge_c=11, block=27, simplify=1.8, snap_hv=False,
                     protect_face=True, max_strokes=240, bg="drop"),
    "plant":    dict(edge_c=10, block=29, simplify=2.0, snap_hv=False,
                     protect_face=False, max_strokes=200, bg="drop"),
    "generic":  dict(edge_c=11, block=29, simplify=1.8, snap_hv=False,
                     protect_face=False, max_strokes=240, bg="drop"),
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
    (subject_mask or None, label, meta dict). meta carries mask_frac and
    border_touch so callers can judge whether the mask is a silhouette
    (single subject, framed) or merely a hint."""
    h, w = gray.shape
    meta = {}
    img = bgr if bgr is not None else gray

    # 1) YuNet face detection (bundled Apache-2.0 model)
    faces = _detect_faces(gray, bgr)
    if len(faces):
        meta["faces"] = faces
        x0 = max(0, min(f[0] for f in faces) - w // 12)
        y0 = max(0, min(f[1] for f in faces) - h // 12)
        x1 = min(w, max(f[0] + f[2] for f in faces) + w // 12)
        y1 = min(h, max(f[1] + f[3] for f in faces) + int(h * 0.35))
        mask = _grabcut(img, (x0, y0, x1 - x0, y1 - y0))
        meta["detector"] = "face"
        _mask_meta(mask, meta)
        return mask, ("face" if _big_single_face(faces, w, h) else "person"), meta

    # 2) colour GrabCut seeded by a thin border ring: everything but the
    # frame edge starts as probable subject, so a subject that nearly fills
    # the frame (tail to nose) is not clipped by a fixed centre rect
    mask = _grabcut(img)
    if mask is not None and 0.04 < mask.mean() / 255 < 0.92:
        meta["detector"] = "grabcut"
        _mask_meta(mask, meta)
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
    _mask_meta(m, meta)
    return m, _heuristic_label(gray, m, meta), meta


def _mask_meta(mask, meta):
    if mask is None:
        return
    border = np.concatenate([mask[0, :], mask[-1, :], mask[:, 0], mask[:, -1]])
    meta["mask_frac"] = round(float(mask.mean() / 255), 3)
    meta["border_touch"] = round(float((border > 0).mean()), 3)


def _big_single_face(faces, w, h):
    return len(faces) == 1 and faces[0][2] > w * 0.12


def _grabcut(img, rect=None, iters=5):
    """GrabCut subject mask; None on failure/empty. `img` is BGR (colour
    separates a white dog from red barn + green grass — grayscale cannot)
    or gray. Runs on a <=GRABCUT_WORK px copy (the GMM does not need more
    and it is ~10x faster), with a fixed RNG seed so the k-means init is
    reproducible call after call. rect=None seeds a GRABCUT_MARGIN border
    ring as background. Small islands (< 25% of the largest component) are
    dropped; comparable components stay (a toy beside a toy)."""
    try:
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        h, w = img.shape[:2]
        s = min(1.0, GRABCUT_WORK / max(h, w))
        if s < 1.0:
            small = cv2.resize(img, (round(w * s), round(h * s)),
                               interpolation=cv2.INTER_AREA)
        else:
            small = img
        sh, sw = small.shape[:2]
        if rect is None:
            mx, my = max(2, int(sw * GRABCUT_MARGIN)), max(2, int(sh * GRABCUT_MARGIN))
            r = (mx, my, sw - 2 * mx, sh - 2 * my)
        else:
            x, y, rw, rh = rect
            r = (int(x * s), int(y * s), max(2, int(rw * s)), max(2, int(rh * s)))
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        mask = np.zeros((sh, sw), np.uint8)
        cv2.setRNGSeed(0)
        cv2.grabCut(small, mask, r, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
        m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
                     255, 0).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        if n > 2:                                # drop islands: keep every
            areas = st[1:, cv2.CC_STAT_AREA]     # component >= 25% of the
            keep = 1 + np.nonzero(areas >= 0.25 * areas.max())[0]   # largest
            m = np.where(np.isin(lab, keep), 255, 0).astype(np.uint8)
        if s < 1.0:
            m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
            m = np.where(m >= 128, 255, 0).astype(np.uint8)
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
                detail="medium", drop=False):
    """Binary ink mask (255 = line) from a grayscale photo. subject_mask
    (optional) applies the soft background rule, or — with drop=True —
    zones the clean style's wide-block pass: lenient on the silhouette
    ring (catch the low-contrast outline), strict inside the subject
    (fur/skin SHADING is not a line on a coloring page). _trace removes
    the background itself afterwards."""
    policy = dict(policy or POLICIES["generic"])
    mult = DETAIL_MULT.get(detail, 1.0)
    leveled = gray.mean() < 70
    if leveled:                                # low-light auto-level
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        # normalized low-light grain amplifies into texture: tighten policy
        policy["edge_c"] = min(24, policy["edge_c"] * 1.8)
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
        if drop and subject_mask is not None:
            zone = _zones(gray.shape, subject_mask, policy, mult)
            strict = cv2.adaptiveThreshold(smooth, 255,
                                           cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY_INV, wblock,
                                           c * WIDE_INTERIOR_C)
            ink2 = np.where(zone == 2, strict, ink2).astype(np.uint8)
        ink = cv2.bitwise_or(ink, ink2)
        # soften flat-area noise via Otsu ceiling — but never clear more than
        # 55% of the ink (guard against killing whole subjects on dark photos)
        otsu, _ = cv2.threshold(smooth, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ceiling = (smooth > otsu + 55)
        if ceiling.mean() < 0.55:
            ink[ceiling] = 0

    ink = _desplinter(ink, mult)
    if subject_mask is not None and not drop:
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
    """Soft rule (bg="soft" policies): background ink thinned (thicker
    threshold), subject kept — implemented as extra erosion of ink OUTSIDE
    the subject mask."""
    bg = cv2.bitwise_and(ink, cv2.bitwise_not(subject_mask))
    bg = cv2.erode(bg, np.ones((2, 2), np.uint8), iterations=1)
    fg = cv2.bitwise_and(ink, subject_mask)
    return cv2.bitwise_or(fg, bg)


def _mask_usable(mask, meta=None):
    """Is the detected mask a SILHOUETTE we can drop the background around?
    Single framed subject: a sane share of the frame, not spilling over the
    border (a mask hugging the frame edge is a scene, not a subject)."""
    if mask is None:
        return False
    meta = dict(meta or {})
    if "mask_frac" not in meta:
        _mask_meta(mask, meta)
    lo, hi = DROP_MASK_FRAC
    return lo <= meta["mask_frac"] <= hi and meta["border_touch"] <= DROP_BORDER_TOUCH


def _zone_radius(shape, policy, mult):
    """Dilation radius (image px) that keeps the silhouette band — the
    adaptive threshold paints it on the DARK side of the edge, i.e. just
    outside a light subject — proportional to the threshold block."""
    return max(4, int(policy["block"] * mult * 0.75))


def _drop_background(ink, subject_mask, policy, mult):
    """Hard rule (bg="drop" policies): keep ink inside the DILATED subject
    mask only; everything else (fence boards, grass, wallpaper) goes. The
    survivors are re-desplintered because cutting at the mask edge leaves
    stubs."""
    r = _zone_radius(ink.shape, policy, mult)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    zone = cv2.dilate(subject_mask, k)
    # the ring around the FEET is ground (grass tufts hug the paws): there
    # the mask is trusted almost as-is, and the ground contact line stands
    # in for the ink below it
    ys = np.nonzero(subject_mask.any(axis=1))[0]
    if len(ys):
        bottom = int(ys.max())
        feet = max(0, bottom - int(FEET_BAND * (bottom - int(ys.min()) + 1)))
        tight = cv2.dilate(subject_mask, cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2 * FEET_RADIUS + 1, 2 * FEET_RADIUS + 1)))
        zone[feet:, :] = tight[feet:, :]
        zone[min(ink.shape[0], bottom + 3):, :] = 0
    keep = cv2.bitwise_and(ink, zone)
    return _desplinter(keep, mult)


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
    thr = max(0.9, float(np.percentile(pos, 80)) * 1.1) if pos.size else 9e9
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


def _thin(ink):
    """Zhang-Suen thinning: uint8 0/255 ink -> uint8 0/1 one-pixel-wide
    centreline. Vectorised over the whole image with a fixed two-pass sweep
    order, so it is deterministic and fast (a 1600px photo thins in ~1s)."""
    img = (ink > 0).astype(np.uint8)
    while True:
        changed = False
        for step in (0, 1):
            pd = np.pad(img, 1)
            p2 = pd[:-2, 1:-1]; p3 = pd[:-2, 2:]; p4 = pd[1:-1, 2:]; p5 = pd[2:, 2:]
            p6 = pd[2:, 1:-1]; p7 = pd[2:, :-2]; p8 = pd[1:-1, :-2]; p9 = pd[:-2, :-2]
            seq = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
            b = p2.astype(np.int16) + p3 + p4 + p5 + p6 + p7 + p8 + p9
            a = np.zeros_like(b)
            for i in range(8):                       # 0->1 transitions around the ring
                a += (seq[i] == 0) & (seq[i + 1] == 1)
            if step == 0:
                c1 = (p2 * p4 * p6) == 0
                c2 = (p4 * p6 * p8) == 0
            else:
                c1 = (p2 * p4 * p8) == 0
                c2 = (p2 * p6 * p8) == 0
            m = (img == 1) & (b >= 2) & (b <= 6) & (a == 1) & c1 & c2
            if m.any():
                img[m] = 0
                changed = True
        if not changed:
            return img


_NB8 = ((-1, 0), (0, -1), (0, 1), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1))


def _neighbours(sk):
    nb = np.zeros(sk.shape, np.int16)
    for dy, dx in _NB8:
        nb += np.roll(np.roll(sk, dy, 0), dx, 1)
    return nb


def _crossings(sk):
    """Crossing number: 0->1 transitions around each pixel's 8-ring. A line
    pixel has 2, an end 1, a genuine junction >= 3. (The raw neighbour
    count overcounts: thinning leaves two-pixel staircases whose pixels
    have three neighbours yet split nothing.)"""
    pd = np.pad(sk, 1)
    p2 = pd[:-2, 1:-1]; p3 = pd[:-2, 2:]; p4 = pd[1:-1, 2:]; p5 = pd[2:, 2:]
    p6 = pd[2:, 1:-1]; p7 = pd[2:, :-2]; p8 = pd[1:-1, :-2]; p9 = pd[:-2, :-2]
    seq = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
    a = np.zeros(sk.shape, np.int16)
    for i in range(8):
        a += (seq[i] == 0) & (seq[i + 1] == 1)
    return a


def _prune(skel, k):
    """Remove thinning spurs shorter than k px: erode free ends k times,
    then grow the surviving ends back along the original skeleton
    (Gonzalez & Woods pruning). Spurs hanging off the middle of a line
    have no surviving end to grow back from, so they stay gone; genuine
    line ends are restored. Loops are untouched."""
    orig = skel.astype(np.uint8)
    cur = orig.copy()
    for _ in range(int(k)):
        ends = (cur == 1) & (_neighbours(cur) <= 1)
        if not ends.any():
            break
        cur[ends] = 0
    grow = ((cur == 1) & (_neighbours(cur) <= 1)).astype(np.uint8)
    k3 = np.ones((3, 3), np.uint8)
    for _ in range(int(k)):
        grow = cv2.dilate(grow, k3) & orig
    return (cur | grow).astype(np.uint8)


def _skeleton_polylines(skel):
    """1-px skeleton -> [(pts[(x, y), ...], closed, junction_ends)].
    Junction pixels (crossing number >= 3) split the skeleton into branches;
    each branch is walked pixel by pixel (fixed neighbour order, lexico-
    graphic start pixel -> deterministic) and re-attached to the centroid
    of the junction cluster at either end so strokes meet instead of
    stopping a pixel short. Branches meeting at a two-way junction (a
    thinning staircase, or what is left once a spur is pruned) are merged
    back into one polyline. closed=True for loops. junction_ends counts
    the ends that touch a junction (1 = a free-ending branch)."""
    sk = np.pad(skel, 1).astype(np.uint8)
    junction = (_crossings(sk) >= 3) & (sk == 1)
    chain = ((sk == 1) & ~junction).astype(np.uint8)
    _jn, jlab, _jst, jcen = cv2.connectedComponentsWithStats(
        junction.astype(np.uint8), 8)
    visited = np.zeros(sk.shape, bool)
    ys, xs = np.nonzero(chain)
    order = np.lexsort((xs, ys))

    def walk(y, x):
        path = []
        while True:
            nxt = None
            for dy, dx in _NB8:
                yy, xx = y + dy, x + dx
                if chain[yy, xx] and not visited[yy, xx]:
                    nxt = (yy, xx)
                    break
            if nxt is None:
                return path
            y, x = nxt
            visited[y, x] = True
            path.append((y, x))

    def adj_junction(py, px):
        for dy, dx in _NB8:
            j = jlab[py + dy, px + dx]
            if j > 0:
                return int(j)
        return 0

    polys = []
    for idx in order:
        y0, x0 = int(ys[idx]), int(xs[idx])
        if visited[y0, x0]:
            continue
        visited[y0, x0] = True
        back = walk(y0, x0)                    # one direction ...
        fwd = walk(y0, x0)                     # ... then the other
        pts = list(reversed(fwd)) + [(y0, x0)] + back
        j0, j1 = adj_junction(*pts[0]), adj_junction(*pts[-1])
        closed = False
        if not j0 and not j1 and len(pts) > 6:
            (ey, ex), (ly, lx) = pts[0], pts[-1]
            closed = max(abs(ey - ly), abs(ex - lx)) <= 1
        if j0:
            pts.insert(0, (float(jcen[j0][1]), float(jcen[j0][0])))
        if j1:
            pts.append((float(jcen[j1][1]), float(jcen[j1][0])))
        polys.append(dict(pts=pts, j0=j0, j1=j1, closed=closed))

    # merge branches at two-way junctions (deterministic: lowest index first)
    while True:
        ends = {}
        for pi, p in enumerate(polys):
            if p is None or p["closed"]:
                continue
            if p["j0"]:
                ends.setdefault(p["j0"], []).append((pi, 0))
            if p["j1"]:
                ends.setdefault(p["j1"], []).append((pi, 1))
        merged = False
        for jid in sorted(ends):
            lst = ends[jid]
            if len(lst) != 2:
                continue
            (a, ea), (b, eb) = lst
            if a == b:                         # both ends at one junction: a loop
                polys[a]["closed"] = True
                polys[a]["j0"] = polys[a]["j1"] = 0
                merged = True
                break
            pa, pb = polys[a], polys[b]
            pts_a = pa["pts"] if ea == 1 else pa["pts"][::-1]
            ja = pa["j0"] if ea == 1 else pa["j1"]
            pts_b = pb["pts"] if eb == 0 else pb["pts"][::-1]
            jb = pb["j1"] if eb == 0 else pb["j0"]
            polys[a] = dict(pts=pts_a + pts_b[1:], j0=ja, j1=jb, closed=False)
            polys[b] = None
            merged = True
            break
        if not merged:
            break

    out = []
    for p in polys:
        if p is None:
            continue
        pts = p["pts"]
        if p["closed"] and len(pts) < 4:
            continue
        ends = int(bool(p["j0"])) + int(bool(p["j1"]))
        out.append(([(float(px) - 1.0, float(py) - 1.0) for py, px in pts],
                    p["closed"], ends))
    return out


def _poly_len(pts):
    return float(sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                     for i in range(len(pts) - 1)))


def _smooth_open(pts, k=5):
    """Moving average along an open polyline (ends pinned) — the same
    wobble-removal pass _smooth_contour does for closed contours."""
    if len(pts) < k + 2:
        return pts
    a = np.array(pts, np.float32)
    ker = np.ones(k, np.float32) / k
    xs = np.convolve(np.pad(a[:, 0], (k // 2, k // 2), mode="edge"), ker, "valid")
    ys = np.convolve(np.pad(a[:, 1], (k // 2, k // 2), mode="edge"), ker, "valid")
    out = [(float(x), float(y)) for x, y in zip(xs, ys)]
    out[0], out[-1] = pts[0], pts[-1]
    return out


def _zones(shape, subject_mask, policy, mult):
    """Per-pixel zone map: 2 = subject interior, 1 = silhouette ring
    (within the dilation radius of the mask edge, where the threshold
    paints a light subject's outline), 0 = background."""
    zone = np.full(shape, 2, np.uint8)
    if subject_mask is None:
        return zone
    r = _zone_radius(shape, policy, mult)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    ki = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r + 1, r + 1))
    zone[:] = 0
    zone[cv2.dilate(subject_mask, k) > 0] = 1
    zone[cv2.erode(subject_mask, ki) > 0] = 2
    return zone


def vectorize(ink, policy=None, detail="medium", subject_mask=None,
              gray=None, drop=False):
    """Ink mask -> ordered list of SVG path elements in PAGE coordinates.

    Every 8-connected ink component is classified by its shape:
      RIBBON — an edge band (perimeter >> inscribed radius): thinned to its
               centreline and walked into polylines, so a thick band yields
               ONE stroke, not both of its sides;
      BLOB   — a solid patch (eye, nose, window, a dark silhouette): its
               outline is traced. Interior blobs that are neither dark
               (< BLOB_DARK_RATIO x subject median) nor large are texture
               (fur shadow) and are dropped.
    Zone-aware floors: in drop mode a connected skeleton structure inside
    the subject must total >= 3% of the image size, one on the silhouette
    ring >= 5% (grass tufts hugging the feet are short; the outline is
    long).
    White-fill layering: the largest closed shape is drawn first with a
    white fill (knocks out what is behind — charlib doctrine), thin
    strokes after (fill none).
    """
    policy = policy or POLICIES["generic"]
    mult = DETAIL_MULT.get(detail, 1.0)
    ih, iw = ink.shape
    maxdim = max(ih, iw)
    s, ox, oy = _page_fit(iw, ih)
    eps = max(1.0, policy["simplify"] * mult)
    max_strokes = policy["max_strokes"]
    zone = _zones(ink.shape, subject_mask, policy, mult)

    from scipy import ndimage
    n, labels, stats, _cent = cv2.connectedComponentsWithStats(ink, 8)
    if n <= 1:
        return []
    idx = np.arange(1, n)
    dt = cv2.distanceTransform(ink, cv2.DIST_L2, 5)
    rmax = np.asarray(ndimage.maximum(dt, labels, idx), np.float64)
    perim = np.zeros(n, np.float64)
    outer, _h = cv2.findContours(ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    for c in outer:
        lab = int(labels[c[0][0][1], c[0][0][0]])
        perim[lab] = max(perim[lab], cv2.arcLength(c, True))
    area = stats[:, cv2.CC_STAT_AREA].astype(np.float64)
    elong = perim[1:] / (4.0 * rmax + 1e-6)
    is_blob = (elong < BLOB_ELONGATION) & (rmax >= 2.0) & (area[1:] >= 16)
    # a blob narrower than ~0.4% of the image is a dot, not a feature (an
    # eye is wider): dots are neither colorable nor readable
    dot = rmax < max(2.0, BLOB_MIN_RADIUS * maxdim)

    keep_blob = is_blob.copy()
    if gray is not None and is_blob.any():
        ref = gray[subject_mask > 0] if subject_mask is not None else gray
        median = float(np.median(ref)) if ref.size else 128.0
        subj_area = float((subject_mask > 0).sum()) if subject_mask is not None \
            else float(ih * iw)
        mean_gray = np.asarray(ndimage.mean(gray, labels, idx), np.float64)
        dark = mean_gray < BLOB_DARK_RATIO * median
        large = area[1:] >= BLOB_LARGE_FRAC * subj_area
        keep_blob = is_blob & ((dark & ~dot) | large)
        if drop:
            # a blob outside the subject is a shadow; one on the silhouette
            # ring (grass between the paws leaks into the mask) must be as
            # dark as a nose to count
            cx = np.clip(_cent[1:, 0].astype(int), 0, iw - 1)
            cy = np.clip(_cent[1:, 1].astype(int), 0, ih - 1)
            z = zone[cy, cx]
            inside = subject_mask[cy, cx] > 0
            very_dark = mean_gray < BLOB_INK_RATIO * median
            keep_blob &= (z == 2) | (inside & very_dark) | large

    blob_ink = np.zeros_like(ink)
    ribbon_ink = np.zeros_like(ink)
    blob_labels = idx[keep_blob]
    ribbon_labels = idx[~is_blob]
    if len(blob_labels):
        blob_ink[np.isin(labels, blob_labels)] = 255
    if len(ribbon_labels):
        ribbon_ink[np.isin(labels, ribbon_labels)] = 255

    def zone_of(pts):
        zs = [zone[min(ih - 1, max(0, int(y))), min(iw - 1, max(0, int(x)))]
              for x, y in pts]
        zs = np.asarray(zs)
        return float((zs == 2).mean()), float((zs == 0).mean())

    entries = []                                   # dict(pts, closed, rank, sw, area)

    # ---- blobs: outline (outer contour + genuine holes)
    if blob_ink.any():
        contours, hier = cv2.findContours(blob_ink, cv2.RETR_CCOMP,
                                          cv2.CHAIN_APPROX_NONE)
        areas = {i: cv2.contourArea(c) for i, c in enumerate(contours)}
        for i, cnt in enumerate(contours):
            parent = hier[0][i][3] if hier is not None else -1
            if parent != -1:
                pa = areas.get(parent, 0)
                if pa <= 0 or areas[i] > 0.25 * pa:
                    continue                       # hole mirrors its parent
            if cv2.arcLength(cnt, True) < MIN_STROKE_LEN or areas[i] < 16:
                continue
            approx = cv2.approxPolyDP(_smooth_contour(cnt, k=7), eps, True)
            pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
            if len(pts) < 3:
                continue
            inner, outside = zone_of(pts)
            sw = SW_BACKGROUND if outside > 0.5 else (
                SW_SUBJECT if inner >= 0.6 else SW_SILHOUETTE)
            entries.append(dict(pts=pts, closed=True, rank=areas[i], sw=sw,
                                area=areas[i]))

    # ---- ribbons: centreline. Length floors apply to the whole connected
    # skeleton STRUCTURE (a ragged band thins into many short branches
    # between junctions — the outline is long as a whole, a grass tuft is
    # not), spurs are judged per branch.
    if ribbon_ink.any():
        skel = _prune(_thin(ribbon_ink), SPUR_LEN)
        _nc, clab = cv2.connectedComponents(skel, connectivity=8)
        polys = []
        struct_len, struct_inner, struct_box = {}, {}, {}
        for pts, closed, jends in _skeleton_polylines(skel):
            length = _poly_len(pts)
            if length < 4 or (jends == 1 and length < SPUR_LEN):
                continue
            mid = pts[len(pts) // 2]
            cid = int(clab[min(ih - 1, max(0, int(mid[1]))),
                           min(iw - 1, max(0, int(mid[0])))])
            inner, outside = zone_of(pts)
            struct_len[cid] = struct_len.get(cid, 0.0) + length
            struct_inner[cid] = struct_inner.get(cid, 0.0) + length * inner
            bx = struct_box.get(cid, [1e9, 1e9, -1e9, -1e9])
            for x, y in pts:
                bx = [min(bx[0], x), min(bx[1], y), max(bx[2], x), max(bx[3], y)]
            struct_box[cid] = bx
            polys.append((pts, closed, length, cid, inner, outside))
        for pts, closed, length, cid, inner, outside in polys:
            total = struct_len[cid]
            s_inner = struct_inner[cid] / total if total else 0.0
            bx = struct_box[cid]
            diag = math.hypot(bx[2] - bx[0], bx[3] - bx[1]) + 1e-6
            if drop:
                floor = (INTERIOR_FLOOR if s_inner >= 0.6 else RING_FLOOR) * maxdim
                # texture rule: a structure that packs far more line than
                # its extent (fur shadow network) is texture, not a contour
                if not closed and s_inner >= 0.6 and \
                        total > TEXTURE_RATIO * diag and diag < 0.5 * maxdim:
                    continue
            else:
                floor = MIN_STROKE_LEN
            if total < max(MIN_STROKE_LEN, floor):
                continue
            pts = _smooth_open(pts, 5)
            arr = np.array(pts, np.float32).reshape(-1, 1, 2)
            approx = cv2.approxPolyDP(arr, eps, closed)
            pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
            if len(pts) < (3 if closed else 2):
                continue
            sw = SW_BACKGROUND if outside > 0.5 else (
                SW_SUBJECT if inner >= 0.6 else SW_SILHOUETTE)
            enclosed = abs(cv2.contourArea(np.array(pts, np.float32))) if closed else 0.0
            entries.append(dict(pts=pts, closed=closed, sw=sw, area=enclosed,
                                rank=max(enclosed, length * length / 4.0)))

    # keep the richest strokes, drop the tail (soft max_strokes rule)
    entries.sort(key=lambda e: -e["rank"])
    entries = entries[:max_strokes]
    shapes = sorted((e for e in entries if e["closed"]), key=lambda e: -e["area"])
    strokes = sorted((e for e in entries if not e["closed"]), key=lambda e: -e["rank"])

    def to_page(pts):
        return [((x * s + ox), (y * s + oy)) for x, y in pts]

    out = []
    for j, e in enumerate(shapes):
        # ONLY the largest closed silhouette gets a white fill (knockout for
        # compositing); filling every loop would erase interior detail
        pp = to_page(e["pts"])
        fill = "white" if j == 0 else "none"
        if policy["snap_hv"]:
            pp = _snap_polyline(pp + [pp[0]])[:-1]
            d = "M " + " L ".join(f"{_f(a)} {_f(b)}" for a, b in pp) + " Z"
            out.append(P(d, e["sw"], fill))
        else:
            out.append(smooth_path(pp, sw=e["sw"], closed=True, fill=fill))
    for e in strokes:
        pp = to_page(e["pts"])
        if policy["snap_hv"]:
            pp = _snap_polyline(pp)
            d = "M " + " L ".join(f"{_f(a)} {_f(b)}" for a, b in pp)
            out.append(P(d, e["sw"]))
        else:
            out.append(smooth_path(pp, sw=e["sw"]))
    return out


def _elements_length(elements):
    """Total control-polygon length (page px) of the emitted paths — a
    cheap 'how much line is there' measure."""
    total = 0.0
    for el in elements:
        for d in re.findall(r' d="([^"]+)"', el):
            nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", d)]
            pts = list(zip(nums[0::2], nums[1::2]))
            total += _poly_len(pts)
    return total


def _elements_extent(elements):
    """(x0, y0, x1, y1) over every coordinate in the emitted path data
    (page px), or None. Control points included — good enough for the
    feet anchor and the ground line."""
    xs, ys = [], []
    for el in elements:
        for d in re.findall(r' d="([^"]+)"', el):
            nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", d)]
            xs.extend(nums[0::2])
            ys.extend(nums[1::2])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


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


def _assemble(elements, title, caption, policy_name, params, layout=None,
              extra=""):
    meta = (f'<g data-policy="{policy_name}" '
            f'data-params="edge_c={params["edge_c"]:.0f};simplify={params["simplify"]:.1f}">'
            + "".join(elements) + extra + "</g>")
    return spage(title, meta, caption=caption, layout=layout)


def spage_wrap(elements, title, caption, policy_name, params, layout=None,
               extra=""):
    return _assemble(elements, title, caption, policy_name, params, layout, extra)


def _ground_line(tr):
    """Ground contact line for a background-dropped subject: a straight
    stroke just under the subject mask's lowest row, spanning its width
    plus a margin, clipped to the art band. Page px."""
    if not tr.get("drop") or tr.get("mask") is None:
        return ""
    ys, xs = np.nonzero(tr["mask"])
    if not len(ys):
        return ""
    ih, iw = tr["mask"].shape
    s, ox, oy = _page_fit(iw, ih)
    gy = min(ART_BAND[3] - 6, ys.max() * s + oy + 5)
    x0 = max(ART_BAND[0] + 4, xs.min() * s + ox - 30)
    x1 = min(ART_BAND[2] - 4, xs.max() * s + ox + 30)
    if x1 - x0 < 40:
        return ""
    return ('<g data-ground="1">'
            + P(f"M {_f(x0)} {_f(gy)} L {_f(x1)} {_f(gy)}", 4) + "</g>")


# ---------------------------------------------------------------- public API
def photo_to_svg(photo_path, *, style="clean", subject="auto", detail="medium",
                 title=None, caption=None, max_dim=1600, qa=True,
                 layout=None):
    """Photo file -> standalone coloring page SVG string. layout="creative"
    marks open-composition pages (e.g. sketch traces) for the validator.
    A background-dropped subject stands on a ground contact line."""
    tr = _trace(photo_path, style, subject, detail, max_dim)
    if qa:
        for _ in range(QA_MAX_ROUNDS):
            svg = _assemble(tr["elements"], title, caption, tr["label"],
                            tr["params"], layout, _ground_line(tr))
            rep = _qa_report(svg)
            if rep["ok"] and (rep["raster"] is None
                              or rep["raster"]["sliver_count"] <= 70):
                break
            if not _qa_adjust(POLICIES[tr["label"]], tr["params"], rep):
                break
            tr = _trace(photo_path, style, subject, detail, max_dim,
                        overrides=tr["params"], detected=tr["detected"])
    return spage_wrap(tr["elements"], title, caption, tr["label"], tr["params"],
                      layout, _ground_line(tr))


def photo_to_fragment(photo_path, *, style="clean", subject="auto",
                      detail="medium", max_dim=1600, pad=20):
    """Photo -> G()-placeable charlib fragment. Local origin = the traced
    art's BOTTOM-CENTRE (same feet-anchor convention as every charlib
    helper): G(x, ground_y, fragment, s) stands the subject on a ground
    line. No ground line of its own — the scene supplies it."""
    tr = _trace(photo_path, style, subject, detail, max_dim)
    ext = tr["extent"]                      # strokes + knockout mat
    if ext is not None:
        bcx, bcy = (ext[0] + ext[2]) / 2, ext[3]
    else:
        bcx, bcy = (ART_BAND[0] + ART_BAND[2]) / 2, (ART_BAND[1] + ART_BAND[3]) / 2
    return (f'<g data-el="photo-trace" '
            f'transform="translate({_f(-bcx)},{_f(-bcy)})">'
            + "".join(tr["elements"]) + "</g>")


def composite_page(photo_path, scene_body, ground_y, *, x=425, scale=1.0,
                   style="clean", detail="medium", title="My Photo Page",
                   caption=None, num=None):
    """Traced photo subject matted onto a scene kit body beside charlib
    art. The fragment self-anchors at its ink bottom-centre, so it stands
    ON ground_y at (x, ground_y) like any charlib figure."""
    frag = photo_to_fragment(photo_path, style=style, detail=detail)
    body = scene_body + G(x, ground_y, matted(frag, scale=scale), scale)
    return spage(title, body, caption=caption, num=num)


def _trace(photo_path, style, subject, detail, max_dim, overrides=None,
           detected=None):
    """One pass photo -> elements. Returns a dict: elements, label, params,
    ink, mask, drop (background removed?), detected (cached detection so
    QA rounds do not rerun GrabCut)."""
    gray, bgr = load_photo(photo_path, max_dim)
    if detected is None:
        if subject == "auto":
            detected = detect_subject(gray, bgr)
        else:
            detected = (None, subject if subject in POLICIES else "generic", {})
    mask, label, meta = detected
    policy = dict(POLICIES.get(label, POLICIES["generic"]))
    if overrides:
        policy.update({k: v for k, v in overrides.items() if k in policy})
    mult = DETAIL_MULT.get(detail, 1.0)
    drop = policy.get("bg") == "drop" and _mask_usable(mask, meta)
    ink = extract_ink(gray, style=style, policy=policy, detail=detail,
                      subject_mask=mask if drop else None, drop=drop)
    # graceful degradation: sketch on an ultra-soft photo can find almost
    # nothing — fall back to the clean extractor rather than an empty page
    if style == "sketch":
        n_comp, _labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
        solid = sum(1 for i in range(1, n_comp) if stats[i, 4] >= 40)
        if solid < 3:
            ink = extract_ink(gray, style="clean", policy=policy, detail=detail,
                              subject_mask=mask if drop else None, drop=drop)

    def finish(ink):
        if drop:
            ink = _drop_background(ink, mask, policy, mult)
        elif mask is not None:
            ink = _focus_subject(ink, mask, mult)
        return ink, vectorize(ink, policy=policy, detail=detail,
                              subject_mask=mask, gray=gray, drop=drop)
    ink, elements = finish(ink)
    # ...and the same degradation after vectorizing: flat, step-edged
    # subjects give the ridge detector almost nothing to follow
    if style == "sketch" and _elements_length(elements) < SKETCH_MIN_LENGTH:
        ink, elements = finish(extract_ink(gray, style="clean", policy=policy,
                                           detail=detail,
                                           subject_mask=mask if drop else None,
                                           drop=drop))
    if drop and elements:
        # a traced subject is a FOREGROUND object: its open silhouette
        # cannot knock out scene lines behind it the way a filled helper
        # does, so the subject mask itself goes first as a white,
        # stroke-less knockout (matted() adds the halo around the strokes)
        elements = _knockout(mask, policy, mult) + elements
    return dict(elements=elements, label=label, params=policy, ink=ink,
                mask=mask, drop=drop, detected=detected,
                extent=_elements_extent(elements))


def _knockout(mask, policy, mult):
    """White fill of the subject mask dilated out to about the silhouette
    centreline (the threshold band sits on the dark side of the edge) and
    clipped at the feet like the drop zone, smoothed: the knockout mat
    behind a traced subject."""
    ih, iw = mask.shape
    s, ox, oy = _page_fit(iw, ih)
    r = max(2, _zone_radius(mask.shape, policy, mult) // 3)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    grown = cv2.dilate(mask, k)
    ys = np.nonzero(mask.any(axis=1))[0]
    if len(ys):
        grown[min(ih, int(ys.max()) + 3):, :] = 0
    contours, _h = cv2.findContours(grown, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_NONE)
    out = []
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(cnt) < 0.002 * ih * iw:
            continue
        approx = cv2.approxPolyDP(_smooth_contour(cnt, k=15), 2.0, True)
        pts = [(float(p[0][0]) * s + ox, float(p[0][1]) * s + oy)
               for p in approx]
        if len(pts) < 3:
            continue
        d = "M " + " L ".join(f"{_f(x)} {_f(y)}" for x, y in pts) + " Z"
        out.append(f'<path d="{d}" fill="white" stroke="none" data-knockout="1"/>')
    return out


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
    elif kind == "car":
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
    elif kind == "crisp_toy":
        # difficulty tier 1: white background, hard edges, high contrast
        img[:] = 235
        cv2.rectangle(img, (int(size * 0.2), int(size * 0.3)),
                      (int(size * 0.5), int(size * 0.7)), (40, 40, 200), -1)
        cv2.circle(img, (int(size * 0.68), int(size * 0.5)),
                   int(size * 0.16), (200, 60, 60), -1)
        cv2.rectangle(img, (int(size * 0.6), int(size * 0.72)),
                      (int(size * 0.8), int(size * 0.8)), (60, 160, 60), -1)
    elif kind == "soft_portrait":
        # difficulty tier 2: soft gradients, no hard edges (face-like)
        cv2.ellipse(img, (size // 2, int(size * 0.52)), (int(size * 0.26),
                    int(size * 0.34)), 0, 0, 360, (110, 105, 100), -1)
        cv2.ellipse(img, (size // 2, int(size * 0.38)), (int(size * 0.27),
                    int(size * 0.16)), 0, 0, 360, (60, 55, 50), -1)
        for ex_ in (int(size * 0.42), int(size * 0.58)):
            cv2.circle(img, (ex_, int(size * 0.48)), int(size * 0.025),
                       (40, 40, 40), -1)
        cv2.ellipse(img, (size // 2, int(size * 0.62)), (int(size * 0.07),
                    int(size * 0.03)), 0, 0, 360, (40, 40, 40), -1)
        img = cv2.GaussianBlur(img, (0, 0), 5)
    elif kind == "textured_foliage":
        # difficulty tier 3: high-frequency texture everywhere
        for i in range(140):
            cx_ = int(rng.integers(0, size))
            cy_ = int(rng.integers(int(size * 0.15), size))
            r_ = int(rng.integers(8, 30))
            cv2.ellipse(img, (cx_, cy_), (r_, r_ // 2),
                        int(rng.integers(0, 180)), 0, 360,
                        (int(rng.integers(40, 110)), 90, 50), -1)
        cv2.rectangle(img, (int(size * 0.46), int(size * 0.3)),
                      (int(size * 0.54), size), (70, 60, 45), -1)
    if kind == "low_light":
        img = (img * 0.3 + 8).astype(np.float32)
        grain = rng.normal(0, 10, img.shape).astype(np.float32)
    else:
        grain = rng.normal(0, 6, img.shape).astype(np.float32)
    # soft shadow + sensor grain
    img = cv2.GaussianBlur(img, (0, 0), 3)
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
