"""likeness — keep a REAL person's individual features on a parametric character.

The skill draws people as trait vectors (charlib.face / kid_stand), never as
photo likeness: the same trait dict draws the same face on every page, so a
character cannot drift. This module makes those vectors carry the features
that tell one real child from another:

  traits_from_face(face)   a detected / hinted face (photolib's dict: box +
                           landmarks + features) -> MEASURED proportions
                           (eye spacing, smile width, lower-face length,
                           head turn) and distinctive marks as trait keys
  describe_traits(t)       the plain-language list to read back to the user
                           ("pigtails, glasses, gap-tooth grin, a mole on
                           her left cheek") — they correct it before drawing
  check_traits(t)          typos and combinations that draw wrong (unknown
                           hair style, wide hair + stock wave pose)
  cast_distinctness(cast)  pairs of characters that would read as the same
                           kid at thumbnail size
  model_sheet(t)           a "Meet <name>!" page: big front face, a 3/4
                           turnaround and the standing figure — the approval
                           page before the book is drawn (doubles as an
                           "All about me" page in the book)

Landmark convention (shared with photolib): image pixels, `_l` / `_r` mean
IMAGE-left / IMAGE-right, never the subject's own left/right.

Salience order (what makes a kid recognisable at coloring-book fidelity):
hair silhouette / headwear > glasses > height > signature outfit > face
shape > distinctive marks (gap tooth, freckles, mole, dimples) > eye/nose
style. Spend the user's attention in that order.
"""
import math

from charlib import (HAIR_STYLES, FACE_SHAPES, EYE_STYLES, NOSE_STYLES,
                     MOUTH_STYLES, EAR_STYLES, BROW_STYLES, HEADWEAR, WIDE_HAIR,
                     face_traits, kid_stand, spage, TXT, W)

# population centres of the 5-point landmark ratios (adult + child portraits
# at the YuNet box convention); a trait moves off its classic value only when
# the measurement does
IOD_BOX = 0.42             # interocular distance / face-box width
MOUTH_IOD = 0.82           # mouth-corner width / interocular distance
LOWER_IOD = (0.95, 1.25)   # eye-line -> mouth-line / iod: below = round, above = long
YAW_GAIN = 2.2             # nose offset from the eye midpoint / iod -> look

# feature words a vision pass (hints["faces"][i]["features"]) may report,
# mapped onto trait keys
FEATURE_TRAITS = {
    "glasses": {"glasses": True},
    "freckles": {"freckles": True},
    "heavy_freckles": {"freckles": "heavy"},
    "gap_tooth": {"mouth": "gap_tooth"},
    "missing_tooth": {"mouth": "gap_tooth"},
    "big_grin": {"mouth": "grin"},
    "dimples": {"dimples": True},
    "lashes": {"lashes": True},
    "beard": {"beard": True},
    "headband": {"headband": True},
    "hijab": {"headwear": "hijab"},
    "big_ears": {"ears": "big"},
    "ears": {"ears": "small"},
    "button_nose": {"nose": "button"},
    "round_nose": {"nose": "round"},
    "long_nose": {"nose": "long"},
    "almond_eyes": {"eyes": "almond"},
    "round_eyes": {"eyes": "round"},
    "thick_brows": {"brows": "thick"},
}

# salience weights for cast_distinctness (see module docstring)
_SALIENCE = (("hair", 3.0), ("headwear", 3.0), ("glasses", 2.0), ("beard", 2.0),
             ("outfit", 1.0), ("face_shape", 0.75), ("freckles", 0.75),
             ("mouth", 0.5), ("eyes", 0.5), ("ears", 0.5), ("moles", 0.25),
             ("nose", 0.25), ("dimples", 0.25))
DISTINCT_MIN = 2.5         # below this two characters read as one at thumbnail size


def _pt(lm, k):
    v = lm[k]
    return float(v[0]), float(v[1])


def _clamp(v, lo, hi):
    return min(hi, max(lo, v))


