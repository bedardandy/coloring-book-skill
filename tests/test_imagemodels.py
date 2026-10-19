"""Image-model backends (lib/imagemodels.py) and their use in the photolib
chain: registry, the privacy gate, callable backends, ONNX loaders (driven
by hand-encoded tiny ONNX graphs — no real weights in the repo)."""
import os

import cv2
import numpy as np
import pytest

import imagemodels
import photolib
from imagemodels import BackendError, PrivacyError

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="module")
def photos(tmp_path_factory):
    d = tmp_path_factory.mktemp("im")
    out = {}
    for kind in ("animal", "face_features"):
        p = d / f"{kind}.png"
        cv2.imwrite(str(p), photolib.synthetic_photo(kind))
        out[kind] = str(p)
    return out


@pytest.fixture
def registry():
    """Backends registered by a test are removed afterwards."""
    before = set(imagemodels._REGISTRY)
    yield imagemodels
    for name in set(imagemodels._REGISTRY) - before:
        imagemodels.unregister_backend(name)


def _animal_truth(size=640):
    """The animal fixture's true silhouette (what a good matting model returns)."""
    m = np.zeros((size, size), np.uint8)
    cv2.ellipse(m, (size // 2, int(size * 0.58)), (int(size * 0.30),
                int(size * 0.20)), 0, 0, 360, 255, -1)
    cv2.circle(m, (int(size * 0.72), int(size * 0.42)), int(size * 0.13), 255, -1)
    cv2.ellipse(m, (int(size * 0.60), int(size * 0.30)),
                (int(size * 0.045), int(size * 0.11)), 25, 0, 360, 255, -1)
    return m


# ---------------------------------------------------------------- registry
def test_builtin_yunet_landmarks(photos):
    assert ("yunet", "landmarks", False) in imagemodels.list_backends()
    bgr = cv2.imread(photos["face_features"])
    faces = imagemodels.run_backend("yunet", bgr, "landmarks")
    assert len(faces) == 1 and set(faces[0]["landmarks"]) == {
        "eye_l", "eye_r", "nose", "mouth_l", "mouth_r"}


def test_register_validation(registry):
    with pytest.raises(BackendError, match="capability"):
        registry.register_backend("x", lambda b: b, "colorize")
    with pytest.raises(BackendError, match="callable"):
        registry.register_backend("x", 42, "segment")
    with pytest.raises(BackendError, match="unknown backend"):
        registry.get_backend("nope")
    registry.register_backend("seg-a", lambda b: b[:, :, 0], "segment")
    with pytest.raises(BackendError, match="not 'depth'"):
        registry.run_backend("seg-a", np.zeros((8, 8, 3), np.uint8), "depth")


def test_output_validation_and_resize(registry):
    bgr = np.zeros((40, 60, 3), np.uint8)
    registry.register_backend("small-seg", lambda b: np.ones((10, 15), np.float32),
                              "segment")
    m = registry.run_backend("small-seg", bgr, "segment")
    assert m.shape == (40, 60) and m.dtype == np.uint8 and set(np.unique(m)) == {255}
    registry.register_backend("bad-shape", lambda b: np.zeros(5), "lineart")
    with pytest.raises(BackendError, match="h x w"):
        registry.run_backend("bad-shape", bgr)
    registry.register_backend("nan-depth", lambda b: np.full((4, 4), np.nan), "depth")
    with pytest.raises(BackendError, match="NaN"):
        registry.run_backend("nan-depth", bgr)
    registry.register_backend("bad-faces", lambda b: [{"box": [1, 2]}], "landmarks")
    with pytest.raises(BackendError, match="bad face dict"):
        registry.run_backend("bad-faces", bgr)
    registry.register_backend("boom", lambda b: 1 / 0, "segment")
    with pytest.raises(BackendError, match="ZeroDivisionError"):
        registry.run_backend("boom", bgr)
    d = registry.validate_output("depth", np.arange(12.0).reshape(3, 4), (6, 8))
    assert d.shape == (6, 8) and d.min() == 0.0 and d.max() == 1.0


