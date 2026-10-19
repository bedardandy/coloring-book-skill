"""imagemodels — a small registry of image-model backends for photolib.

photolib's default chain is 100% local (YuNet + GrabCut + thresholds).
This module lets a caller plug better models into that chain without new
dependencies: every backend is a plain function `fn(bgr) -> result`,
registered under a name with ONE capability:

  "segment"    bgr -> uint8 mask (255 = subject), same h x w
               (portrait matting, face parsing, salient-object models)
  "landmarks"  bgr -> [{"box": [x, y, w, h], "score": s, "landmarks":
               {"eye_l", "eye_r", "nose", "mouth_l", "mouth_r": (x, y)}}]
               image px, _l/_r = IMAGE-left/right (photolib's face format)
  "depth"      bgr -> float32 h x w, LARGER = NEARER (MiDaS convention);
               seeds GrabCut: the far share of the frame starts as background
  "lineart"    bgr -> uint8 gray h x w, dark lines on white (an
               informative-drawings ONNX, a ControlNet line-art annotator,
               or a hosted image model asked to redraw as a coloring page)

Use them from photolib with backends={"segment": "my-seg", ...}.

Built-ins: "yunet" (landmarks, the bundled local model). Loaders for
user-supplied LOCAL weights via cv2.dnn.readNetFromONNX: onnx_segmenter,
onnx_lineart, onnx_depth (nothing is downloaded or bundled — there is no
network; see reference/photo-guide.md for candidate open models). Any
Python callable registers the same way — e.g. an agent's client for a
hosted image model.

PRIVACY GATE: a backend registered remote=True (anything that sends pixels
off the machine) raises PrivacyError unless the call passes
allow_remote=True. When the photo shows a face the error says so: a
person's photo would leave the machine, which needs explicit consent from
the user — and a parent or guardian for a child. Local backends never ask.

Outputs are validated (shape, dtype, range) and resized to the input
frame, so a model working at 320px plugs straight in. Deterministic as
long as the backend is (cv2.dnn on CPU is).
"""
import os

import cv2
import numpy as np

CAPABILITIES = ("segment", "landmarks", "depth", "lineart")

_REGISTRY = {}                      # name -> dict(name, fn, capability, remote, description)
_NETS = {}                          # onnx path -> cv2.dnn.Net (loaded on first call)


class BackendError(RuntimeError):
    """Unknown backend, wrong capability, missing weights, bad output."""


class PrivacyError(PermissionError):
    """A remote backend was asked to see a photo without allow_remote=True."""


# ---------------------------------------------------------------- registry
def register_backend(name, fn, capability, remote=False, description=""):
    """Register fn(bgr) -> result under name for one capability. remote=True
    for ANY backend that sends pixels off this machine (a hosted API, a
    server on another host): photolib then refuses to run it without
    allow_remote=True. Re-registering a name replaces it. Returns name."""
    if not isinstance(name, str) or not name:
        raise BackendError("register_backend: name must be a non-empty string")
    if capability not in CAPABILITIES:
        raise BackendError(f"register_backend({name!r}): capability must be one "
                           f"of {', '.join(CAPABILITIES)}, got {capability!r}")
    if not callable(fn):
        raise BackendError(f"register_backend({name!r}): fn must be callable")
    _REGISTRY[name] = dict(name=name, fn=fn, capability=capability,
                           remote=bool(remote), description=description)
    return name


def unregister_backend(name):
    """Remove a backend (built-ins included). Missing names are ignored."""
    _REGISTRY.pop(name, None)


def get_backend(name):
    """The registry entry for name (a dict); BackendError when unknown."""
    if name not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY)) or "none"
        raise BackendError(f"unknown backend {name!r} (registered: {known})")
    return _REGISTRY[name]


def list_backends(capability=None):
    """[(name, capability, remote)] sorted by name, optionally filtered."""
    return [(b["name"], b["capability"], b["remote"])
            for _n, b in sorted(_REGISTRY.items())
            if capability is None or b["capability"] == capability]


def _local_faces(bgr):
    import photolib
    return len(photolib.detect_faces_full(None, bgr))


