"""Photo face -> traced features and -> parametric traits, end to end
(photolib protection + pupils + overlay, likeness.traits_from_face)."""
import re

import cv2
import pytest

import photolib
from likeness import traits_from_face


@pytest.fixture(scope="module")
def face_photo(tmp_path_factory):
    p = tmp_path_factory.mktemp("face") / "face.png"
    cv2.imwrite(str(p), photolib.synthetic_photo("face_features"))
    return str(p)


def _pupils(svg):
    return re.findall(r'<circle data-pupil="1" cx="([\d.]+)" cy="([\d.]+)"', svg)


def test_protected_face_traces_open_eyes(face_photo):
    svg = photolib.photo_to_svg(face_photo, hints=photolib.synthetic_face_hints())
    pupils = _pupils(svg)
    assert len(pupils) == 2
    (x1, y1), (x2, y2) = sorted((float(x), float(y)) for x, y in pupils)
    assert x2 - x1 > 40 and abs(y1 - y2) < 3          # two eyes, level, apart
    off = photolib.photo_to_svg(face_photo, hints=photolib.synthetic_face_hints(),
                                protect_face=False)
    assert not _pupils(off)


def test_no_faces_no_pupils():
    import os
    dog = os.path.join(os.path.dirname(__file__), "..", "assets", "photos", "dog.jpg")
    assert not _pupils(photolib.photo_to_svg(dog, qa=False))


def test_hints_overlay_draws_on_the_photo(face_photo, tmp_path):
    out = tmp_path / "ov.png"
    img = photolib.hints_overlay(face_photo, photolib.synthetic_face_hints(), str(out))
    assert out.exists() and img.shape[:2] == cv2.imread(face_photo).shape[:2]
    assert (img != cv2.imread(face_photo)).any()


def test_hinted_face_becomes_traits(face_photo):
    face = photolib.face_landmarks(face_photo, hints=photolib.synthetic_face_hints())[0]
    t = traits_from_face(face)["traits"]
    assert t["glasses"] is True
    (dx, dy), = t["moles"]
    assert dx > 0          # the fixture's mole is on the image-right cheek
