# Photo guide — photographs to coloring-book outlines

`lib/photolib.py` turns a photo into a colorable line-art page. All
processing is LOCAL and DETERMINISTIC (same photo → byte-identical SVG).

## The splintering doctrine

Naive edge detection splinters. The pipeline attacks each failure mode:

| Failure | Counter-measure |
|---|---|
| Fragmented strokes | edge-preserving bilateral pre-filter; flow-coherent extraction (sketch style) or dual-scale adaptive threshold (clean style); morphological gap-bridging |
| Specks & short runs | connected-component filter (area + extent floors) |
| Doubled edges on thick lines | hole-shadow skip: a hole that merely mirrors its parent contour is not re-traced |
| Texture splatter (fur, leaves) | per-subject soft policies + region-floor QA loop |
| Wobbly vectors | circular moving-average smoothing of contours → RDP simplify → Catmull-Rom (`smooth_path`) averaging |
| Unprintable thin lines | two-tier strokes (subject 4.6/3.6, background 3.4/2.6) + `qa_page` print-safety gate |

## Soft rules, not gates

`POLICIES` maps a subject label to parameters — `edge_c` (threshold),
`block`, `simplify` (RDP epsilon), `snap_hv` (square up near-horizontal /
vertical segments within 7°), `protect_face`, `max_strokes`. Labels come
from a fallback chain: **YuNet face detection** (Apache-2.0 model bundled in
`assets/models/`) → GrabCut around a center rect → center-prior saliency →
whole-image. Heuristics (edge-line density) suggest `building`.

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
- `style="sketch"` — flow-based XDoG pencil look, more line character
- `detail="low|medium|high"` — multiplies simplify/thresholds
- The fragment's local origin is the ink's bottom-centre (feet anchor), so
  `G(x, ground_y, frag, s)` stands it on a ground line like any helper

CLI: `python -m lib.photolib photo.jpg -o page.svg [--style sketch] [--fragment f.svg]`

## Detail policies by subject (tuning table)

| Subject | snap angles | detail bias | notes |
|---|---|---|---|
| face / person | no | protect eyes/nose/mouth band (YuNet box) | hair simplifies to masses; skin texture drops |
| car / vehicle | YES (±7°) | medium | keep silhouette, wheels, windows; badges/text drop |
| plane | YES | medium | same doctrine |
| house / building | YES (max) | coarse | roofline/door/windows stay, bricks drop |
| zoo / wild animal | no | medium | silhouette + face + limb separation; fur texture OFF |
| nature / tree | no | coarse | canopy outline + sparse marks (tree_round doctrine) |
| generic | no | medium | safe default |

## Composition rules (same as everything else)

- A traced subject is a FOREGROUND object: wrap in `matted()` over scene kits
- Keep ~2×-pad clearance between the trace's halo and neighbouring props —
  `validate_svg` flags halo-swallowed stems exactly as it does for helpers
- Main-figure floor (≥180px) applies to traced subjects on scene pages
- Run `python -m lib.photolib` CLI output through `lib.validate` before
  shipping, exactly as with helper-built pages

## Provenance

OpenCV (Apache-2.0) provides GrabCut, morphology, contours; the bundled
YuNet face model is Apache-2.0 from opencv_zoo (see CREDITS.md). No photo
ever leaves the machine; nothing phones home.

## Evaluation (`tools/eval_photo.py`)

The pipeline is scored, not eyeballed. `python tools/eval_photo.py` renders
the synthetic fixture tiers (simple subjects, crisp toy, soft portrait,
textured foliage, low light) through the trace and reports:

- reference-free: strokes, slivers, regions, print safety, ink coverage %
- reference (synthetic only): **subject hit ratio** — fraction of traced ink
  falling inside the known subject silhouette (dilated); low values mean the
  trace invented geometry outside the subject
- round-trip doctrine: the pipeline can re-line-art its own rendered pages
  (tested in CI)

`--calibrate` rewrites `tools/eval_bands.json` from the current run; `--gate`
fails when any metric leaves its band — the CI workflow runs the gate on
every push, so trace regressions block merge the same way validator
violations do.