def traits_from_face(face):
    """Measured trait suggestions from one face dict
    {"box": [x, y, w, h], "landmarks": {"eye_l", "eye_r", "nose", "mouth_l",
    "mouth_r"}, "features": [...]} (photolib.face_landmarks / vision hints).
    Returns {"traits": {...}, "measures": {...}, "notes": [...]}. Only
    measurements clearly off the population centre move a trait; a frontal
    photo is assumed (|yaw| > 0.35 adds a note and skips the spacing
    measurement, which foreshortens). Confirm with the user before use."""
    traits, notes = {}, []
    measures = {}
    lm = face.get("landmarks") or {}
    box = face.get("box")
    if all(k in lm for k in ("eye_l", "eye_r", "nose", "mouth_l", "mouth_r")):
        el, er = _pt(lm, "eye_l"), _pt(lm, "eye_r")
        ml, mr = _pt(lm, "mouth_l"), _pt(lm, "mouth_r")
        nx, _ny = _pt(lm, "nose")
        iod = math.hypot(er[0] - el[0], er[1] - el[1]) or 1.0
        mid_x = (el[0] + er[0]) / 2
        yaw = _clamp((nx - mid_x) / iod * YAW_GAIN, -1.0, 1.0)
        measures["yaw"] = round(yaw, 2)
        mouth_w = math.hypot(mr[0] - ml[0], mr[1] - ml[1])
        measures["mouth_iod"] = round(mouth_w / iod, 3)
        lower = ((ml[1] + mr[1]) / 2 - (el[1] + er[1]) / 2) / iod
        measures["lower_iod"] = round(lower, 3)
        if abs(yaw) > 0.35:
            notes.append(f"head turned (yaw {yaw:+.2f}): spacing and shape are "
                         "foreshortened — prefer a frontal photo for measuring")
        else:
            if box:
                ratio = iod / max(1.0, float(box[2]))
                measures["iod_box"] = round(ratio, 3)
                if abs(ratio - IOD_BOX) > 0.02:
                    traits["eye_spacing"] = round(_clamp(0.38 + (ratio - IOD_BOX) * 1.2,
                                                         0.31, 0.45), 3)
            if lower < LOWER_IOD[0]:
                traits["face_shape"] = "round"
            elif lower > LOWER_IOD[1]:
                traits["face_shape"] = "long"
        if abs(measures["mouth_iod"] - MOUTH_IOD) > 0.06:
            traits["smile_width"] = round(_clamp(1.0 + (measures["mouth_iod"] - MOUTH_IOD) * 1.5,
                                                 0.8, 1.3), 3)
    else:
        notes.append("no landmarks: proportions not measured (trait buckets only)")
    for f in face.get("features") or ():
        word = f if isinstance(f, str) else f.get("name", "")
        if word in FEATURE_TRAITS:
            traits.update(FEATURE_TRAITS[word])
        elif word == "mole" and box and not isinstance(f, str) and f.get("at"):
            # a mole position in image px -> offset in head radii from the
            # face centre (r ~ half the box width)
            fx = box[0] + box[2] / 2
            fy = box[1] + box[3] * 0.55
            r = box[2] / 2
            traits.setdefault("moles", []).append(
                (round(_clamp((f["at"][0] - fx) / r, -0.75, 0.75), 2),
                 round(_clamp((f["at"][1] - fy) / r, -0.4, 0.8), 2)))
        elif word == "mole":
            traits.setdefault("moles", []).append((0.45, 0.5))
            notes.append("mole position not given: placed on the image-right cheek — "
                         "ask which cheek")
        elif word:
            notes.append(f"feature '{word}' has no trait mapping — describe it to "
                         "the user and decide whether a custom mark is worth it")
    return {"traits": traits, "measures": measures, "notes": notes}


def describe_traits(t):
    """Plain-language list of what will make this character recognisable,
    in salience order — read it back to the user so they can correct it."""
    out = []
    if t.get("headwear"):
        out.append(t["headwear"])
    elif t.get("hair"):
        hp = " (parted " + t["hair_part"] + ")" if t.get("hair_part") == "right" and \
            t["hair"] in ("ponytail", "side_part") else ""
        out.append(t["hair"].replace("_", " ") + " hair" + hp)
    if t.get("glasses"):
        out.append("glasses")
    if t.get("beard"):
        out.append("beard")
    h = t.get("height")
    if h:
        out.append("tall" if h >= 1.08 else "small" if h <= 0.88 else "medium height")
    if t.get("outfit"):
        out.append(f"always wears a {t['outfit']}")
    if t.get("face_shape", "round") != "round":
        out.append(f"{t['face_shape']} face")
    mouth = t.get("mouth")
    if mouth == "gap_tooth":
        out.append("gap-tooth grin")
    elif mouth == "grin":
        out.append("big toothy grin")
    fr = t.get("freckles")
    if fr:
        out.append(("lots of " if fr == "heavy" else "a few " if fr == "light" else "") + "freckles")
    if t.get("dimples"):
        out.append("dimples")
    for dx, _dy in t.get("moles") or ():
        out.append("a mole on the " + ("image-left" if dx < 0 else "image-right") + " cheek")
    if t.get("eyes", "dot") != "dot":
        out.append(f"{t['eyes']} eyes")
    if t.get("lashes"):
        out.append("long lashes")
    if t.get("nose", "none") != "none":
        out.append(f"{t['nose']} nose")
    if t.get("ears"):
        out.append(f"{t['ears']} ears that show")
    if t.get("brows") == "thick":
        out.append("thick eyebrows")
    if "eye_spacing" in t:
        es = t["eye_spacing"]
        if abs(es - 0.38) >= 0.03:
            out.append("wide-set eyes" if es > 0.38 else "close-set eyes")
    if t.get("motif"):
        out.append(f"motif: {t['motif']}")
    return out


