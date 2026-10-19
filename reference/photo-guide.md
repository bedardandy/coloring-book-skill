# Photo guide — photographs to coloring-book outlines

`lib/photolib.py` turns a photo into a colorable line-art page. All
processing is LOCAL and DETERMINISTIC by default (same photo →
byte-identical SVG). Optional inputs — vision hints, image-model backends,
model-drawn line art — sharpen the trace; without them nothing changes.

## The splintering doctrine

Naive edge detection splinters. The pipeline attacks each failure mode:

| Failure | Counter-measure |
|---|---|
| Fragmented strokes | edge-preserving bilateral pre-filter; flow-coherent extraction (sketch style) or dual-scale adaptive threshold (clean style); morphological gap-bridging |
| Specks & short runs | connected-component filter (area + extent floors) |
| Doubled edges on thick bands | **centreline tracing**: every ink component is classed as a RIBBON (edge band) or a BLOB (solid dark patch); ribbons are thinned (Zhang-Suen) and walked into polylines, so a band yields one stroke, not both of its sides; blobs are outlined |
| Background clutter (fence boards, grass, wallpaper) | **background drop** for single-subject policies: ink outside the dilated GrabCut mask is removed; a ground contact line is drawn under the subject; the ring around the feet is tightened to the mask (grass hugs paws) |
| Texture splatter (fur, leaves) | inside a dropped subject the wide-block threshold is 1.5x stricter (shading is not a line); interior line structures shorter than 3% of the image or packing >3.5x more line than their extent are texture; blobs that are neither dark (eye, nose) nor large are fur shadow |
| Wobbly vectors | moving-average smoothing of contours/centrelines → RDP simplify → Catmull-Rom (`smooth_path`) averaging |
| Unprintable thin lines | three-tier strokes (silhouette 4.6 / interior 3.6 / background 2.6) + `qa_page` print-safety gate |
| Lost facial features (pupils, nostrils, a mole read as "dots") | **feature-protection zones** from face landmarks (`protect_face`): inside them the dot/blob filters, length floors and texture rule relax — see *Preserving facial features* |

## Soft rules, not gates

`POLICIES` maps a subject label to parameters — `edge_c` (threshold),
`block`, `simplify` (RDP epsilon), `snap_hv` (square up near-horizontal /
vertical segments within 7°), `protect_face` (landmark feature zones),
`max_strokes`, and `bg`:
`"drop"` (animal, plant, generic — ink outside the dilated subject mask is
removed) or `"soft"` (face, person, vehicle, building — background ink is
thinned, not removed, because there the mask is a hint, not a silhouette).
Labels come from a fallback chain: **YuNet face detection** (Apache-2.0
model bundled in `assets/models/`) → **colour GrabCut** seeded by a thin
border ring (the subject may fill the frame tail to nose; runs on a ≤640px
copy with a fixed RNG seed, so it is fast and reproducible) → center-prior
saliency → whole-image. Heuristics (edge-line density) suggest `building`.

A mask is only trusted for the drop when it looks like one framed subject:
5–70% of the frame and ≤30% of the frame border inside it (`_mask_usable`).
Otherwise the soft rule applies. The colour separation matters: a white dog
against a red barn and green grass segments cleanly in BGR and not at all
in grayscale.

The **closed QA loop** runs `validate_svg` + `qa_page` on the OUTPUT and
nudges parameters (≤3 rounds): too many slivers → raise thresholds; too few
regions → lower them. Final parameters are written into the page as
`data-policy` / `data-params` for reproducibility. Policies bias the trace;
they never hard-fail a photo.

## API

```python
from photolib import photo_to_svg, photo_to_fragment, composite_page

svg = photo_to_svg("lion.jpg", style="clean", detail="medium",
                   title="Zoo Day", caption="The lion was napping.")
frag = photo_to_fragment("lion.jpg")        # feet-anchored asset
body = scene_meadow() + G(580, SCENE_GROUND, matted(frag, scale=0.95), 0.95)
svg = composite_page("lion.jpg", scene_meadow(), SCENE_GROUND, x=580,
                     scale=0.95, title="Harper Meets a Lion")
```

- `style="clean"` — thresholded contour look, matches charlib house style
- `style="sketch"` — flow-based XDoG pencil look, more line character; on
  flat, step-edged subjects where the ridge detector finds almost nothing it
  falls back to the clean extractor rather than an empty page
