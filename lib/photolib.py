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

Faces: detect_faces_full / face_landmarks return YuNet boxes WITH their
five landmarks ({"box", "score", "landmarks": eye_l, eye_r, nose, mouth_l,
mouth_r}; _l/_r = IMAGE-left/right). With protect_face (face/person/animal
policies, or any hinted face) the landmarks become FEATURE-PROTECTION
ZONES — eye ellipses scaled by the interocular distance, a brow band,
nose, mouth, declared glasses/moles/... — inside which small dark blobs
(pupils, nostrils) survive the dot filter, length floors and the texture
rule relax, simplify is finer and strokes draw at the interior weight.
feature_fidelity() scores whether traced ink sits on each feature; pages
with faces carry it as data-fidelity.

Optional inputs, all off by default (output is byte-identical without):
  hints=      a JSON-able dict an agent writes by LOOKING at the photo
              (label, subject_box, faces + features, keep/drop boxes) —
              see parse_hints and reference/photo-guide.md
  backends=   {"segment"|"landmarks"|"depth"|"lineart": registered name},
              from lib/imagemodels.py (local ONNX models, callables);
              remote backends are refused unless allow_remote=True
  lineart=    a line drawing from an image model, vectorized by the house
              pipeline (trace_lineart); landmarks/mask still come from
              the photo, so feature_fidelity guards against identity drift

All processing is local by default; every stage is deterministic (fixed
iteration counts, no randomness). Photos of real people stay on disk: the
pipeline extracts LINE ART only, never likeness shading.

CLI:
    python -m lib.photolib photo.jpg -o page.svg [--style sketch]
        [--detail medium] [--fragment out_fragment.svg] [--hints h.json]
        [--lineart drawing.png] [--no-protect-face]
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
DEPTH_FAR = 0.35                   # depth backend: farthest 35% of the GrabCut rect seeds as background
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
# feature protection (protect_face / keep boxes). Zone sizes are fractions
# of the interocular distance (IOD, eye centre to eye centre)
EYE_ZONE = (0.40, 0.26)            # eye ellipse semi-axes (along, across the eye line) x IOD
BROW_RISE, BROW_ZONE = 0.36, (0.50, 0.20)   # brow band: centre above each eye, semi-axes
NOSE_ZONE = (0.36, 0.30)           # nose-tip ellipse semi-axes (nostrils sit either side)
MOUTH_PAD = (0.20, 0.28)           # mouth ellipse: half corner span + this, and this across
GLASSES_ZONE = (1.15, 0.50)        # declared glasses: rect half-extent around the eye midpoint
PROTECT_MIN_COMPONENT = 6          # ink component area kept inside a protection zone
PROTECT_MIN_LEN = 8.0              # image-px floor for protected strokes (pupil ring, nostril)
PROTECT_SPUR = 4.0                 # spur pruning inside zones (a short brow is not a spur)
PROTECT_DARK_RATIO = 0.85          # protected blob kept if darker than 85% of the median
PROTECT_SIMPLIFY = 0.4             # simplify epsilon x this inside zones (small shapes stay round)
PUPIL_WINDOW = 0.22               # iris search window half-size, x interocular distance
PUPIL_DARK = 0.35                 # iris = darker than window min + this x (median - min)
PUPIL_CONTRAST = 25.0             # below this median-min gray range: no iris (closed / soft)
PUPIL_R = (0.05, 0.12)            # iris dot radius clamp, x interocular distance
PROTECT_MAX_STROKES = 80           # protected strokes ride outside the max_strokes cut, up to this
FIDELITY_RADIUS = 0.20             # feature_fidelity: ink within this x IOD of a feature = present
FIDELITY_MIN = 0.80                # line art from a generative model below this = identity drift
FACE_KEYS = ("eye_l", "eye_r", "nose", "mouth_l", "mouth_r")   # _l/_r = IMAGE left/right
# canonical landmark positions as fractions of a frontal face box — fills
# in the landmarks a face hint leaves out (a box alone still protects)
CANON_LANDMARKS = {"eye_l": (0.32, 0.40), "eye_r": (0.68, 0.40),
                   "nose": (0.50, 0.60), "mouth_l": (0.36, 0.78),
                   "mouth_r": (0.64, 0.78)}
# declared features whose zone is derived from the landmarks; any other
# feature name (mole, birthmark, earring, hair_clip ...) needs its own box
DERIVED_FEATURES = ("glasses", "gap_tooth", "braces", "freckles", "dimples",
                    "headband")
HINT_KEYS = ("units", "image_size", "label", "subject_box", "faces", "keep",
             "drop", "notes")

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


def _yunet_rows(gray, bgr=None):
    """Raw YuNet rows (x, y, w, h, right-eye xy, left-eye xy, nose xy,
    right-mouth xy, left-mouth xy, score) for faces >= 1/16 of the width."""
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
    if faces is None:
        return []
    return [f for f in faces if f[2] >= w / 16]


def _detect_faces(gray, bgr=None):
    """YuNet face detection (Apache-2.0 model bundled in assets/models).
    Returns [x, y, w, h] list. OpenCV 5 removed Haar cascades; YuNet is the
    supported detector and runs fully local. detect_faces_full keeps the
    landmarks too."""
    return [(int(f[0]), int(f[1]), int(f[2]), int(f[3]))
            for f in _yunet_rows(gray, bgr)]


def _pt(p):
    return (round(float(p[0]), 1), round(float(p[1]), 1))


def _lr(a, b):
    """Order two points IMAGE-left first (smaller x)."""
    return (a, b) if a[0] <= b[0] else (b, a)


def detect_faces_full(gray, bgr=None):
    """YuNet faces WITH landmarks, in image px:
        [{"box": [x, y, w, h], "score": s,
          "landmarks": {"eye_l": (x, y), "eye_r": (x, y), "nose": (x, y),
                        "mouth_l": (x, y), "mouth_r": (x, y)}}]
    _l / _r mean IMAGE-left / IMAGE-right (smaller / larger x), never the
    subject's own left/right: a frontal subject's RIGHT eye is "eye_l".
    (YuNet names its points from the subject's side; they are re-ordered
    by x here so no consumer has to think about it.) Same faces, same
    order as _detect_faces."""
    out = []
    for f in _yunet_rows(gray, bgr):
        eye_l, eye_r = _lr(_pt(f[4:6]), _pt(f[6:8]))
        mouth_l, mouth_r = _lr(_pt(f[10:12]), _pt(f[12:14]))
        out.append({"box": [int(f[0]), int(f[1]), int(f[2]), int(f[3])],
                    "score": round(float(f[14]), 3),
                    "landmarks": {"eye_l": eye_l, "eye_r": eye_r,
                                  "nose": _pt(f[8:10]), "mouth_l": mouth_l,
                                  "mouth_r": mouth_r},
                    "source": "yunet"})
    return out


def face_landmarks(photo_path, hints=None, *, backends=None,
                   allow_remote=False, max_dim=1600):
    """Faces of a photo file in the detect_faces_full dict format: YuNet,
    augmented by a "landmarks" backend and overridden by hinted faces
    (a hint face overlapping a detection replaces it). Coordinates are px
    of the WORKING image (load_photo at max_dim — pass a large max_dim for
    the original resolution); ratios (IOD / box width, ...) are scale-free
    either way. Hint faces carry "features" (names) and "feature_boxes"."""
    gray, bgr = load_photo(photo_path, max_dim)
    hz = parse_hints(hints, gray.shape, _upright_size(photo_path))
    return _all_faces(gray, bgr, hz, backends, allow_remote)


def _all_faces(gray, bgr, hz, backends, allow_remote):
    faces = detect_faces_full(gray, bgr)
    name = (backends or {}).get("landmarks")
    if name:
        import imagemodels
        # the privacy gate counts hinted faces too (a profile YuNet misses)
        extra = imagemodels.run_backend(name, bgr if bgr is not None else
                                        cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR),
                                        "landmarks", allow_remote=allow_remote,
                                        faces=len(faces) + len(hz["faces"] if hz else ()))
        faces = _merge_faces(faces, extra)       # validated by run_backend
    if hz and hz["faces"]:
        faces = _merge_faces(faces, hz["faces"])
    return faces


# ---------------------------------------------------------------- vision hints
class HintError(ValueError):
    """Malformed hints dict (raised with the offending field named)."""