# ---------------------------------------------------------------- privacy gate
def test_privacy_gate_blocks_remote_backends(registry, photos):
    calls = []

    def hosted(bgr):                               # stands in for an API client
        calls.append(bgr.shape)
        return _animal_truth()
    registry.register_backend("hosted-seg", hosted, "segment", remote=True)
    face = cv2.imread(photos["face_features"])
    with pytest.raises(PrivacyError) as e:
        registry.run_backend("hosted-seg", face)
    msg = str(e.value)
    assert "person" in msg and "consent" in msg and "parent" in msg
    animal = cv2.imread(photos["animal"])
    with pytest.raises(PrivacyError) as e:
        registry.run_backend("hosted-seg", animal)
    assert "person" not in str(e.value) and "allow_remote=True" in str(e.value)
    assert not calls                               # nothing left the machine
    # the photolib entry points refuse too — before any pixels are sent
    with pytest.raises(PrivacyError):
        photolib.photo_to_svg(photos["face_features"], qa=False,
                              backends={"segment": "hosted-seg"})
    assert not calls
    # explicit consent: runs
    registry.run_backend("hosted-seg", animal, allow_remote=True)
    assert calls
    # local backends never ask
    registry.register_backend("local-seg", lambda b: _animal_truth(), "segment")
    registry.run_backend("local-seg", face)


def test_backends_mapping_validated(registry, photos):
    with pytest.raises(BackendError, match="capability"):
        photolib.photo_to_svg(photos["animal"], qa=False,
                              backends={"colorize": "yunet"})
    with pytest.raises(BackendError, match="unknown backend"):
        photolib.photo_to_svg(photos["animal"], qa=False,
                              backends={"segment": "missing"})
    with pytest.raises(BackendError, match="landmarks"):
        photolib.photo_to_svg(photos["animal"], qa=False,
                              backends={"segment": "yunet"})


# ---------------------------------------------------------------- callable backends in the chain
def test_segment_backend_replaces_grabcut(registry, photos):
    registry.register_backend("truth-seg", lambda b: _animal_truth(), "segment")
    gray, bgr = photolib.load_photo(photos["animal"])
    mask, label, meta = photolib.detect_subject(gray, bgr,
                                                backends={"segment": "truth-seg"})
    assert meta["detector"] == "backend:truth-seg"
    assert np.array_equal(mask, _animal_truth())
    svg = photolib.photo_to_svg(photos["animal"], qa=False,
                                backends={"segment": "truth-seg"})
    assert 'data-ground="1"' in svg                  # usable mask: background dropped
    # an unusable mask (the whole frame) is rejected: GrabCut takes over
    registry.register_backend("full-seg", lambda b: np.full(b.shape[:2], 255, np.uint8),
                              "segment")
    _m, _l, meta = photolib.detect_subject(gray, bgr, backends={"segment": "full-seg"})
    assert meta["backend_rejected"] == "full-seg" and meta["detector"] == "grabcut"


def test_landmarks_backend_augments_yunet(registry, photos):
    """A landmarks backend (e.g. a profile-face or toy-face model) adds a
    face YuNet misses: the animal fixture then traces under the face
    policy with protection zones and a fidelity score."""
    face = {"box": [380, 170, 200, 170],
            "landmarks": {"eye_l": [440, 240], "eye_r": [500, 240],
                          "nose": [470, 280], "mouth_l": [450, 310],
                          "mouth_r": [490, 310]}}
    registry.register_backend("toy-faces", lambda b: [face], "landmarks")
    faces = photolib.face_landmarks(photos["animal"], backends={"landmarks": "toy-faces"})
    assert len(faces) == 1 and faces[0]["source"] == "toy-faces"
    svg = photolib.photo_to_svg(photos["animal"], qa=False,
                                backends={"landmarks": "toy-faces"})
    assert 'data-policy="face"' in svg or 'data-policy="person"' in svg
    assert photolib.read_fidelity(svg) is not None


def test_depth_backend_seeds_grabcut(registry, photos):
    def depth(bgr):                                  # the subject is nearer
        return (_animal_truth().astype(np.float32) / 255.0) * 5.0 + 1.0
    registry.register_backend("toy-depth", depth, "depth")
    gray, bgr = photolib.load_photo(photos["animal"])
    mask, _label, meta = photolib.detect_subject(gray, bgr,
                                                 backends={"depth": "toy-depth"})
    assert meta["detector"] == "grabcut+depth"
    truth = _animal_truth() > 0
    iou = (truth & (mask > 0)).sum() / (truth | (mask > 0)).sum()
    assert iou > 0.8