def check_privacy(name, bgr=None, allow_remote=False, faces=None):
    """Raise PrivacyError if backend `name` is remote and allow_remote is not
    set. faces: number of faces already detected (None = run the local
    YuNet detector on bgr to find out — it never leaves the machine)."""
    b = get_backend(name)
    if not b["remote"] or allow_remote:
        return
    if faces is None and bgr is not None:
        faces = _local_faces(bgr)
    if faces:
        raise PrivacyError(
            f"backend {name!r} is REMOTE and this photo shows a person "
            f"({faces} face{'s' if faces != 1 else ''} detected): running it "
            "would send a person's photo off this machine. That needs explicit "
            "consent from the user — and from a parent or guardian when the "
            "photo shows a child. Ask first; pass allow_remote=True only after "
            "they agree, or use a local backend / the default local pipeline.")
    raise PrivacyError(
        f"backend {name!r} is REMOTE: running it would send this photo off "
        "this machine. Pass allow_remote=True only with the user's explicit "
        "consent, or use a local backend / the default local pipeline.")


def run_backend(name, bgr, capability=None, *, allow_remote=False, faces=None):
    """Run a registered backend on a BGR uint8 image (privacy gate first)
    and return its validated output (see the module docstring)."""
    b = get_backend(name)
    if capability is not None and b["capability"] != capability:
        raise BackendError(f"backend {name!r} is a {b['capability']!r} backend, "
                           f"not {capability!r}")
    bgr = np.asarray(bgr)
    if bgr.ndim == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    check_privacy(name, bgr, allow_remote, faces)
    try:
        out = b["fn"](bgr)
    except (PrivacyError, BackendError):
        raise
    except Exception as e:                      # surface model errors by name
        raise BackendError(f"backend {name!r} failed: {type(e).__name__}: {e}") from e
    return validate_output(b["capability"], out, bgr.shape[:2], name)