_ALLOWED = {"hair": HAIR_STYLES, "face_shape": FACE_SHAPES, "eyes": EYE_STYLES,
            "nose": NOSE_STYLES, "mouth": MOUTH_STYLES, "ears": EAR_STYLES,
            "brows": BROW_STYLES, "headwear": HEADWEAR,
            "hair_part": ("left", "right"), "freckles": (False, True, "light", "heavy"),
            "outfit": ("tee", "dress")}


def check_traits(t, poses=()):
    """Problems with a trait dict, as (severity, message) pairs: unknown
    values (a typo draws the classic default silently), out-of-range
    proportions, and stock poses whose hands hide behind wide hair."""
    out = []
    for k, allowed in _ALLOWED.items():
        if k in t and t[k] not in allowed:
            out.append(("HIGH", f"{t.get('name', '?')}: {k}={t[k]!r} is not one of "
                                f"{', '.join(repr(a) for a in allowed)}"))
    for k, lo, hi in (("eye_spacing", 0.30, 0.46), ("eye_size", 0.8, 1.4),
                      ("smile_width", 0.8, 1.3), ("look", -1.0, 1.0)):
        if k in t and not lo <= float(t[k]) <= hi:
            out.append(("MED", f"{t.get('name', '?')}: {k}={t[k]} is clamped to {lo}-{hi}"))
    for dx, dy in t.get("moles") or ():
        if math.hypot(dx, dy) > 0.85:
            out.append(("MED", f"{t.get('name', '?')}: mole at ({dx}, {dy}) falls off the face"))
    wide = WIDE_HAIR.get(t.get("headwear") or t.get("hair"))
    if wide:
        for pose in poses:
            if pose in ("wave", "up"):
                out.append(("MED", f"{t.get('name', '?')}: {t.get('headwear') or t['hair']} "
                                   f"reaches {wide}r — stock pose '{pose}' hides a hand behind "
                                   f"it; use wave_high / cheer"))
    if t.get("headwear") and t.get("hair") not in (None, "tousled"):
        out.append(("LOW", f"{t.get('name', '?')}: headwear replaces the hair silhouette "
                           f"({t['hair']} is not drawn)"))
    return out


def _trait_distance(a, b):
    d, diffs = 0.0, []
    for k, w in _SALIENCE:
        va, vb = a.get(k), b.get(k)
        if k == "hair" and (a.get("headwear") or b.get("headwear")):
            continue                      # the headwear term carries it
        if bool(va) != bool(vb) or (va and vb and va != vb):
            d += w
            diffs.append(k)
    ha, hb = float(a.get("height", 1.0)), float(b.get("height", 1.0))
    if abs(ha - hb) >= 0.12:
        d += 1.5
        diffs.append("height")
    return d, diffs


def cast_distinctness(cast):
    """Pairwise salience distance between characters (kids/adults — pets
    are distinct by species). Returns (severity, message) findings for pairs
    below DISTINCT_MIN: at thumbnail size they read as the same child."""
    people = [t for t in cast if t.get("hair") or t.get("headwear")]
    out = []
    for i in range(len(people)):
        for j in range(i + 1, len(people)):
            a, b = people[i], people[j]
            d, diffs = _trait_distance(a, b)
            if d < DISTINCT_MIN:
                out.append(("MED", f"{a.get('name', '?')} and {b.get('name', '?')} differ only in "
                                   f"{', '.join(diffs) or 'nothing'} (score {d:.2f} < "
                                   f"{DISTINCT_MIN}) — give one a different hair silhouette, "
                                   f"glasses or a signature outfit"))
    return out


def model_sheet(t, title=None, num=None, caption=None):
    """'Meet <name>!' page: a big front face with a 3/4 turnaround under it
    and the standing figure beside — the page to show the user for
    approval before drawing the book ('is this Harper?'), and a ready
    'All about me' page. Caption defaults to describe_traits()."""
    name = t.get("name", "")
    title = title or (f"Meet {name}!" if name else "Meet the Star!")
    big_r = 92
    body = face_traits(250, 330, big_r, t)
    for i, lk in enumerate((-0.7, 0.0, 0.7)):
        body += face_traits(125 + i * 132, 650, 40, dict(t, look=lk))
    pose = "wave_high" if WIDE_HAIR.get(t.get("headwear") or t.get("hair")) else "wave"
    body += f'<g transform="translate(615,950) scale(2)">{kid_stand(t, pose=pose)}</g>'
    if caption is None:
        words = describe_traits(t)
        caption = (f"{name}: " if name else "") + ", ".join(words[:6]) + "." if words else None
    if name:
        body += TXT(250, 800, name, size=48)
    return spage(title, body, num=num, caption=caption, layout="activity")