- `detail="low|medium|high"` — multiplies simplify/thresholds
- A background-dropped page stands the subject on a ground contact line
  (`<g data-ground="1">`); fragments carry no ground line — the scene
  supplies it
- The fragment's local origin is the traced art's bottom-centre (feet
  anchor), so `G(x, ground_y, frag, s)` stands it on a ground line like any
  helper. A photo traced at full art-band size is ~700px wide: scale it
  (0.5–0.6) before matting it into a scene
- Every entry point (`photo_to_svg`, `photo_to_fragment`, `composite_page`)
  also takes `hints=`, `backends=`, `allow_remote=`, `lineart=`,
  `protect_face=` (sections below); `trace_lineart(drawing, photo=...)`
  traces a model-drawn line art; `face_landmarks(photo, hints)` /
  `detect_faces_full(gray, bgr)` return faces with landmarks

CLI: `python3 -m lib.photolib photo.jpg -o page.svg [--style sketch]
[--fragment f.svg] [--hints hints.json] [--lineart drawing.png]
[--no-protect-face]` — prints `feature fidelity 0.86 (missing: face0.nose)`
when the photo has faces.

## Detail policies by subject (tuning table)

| Subject | snap angles | detail bias | notes |
|---|---|---|---|
| face / person | no | feature zones from YuNet/hint landmarks (eyes, brows, nose, mouth, declared features) | hair simplifies to masses; skin texture drops |
| car / vehicle | YES (±7°) | medium | keep silhouette, wheels, windows; badges/text drop |
| plane | YES | medium | same doctrine |
| house / building | YES (max) | coarse | roofline/door/windows stay, bricks drop |
| zoo / wild animal | no | medium | background DROPPED; silhouette + face + limb separation; fur texture OFF |
| nature / tree | no | coarse | background DROPPED; canopy outline + sparse marks (tree_round doctrine) |
| generic | no | medium | background DROPPED when the mask is a framed single subject; safe default |

Measured on the sample photos (`assets/photos/`, see the evaluation
section): the golden retriever traces to a single silhouette with ear, eye,
mouth and legs in both styles (the sketch style is the showcase page); the
teddy-bear face crop is the hard case — its GrabCut mask covers the lit
face only (tan fur against a tan wall), so the ears are dropped with the
background and the trace reads as a head outline with nose and mouth.

## Composition rules (same as everything else)

- A traced subject is a FOREGROUND object: wrap in `matted()` over scene kits.
  A background-dropped trace also carries its own knockout — a white,
  stroke-less fill of the dilated subject mask (`data-knockout="1"`) drawn
  first — so hills and paths behind the subject stop at its silhouette even
  though the traced outline is an open stroke, not a filled shape
- Keep ~2×-pad clearance between the trace's halo and neighbouring props —
  `validate_svg` flags halo-swallowed stems exactly as it does for helpers
- Main-figure floor (≥180px) applies to traced subjects on scene pages
- Run `python3 -m lib.photolib` CLI output through `lib.validate` before
  shipping, exactly as with helper-built pages

## Vision hints (use your own eyes)

If you can see the photo, LOOK at it and write a hints dict. Current models
place boxes and points accurately; the pipeline trusts them over its own
detectors. Hints never change output when absent (`None` or `{}`).

```json
{
  "units": "px",
  "image_size": [1600, 1200],
  "label": "person",
  "subject_box": [410, 120, 760, 1050],
  "faces": [{
    "box": [600, 180, 330, 400],
    "landmarks": {"eye_l": [690, 350], "eye_r": [835, 352], "nose": [762, 440],
                  "mouth_l": [705, 505], "mouth_r": [820, 507]},
    "features": ["glasses", "gap_tooth", {"name": "mole", "box": [850, 470, 14, 14]}]
  }],
  "keep": [[300, 900, 180, 160]],
  "drop": [[0, 0, 400, 300]]
}
```

