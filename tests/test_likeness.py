"""Individual facial features on parametric characters (charlib.face) and the
likeness helpers (lib/likeness.py)."""
import hashlib
import itertools
import xml.etree.ElementTree as ET

import pytest

import charlib as cl
from likeness import (traits_from_face, describe_traits, check_traits,
                      cast_distinctness, model_sheet, FEATURE_TRAITS)
from validate import validate_svg

CLASSIC_HAIR = ("bob_bangs", "bob", "tousled", "long_wavy", "pigtails", "curly", "buzz")


def _classic_digest():
    out = []
    for hair in CLASSIC_HAIR:
        for g, f, hb, beard, seed, mouth, brows in itertools.product(
                (0, 1), (0, 1), (0, 1), (0, 1), (0, 4242), ("smile", "open", "none"), (0, 1)):
            out.append(cl.face(100, 100, 38, hair=hair, glasses=g, freckles=f, headband=hb,
                               beard=beard, seed=seed, mouth=mouth, brows=brows))
    for t in ({"name": "Mia", "hair": "pigtails", "glasses": True, "freckles": True, "outfit": "dress"},
              {"name": "Max", "hair": "buzz", "outfit": "tee", "beard": True}):
        for pose in cl._KID_POSES:
            out.append(cl.kid_stand(t, pose=pose, accessories=("cap", "scarf", "cape", "wand", "crown")))
        for fn in ("kid_sitting", "kid_reach", "kid_run", "kid_jump", "kid_point", "kid_carry",
                   "kid_wheelchair", "kid_toddler"):
            out.append(getattr(cl, fn)(t))
        out.append(cl.face_traits(0, 0, 37, t))
    return hashlib.sha256("".join(out).encode()).hexdigest()


def test_classic_faces_unchanged():
    # every individual-feature trait defaults to the 2026-07 geometry: a
    # trait dict that sets none of them draws byte-identical SVG (the example
    # book and showcase pages depend on it)
    assert _classic_digest() == \
        "da3f9fa5db74441aec8e65a50951b0c77dfd6d6c58a3b931e8c587900c66abf9"


def _parse(frag):
    return ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{frag}</svg>')


FEATURE_CASES = (
    [dict(hair=h) for h in cl.HAIR_STYLES]
    + [dict(face_shape=s) for s in cl.FACE_SHAPES]
    + [dict(eyes=e) for e in cl.EYE_STYLES]
    + [dict(eyes=e, lashes=True) for e in cl.EYE_STYLES]
    + [dict(nose=n) for n in cl.NOSE_STYLES]
    + [dict(mouth=m) for m in cl.MOUTH_STYLES]
    + [dict(ears=e, hair="buzz") for e in ("small", "big")]
    + [dict(headwear="hijab"), dict(dimples=True), dict(moles=[(0.4, 0.5)]),
       dict(freckles="light"), dict(freckles="heavy"), dict(brows="thick"),
       dict(look=0.7, ears="small", nose="long"), dict(hair="ponytail", hair_part="right"),
       dict(hair="side_part", hair_part="right"), dict(face_shape="long", beard=True)])


@pytest.mark.parametrize("kw", FEATURE_CASES, ids=lambda kw: ",".join(f"{k}={v}" for k, v in kw.items()))
def test_feature_renders_one_tagged_face(kw):
    svg = cl.face(200, 200, 40, **kw)
    root = _parse(svg)
    faces = [el for el in root.iter() if el.get("data-face")]
    assert len(faces) == 1 and faces[0].get("data-face") == "200,200,40"


@pytest.mark.parametrize("hair", cl.HAIR_STYLES + ("hijab",))
def test_every_style_on_a_figure_validates(hair):
    t = dict(hair=hair, outfit="dress") if hair != "hijab" else dict(headwear="hijab", outfit="dress")
    t.update(eyes="almond", nose="button", mouth="gap_tooth", freckles=True)
    body = cl.G(425, 900, cl.kid_stand(t, pose="wave_high"), 1.4)
    rep = validate_svg(cl.spage("Style", body, layout="activity"))
    assert rep["counts"]["HIGH"] == 0, rep["findings"]


def test_new_hair_styles_differ_from_default():
    base = cl.face(0, 0, 40)
    for h in ("ponytail", "afro", "bun", "braids", "side_part", "bald"):
        assert cl.face(0, 0, 40, hair=h) != base


def test_hijab_replaces_hair_and_keeps_face_open():
    svg = cl.face(0, 0, 40, hair="pigtails", headwear="hijab")
    assert svg == cl.face(0, 0, 40, hair="buzz", headwear="hijab")
    assert 'fill-rule="evenodd"' in svg


def test_look_slides_features_and_hides_far_ear():
    front = cl.face(0, 0, 40, ears="small", hair="buzz")
    right = cl.face(0, 0, 40, ears="small", hair="buzz", look=0.8)
    assert front.count("<ellipse") == 2 and right.count("<ellipse") == 1
    # eye dots move toward the turn
    def eye_xs(svg):
        return sorted(float(el.get("cx")) for el in _parse(svg).iter()
                      if el.tag.endswith("circle") and el.get("fill") == "black")
    assert all(b > a for a, b in zip(eye_xs(front), eye_xs(right)))