def test_lineart_backend_is_traced(registry, photos):
    def drawer(bgr):                                 # "redraw as a coloring page"
        g = np.full(bgr.shape[:2], 255, np.uint8)
        cv2.circle(g, (320, 320), 150, 0, 6)
        cv2.line(g, (250, 300), (390, 300), 0, 5)
        return g
    registry.register_backend("toy-lineart", drawer, "lineart")
    svg = photolib.photo_to_svg(photos["animal"], qa=False,
                                backends={"lineart": "toy-lineart"})
    art = svg[svg.index("data-policy"):svg.index("<g data-chrome")
              if "<g data-chrome" in svg else len(svg)]
    assert 1 <= art.count('stroke="black"') <= 4


# ---------------------------------------------------------------- ONNX loaders
def test_onnx_loaders_need_local_weights(tmp_path):
    for loader in (imagemodels.onnx_segmenter, imagemodels.onnx_lineart,
                   imagemodels.onnx_depth):
        with pytest.raises(BackendError, match="no ONNX weights"):
            loader(str(tmp_path / "missing.onnx"))


def test_onnx_loaders_run_tiny_models(tmp_path, registry):
    import sys
    sys.path.insert(0, HERE)
    import onnx_tiny
    mean1 = onnx_tiny.write_model(str(tmp_path / "mean1.onnx"), "mean1", 32)
    ident = onnx_tiny.write_model(str(tmp_path / "id3.onnx"), "identity3", 32)
    img = np.zeros((96, 128, 3), np.uint8)
    cv2.rectangle(img, (40, 30), (90, 70), (255, 255, 255), -1)

    seg = imagemodels.onnx_segmenter(mean1, size=(32, 32), mean=(0, 0, 0),
                                     std=(1, 1, 1))
    registry.register_backend("tiny-seg", seg, "segment")
    m = imagemodels.run_backend("tiny-seg", img, "segment")
    assert m.shape == (96, 128) and m[50, 65] == 255 and m[5, 5] == 0

    # parsing model: 3 "classes" = channels; a blue square is class 2 in
    # RGB order, the black surround ties -> class 0
    blue = np.zeros((32, 32, 3), np.uint8)
    blue[8:24, 8:24] = (255, 0, 0)
    parse = imagemodels.onnx_segmenter(ident, size=(32, 32), mean=(0, 0, 0),
                                       std=(1, 1, 1), classes=[2])
    pm = parse(blue)
    assert pm[16, 16] == 255 and pm[2, 2] == 0

    la = imagemodels.onnx_lineart(mean1, size=(32, 32))
    g = la(img)
    assert g.dtype == np.uint8 and g.shape == (96, 128) and g[50, 65] > 200
    inv = imagemodels.onnx_lineart(mean1, size=(32, 32), invert=True)(img)
    assert inv[50, 65] < 55

    dep = imagemodels.onnx_depth(mean1, size=(32, 32), mean=(0, 0, 0), std=(1, 1, 1))
    d = dep(img)
    assert d.dtype == np.float32 and d[50, 65] > d[5, 5]


def test_postprocess_helpers():
    logits = np.zeros((1, 3, 4, 4), np.float32)
    logits[0, 2, :2] = 5.0
    m = imagemodels.segment_from_output(logits)              # default: classes != 0
    assert m[0, 0] == 255 and m[3, 3] == 0
    alpha = np.full((1, 1, 2, 2), -3.0, np.float32)
    alpha[0, 0, 0, 0] = 3.0
    m = imagemodels.segment_from_output(alpha, sigmoid=True)
    assert m[0, 0] == 255 and m[1, 1] == 0
    assert imagemodels.lineart_from_output(np.ones((1, 1, 2, 2)), invert=True).max() == 0
    assert imagemodels.depth_from_output(np.ones((1, 2, 2)), invert=True).max() == -1