| field | meaning |
|---|---|
| `units` | `"px"` (default) or `"norm"` (0–1 fractions of width/height) |
| `image_size` | `[w, h]` the px coordinates refer to — default: the ORIGINAL upright photo (the trace may downscale it; coordinates are rescaled for you) |
| `label` | force a policy (`face person vehicle building animal plant generic`). A non-face label keeps hinted faces for protection only (a teddy's face: `"label": "animal"` keeps the background drop) |
| `subject_box` | `[x, y, w, h]`: GrabCut is seeded with this rect instead of the border ring |
| `faces` | list of `{box, landmarks?, score?, features?}`. Landmarks you omit are placed canonically inside the box. A hinted face overlapping a YuNet face replaces it (borrowing YuNet's landmarks for the ones you omitted); others are added — use this for profile faces, toys, drawings, small faces YuNet misses |
| `features` | per face: names from `glasses gap_tooth braces freckles dimples headband` (zone derived from the landmarks), or ANY name with a box (`{"name": "mole", "box": [...]}`, birthmark, earring, hair_clip ...) |
| `keep` | boxes whose detail must survive: protection zones, and exempt from the background drop |
| `drop` | boxes whose ink is removed (photobombing fence, text, a stranger). Drop wins over keep/zones |
| `notes` | free text, ignored |

`_l` / `_r` are IMAGE-left / IMAGE-right (smaller / larger x) — NOT the
subject's own left/right. A frontal child's right eye is `eye_l`. Eyes and
mouth corners are re-ordered by x anyway, so a mix-up cannot flip a face.

Malformed hints raise `HintError` naming the field (unknown key, wrong
units, box outside the image, px values that look normalized, a feature
without a box that needs one). The CLI exits 2 with the message. Pass a
dict or a path to a JSON file: `photo_to_svg(p, hints="hints.json")`.

## Preserving facial features

Landmarks (YuNet's five points, a landmarks backend, or hints) become
**protection zones** when the policy has `protect_face` (face, person,
animal) or the hints name faces; `protect_face=True/False` forces it.
Zone sizes scale with the interocular distance (IOD) and rotate with the
eye line: two eye ellipses (0.40 × 0.26 IOD), a brow band above each eye,
nose (nostrils either side), mouth (corner span + padding), plus declared
features — glasses (a rect over both eyes and the bridge), freckle cheeks,
dimples, headband, any feature box — and every `keep` box.

Inside a zone (constants `PROTECT_*` in photolib):

- small dark blobs survive the dot filter when darker than 85% of their
  OWN surround (a nostril is dark against skin, not against hair)
- components down to 6 px, strokes down to 8 px; spur pruning shortens to
  4 px; the texture rule is off; the opening that erases 2 px glasses
  frames is skipped
- RDP epsilon × 0.4 (a pupil ring stays round), interior stroke weight
- protected strokes have their own budget (80) outside `max_strokes`, so a
  busy photo cannot crowd the eyes out

Skin texture outside the zones drops exactly as before.

**Open eyes.** Lids, lashes and the sclera edge trace as a squiggle that
reads "asleep" at page size (the fidelity score still says 1.0 — ink is
there). So a protected face (photo trace, not model line art) gets an iris
dot per eye: the dark component around the darkest pixel near each eye
landmark, cut to a disk so a glasses rim cannot join it, radius from its
area clamped to 0.05-0.12 × IOD (`PUPIL_*`). A window without real contrast
(a closed eye, a very soft photo) adds nothing. Dots carry `data-pupil="1"`.
This is the parametric faces' dot-eye convention, and it is what reads.

**Check your hints by eye.** `hints_overlay(photo, hints, "overlay.png")`
(CLI `--overlay overlay.png`) draws YuNet faces (blue), hinted faces
(magenta) with their landmarks and feature boxes, the subject box (yellow),
keep (green) and drop (red) boxes onto the working image. Look at it
before tracing: a hinted eye 30 px off protects the wrong pixels.

**From a photo to a character.** `face_landmarks()` output feeds
`likeness.traits_from_face(face)` (measured eye spacing / smile width /
face length + feature words → trait keys) — the route for the PARAMETRIC
book characters, which stay consistent on every page. Tracing a person's
photo is for a one-off "photo page", not for the cast.

`feature_fidelity(svg_or_elements, faces, image_shape)` maps each
landmark (and declared feature: glasses → bridge, mole → its box centre
...) onto the page with the trace's own `_page_fit` and reports whether
ink passes within 0.2 × IOD: `{"score", "hits", "total", "missing",
"faces"}`. It measures presence at the right place, not shape. Pages with
faces carry it: `<g data-policy=... data-fidelity="0.86"
data-fidelity-missing="face0.nose">`; `read_fidelity(svg)` reads it back.
On the synthetic portrait (eval tier below) protection lifts fidelity from
0.43 to 1.0: without it the eyes (nested inside the glasses rims),
nostrils and mole are lost.

For a likeness on a CHARACTER page instead of a trace, hand the face dict
to `charlib.traits_from_landmarks` — proportions become trait buckets, not
shading.

## Image-model backends

`lib/imagemodels.py` plugs models into the fallback chain. A backend is
`fn(bgr) -> result` registered under a name and ONE capability:

| capability | returns | used for |
|---|---|---|
| `segment` | uint8 mask, 255 = subject | replaces GrabCut when the mask is usable (framed subject; any sane mask in the face / subject-box branches) — else GrabCut runs and `meta["backend_rejected"]` says so |
| `landmarks` | faces list (photolib dict format) | augments YuNet (profile faces, toy faces) |
| `depth` | float h×w, larger = nearer | seeds GrabCut: the farthest 35% of the rect starts as background (colour-matched subjects) |
| `lineart` | uint8 gray, dark lines on white | traced instead of the photo's own edges (next section) |

```python
import imagemodels as im
im.register_backend("modnet", im.onnx_segmenter("models/modnet.onnx", size=(512, 512)), "segment")
im.register_backend("midas", im.onnx_depth("models/midas_small.onnx", size=(256, 256)), "depth")
im.register_backend("lines", im.onnx_lineart("models/informative_drawings.onnx"), "lineart")
svg = photo_to_svg("dog.jpg", backends={"segment": "modnet", "depth": "midas"})
```

Outputs are validated and resized to the photo, so a 320 px model plugs
straight in. `onnx_segmenter(path, size, mean, std, swap_rb, output,
threshold, sigmoid, classes)` handles alpha mattes (one channel,
threshold) and parsing models (C classes, argmax, keep `classes`);
`onnx_lineart(..., invert, value_range)` (`invert=True` for white-on-black
edge models); `onnx_depth(..., invert)` (`invert=True` if the model emits
distance). Built-in: `"yunet"` (landmarks). Weights are NEVER bundled or
downloaded — fetch them yourself and check the license of the exact file:

| model (open) | capability | notes |
|---|---|---|
| PP-HumanSeg (opencv_zoo `human_segmentation_pphumanseg`) | segment | Apache-2.0; 192×192, mean/std 0.5, 2 classes → `classes=[1]` |
| MODNet portrait matting | segment | Apache-2.0 code/weights; 512, mean/std 0.5, alpha |
| U²-Net / u2netp (salient object) | segment | Apache-2.0; 320, ImageNet mean/std, alpha |
| BiSeNet face parsing (face-parsing.PyTorch) | segment | MIT code, but weights trained on CelebAMask-HQ (non-commercial dataset terms); 512, 19 classes |
| MiDaS v2.1 small | depth | MIT; 256, ImageNet mean/std, inverse depth |
| Depth-Anything-V2-Small | depth | Apache-2.0 (Small only — Base/Large are CC-BY-NC); 518 |
| informative-drawings (contour / opensketch / anime styles; ControlNet's "lineart" annotator) | lineart | MIT; 0–1 in, 0–1 out, dark lines |
| HED / PiDiNet edge annotators | lineart | white on black → `invert=True`; check each file's license |

Any Python callable registers the same way — a hosted image model's
client, a local server. **Anything that sends pixels off the machine MUST
be registered `remote=True`** (privacy gate below).

## Line art from generative models

`trace_lineart(drawing, photo=None, *, hints, backends, protect_face,
fragment, ...)` (= `photo_to_svg(photo, lineart=drawing)`) runs a line
drawing through the house vectorizer: Otsu threshold (clamped 64–200 so
anti-aliased lines survive a resize), light close, speck filter, then the
same centreline tracing, stroke tiers, background drop and QA loop. The
drawing may come from a local ONNX line-art model, a ControlNet
preprocessor, or an image-generation model asked to "redraw this photo as
a coloring page". Accepts a path (alpha = paper) or an array (gray, BGR,
BGRA, float 0–1, bool).

With `photo=` the drawing is resized onto the photo's pixel grid (aspect
must match within 3% — else `ValueError`: generate at the photo's aspect)
and the subject mask, landmarks, protection zones and fidelity all come
from the PHOTO. That makes `feature_fidelity` the guard against identity
drift: a generative redraw that moved the eyes or drew a different face
scores low. **Below `FIDELITY_MIN` (0.80) reject the drawing or
re-generate**; tell the user rather than shipping a stranger's face.

```python
svg = trace_lineart("redraw.png", photo="kid.jpg", hints=hints)
if (read_fidelity(svg) or 0) < FIDELITY_MIN:
    ...  # re-generate, or fall back to photo_to_svg("kid.jpg", hints=hints)
```

## Privacy: photos of real people

- **Local by default.** YuNet, GrabCut, every threshold and every built-in
  backend run on this machine. Nothing phones home.
- **Remote only with explicit opt-in.** A backend registered `remote=True`
  raises `PrivacyError` unless the call passes `allow_remote=True`. When
  YuNet (locally) finds a face, the error says a person's photo would
  leave the machine. For a photo of a child that needs the user's explicit
  consent AND the parent's/guardian's. Never set `allow_remote=True` on
  your own initiative, never register a hosted client as `remote=False`,
  and say which service will receive the photo when you ask.
- **Hints are geometry only.** Boxes and points; no names, no
  descriptions of the person in `notes`.
- **Never commit photos.** The repo holds only the open-licensed samples
  in `assets/photos/`; `tools/pii_scan.py --gate` (CI) fails on committed
  images carrying EXIF camera/GPS/owner tags. Real test photos live in a
  directory passed as `--photos DIR`, outside the repo.
- The output is LINE ART only — never likeness shading.

## Provenance

OpenCV (Apache-2.0) provides GrabCut, morphology, contours; the bundled
YuNet face model is Apache-2.0 from opencv_zoo (see CREDITS.md). Thinning
is an in-house numpy Zhang-Suen (no opencv-contrib). No photo leaves the
machine unless a caller registers a remote backend AND passes
allow_remote=True; nothing phones home.

## Evaluation (`tools/eval_photo.py`)

The pipeline is scored, not eyeballed. `python3 tools/eval_photo.py` renders
the synthetic fixture tiers (simple subjects, crisp toy, soft portrait,
textured foliage, low light) through the trace and reports:

- reference-free: strokes, slivers, regions, print safety, ink coverage %
- reference (synthetic only): **subject hit ratio** — fraction of traced ink
  falling inside the known subject silhouette (dilated); low values mean the
  trace invented geometry outside the subject
- round-trip doctrine: the pipeline can re-line-art its own rendered pages
  (tested in CI)

A second, **real-photo tier** traces the open-licensed sample photos in
`assets/photos/` (a golden retriever, a 1903 teddy bear — attribution in
`CREDITS.md`; EXIF stripped, pixels untouched) plus any `*.jpg`/`*.png` in a
directory passed as `--photos DIR` (never committed — the third local test
photo, a 1930s children's bedroom, shows children and stays out of the
repo). It is scored reference-free: **subject-ink ratio** (share of traced
ink inside the dilated GrabCut mask — the same detection the trace used),
sliver count, region count, strokes, ink coverage. Keys in the bands file
are `photo:<name>|<style>|<metric>`; a photo absent from a run is simply
not checked, so CI gates the two in-repo photos and the synthetic tier
without needing the external directory. `--no-photos` runs the synthetic
tier alone.

A third, **feature-fidelity tier** traces `synthetic_photo("face_features")`
— a head-and-shoulders portrait (IOD 80 px at 640) with glasses, a mole and
mottled skin, whose landmarks are KNOWN (`synthetic_face_truth`) — through
its hints (`synthetic_face_hints`; YuNet does fire on it, but hints carry
the declared features) and scores `feature_fidelity` with protect_face on
(banded, `face_features|<style>|feature_fidelity`, ±0.08: one missed
feature of 7 fails the gate) and off (reported only).

`--calibrate` rewrites `tools/eval_bands.json` from the current run (pass
`--photos` too, or the external photos' bands are dropped — and note it
traces EVERY photo in that directory, so point it at a directory holding
only the photos whose bands belong in the repo); `--gate` fails
when any metric leaves its band — the CI workflow runs the gate on every
push, so trace regressions block merge the same way validator violations
do. Real-photo counts get ±15% bands (min ±3) and ratios ±0.08: hundreds of
strokes ride on GrabCut and bilateral filtering, which drift slightly across
OpenCV builds.