def test_measured_proportions_override_seed_jitter():
    a = cl.face(0, 0, 40, seed=777, eye_spacing=0.42)
    b = cl.face(0, 0, 40, seed=12345, eye_spacing=0.42)
    xa = [el.get("cx") for el in _parse(a).iter() if el.get("fill") == "black"]
    xb = [el.get("cx") for el in _parse(b).iter() if el.get("fill") == "black"]
    assert xa == xb


def test_round_eyes_behind_glasses_fall_back_to_dots():
    assert cl.face(0, 0, 40, eyes="round", glasses=True) == cl.face(0, 0, 40, glasses=True)


def test_face_traits_forwards_feature_keys():
    t = {"name": "Ana", "hair": "braids", "mouth": "gap_tooth", "nose": "button", "moles": [(0.4, 0.5)]}
    assert cl.face_traits(0, 0, 37, t) == cl.face(
        0, 0, 37, hair="braids", mouth="gap_tooth", nose="button", moles=[(0.4, 0.5)],
        seed=cl.face_seed_for("Ana"))


# ---------------------------------------------------------------- likeness
def _face(iod=42.0, mouth=34.0, lower=44.0, nose_dx=0.0, box_w=100.0, features=()):
    ex, ey = 200.0, 200.0
    return {"box": [ex - box_w / 2, ey - 45, box_w, 125],
            "landmarks": {"eye_l": (ex - iod / 2, ey), "eye_r": (ex + iod / 2, ey),
                          "nose": (ex + nose_dx, ey + lower * 0.55),
                          "mouth_l": (ex - mouth / 2, ey + lower), "mouth_r": (ex + mouth / 2, ey + lower)},
            "features": list(features)}


def test_traits_from_average_face_change_nothing():
    res = traits_from_face(_face())
    assert res["traits"] == {} and abs(res["measures"]["yaw"]) < 1e-9


def test_traits_from_face_measures_proportions():
    wide = traits_from_face(_face(iod=50, mouth=41))["traits"]
    assert wide["eye_spacing"] > 0.38
    narrow = traits_from_face(_face(iod=35, mouth=29))["traits"]
    assert narrow["eye_spacing"] < 0.38
    assert traits_from_face(_face(mouth=46))["traits"]["smile_width"] > 1.0
    assert traits_from_face(_face(lower=60))["traits"]["face_shape"] == "long"
    assert traits_from_face(_face(lower=35))["traits"]["face_shape"] == "round"


def test_turned_head_is_noted_not_measured():
    res = traits_from_face(_face(iod=50, nose_dx=12))
    assert res["measures"]["yaw"] > 0.35
    assert "eye_spacing" not in res["traits"] and res["notes"]


def test_feature_words_map_to_traits():
    res = traits_from_face(_face(features=["glasses", "gap_tooth", "dimples",
                                           {"name": "mole", "at": (230, 240)}, "unicorn"]))
    t = res["traits"]
    assert t["glasses"] and t["mouth"] == "gap_tooth" and t["dimples"]
    (dx, dy), = t["moles"]
    assert dx > 0 and dy > 0          # image-right, below the face centre
    assert any("unicorn" in n for n in res["notes"])
    for word, traits in FEATURE_TRAITS.items():
        for k, v in traits.items():
            assert not check_traits({k: v}), (word, k, v)


def test_no_landmarks_is_honest():
    res = traits_from_face({"box": [0, 0, 10, 10], "features": ["freckles"]})
    assert res["traits"] == {"freckles": True} and res["notes"]


def test_check_traits_catches_typos_and_hidden_hands():
    probs = check_traits({"name": "X", "hair": "afros", "eye_spacing": 0.7}, poses=("wave",))
    sev = [p[0] for p in probs]
    assert "HIGH" in sev and "MED" in sev
    assert any("wave_high" in m for _s, m in check_traits({"hair": "afro"}, poses=("wave",)))
    assert check_traits({"hair": "buzz", "glasses": True}, poses=("wave",)) == []


def test_cast_distinctness_flags_lookalikes():
    a = {"name": "Lily", "hair": "pigtails", "outfit": "dress"}
    b = {"name": "Mia", "hair": "pigtails", "outfit": "dress", "freckles": True}
    c = {"name": "Max", "hair": "buzz", "outfit": "tee", "glasses": True, "height": 1.15}
    found = cast_distinctness([a, b, c, {"coat": "spots"}])
    assert len(found) == 1 and "Lily" in found[0][1] and "Mia" in found[0][1]


def test_describe_traits_salience_order():
    words = describe_traits({"hair": "ponytail", "glasses": True, "mouth": "gap_tooth",
                             "moles": [(-0.4, 0.5)], "height": 0.85})
    assert words[0] == "ponytail hair" and words[1] == "glasses"
    assert "gap-tooth grin" in words and "a mole on the image-left cheek" in words


@pytest.mark.parametrize("t", [
    {"name": "Harper", "hair": "pigtails", "glasses": True, "mouth": "gap_tooth", "outfit": "dress"},
    {"name": "Amara", "hair": "afro", "eyes": "almond", "lashes": True, "dimples": True},
    {"name": "Noor", "headwear": "hijab", "outfit": "dress", "nose": "button"},
    {"name": "Grandpa Joe", "hair": "bald", "beard": True, "glasses": True, "face_shape": "long"},
])
def test_model_sheet_validates(t):
    svg = model_sheet(t)
    rep = validate_svg(svg)
    assert rep["counts"]["HIGH"] == 0 and rep["counts"]["MED"] == 0, rep["findings"]
    assert svg.count("data-face=") == 5   # big face + 3 turnaround + figure