def hints_overlay(photo_path, hints=None, out_path=None, *, max_dim=1600):
    """Draw what the pipeline will use ON the photo, for the agent to LOOK
    at before tracing: YuNet faces (blue), hinted faces (magenta) with
    their five landmarks, the subject box (yellow), keep boxes (green) and
    drop boxes (red). Spatial reasoning is good but not infallible — a
    hinted eye 30px off protects the wrong pixels. Returns the BGR image;
    writes a PNG when out_path is given. Local only."""
    gray, bgr = load_photo(photo_path, max_dim)
    hz = parse_hints(hints, gray.shape, _upright_size(photo_path))
    img = bgr.copy()
    t = max(2, round(max(img.shape[:2]) / 400))

    def box(b, col):
        x, y, w, h = (int(round(v)) for v in b)
        cv2.rectangle(img, (x, y), (x + w, y + h), col, t)

    for f in _all_faces(gray, bgr, hz, None, False):
        col = (255, 0, 255) if f.get("source") == "hint" else (255, 0, 0)
        box(f["box"], col)
        for name, (x, y) in f["landmarks"].items():
            cv2.circle(img, (int(round(x)), int(round(y))), 2 * t, col, -1)
            cv2.putText(img, name, (int(x) + 3 * t, int(y) - 2 * t),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.25 * t, col, max(1, t // 2))
        for b in (f.get("feature_boxes") or {}).values():
            box(b, col)
    if hz:
        if hz.get("subject_box"):
            box(hz["subject_box"], (0, 220, 255))
        for b in hz.get("keep") or ():
            box(b, (0, 180, 0))
        for b in hz.get("drop") or ():
            box(b, (0, 0, 255))
    if out_path:
        cv2.imwrite(out_path, img)
    return img


def _upright_size(path):
    """(w, h) of a photo file after EXIF rotation, without decoding it."""
    if path is None or not isinstance(path, (str, os.PathLike)):
        return None
    from PIL import Image
    with Image.open(path) as im:
        w, h = im.size
        try:
            orient = im.getexif().get(0x0112, 1)
        except Exception:
            orient = 1
    return (h, w) if orient in (5, 6, 7, 8) else (w, h)


def _num(v, where):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise HintError(f"{where}: expected a number, got {v!r}")
    return float(v)


def _box_iou(a, b):
    ax1, ay1, bx1, by1 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax1, bx1) - max(a[0], b[0]))
    ih = max(0.0, min(ay1, by1) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def normalize_face(f, shape, source="hint"):
    """Validate one face dict (box required; landmarks, score, features
    optional) in IMAGE px and return it in the detect_faces_full format.
    Missing landmarks come from CANON_LANDMARKS inside the box; eyes and
    mouth corners are re-ordered so _l is the smaller x."""
    if not isinstance(f, dict):
        raise HintError(f"face: expected a dict, got {type(f).__name__}")
    unknown = set(f) - {"box", "score", "landmarks", "features",
                        "feature_boxes", "source"}
    if unknown:
        raise HintError(f"face: unknown key(s) {sorted(unknown)}; allowed: "
                        "box, landmarks, score, features")
    if "box" not in f:
        raise HintError("face: 'box' [x, y, w, h] is required")
    box = _check_box(f["box"], "face.box", shape)
    lm_in = f.get("landmarks") or {}
    if not isinstance(lm_in, dict):
        raise HintError("face.landmarks: expected a dict of name -> [x, y]")
    bad = set(lm_in) - set(FACE_KEYS)
    if bad:
        raise HintError(f"face.landmarks: unknown name(s) {sorted(bad)}; use "
                        f"{', '.join(FACE_KEYS)} (_l/_r = IMAGE left/right)")
    lm, given = {}, []
    for k in FACE_KEYS:
        if k in lm_in:
            lm[k] = _pt(_check_point(lm_in[k], f"face.landmarks.{k}"))
            given.append(k)
        else:
            fx, fy = CANON_LANDMARKS[k]
            lm[k] = _pt((box[0] + fx * box[2], box[1] + fy * box[3]))
    lm["eye_l"], lm["eye_r"] = _lr(lm["eye_l"], lm["eye_r"])
    lm["mouth_l"], lm["mouth_r"] = _lr(lm["mouth_l"], lm["mouth_r"])
    score = _num(f.get("score", 1.0), "face.score")
    if not 0.0 <= score <= 1.0:
        raise HintError(f"face.score: must be in [0, 1], got {score}")
    out = {"box": [int(round(v)) for v in box], "score": round(score, 3),
           "landmarks": lm, "source": f.get("source", source)}
    if len(given) < len(FACE_KEYS):
        out["_given"] = given                   # merge may borrow the rest
    names, fboxes = [], {}
    for i, feat in enumerate(f.get("features") or []):
        if isinstance(feat, str):
            name, fb = feat, None
        elif isinstance(feat, dict) and isinstance(feat.get("name"), str):
            extra = set(feat) - {"name", "box"}
            if extra:
                raise HintError(f"face.features[{i}]: unknown key(s) {sorted(extra)}")
            name = feat["name"]
            fb = _check_box(feat["box"], f"face.features[{i}].box", shape) \
                if feat.get("box") is not None else None
        else:
            raise HintError(f"face.features[{i}]: expected a name or "
                            f"{{'name': ..., 'box': [x, y, w, h]}}, got {feat!r}")
        if fb is None and isinstance(f.get("feature_boxes"), dict) \
                and name in f["feature_boxes"]:
            fb = _check_box(f["feature_boxes"][name], f"face.feature_boxes.{name}",
                            shape)
        if fb is None and name not in DERIVED_FEATURES:
            raise HintError(f"face.features[{i}]: '{name}' needs a box (it can "
                            f"be anywhere on the face); features placed from the "
                            f"landmarks alone are: {', '.join(DERIVED_FEATURES)}")
        names.append(name)
        if fb is not None:
            fboxes[name] = [round(v, 1) for v in fb]
    if names:
        out["features"] = names
        out["feature_boxes"] = fboxes
    return out


def _check_point(p, where):
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        raise HintError(f"{where}: expected [x, y], got {p!r}")
    return (_num(p[0], where), _num(p[1], where))


def _check_box(b, where, shape):
    """[x, y, w, h] in IMAGE px, positive size, overlapping the image."""
    if not isinstance(b, (list, tuple)) or len(b) != 4:
        raise HintError(f"{where}: expected [x, y, w, h], got {b!r}")
    x, y, w, h = (_num(v, where) for v in b)
    if w <= 0 or h <= 0:
        raise HintError(f"{where}: width and height must be > 0, got {list(b)}")
    ih, iw = shape[:2]
    if x >= iw or y >= ih or x + w <= 0 or y + h <= 0:
        raise HintError(f"{where}: {list(b)} lies outside the {iw}x{ih} image "
                        "(wrong units? px boxes are in photo pixels, norm in 0-1)")
    return (x, y, w, h)


def parse_hints(hints, shape, photo_size=None):
    """Validate a vision-hints dict (or a path to its JSON file) and return
    it converted to WORKING-image px, or None when hints is None.

    shape is the working image (h, w); photo_size the (w, h) the photo's
    px coordinates refer to (the original upright photo — load_photo may
    have downscaled it). units "norm" means 0-1 fractions of the frame;
    "image_size": [w, h] overrides photo_size (an agent that looked at a
    resized copy says which). Raises HintError naming the bad field."""
    if hints is None:
        return None
    if isinstance(hints, dict) and hints.get("_parsed"):
        return hints
    if isinstance(hints, (str, os.PathLike)):
        import json
        try:
            with open(hints) as fh:
                hints = json.load(fh)
        except (OSError, ValueError) as e:
            raise HintError(f"hints file {hints!r}: {e}") from None
    if not isinstance(hints, dict):
        raise HintError(f"hints: expected a dict, got {type(hints).__name__}")
    unknown = set(hints) - set(HINT_KEYS)
    if unknown:
        raise HintError(f"hints: unknown key(s) {sorted(unknown)}; allowed: "
                        f"{', '.join(HINT_KEYS)}")
    ih, iw = shape[:2]
    units = hints.get("units", "px")
    if units not in ("px", "norm"):
        raise HintError(f"hints.units: 'px' or 'norm', got {units!r}")
    if units == "norm":
        sx, sy = float(iw), float(ih)
    else:
        ref = hints.get("image_size") or photo_size or (iw, ih)
        if hints.get("image_size") is not None:
            ref = _check_point(ref, "hints.image_size")
            if min(ref) <= 0:
                raise HintError(f"hints.image_size: must be positive, got {ref}")
        sx, sy = iw / float(ref[0]), ih / float(ref[1])

    def conv_box(b, where):
        if not isinstance(b, (list, tuple)) or len(b) != 4:
            raise HintError(f"{where}: expected [x, y, w, h], got {b!r}")
        v = [_num(c, where) for c in b]
        if units == "norm" and not all(-0.01 <= c <= 1.01 for c in v):
            raise HintError(f"{where}: norm units must be 0-1, got {list(b)}")
        if units == "px" and all(0 <= c <= 1.0 for c in v) and max(iw, ih) > 4:
            raise HintError(f"{where}: {list(b)} looks normalized — set "
                            "\"units\": \"norm\" (px boxes are photo pixels)")
        return [v[0] * sx, v[1] * sy, v[2] * sx, v[3] * sy]

    def conv_pt(p, where):
        x, y = _check_point(p, where)
        if units == "norm" and not (-0.01 <= x <= 1.01 and -0.01 <= y <= 1.01):
            raise HintError(f"{where}: norm units must be 0-1, got {list(p)}")
        return [x * sx, y * sy]

    out = {"_parsed": True, "label": None, "subject_box": None, "faces": [],
           "keep": [], "drop": []}
    label = hints.get("label")
    if label is not None:
        if label not in POLICIES:
            raise HintError(f"hints.label: {label!r} is not a policy; use one "
                            f"of {', '.join(POLICIES)}")
        out["label"] = label
    if hints.get("subject_box") is not None:
        out["subject_box"] = _check_box(conv_box(hints["subject_box"],
                                                 "hints.subject_box"),
                                        "hints.subject_box", shape)
    for key in ("keep", "drop"):
        boxes = hints.get(key) or []
        if not isinstance(boxes, (list, tuple)):
            raise HintError(f"hints.{key}: expected a list of [x, y, w, h]")
        out[key] = [_check_box(conv_box(b, f"hints.{key}[{i}]"),
                               f"hints.{key}[{i}]", shape)
                    for i, b in enumerate(boxes)]
    faces = hints.get("faces") or []
    if not isinstance(faces, (list, tuple)):
        raise HintError("hints.faces: expected a list of face dicts")
    for i, f in enumerate(faces):
        if not isinstance(f, dict):
            raise HintError(f"hints.faces[{i}]: expected a dict, got {f!r}")
        g = dict(f)
        if "box" in g:
            g["box"] = conv_box(g["box"], f"hints.faces[{i}].box")
        if isinstance(g.get("landmarks"), dict):
            g["landmarks"] = {k: conv_pt(v, f"hints.faces[{i}].landmarks.{k}")
                              if k in FACE_KEYS else v
                              for k, v in g["landmarks"].items()}
        feats = []
        for j, feat in enumerate(g.get("features") or []):
            if isinstance(feat, dict) and feat.get("box") is not None:
                feat = dict(feat, box=conv_box(feat["box"],
                                               f"hints.faces[{i}].features[{j}].box"))
            feats.append(feat)
        if feats:
            g["features"] = feats
        if isinstance(g.get("feature_boxes"), dict):
            g["feature_boxes"] = {
                k: conv_box(v, f"hints.faces[{i}].feature_boxes.{k}")
                for k, v in g["feature_boxes"].items()}
        try:
            out["faces"].append(normalize_face(g, shape))
        except HintError as e:
            raise HintError(f"hints.faces[{i}]: {e}") from None
    return out


def _merge_faces(base, extra):
    """extra faces (hints, backends) override overlapping base faces
    (IoU >= 0.3) — borrowing the base face's landmarks for any the extra
    face left out — and are appended otherwise. Deterministic order: base
    order, then unmatched extras."""
    out = [dict(f) for f in base]
    for e in extra:
        e = dict(e)
        hit = None
        for i, b in enumerate(out):
            if _box_iou(e["box"], b["box"]) >= 0.3:
                hit = i
                break
        given = e.pop("_given", None)
        if hit is not None and given is not None:
            lm = dict(out[hit]["landmarks"])
            lm.update({k: e["landmarks"][k] for k in given})
            lm["eye_l"], lm["eye_r"] = _lr(lm["eye_l"], lm["eye_r"])
            lm["mouth_l"], lm["mouth_r"] = _lr(lm["mouth_l"], lm["mouth_r"])
            e["landmarks"] = lm
        if hit is not None:
            out[hit] = e
        else:
            out.append(e)
    for f in out:
        f.pop("_given", None)
    return out


def _iod(face):
    lm = face["landmarks"]
    d = math.hypot(lm["eye_r"][0] - lm["eye_l"][0], lm["eye_r"][1] - lm["eye_l"][1])
    return max(d, 0.25 * face["box"][2], 2.0)


def _face_frame(face):
    """(iod, angle_deg of the eye line, unit 'up' vector) for one face."""
    lm = face["landmarks"]
    (x0, y0), (x1, y1) = lm["eye_l"], lm["eye_r"]
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    a = math.radians(ang)
    return _iod(face), ang, (math.sin(a), -math.cos(a))


def protection_zones(faces, shape, keep=()):
    """uint8 mask (255 = protected) of FEATURE zones in image px: per face
    two eye ellipses and a brow band (scaled by the interocular distance,
    rotated with the eye line), nose, mouth, plus declared features
    (glasses rect around both eyes, freckle cheeks, dimples, headband,
    and any feature box) and the hints' keep boxes. None when empty."""
    ih, iw = shape[:2]
    z = np.zeros((ih, iw), np.uint8)

    def ell(c, ax, ang):
        cv2.ellipse(z, (int(round(c[0])), int(round(c[1]))),
                    (max(1, int(round(ax[0]))), max(1, int(round(ax[1])))),
                    ang, 0, 360, 255, -1)

    def rect(cx, cy, hw, hh, ang):
        pts = cv2.boxPoints(((cx, cy), (2 * hw, 2 * hh), ang))
        cv2.fillPoly(z, [np.round(pts).astype(np.int32)], 255)

    for f in faces:
        lm = f["landmarks"]
        iod, ang, up = _face_frame(f)
        feats = set(f.get("features") or ())
        for e in (lm["eye_l"], lm["eye_r"]):
            ell(e, (EYE_ZONE[0] * iod, EYE_ZONE[1] * iod), ang)
            ell((e[0] + up[0] * BROW_RISE * iod, e[1] + up[1] * BROW_RISE * iod),
                (BROW_ZONE[0] * iod, BROW_ZONE[1] * iod), ang)
        ell(lm["nose"], (NOSE_ZONE[0] * iod, NOSE_ZONE[1] * iod), ang)
        ml, mr = lm["mouth_l"], lm["mouth_r"]
        half = math.hypot(mr[0] - ml[0], mr[1] - ml[1]) / 2
        mc = ((ml[0] + mr[0]) / 2, (ml[1] + mr[1]) / 2)
        ell(mc, (half + MOUTH_PAD[0] * iod, MOUTH_PAD[1] * iod), ang)
        mid = ((lm["eye_l"][0] + lm["eye_r"][0]) / 2,
               (lm["eye_l"][1] + lm["eye_r"][1]) / 2)
        if "glasses" in feats:
            rect(mid[0], mid[1], GLASSES_ZONE[0] * iod, GLASSES_ZONE[1] * iod, ang)
        if "freckles" in feats:
            for e in (lm["eye_l"], lm["eye_r"]):
                ell((e[0] - up[0] * 0.55 * iod, e[1] - up[1] * 0.55 * iod),
                    (0.42 * iod, 0.28 * iod), ang)
        if "dimples" in feats:
            for p, sgn in ((ml, -1), (mr, 1)):
                ell((p[0] + sgn * 0.22 * iod, p[1]), (0.18 * iod, 0.18 * iod), ang)
        if "headband" in feats:
            bx, by, bw, bh = f["box"]
            rect(bx + bw / 2, by + 0.02 * bh, 0.6 * bw, 0.14 * bh, ang)
        for fb in (f.get("feature_boxes") or {}).values():
            x, y, w, h = fb
            pad = 0.1 * iod
            cv2.rectangle(z, (int(x - pad), int(y - pad)),
                          (int(math.ceil(x + w + pad)), int(math.ceil(y + h + pad))),
                          255, -1)
    for x, y, w, h in keep:
        cv2.rectangle(z, (int(x), int(y)), (int(math.ceil(x + w)),
                      int(math.ceil(y + h))), 255, -1)
    return z if z.any() else None


def _box_mask(boxes, shape):
    z = np.zeros(shape[:2], np.uint8)
    for x, y, w, h in boxes:
        cv2.rectangle(z, (int(x), int(y)), (int(math.ceil(x + w)),
                      int(math.ceil(y + h))), 255, -1)
    return z if z.any() else None


def detect_subject(gray, bgr=None, *, hints=None, backends=None,
                   allow_remote=False):
    """Soft-rule fallback chain, all local. Returns
    (subject_mask or None, label, meta dict). meta carries mask_frac and
    border_touch so callers can judge whether the mask is a silhouette
    (single subject, framed) or merely a hint; meta["faces_full"] holds the
    faces with landmarks.

    hints (parse_hints output, or a raw dict in this image's px/norm):
    subject_box seeds GrabCut with that rect; hinted faces join YuNet's;
    label overrides the policy (a non-face label keeps hinted faces for
    protection only, not subject detection). backends ({capability: name},
    lib/imagemodels.py): "segment" replaces GrabCut when its mask is
    usable, "landmarks" augments YuNet, "depth" seeds GrabCut near/far."""
    h, w = gray.shape
    meta = {}
    img = bgr if bgr is not None else gray
    hz = parse_hints(hints, gray.shape)
    backends = _check_backends(backends)

    # 1) YuNet face detection (bundled Apache-2.0 model), plus a landmarks
    # backend and hinted faces when given
    full = people = _all_faces(gray, bgr, hz, backends, allow_remote)
    if full:
        meta["faces_full"] = full
    label_hint = hz["label"] if hz else None
    if label_hint not in (None, "face", "person"):
        full = [f for f in full if f.get("source") != "hint"]
    faces = [tuple(f["box"]) for f in full]
    if hz and hz["subject_box"] is not None:
        if faces:
            meta["faces"] = faces
        x, y, bw, bh = hz["subject_box"]
        mask = _backend_mask(img, backends, allow_remote, people, meta, rect=True)
        if mask is None:
            mask = _grabcut_seeded(img, backends, allow_remote, people,
                                   (int(x), int(y), max(2, int(bw)), max(2, int(bh))))
            meta["detector"] = "hint-box"
        _mask_meta(mask, meta)
        if label_hint:
            label = label_hint
        elif faces:
            label = "face" if _big_single_face(faces, w, h) else "person"
        else:
            label = _heuristic_label(gray, mask, meta)
        return mask, label, meta
    if len(faces):
        meta["faces"] = faces
        x0 = max(0, min(f[0] for f in faces) - w // 12)
        y0 = max(0, min(f[1] for f in faces) - h // 12)
        x1 = min(w, max(f[0] + f[2] for f in faces) + w // 12)
        y1 = min(h, max(f[1] + f[3] for f in faces) + int(h * 0.35))
        mask = _backend_mask(img, backends, allow_remote, people, meta, rect=True)
        if mask is None:
            mask = _grabcut_seeded(img, backends, allow_remote, people,
                                   (x0, y0, x1 - x0, y1 - y0))
            meta["detector"] = "face"
        _mask_meta(mask, meta)
        return mask, label_hint or ("face" if _big_single_face(faces, w, h)
                                    else "person"), meta

    # 1b) a segmentation backend's mask, when it looks like a framed subject
    mask = _backend_mask(img, backends, allow_remote, people, meta)
    if mask is not None:
        _mask_meta(mask, meta)
        return mask, label_hint or _heuristic_label(gray, mask, meta), meta

    # 2) colour GrabCut seeded by a thin border ring: everything but the
    # frame edge starts as probable subject, so a subject that nearly fills
    # the frame (tail to nose) is not clipped by a fixed centre rect
    mask = _grabcut_seeded(img, backends, allow_remote, people, None)
    if mask is not None and 0.04 < mask.mean() / 255 < 0.92:
        meta["detector"] = "grabcut" if not backends.get("depth") else "grabcut+depth"
        _mask_meta(mask, meta)
        return mask, label_hint or _heuristic_label(gray, mask, meta), meta

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


def _check_backends(backends):
    """{capability: registered backend name} -> validated dict ({} if None)."""
    if not backends:
        return {}
    import imagemodels
    if not isinstance(backends, dict):
        raise imagemodels.BackendError(
            "backends: expected {capability: backend name}, e.g. "
            "{'segment': 'my-seg'}")
    for cap, name in backends.items():
        if cap not in imagemodels.CAPABILITIES:
            raise imagemodels.BackendError(
                f"backends: unknown capability {cap!r}; use one of "
                f"{', '.join(imagemodels.CAPABILITIES)}")
        b = imagemodels.get_backend(name)          # raises when unregistered
        if b["capability"] != cap:
            raise imagemodels.BackendError(
                f"backends[{cap!r}]: {name!r} is a {b['capability']!r} backend")
    return dict(backends)


def _run_backend(cap, img, backends, allow_remote, faces):
    import imagemodels
    bgr = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return imagemodels.run_backend(backends[cap], bgr, cap,
                                   allow_remote=allow_remote, faces=len(faces))


def _backend_mask(img, backends, allow_remote, faces, meta, rect=False):
    """A "segment" backend's mask when it is usable — a framed single
    subject (_mask_usable), or for the face / subject-box branches any
    mask of sane size (2-95% of the frame; there it is a hint) — else None
    and GrabCut runs."""
    if not backends.get("segment"):
        return None
    m = _run_backend("segment", img, backends, allow_remote, faces)
    frac = float((m > 0).mean())
    ok = (0.02 <= frac <= 0.95) if rect else _mask_usable(m)
    if not ok:
        meta["backend_rejected"] = backends["segment"]
        return None
    meta["detector"] = "backend:" + backends["segment"]
    return m


def _grabcut_seeded(img, backends, allow_remote, faces, rect):
    """_grabcut, with a "depth" backend's map as an extra near/far seed."""
    depth = None
    if backends.get("depth"):
        depth = _run_backend("depth", img, backends, allow_remote, faces)
    return _grabcut(img, rect, depth=depth)


def _grabcut(img, rect=None, iters=5, depth=None):
    """GrabCut subject mask; None on failure/empty. `img` is BGR (colour
    separates a white dog from red barn + green grass — grayscale cannot)
    or gray. Runs on a <=GRABCUT_WORK px copy (the GMM does not need more
    and it is ~10x faster), with a fixed RNG seed so the k-means init is
    reproducible call after call. rect=None seeds a GRABCUT_MARGIN border
    ring as background. Small islands (< 25% of the largest component) are
    dropped; comparable components stay (a toy beside a toy).
    depth (optional float map, larger = nearer, from a depth backend): the
    farthest DEPTH_FAR share of the rect starts as probable background
    instead of probable subject — a separation cue where colours match."""
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
        if depth is None:
            cv2.grabCut(small, mask, r, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
        else:
            d = cv2.resize(depth.astype(np.float32), (sw, sh),
                           interpolation=cv2.INTER_AREA)
            rx, ry, rw_, rh_ = r
            mask[:] = cv2.GC_BGD
            mask[ry:ry + rh_, rx:rx + rw_] = cv2.GC_PR_FGD
            inside = mask == cv2.GC_PR_FGD
            if inside.any():
                far = float(np.percentile(d[inside], DEPTH_FAR * 100))
                mask[inside & (d <= far)] = cv2.GC_PR_BGD
            cv2.grabCut(small, mask, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
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
                detail="medium", drop=False, protect=None):
    """Binary ink mask (255 = line) from a grayscale photo. subject_mask
    (optional) applies the soft background rule, or — with drop=True —
    zones the clean style's wide-block pass: lenient on the silhouette
    ring (catch the low-contrast outline), strict inside the subject
    (fur/skin SHADING is not a line on a coloring page). _trace removes
    the background itself afterwards. protect (uint8 zone mask, optional):
    feature zones keep the lenient pass, skip the bright-area ceiling and
    — in sketch style — add the clean fine pass (ridges miss small dots)."""
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
        if protect is not None:
            block = max(9, int(policy["block"] * mult) // 2 * 2 + 1)
            fine = cv2.adaptiveThreshold(smooth, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY_INV, block,
                                         max(3.0, policy["edge_c"] * mult))
            ink = np.where(protect > 0, cv2.bitwise_or(ink, fine), ink).astype(np.uint8)
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
            interior = zone == 2
            if protect is not None:
                interior &= protect == 0
            ink2 = np.where(interior, strict, ink2).astype(np.uint8)
        ink = cv2.bitwise_or(ink, ink2)
        # soften flat-area noise via Otsu ceiling — but never clear more than
        # 55% of the ink (guard against killing whole subjects on dark photos)
        otsu, _ = cv2.threshold(smooth, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ceiling = (smooth > otsu + 55)
        if ceiling.mean() < 0.55:
            if protect is not None:
                ceiling &= protect == 0
            ink[ceiling] = 0

    ink = _desplinter(ink, mult, protect)
    if subject_mask is not None and not drop:
        ink = _focus_subject(ink, subject_mask, mult, protect)
    return ink


def _desplinter(ink, mult, protect=None):
    """Morphological anti-splinter: bridge gaps, delete specks/short runs.
    Inside protect zones the opening is skipped (it erases 2px glasses
    frames) and components down to PROTECT_MIN_COMPONENT px survive (a
    nostril, a mole)."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, k, iterations=2)
    closed = ink
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, k)
    if protect is not None:
        ink = np.where(protect > 0, closed, ink).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    keep = np.zeros_like(ink)
    min_area = MIN_COMPONENT * (1.5 if mult > 1.2 else 1.0)
    prot = None
    if protect is not None and n > 1:
        from scipy import ndimage
        prot = np.asarray(ndimage.mean(protect > 0, labels, np.arange(1, n))) >= 0.5
    for i in range(1, n):
        x, y, w_, h_, area = stats[i]
        if area >= min_area and max(w_, h_) >= 5:
            keep[labels == i] = 255
        elif prot is not None and prot[i - 1] and area >= PROTECT_MIN_COMPONENT:
            keep[labels == i] = 255
    return keep


def _focus_subject(ink, subject_mask, mult, protect=None):
    """Soft rule (bg="soft" policies): background ink thinned (thicker
    threshold), subject kept — implemented as extra erosion of ink OUTSIDE
    the subject mask (and outside any protect zone)."""
    if protect is not None:
        subject_mask = cv2.bitwise_or(subject_mask, protect)
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


def _drop_background(ink, subject_mask, policy, mult, protect=None):
    """Hard rule (bg="drop" policies): keep ink inside the DILATED subject
    mask only; everything else (fence boards, grass, wallpaper) goes. The
    survivors are re-desplintered because cutting at the mask edge leaves
    stubs. protect zones (feature zones, keep boxes) always survive."""
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
    if protect is not None:
        zone = cv2.bitwise_or(zone, protect)
    keep = cv2.bitwise_and(ink, zone)
    return _desplinter(keep, mult, protect)


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
              gray=None, drop=False, protect=None):
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
    protect (uint8 zone mask, optional — feature zones from landmarks and
    keep boxes): components mostly inside it are FEATURES — small blobs
    (pupil, nostril, mole) are kept when darker than PROTECT_DARK_RATIO x
    their own surround, even below the dot radius; strokes
    there need only PROTECT_MIN_LEN, skip the texture rule, simplify with
    PROTECT_SIMPLIFY x epsilon, draw at the interior weight and ride
    outside the max_strokes cut (up to PROTECT_MAX_STROKES).
    """
    policy = policy or POLICIES["generic"]
    mult = DETAIL_MULT.get(detail, 1.0)
    ih, iw = ink.shape
    maxdim = max(ih, iw)
    s, ox, oy = _page_fit(iw, ih)
    eps = max(1.0, policy["simplify"] * mult)
    eps_p = max(0.5, eps * PROTECT_SIMPLIFY)
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
    prot = np.zeros(n - 1, bool)
    if protect is not None:
        prot = np.asarray(ndimage.mean(protect > 0, labels, idx)) >= 0.5
        # a feature nested in another component's hole (an eye inside a
        # glasses rim) has no EXTERNAL contour of its own: measure it
        for i in 1 + np.nonzero(prot & (perim[1:] == 0))[0]:
            x, y, w_, h_ = stats[i, :4]
            sub = (labels[y:y + h_, x:x + w_] == i).astype(np.uint8)
            cs, _h2 = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            perim[i] = max((cv2.arcLength(c, True) for c in cs), default=0.0)
    elong = perim[1:] / (4.0 * rmax + 1e-6)
    is_blob = (elong < BLOB_ELONGATION) & (rmax >= 2.0) & (area[1:] >= 16)
    # a blob narrower than ~0.4% of the image is a dot, not a feature (an
    # eye is wider): dots are neither colorable nor readable
    dot = rmax < max(2.0, BLOB_MIN_RADIUS * maxdim)
    if protect is not None:
        small = (elong < BLOB_ELONGATION) & (rmax >= 1.0) & \
            (area[1:] >= PROTECT_MIN_COMPONENT)
        is_blob = is_blob | (prot & small)

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
        if protect is not None:
            # features are judged against their own surround (a nostril is
            # dark against skin, not against a subject that includes hair)
            for j in np.nonzero(is_blob & prot & ~keep_blob)[0]:
                i = j + 1
                x, y, w_, h_ = stats[i, :4]
                y0, x0 = max(0, y - 4), max(0, x - 4)
                lab = labels[y0:y + h_ + 4, x0:x + w_ + 4]
                ring = cv2.dilate((lab == i).astype(np.uint8), np.ones((5, 5), np.uint8))
                ring = (ring > 0) & (lab == 0)
                if not ring.any():
                    continue
                around = float(gray[y0:y + h_ + 4, x0:x + w_ + 4][ring].mean())
                if mean_gray[j] < PROTECT_DARK_RATIO * around or large[j]:
                    keep_blob[j] = True

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

    def prot_of(pts):
        if protect is None:
            return 0.0
        ps = [protect[min(ih - 1, max(0, int(y))), min(iw - 1, max(0, int(x)))]
              for x, y in pts]
        return float((np.asarray(ps) > 0).mean())

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
            cp = protect is not None and prot_of(
                [(float(q[0][0]), float(q[0][1])) for q in cnt]) >= 0.5
            if cp:
                if cv2.arcLength(cnt, True) < PROTECT_MIN_LEN or areas[i] < 4:
                    continue
                approx = cv2.approxPolyDP(_smooth_contour(cnt, k=3), eps_p, True)
            else:
                if cv2.arcLength(cnt, True) < MIN_STROKE_LEN or areas[i] < 16:
                    continue
                approx = cv2.approxPolyDP(_smooth_contour(cnt, k=7), eps, True)
            pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
            if len(pts) < 3:
                continue
            inner, outside = zone_of(pts)
            sw = SW_SUBJECT if cp else SW_BACKGROUND if outside > 0.5 else (
                SW_SUBJECT if inner >= 0.6 else SW_SILHOUETTE)
            entries.append(dict(pts=pts, closed=True, rank=areas[i], sw=sw,
                                area=areas[i], prot=cp))

    # ---- ribbons: centreline. Length floors apply to the whole connected
    # skeleton STRUCTURE (a ragged band thins into many short branches
    # between junctions — the outline is long as a whole, a grass tuft is
    # not), spurs are judged per branch.
    if ribbon_ink.any():
        thin = _thin(ribbon_ink)
        skel = _prune(thin, SPUR_LEN)
        if protect is not None:                # a short brow is not a spur
            skel = np.where(protect > 0, _prune(thin, PROTECT_SPUR),
                            skel).astype(np.uint8)
        _nc, clab = cv2.connectedComponents(skel, connectivity=8)
        polys = []
        struct_len, struct_inner, struct_box = {}, {}, {}
        struct_prot = {}
        for pts, closed, jends in _skeleton_polylines(skel):
            length = _poly_len(pts)
            pf = prot_of(pts)
            if pf >= 0.5:
                if length < 3 or (jends == 1 and length < PROTECT_SPUR):
                    continue
            elif length < 4 or (jends == 1 and length < SPUR_LEN):
                continue
            mid = pts[len(pts) // 2]
            cid = int(clab[min(ih - 1, max(0, int(mid[1]))),
                           min(iw - 1, max(0, int(mid[0])))])
            inner, outside = zone_of(pts)
            struct_len[cid] = struct_len.get(cid, 0.0) + length
            struct_inner[cid] = struct_inner.get(cid, 0.0) + length * inner
            struct_prot[cid] = struct_prot.get(cid, 0.0) + length * pf
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
            sp = protect is not None and total and struct_prot[cid] / total >= 0.5
            if sp:
                floor = PROTECT_MIN_LEN               # features: no texture rule
                if total < floor:
                    continue
            elif drop:
                floor = (INTERIOR_FLOOR if s_inner >= 0.6 else RING_FLOOR) * maxdim
                # texture rule: a structure that packs far more line than
                # its extent (fur shadow network) is texture, not a contour
                if not closed and s_inner >= 0.6 and \
                        total > TEXTURE_RATIO * diag and diag < 0.5 * maxdim:
                    continue
            else:
                floor = MIN_STROKE_LEN
            if not sp and total < max(MIN_STROKE_LEN, floor):
                continue
            pts = _smooth_open(pts, 3 if sp else 5)
            arr = np.array(pts, np.float32).reshape(-1, 1, 2)
            approx = cv2.approxPolyDP(arr, eps_p if sp else eps, closed)
            pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
            if len(pts) < (3 if closed else 2):
                continue
            sw = SW_SUBJECT if sp else SW_BACKGROUND if outside > 0.5 else (
                SW_SUBJECT if inner >= 0.6 else SW_SILHOUETTE)
            enclosed = abs(cv2.contourArea(np.array(pts, np.float32))) if closed else 0.0
            entries.append(dict(pts=pts, closed=closed, sw=sw, area=enclosed,
                                rank=max(enclosed, length * length / 4.0),
                                prot=bool(sp)))

    # keep the richest strokes, drop the tail (soft max_strokes rule);
    # protected features have their own budget so busy photos keep them
    entries.sort(key=lambda e: -e["rank"])
    if protect is None:
        entries = entries[:max_strokes]
    else:
        entries = sorted([e for e in entries if e["prot"]][:PROTECT_MAX_STROKES]
                         + [e for e in entries if not e["prot"]][:max_strokes],
                         key=lambda e: -e["rank"])
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
              extra="", fidelity=None):
    fid = ""
    if fidelity is not None and fidelity.get("score") is not None:
        fid = f' data-fidelity="{fidelity["score"]:.2f}"'
        if fidelity["missing"]:
            fid += f' data-fidelity-missing="{",".join(fidelity["missing"])}"'
    meta = (f'<g data-policy="{policy_name}" '
            f'data-params="edge_c={params["edge_c"]:.0f};simplify={params["simplify"]:.1f}"'
            f'{fid}>' + "".join(elements) + extra + "</g>")
    return spage(title, meta, caption=caption, layout=layout)


def spage_wrap(elements, title, caption, policy_name, params, layout=None,
               extra="", fidelity=None):
    return _assemble(elements, title, caption, policy_name, params, layout,
                     extra, fidelity)


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


# ---------------------------------------------------------------- feature fidelity
_PATH_TOK = re.compile(r"[MLCQZHVmlcqzhv]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _path_polylines(d):
    """SVG path data -> polylines [(x, y), ...] (curves sampled at 6
    steps): enough geometry to measure how close a drawn line passes to a
    point. Handles M L H V C Q Z, absolute and relative."""
    toks = _PATH_TOK.findall(d)
    lines, cur = [], []
    x = y = sx = sy = 0.0
    cmd, i = "M", 0

    def nums(k):
        nonlocal i
        v = [float(t) for t in toks[i:i + k]]
        i += k
        return v

    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                if cur:
                    cur.append((sx, sy))
                x, y = sx, sy
                continue
        if i >= len(toks) or toks[i].isalpha():
            continue
        rel = cmd.islower()
        c = cmd.upper()
        ox_, oy_ = (x, y) if rel else (0.0, 0.0)
        try:
            if c == "M":
                px, py = nums(2)
                if len(cur) > 1:
                    lines.append(cur)
                x, y = px + ox_, py + oy_
                sx, sy = x, y
                cur = [(x, y)]
                cmd = "l" if rel else "L"
            elif c == "L":
                px, py = nums(2)
                x, y = px + ox_, py + oy_
                cur.append((x, y))
            elif c == "H":
                (px,) = nums(1)
                x = px + ox_
                cur.append((x, y))
            elif c == "V":
                (py,) = nums(1)
                y = py + oy_
                cur.append((x, y))
            elif c in "CQ":
                k = 6 if c == "C" else 4
                v = nums(k)
                ctrl = [(v[j] + ox_, v[j + 1] + oy_) for j in range(0, k, 2)]
                p0 = (x, y)
                for t in (1 / 6, 2 / 6, 3 / 6, 4 / 6, 5 / 6, 1.0):
                    u = 1 - t
                    if c == "C":
                        (c1, c2, p3) = ctrl
                        bx = u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * p3[0]
                        by = u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * p3[1]
                    else:
                        (c1, p3) = ctrl
                        bx = u * u * p0[0] + 2 * u * t * c1[0] + t * t * p3[0]
                        by = u * u * p0[1] + 2 * u * t * c1[1] + t * t * p3[1]
                    cur.append((bx, by))
                x, y = ctrl[-1]
            else:
                i += 1                                 # unsupported: skip a token
        except ValueError:
            break
    if cur:
        lines.append(cur)
    return lines


def _ink_segments(svg_or_elements):
    """(A, B, half_width) arrays of the drawn line segments (page px).
    A page string is cut to its photo-trace group (data-policy up to the
    chrome — title and caption glyphs are not ink of the subject); the
    ground contact line and stroke-less knockout fills never count."""
    if isinstance(svg_or_elements, str):
        svg = svg_or_elements
        k = svg.find("data-policy")
        if k >= 0:
            end = svg.find('<g data-chrome', k)
            svg = svg[k:end if end > 0 else len(svg)]
        svg = re.sub(r'<g data-ground="1">.*?</g>', "", svg, flags=re.S)
        els = re.findall(r"<path\b[^>]*>", svg)
    else:
        els = [e for el in svg_or_elements for e in re.findall(r"<path\b[^>]*>", el)]
    a, b, hw = [], [], []
    for el in els:
        if "data-knockout" in el or 'stroke="none"' in el:
            continue
        m = re.search(r'stroke-width="([\d.]+)"', el)
        half = float(m.group(1)) / 2 if m else 1.5
        for d in re.findall(r' d="([^"]+)"', el):
            for line in _path_polylines(d):
                if len(line) == 1:
                    line = line * 2
                for p, q in zip(line[:-1], line[1:]):
                    a.append(p)
                    b.append(q)
                    hw.append(half)
    return (np.asarray(a, np.float64).reshape(-1, 2),
            np.asarray(b, np.float64).reshape(-1, 2), np.asarray(hw, np.float64))


def _fidelity_points(face):
    """[(name, (x, y) image px, radius x IOD)] for one face: the five
    landmarks, then each declared feature (its box centre; glasses = the
    bridge between the eyes; gap_tooth/braces = mouth centre; freckles =
    the image-left cheek; dimples = beside the image-left mouth corner;
    headband = top of the face box)."""
    lm = face["landmarks"]
    iod, _ang, up = _face_frame(face)
    pts = [(k, lm[k], FIDELITY_RADIUS) for k in FACE_KEYS]
    mid = ((lm["eye_l"][0] + lm["eye_r"][0]) / 2, (lm["eye_l"][1] + lm["eye_r"][1]) / 2)
    mc = ((lm["mouth_l"][0] + lm["mouth_r"][0]) / 2,
          (lm["mouth_l"][1] + lm["mouth_r"][1]) / 2)
    fboxes = face.get("feature_boxes") or {}
    for name in face.get("features") or ():
        if name in fboxes:
            x, y, w, h = fboxes[name]
            pts.append((name, (x + w / 2, y + h / 2),
                        max(FIDELITY_RADIUS, 0.5 * math.hypot(w, h) / iod)))
        elif name == "glasses":
            pts.append((name, mid, FIDELITY_RADIUS))
        elif name in ("gap_tooth", "braces"):
            pts.append((name, mc, FIDELITY_RADIUS))
        elif name == "freckles":
            e = lm["eye_l"]
            pts.append((name, (e[0] - up[0] * 0.55 * iod, e[1] - up[1] * 0.55 * iod), 0.3))
        elif name == "dimples":
            pts.append((name, (lm["mouth_l"][0] - 0.22 * iod, lm["mouth_l"][1]), 0.2))
        elif name == "headband":
            bx, by, bw, bh = face["box"]
            pts.append((name, (bx + bw / 2, by + 0.02 * bh), 0.3))
    return iod, pts


def feature_fidelity(svg_or_elements, faces, image_shape):
    """Does traced ink sit on each facial feature? faces (detect_faces_full
    / hint format, IMAGE px of an image of image_shape (h, w[, c])) are
    mapped to the page with the same _page_fit transform the trace used;
    a feature is present when a drawn line (its stroke edge, not just its
    centreline) passes within FIDELITY_RADIUS x the interocular distance.
    svg_or_elements: a photo_to_svg / trace_lineart page, a fragment, or a
    list of path elements in page coords. Returns
      {"score": hits / total in [0, 1] (None without faces), "hits", "total",
       "missing": ["face0.nose", ...],
       "faces": [{"iod": page px, "features": {name: {"hit", "dist", "radius"}}}]}
    It checks PRESENCE at the right place — not shape: a generative
    redraw that moves the eyes or draws a different face drops it."""
    ih, iw = image_shape[:2]
    s, ox, oy = _page_fit(iw, ih)
    a, b, hw = _ink_segments(svg_or_elements)
    ab = b - a
    ll = (ab * ab).sum(1) + 1e-12
    out = {"score": None, "hits": 0, "total": 0, "missing": [], "faces": []}
    for fi, face in enumerate(faces or ()):
        iod, pts = _fidelity_points(face)
        rec = {"iod": round(iod * s, 1), "features": {}}
        for name, (px, py), rf in pts:
            p = np.array([px * s + ox, py * s + oy])
            r = rf * iod * s
            if len(a):
                t = np.clip(((p - a) * ab).sum(1) / ll, 0.0, 1.0)
                d = np.hypot(*(a + ab * t[:, None] - p).T) - hw
                dist = float(max(0.0, d.min()))
            else:
                dist = float("inf")
            hit = dist <= r
            key = name if name not in rec["features"] else f"{name}_{len(rec['features'])}"
            rec["features"][key] = {"hit": bool(hit), "dist": round(dist, 1),
                                    "radius": round(r, 1)}
            out["total"] += 1
            out["hits"] += int(hit)
            if not hit:
                out["missing"].append(f"face{fi}.{key}")
        out["faces"].append(rec)
    if out["total"]:
        out["score"] = round(out["hits"] / out["total"], 3)
    return out


def read_fidelity(svg):
    """The data-fidelity score recorded on a page, or None."""
    m = re.search(r'data-fidelity="([\d.]+)"', svg)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------- line art ingestion
LINEART_THR = (64, 200)            # Otsu threshold clamp for a line drawing (dark on light)
LINEART_ASPECT_TOL = 0.03          # line art vs photo aspect mismatch tolerated (then resized)


def _load_lineart(src, shape=None, max_dim=1600):
    """Line drawing (file path or array: gray, BGR, BGRA, float 0-1 or
    uint8; dark lines on a light ground) -> uint8 gray. With shape (the
    photo's working (h, w)) it is resized onto the photo's pixel grid —
    the aspect ratio must match within LINEART_ASPECT_TOL, or landmarks
    and mask would not line up; without, it is capped at max_dim."""
    if isinstance(src, (str, os.PathLike)):
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(src))
        if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im)       # transparent = paper
        g = np.array(im.convert("L"))
    else:
        arr = np.asarray(src)
        if arr.dtype == bool:
            arr = np.where(arr, 0, 255).astype(np.uint8)   # True = line
        elif arr.dtype != np.uint8:
            arr = np.clip(arr.astype(np.float64) * (255.0 if arr.max() <= 1.0 else 1.0),
                          0, 255).astype(np.uint8)
        if arr.ndim == 3 and arr.shape[2] == 4:
            a = arr[:, :, 3:4].astype(np.float32) / 255.0
            arr = (arr[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_BGR2GRAY)
        if arr.ndim != 2:
            raise ValueError(f"lineart: expected an image array, got shape {arr.shape}")
        g = arr
    h, w = g.shape
    if shape is not None:
        th, tw = shape[:2]
        if abs((w / h) / (tw / th) - 1.0) > LINEART_ASPECT_TOL:
            raise ValueError(
                f"lineart is {w}x{h} but the photo is {tw}x{th}: the aspect "
                "ratios differ, so landmarks and the subject mask would not line "
                "up — generate the line art at the photo's aspect (or crop the "
                "photo to match)")
        if (h, w) != (th, tw):
            g = cv2.resize(g, (tw, th), interpolation=cv2.INTER_AREA
                           if w > tw else cv2.INTER_LINEAR)
    elif max(h, w) > max_dim:
        s = max_dim / max(h, w)
        g = cv2.resize(g, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    return g


def _pupils(gray, faces, dropz=None):
    """Filled iris dots for protected faces, page coords. Per eye landmark:
    the dark component nearest the landmark inside a PUPIL_WINDOW x iod
    window (darker than the window's min + PUPIL_DARK x its range) becomes a
    dot at its centroid, radius from its area clamped to PUPIL_R x iod. A
    window without real contrast (a closed eye, a soft photo) adds nothing."""
    ih, iw = gray.shape
    s, ox, oy = _page_fit(iw, ih)
    out = []
    for f in faces:
        lm = f.get("landmarks") or {}
        if "eye_l" not in lm or "eye_r" not in lm:
            continue
        iod = math.hypot(lm["eye_r"][0] - lm["eye_l"][0], lm["eye_r"][1] - lm["eye_l"][1])
        if iod < 12:
            continue
        R = max(3, int(round(PUPIL_WINDOW * iod)))
        for key in ("eye_l", "eye_r"):
            ex, ey = (int(round(v)) for v in lm[key])
            x0, y0, x1, y1 = max(0, ex - R), max(0, ey - R), min(iw, ex + R + 1), min(ih, ey + R + 1)
            if x1 - x0 < 3 or y1 - y0 < 3:
                continue
            if dropz is not None and dropz[ey if ey < ih else ih - 1, ex if ex < iw else iw - 1]:
                continue
            win = cv2.GaussianBlur(gray[y0:y1, x0:x1], (3, 3), 0).astype(np.float32)
            lo, med = float(win.min()), float(np.median(win))
            if med - lo < PUPIL_CONTRAST:
                continue
            # seed at the darkest pixel near the landmark; the iris is the dark
            # component around it, cut to a disk so a glasses rim or a lash
            # line touching it does not join in
            hh, ww = win.shape
            yy, xx = np.mgrid[0:hh, 0:ww]
            core = np.hypot(xx - (ex - x0), yy - (ey - y0)) <= 0.5 * R
            sy, sx = np.unravel_index(np.where(core, win, 1e9).argmin(), win.shape)
            dark = (win <= lo + PUPIL_DARK * (med - lo)) & \
                (np.hypot(xx - sx, yy - sy) <= 0.55 * R)
            n, lab = cv2.connectedComponents(dark.astype(np.uint8), connectivity=8)
            blob = lab == lab[sy, sx]
            if not dark[sy, sx] or not blob.any():
                continue
            ys_, xs_ = np.nonzero(blob)
            r = math.sqrt(len(xs_) / math.pi)
            r = min(PUPIL_R[1] * iod, max(PUPIL_R[0] * iod, r))
            cx, cy = xs_.mean() + x0, ys_.mean() + y0
            out.append(f'<circle data-pupil="1" cx="{_f(cx * s + ox)}" cy="{_f(cy * s + oy)}" '
                       f'r="{_f(r * s)}" fill="black" stroke="black" stroke-width="{_f(SW_SUBJECT)}"/>')
    return out


def _lineart_ink(la, mult, protect=None):
    """Line drawing -> binary ink: Otsu threshold (clamped to LINEART_THR,
    so faint anti-aliased lines survive a resize), a light close, then a
    component speck filter. No opening — model line art is often 1-2px."""
    otsu, _ = cv2.threshold(la, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thr = min(LINEART_THR[1], max(LINEART_THR[0], otsu))
    ink = np.where(la < thr, 255, 0).astype(np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    if n <= 1:
        return ink
    area = stats[1:, cv2.CC_STAT_AREA]
    keep = area >= MIN_COMPONENT * (1.5 if mult > 1.2 else 1.0)
    if protect is not None:
        from scipy import ndimage
        prot = np.asarray(ndimage.mean(protect > 0, labels, np.arange(1, n))) >= 0.5
        keep |= prot & (area >= PROTECT_MIN_COMPONENT)
    return np.where(np.isin(labels, 1 + np.nonzero(keep)[0]), 255, 0).astype(np.uint8)


# ---------------------------------------------------------------- public API
def photo_to_svg(photo_path, *, style="clean", subject="auto", detail="medium",
                 title=None, caption=None, max_dim=1600, qa=True,
                 layout=None, hints=None, backends=None, allow_remote=False,
                 lineart=None, protect_face=None):
    """Photo file -> standalone coloring page SVG string. layout="creative"
    marks open-composition pages (e.g. sketch traces) for the validator.
    A background-dropped subject stands on a ground contact line.

    hints: vision-hints dict or JSON path (parse_hints). backends:
    {capability: registered name} (lib/imagemodels.py); a remote backend
    raises PrivacyError unless allow_remote=True. lineart: a line drawing
    (path or array) traced INSTEAD of the photo's own edges — see
    trace_lineart. protect_face: None = the policy's flag (or True when
    hints name faces), True/False forces it. Pages with faces record
    feature_fidelity as data-fidelity on the policy group."""
    tr = _trace(photo_path, style, subject, detail, max_dim, hints=hints,
                backends=backends, allow_remote=allow_remote, lineart=lineart,
                protect_face=protect_face)
    if qa:
        for _ in range(QA_MAX_ROUNDS):
            svg = _assemble(tr["elements"], title, caption, tr["label"],
                            tr["params"], layout, _ground_line(tr), tr["fidelity"])
            rep = _qa_report(svg)
            if rep["ok"] and (rep["raster"] is None
                              or rep["raster"]["sliver_count"] <= 70):
                break
            if not _qa_adjust(POLICIES[tr["label"]], tr["params"], rep):
                break
            tr = _trace(photo_path, style, subject, detail, max_dim,
                        overrides=tr["params"], detected=tr["detected"],
                        ctx=tr["ctx"])
    return spage_wrap(tr["elements"], title, caption, tr["label"], tr["params"],
                      layout, _ground_line(tr), tr["fidelity"])


def photo_to_fragment(photo_path, *, style="clean", subject="auto",
                      detail="medium", max_dim=1600, pad=20, hints=None,
                      backends=None, allow_remote=False, lineart=None,
                      protect_face=None):
    """Photo -> G()-placeable charlib fragment. Local origin = the traced
    art's BOTTOM-CENTRE (same feet-anchor convention as every charlib
    helper): G(x, ground_y, fragment, s) stands the subject on a ground
    line. No ground line of its own — the scene supplies it. hints /
    backends / lineart / protect_face as for photo_to_svg."""
    tr = _trace(photo_path, style, subject, detail, max_dim, hints=hints,
                backends=backends, allow_remote=allow_remote, lineart=lineart,
                protect_face=protect_face)
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
                   caption=None, num=None, hints=None, backends=None,
                   allow_remote=False, lineart=None, protect_face=None):
    """Traced photo subject matted onto a scene kit body beside charlib
    art. The fragment self-anchors at its ink bottom-centre, so it stands
    ON ground_y at (x, ground_y) like any charlib figure."""
    frag = photo_to_fragment(photo_path, style=style, detail=detail,
                             hints=hints, backends=backends,
                             allow_remote=allow_remote, lineart=lineart,
                             protect_face=protect_face)
    body = scene_body + G(x, ground_y, matted(frag, scale=scale), scale)
    return spage(title, body, caption=caption, num=num)


def trace_lineart(lineart, photo=None, *, subject="auto", detail="medium",
                  title=None, caption=None, max_dim=1600, qa=True,
                  layout=None, hints=None, backends=None, allow_remote=False,
                  protect_face=None, fragment=False):
    """A line drawing from an image model (a local ControlNet line-art
    preprocessor, an informative-drawings ONNX, or a generation model asked
    to "redraw as a coloring page") -> house-style page: thresholded,
    centreline-traced, stroke-tiered and QA'd like a photo trace.

    With photo= the drawing is aligned onto the photo's pixel grid (same
    aspect required) and the subject mask, landmarks, protection zones and
    feature_fidelity all come from the PHOTO — so a generative redraw that
    moved the eyes or drew a different face scores low: read_fidelity(svg)
    below FIDELITY_MIN means reject or re-generate. Without a photo, faces
    come from hints only (in the drawing's px). fragment=True returns a
    photo_to_fragment-style fragment instead of a page."""
    if fragment:
        return photo_to_fragment(photo, detail=detail, subject=subject,
                                 max_dim=max_dim, hints=hints,
                                 backends=backends, allow_remote=allow_remote,
                                 lineart=lineart, protect_face=protect_face)
    return photo_to_svg(photo, subject=subject, detail=detail, title=title,
                        caption=caption, max_dim=max_dim, qa=qa, layout=layout,
                        hints=hints, backends=backends,
                        allow_remote=allow_remote, lineart=lineart,
                        protect_face=protect_face)


def _trace(photo_path, style, subject, detail, max_dim, overrides=None,
           detected=None, hints=None, backends=None, allow_remote=False,
           lineart=None, protect_face=None, ctx=None):
    """One pass photo -> elements. Returns a dict: elements, label, params,
    ink, mask, drop (background removed?), detected (cached detection so
    QA rounds do not rerun GrabCut), fidelity (None without faces) and ctx
    (cached hints / line art / zones for the QA rounds)."""
    if ctx is None:
        ctx = dict(hints=hints, backends=_check_backends(backends),
                   allow_remote=allow_remote, lineart=lineart,
                   protect_face=protect_face)
    backends = ctx["backends"]
    if photo_path is None:
        if ctx["lineart"] is None:
            raise ValueError("a photo path is required (or lineart= alone)")
        if "la" not in ctx:
            ctx["la"] = _load_lineart(ctx["lineart"], None, max_dim)
        gray = ctx["la"]
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        src = ctx["lineart"]
        ref_size = _upright_size(src) if isinstance(src, (str, os.PathLike)) \
            else (np.asarray(src).shape[1], np.asarray(src).shape[0])
    else:
        gray, bgr = load_photo(photo_path, max_dim)
        ref_size = _upright_size(photo_path)
    if "hz" not in ctx:
        ctx["hz"] = parse_hints(ctx["hints"], gray.shape, ref_size)
    hz = ctx["hz"]
    if detected is None:
        if subject == "auto" and photo_path is not None:
            detected = detect_subject(gray, bgr, hints=hz, backends=backends,
                                      allow_remote=allow_remote)
        else:
            label = subject if subject in POLICIES else (
                (hz and hz["label"]) or "generic")
            faces = (_all_faces(gray, bgr, hz, backends, allow_remote)
                     if photo_path is not None else (hz["faces"] if hz else []))
            detected = (None, label, {"faces_full": faces} if faces else {})
    mask, label, meta = detected
    faces = meta.get("faces_full", [])
    policy = dict(POLICIES.get(label, POLICIES["generic"]))
    if overrides:
        policy.update({k: v for k, v in overrides.items() if k in policy})
    mult = DETAIL_MULT.get(detail, 1.0)
    drop = policy.get("bg") == "drop" and _mask_usable(mask, meta)

    # feature protection: landmark zones (protect_face) + hinted keep boxes;
    # hinted drop boxes win over both
    if "protect" not in ctx:
        pf = ctx["protect_face"]
        on = pf if pf is not None else bool(
            policy.get("protect_face") or any(f.get("source") == "hint" for f in faces))
        keep = hz["keep"] if hz else []
        protect = protection_zones(faces if on else [], gray.shape, keep) \
            if ((on and faces) or keep) else None
        dropz = _box_mask(hz["drop"], gray.shape) if hz and hz["drop"] else None
        if protect is not None and dropz is not None:
            protect = np.where(dropz > 0, 0, protect).astype(np.uint8)
            protect = protect if protect.any() else None
        ctx["protect"], ctx["dropz"] = protect, dropz
        ctx["protect_faces"] = bool(on and faces)
    protect, dropz = ctx["protect"], ctx["dropz"]

    def finish(ink, shade=gray, lines=False):
        if drop:
            ink = _drop_background(ink, mask, policy, mult, protect)
        elif mask is not None and not lines:
            ink = _focus_subject(ink, mask, mult, protect)
        if dropz is not None:
            ink = np.where(dropz > 0, 0, ink).astype(np.uint8)
        return ink, vectorize(ink, policy=policy, detail=detail,
                              subject_mask=mask, gray=shade, drop=drop,
                              protect=protect)

    if ctx["lineart"] is not None or backends.get("lineart"):
        # an image model drew the lines: trace ITS ink (centreline, tiers,
        # zones) while mask, landmarks and fidelity stay with the photo.
        # (No soft-rule erosion: model line art is often 1-2px wide.)
        if "la_aligned" not in ctx:
            if ctx["lineart"] is not None:
                ctx["la_aligned"] = gray if photo_path is None else \
                    _load_lineart(ctx["lineart"], gray.shape, max_dim)
            else:
                la = _run_backend("lineart", bgr, backends, allow_remote, faces)
                ctx["la_aligned"] = _load_lineart(la, gray.shape, max_dim)
        la = ctx["la_aligned"]
        ink, elements = finish(_lineart_ink(la, mult, protect), shade=la,
                               lines=True)
    else:
        ink = extract_ink(gray, style=style, policy=policy, detail=detail,
                          subject_mask=mask if drop else None, drop=drop,
                          protect=protect)
        # graceful degradation: sketch on an ultra-soft photo can find almost
        # nothing — fall back to the clean extractor rather than an empty page
        if style == "sketch":
            n_comp, _labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
            solid = sum(1 for i in range(1, n_comp) if stats[i, 4] >= 40)
            if solid < 3:
                ink = extract_ink(gray, style="clean", policy=policy,
                                  detail=detail,
                                  subject_mask=mask if drop else None,
                                  drop=drop, protect=protect)
        ink, elements = finish(ink)
        # ...and the same degradation after vectorizing: flat, step-edged
        # subjects give the ridge detector almost nothing to follow
        if style == "sketch" and _elements_length(elements) < SKETCH_MIN_LENGTH:
            ink, elements = finish(extract_ink(gray, style="clean", policy=policy,
                                               detail=detail,
                                               subject_mask=mask if drop else None,
                                               drop=drop, protect=protect))
    if ctx.get("protect_faces") and ctx["lineart"] is None \
            and not backends.get("lineart"):
        # an eye's lids and lashes trace as a squiggle that reads "asleep";
        # the iris, drawn as a filled dot, is what reads "open eye" at
        # coloring-book size (the parametric faces' dot-eye convention)
        elements = elements + _pupils(gray, faces, dropz)
    if drop and elements:
        # a traced subject is a FOREGROUND object: its open silhouette
        # cannot knock out scene lines behind it the way a filled helper
        # does, so the subject mask itself goes first as a white,
        # stroke-less knockout (matted() adds the halo around the strokes)
        elements = _knockout(mask, policy, mult) + elements
    fidelity = feature_fidelity(elements, faces, gray.shape) if faces else None
    return dict(elements=elements, label=label, params=policy, ink=ink,
                mask=mask, drop=drop, detected=detected, fidelity=fidelity,
                faces=faces, ctx=ctx, extent=_elements_extent(elements))


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
    elif kind == "face_features":
        # feature-fidelity tier: a head-and-shoulders portrait with KNOWN
        # landmarks (synthetic_face_truth) — glasses, a mole, mottled skin
        _draw_face_features(img, size)
    if kind == "low_light":
        img = (img * 0.3 + 8).astype(np.float32)
        grain = rng.normal(0, 10, img.shape).astype(np.float32)
    else:
        grain = rng.normal(0, 6, img.shape).astype(np.float32)
    # soft shadow + sensor grain (a portrait lens is sharper: features are
    # small, so the face tier gets a lighter blur)
    img = cv2.GaussianBlur(img, (0, 0), 1.2 if kind == "face_features" else 3)
    return np.clip(img + grain, 0, 255).astype(np.uint8)


# face_features fixture geometry, fractions of the frame size (IMAGE-left
# first). IOD 0.125 x 640 = 80px: a school-portrait framing, head ~40% of
# the frame width
_FACE_GEOM = dict(eye_l=(0.4375, 0.455), eye_r=(0.5625, 0.455),
                  nose=(0.50, 0.535), mouth_l=(0.455, 0.605),
                  mouth_r=(0.545, 0.605), mole=(0.588, 0.575),
                  box=(0.33, 0.30, 0.34, 0.40))


def _draw_face_features(img, size):
    def P_(k):
        return (int(round(_FACE_GEOM[k][0] * size)), int(round(_FACE_GEOM[k][1] * size)))

    def L(v):
        return max(1, int(round(v * size)))
    skin, hair, dark = (150, 172, 205), (52, 46, 40), (35, 32, 30)
    cx = size // 2
    cv2.ellipse(img, (cx, size), (L(0.36), L(0.22)), 0, 0, 360, (140, 95, 60), -1)
    cv2.rectangle(img, (cx - L(0.05), L(0.66)), (cx + L(0.05), L(0.80)), skin, -1)
    cv2.ellipse(img, (cx, L(0.39)), (L(0.195), L(0.19)), 0, 0, 360, hair, -1)
    cv2.ellipse(img, (cx, L(0.505)), (L(0.165), L(0.205)), 0, 0, 360, skin, -1)
    rng = np.random.default_rng(7)                 # mottled skin: texture, not lines
    for _ in range(70):
        px = int(cx + rng.integers(-L(0.14), L(0.14)))
        py = int(L(0.505) + rng.integers(-L(0.17), L(0.17)))
        d = int(rng.integers(-14, 15))
        cv2.circle(img, (px, py), int(rng.integers(2, 6)),
                   tuple(c + d for c in skin), -1)
    for k in ("eye_l", "eye_r"):
        ex, ey = P_(k)
        cv2.ellipse(img, (ex, ey - L(0.047)), (L(0.034), L(0.008)), 0, 195, 345,
                    (70, 70, 85), L(0.006))                       # brow
        cv2.ellipse(img, (ex, ey), (L(0.026), L(0.012)), 0, 0, 360, (235, 235, 235), -1)
        cv2.circle(img, (ex, ey), L(0.010), (60, 70, 90), -1)     # iris
        cv2.circle(img, (ex, ey), L(0.004), (15, 15, 15), -1)     # pupil
        cv2.ellipse(img, (ex, ey), (L(0.026), L(0.012)), 0, 180, 360, dark, 2)
        cv2.ellipse(img, (ex, ey), (L(0.045), L(0.033)), 0, 0, 360, dark, 2)  # glasses rim
    (lx, ly), (rx, _ry) = P_("eye_l"), P_("eye_r")
    cv2.line(img, (lx + L(0.045), ly - 2), (rx - L(0.045), ly - 2), dark, 2)   # bridge
    nx, ny = P_("nose")
    for sx_ in (-1, 1):                                               # nostrils
        cv2.ellipse(img, (nx + sx_ * L(0.014), ny), (L(0.007), L(0.004)), 0, 0, 360,
                    (80, 92, 118), -1)
    (mlx, mly), (mrx, _m) = P_("mouth_l"), P_("mouth_r")
    cv2.ellipse(img, (cx, mly + L(0.004)), ((mrx - mlx) // 2, L(0.010)), 0, 0, 360,
                (105, 110, 170), -1)                                  # lips
    cv2.ellipse(img, (cx, mly - L(0.004)), ((mrx - mlx) // 2, L(0.008)), 0, 10, 170,
                (55, 45, 85), 2)                                      # mouth line
    cv2.circle(img, P_("mole"), L(0.0045), (75, 85, 110), -1)


def synthetic_face_truth(size=640):
    """The face_features fixture's KNOWN face, in the detect_faces_full
    dict format (image px), with its declared features: glasses and a
    mole (feature box)."""
    g = _FACE_GEOM
    lm = {k: _pt((g[k][0] * size, g[k][1] * size)) for k in FACE_KEYS}
    bx, by, bw, bh = g["box"]
    m = 0.008 * size
    mx, my = g["mole"][0] * size, g["mole"][1] * size
    return [{"box": [int(bx * size), int(by * size), int(bw * size), int(bh * size)],
             "score": 1.0, "landmarks": lm, "source": "truth",
             "features": ["glasses", "mole"],
             "feature_boxes": {"mole": [round(mx - m, 1), round(my - m, 1),
                                        round(2 * m, 1), round(2 * m, 1)]}}]


def synthetic_face_hints(size=640, units="px"):
    """The hints dict an agent would write for the face_features fixture
    (the known face, as px or norm). JSON-able."""
    f = synthetic_face_truth(size)[0]
    k = 1.0 / size if units == "norm" else 1.0
    pt = lambda p: [round(p[0] * k, 4), round(p[1] * k, 4)]
    bx = lambda b: [round(v * k, 4) for v in b]
    return {"units": units,
            "faces": [{"box": bx(f["box"]),
                       "landmarks": {n: pt(p) for n, p in f["landmarks"].items()},
                       "features": ["glasses",
                                    {"name": "mole", "box": bx(f["feature_boxes"]["mole"])}]}]}


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
    ap.add_argument("--hints", default=None,
                    help="vision-hints JSON (label, subject_box, faces, keep, drop)")
    ap.add_argument("--overlay", default=None,
                    help="write a PNG of the detected/hinted faces, landmarks and "
                         "boxes drawn on the photo (look at it before tracing)")
    ap.add_argument("--lineart", default=None,
                    help="trace this line drawing (aligned to the photo) instead "
                         "of the photo's own edges")
    ap.add_argument("--no-protect-face", action="store_true",
                    help="disable facial-feature protection zones")
    a = ap.parse_args(argv)
    if a.overlay:
        try:
            hints_overlay(a.photo, a.hints, a.overlay)
        except HintError as e:
            print(f"bad hints: {e}", file=sys.stderr)
            return 2
        print("wrote", a.overlay)
    kw = dict(hints=a.hints, lineart=a.lineart,
              protect_face=False if a.no_protect_face else None)
    try:
        svg = photo_to_svg(a.photo, style=a.style, subject=a.subject,
                           detail=a.detail, title=a.title, **kw)
    except HintError as e:
        print(f"photolib: bad hints: {e}", file=sys.stderr)
        return 2
    with open(a.out, "w") as fh:
        fh.write(svg)
    print("wrote", a.out)
    fid = read_fidelity(svg)
    if fid is not None:
        m = re.search(r'data-fidelity-missing="([^"]*)"', svg)
        print(f"feature fidelity {fid:.2f}"
              + (f" (missing: {m.group(1)})" if m else " (all features traced)"))
    if a.fragment:
        with open(a.fragment, "w") as fh:
            fh.write(photo_to_fragment(a.photo, style=a.style,
                                       detail=a.detail, **kw))
        print("wrote", a.fragment)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
