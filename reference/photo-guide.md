# Photo guide — photographs to coloring-book outlines

`lib/photolib.py` turns a photo into a colorable line-art page. All
processing is LOCAL and DETERMINISTIC (same photo → byte-identical SVG).

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

## Soft rules, not gates

`POLICIES` maps a subject label to parameters — `edge_c` (threshold),
`block`, `simplify` (RDP epsilon), `snap_hv` (square up near-horizontal /
vertical segments within 7°), `protect_face`, `max_strokes`, and `bg`:
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

CLI: `python3 -m lib.photolib photo.jpg -o page.svg [--style sketch] [--fragment f.svg]`

## Detail policies by subject (tuning table)

| Subject | snap angles | detail bias | notes |
|---|---|---|---|
| face / person | no | protect eyes/nose/mouth band (YuNet box) | hair simplifies to masses; skin texture drops |
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

## Provenance

OpenCV (Apache-2.0) provides GrabCut, morphology, contours; the bundled
YuNet face model is Apache-2.0 from opencv_zoo (see CREDITS.md). Thinning
is an in-house numpy Zhang-Suen (no opencv-contrib). No photo ever leaves
the machine; nothing phones home.

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

`--calibrate` rewrites `tools/eval_bands.json` from the current run (pass
`--photos` too, or the external photos' bands are dropped — and note it
traces EVERY photo in that directory, so point it at a directory holding
only the photos whose bands belong in the repo); `--gate` fails
when any metric leaves its band — the CI workflow runs the gate on every
push, so trace regressions block merge the same way validator violations
do. Real-photo counts get ±15% bands (min ±3) and ratios ±0.08: hundreds of
strokes ride on GrabCut and bilateral filtering, which drift slightly across
OpenCV builds.