def validate_output(capability, out, shape, name="backend"):
    """Check a backend result and bring it onto the input frame (h, w)."""
    h, w = shape[:2]
    if capability == "landmarks":
        import photolib
        if not isinstance(out, (list, tuple)):
            raise BackendError(f"{name}: landmarks must return a list of face "
                               f"dicts, got {type(out).__name__}")
        try:
            return [photolib.normalize_face(f, (h, w), source=name) for f in out]
        except photolib.HintError as e:
            raise BackendError(f"{name}: bad face dict: {e}") from None
    arr = np.asarray(out)
    if arr.ndim == 3 and arr.shape[2] in (1, 3, 4):
        arr = arr[:, :, :3].mean(axis=2) if arr.shape[2] > 1 else arr[:, :, 0]
    if arr.ndim != 2 or arr.size == 0:
        raise BackendError(f"{name}: {capability} must return an h x w array, "
                           f"got shape {getattr(arr, 'shape', None)}")
    if not np.isfinite(arr.astype(np.float64)).all():
        raise BackendError(f"{name}: {capability} output has NaN/inf")
    if capability == "depth":
        d = cv2.resize(arr.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
        lo, hi = float(d.min()), float(d.max())
        return (d - lo) / (hi - lo) if hi > lo else np.zeros_like(d)
    if arr.dtype == bool:
        arr = arr.astype(np.uint8) * 255
    elif arr.dtype != np.uint8:
        f = arr.astype(np.float64)
        arr = np.clip(f * 255.0 if f.max() <= 1.0 else f, 0, 255).astype(np.uint8)
    if arr.shape != (h, w):
        arr = cv2.resize(arr, (w, h), interpolation=cv2.INTER_LINEAR)
    if capability == "segment":
        return np.where(arr >= 128, 255, 0).astype(np.uint8)
    return arr                                   # lineart: uint8 gray


# ---------------------------------------------------------------- ONNX loaders
def _net(path):
    if path not in _NETS:
        _NETS[path] = cv2.dnn.readNetFromONNX(path)
    return _NETS[path]


def _check_weights(path, kind):
    if not path or not os.path.isfile(path):
        raise BackendError(
            f"{kind}: no ONNX weights at {path!r}. Nothing is bundled or "
            "downloaded — fetch an open model yourself (candidates in "
            "reference/photo-guide.md, 'Image-model backends') and pass its path.")


def _blob(bgr, size, mean, std, swap_rb):
    """NCHW float32 input: resize to size (w, h), scale to 0-1, then
    (x - mean) / std per channel (RGB order when swap_rb)."""
    b = cv2.dnn.blobFromImage(bgr, 1.0 / 255.0, tuple(int(v) for v in size),
                              (0, 0, 0), swapRB=swap_rb, crop=False)
    m = np.asarray(mean, np.float32).reshape(1, -1, 1, 1)
    s = np.asarray(std, np.float32).reshape(1, -1, 1, 1)
    return ((b - m) / s).astype(np.float32)


def _forward(path, blob, output=None):
    net = _net(path)
    net.setInput(blob)
    out = net.forward(output) if output else net.forward()
    return np.asarray(out, np.float32)


def segment_from_output(out, threshold=0.5, sigmoid=False, classes=None):
    """Model output -> float/bool map (pre-resize): (1, C, H, W) with C > 1
    is per-class logits (face parsing): argmax, subject = classes (default
    every class but 0); C == 1 or (1, H, W) is a probability/alpha map
    (matting): > threshold, after a sigmoid when the model emits logits."""
    a = np.asarray(out, np.float32)
    while a.ndim > 3:
        a = a[0]
    if a.ndim == 3 and a.shape[0] > 1:
        cls = a.argmax(axis=0)
        keep = np.isin(cls, list(classes)) if classes is not None else cls > 0
        return keep.astype(np.uint8) * 255
    a = a[0] if a.ndim == 3 else a
    if sigmoid:
        a = 1.0 / (1.0 + np.exp(-a))
    return (a > threshold).astype(np.uint8) * 255


def lineart_from_output(out, invert=False, value_range=(0.0, 1.0)):
    """Model output (1, C, H, W) -> uint8 dark-lines-on-white: channels
    averaged, value_range mapped to 0-255; invert=True for models that draw
    WHITE lines on black (HED / most ControlNet annotators)."""
    a = np.asarray(out, np.float32)
    while a.ndim > 3:
        a = a[0]
    if a.ndim == 3:
        a = a.mean(axis=0)
    lo, hi = value_range
    g = np.clip((a - lo) / (hi - lo + 1e-12), 0.0, 1.0) * 255.0
    g = g.astype(np.uint8)
    return 255 - g if invert else g


def depth_from_output(out, invert=False):
    """Model output -> float32 depth, LARGER = NEARER. MiDaS / Depth-Anything
    emit relative inverse depth (already nearer = larger); invert=True for a
    model that emits distance."""
    a = np.asarray(out, np.float32)
    while a.ndim > 2:
        a = a[0]
    return -a if invert else a


def onnx_segmenter(path, size=(512, 512), mean=(0.5, 0.5, 0.5),
                   std=(0.5, 0.5, 0.5), swap_rb=True, output=None,
                   threshold=0.5, sigmoid=False, classes=None):
    """fn(bgr) -> uint8 subject mask from a LOCAL ONNX segmentation model
    (input NCHW at size=(w, h), normalised (x/255 - mean) / std). Matting
    models (one alpha channel) threshold at `threshold`; parsing models
    (C classes) keep `classes` (default: all but background 0)."""
    _check_weights(path, "onnx_segmenter")

    def fn(bgr):
        h, w = bgr.shape[:2]
        out = _forward(path, _blob(bgr, size, mean, std, swap_rb), output)
        m = segment_from_output(out, threshold, sigmoid, classes)
        return cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
    return fn


def onnx_lineart(path, size=(512, 512), mean=(0.0, 0.0, 0.0),
                 std=(1.0, 1.0, 1.0), swap_rb=True, output=None,
                 invert=False, value_range=(0.0, 1.0)):
    """fn(bgr) -> uint8 line drawing (dark on white) from a LOCAL ONNX
    photo-to-line-art model (e.g. informative-drawings: 0-1 input, 0-1
    output, dark lines). invert=True for white-on-black edge models."""
    _check_weights(path, "onnx_lineart")

    def fn(bgr):
        h, w = bgr.shape[:2]
        out = _forward(path, _blob(bgr, size, mean, std, swap_rb), output)
        g = lineart_from_output(out, invert, value_range)
        return cv2.resize(g, (w, h), interpolation=cv2.INTER_LINEAR)
    return fn


def onnx_depth(path, size=(256, 256), mean=(0.485, 0.456, 0.406),
               std=(0.229, 0.224, 0.225), swap_rb=True, output=None,
               invert=False):
    """fn(bgr) -> float32 depth (larger = nearer) from a LOCAL ONNX
    monocular depth model (MiDaS-small at 256, Depth-Anything-small at
    518 — ImageNet mean/std)."""
    _check_weights(path, "onnx_depth")

    def fn(bgr):
        h, w = bgr.shape[:2]
        out = _forward(path, _blob(bgr, size, mean, std, swap_rb), output)
        d = depth_from_output(out, invert)
        return cv2.resize(d, (w, h), interpolation=cv2.INTER_LINEAR)
    return fn


# ---------------------------------------------------------------- built-ins
def _yunet(bgr):
    import photolib
    return photolib.detect_faces_full(None, bgr)


register_backend("yunet", _yunet, "landmarks",
                 description="bundled YuNet face detector + 5 landmarks (local)")
